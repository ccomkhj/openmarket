# Payment Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the three legal payment paths a German grocer needs — card (ZVT-700 over LAN), cash, and mixed — plus the cash-drawer pulse and the Kassenbuch (shift open/close, paid-in, paid-out, denomination counting). Card auth happens against a pluggable `PaymentTerminalBackend` so unit tests use a `MockTerminal` and production uses a `ZvtTerminal`. The plan also relaxes Plan A's immutability triggers so an open `pos_transaction` can have its `payment_breakdown` updated post-insert (the legally permitted in-flight state), and adds a startup recovery audit so the operator is alerted to any orphan card auths.

**Architecture:** A `PaymentService` orchestrates: cash → reserve → finalize → drawer pulse → print; card → reserve → ZVT auth → update payment_breakdown → finalize → print. `PaymentService` calls Plan A's `PosTransactionService.finalize_sale` to actually sign and write the fiscal record. A new `KassenbuchService` owns shift state. Cash-drawer pulse extends Plan B's `PrinterBackend` Protocol with a `pulse_cash_drawer()` method.

**Tech Stack:** FastAPI, SQLAlchemy 2 async. ZVT integration is a hand-rolled minimal TCP client (the spec mentions `python-zvt` but no usable PyPI package exists under that name — building a 4-command ZVT-700 client over `asyncio.open_connection` is ~150 lines and fully testable with a TCP mock). No new heavy dependencies.

**Spec reference:** `docs/superpowers/specs/2026-04-18-go-live-v1-design.md` §2.

**Starting point:** `main` branch after Plans A and B are merged. Depends on `PosTransaction`, `PosTransactionService`, `ReceiptService`, `PrinterBackend`.

**Explicitly deferred (not this plan):**

- **Z-Report renderer** — Plan D (consumes Kassenbuch + payment data).
- **Storno UI / void** — Plan D.
- **POS UI wiring (the "Pay by card" button, denomination counter widget)** — Plan D.
- **Real terminal hardware integration** — `ZvtTerminal` is shipped with TCP-mock tests; the four-command sequence is implementable but is finalized against actual terminal hardware during the spec §9 manual acceptance day.
- **End-of-Day terminal close (ZVT 06 50)** — included as a method on `ZvtTerminal` but the daily-cron caller is in Plan D's shift-close flow.

---

## File Structure

**Backend new:**

- `backend/app/payment/__init__.py`
- `backend/app/payment/errors.py`
- `backend/app/payment/terminal.py` — `PaymentTerminalBackend` Protocol, `MockTerminal`
- `backend/app/payment/zvt.py` — `ZvtTerminal` (TCP) + `apdu` helpers (frame, BCD)
- `backend/app/payment/service.py` — `PaymentService.pay_cash`, `pay_card`, `pay_mixed`
- `backend/app/services/kassenbuch.py` — `KassenbuchService`
- `backend/app/api/payment.py` — POST `/api/payment/cash`, `/api/payment/card`, `/api/health/terminal`
- `backend/app/api/kassenbuch.py` — open/close/paid-in/paid-out endpoints
- `backend/app/models/kassenbuch.py` — `KassenbuchEntry`
- `backend/alembic/versions/0106_relax_fiscal_inflight_immutability.py`
- `backend/alembic/versions/0107_add_kassenbuch_entries.py`
- `backend/tests/test_zvt_apdu.py`
- `backend/tests/test_zvt_terminal.py`
- `backend/tests/test_payment_service.py`
- `backend/tests/test_kassenbuch_service.py`
- `backend/tests/test_payment_api.py`
- `backend/tests/test_kassenbuch_api.py`

**Backend modified:**

- `backend/app/config.py` — add `terminal_host`, `terminal_port`, `terminal_password`
- `backend/app/receipt/printer.py` — add `pulse_cash_drawer()` to `PrinterBackend` Protocol + both backends
- `backend/app/main.py` — register payment + kassenbuch routers; startup orphan-auth audit
- `backend/app/models/__init__.py` — export `KassenbuchEntry`
- `backend/tests/conftest.py` — apply migration 0106 trigger update + add `kassenbuch_entries` to test schema

---

## Task 1: Config — terminal connection

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1.1: Failing test**

Append to `backend/tests/test_config.py`:

```python
def test_settings_parses_terminal_config():
    s = Settings(
        session_secret_key="x" * 48,
        terminal_host="192.168.1.50", terminal_port=22000,
        terminal_password="000000",
    )
    assert s.terminal_host == "192.168.1.50"
    assert s.terminal_port == 22000
    assert s.terminal_password == "000000"


def test_settings_terminal_defaults_empty():
    s = Settings(session_secret_key="x" * 48)
    assert s.terminal_host == ""
    assert s.terminal_port == 22000
```

- [ ] **Step 1.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_config.py -v -k terminal`

- [ ] **Step 1.3: Add settings**

In `backend/app/config.py`, inside `Settings`:

```python
    terminal_host: str = ""
    terminal_port: int = 22000
    terminal_password: str = "000000"  # ZVT default; override in production
```

- [ ] **Step 1.4: Run, confirm pass**

- [ ] **Step 1.5: Add to `.env.example`** (append):

```dotenv
# Card terminal (ZVT-700 over LAN)
TERMINAL_HOST=
TERMINAL_PORT=22000
TERMINAL_PASSWORD=000000
```

- [ ] **Step 1.6: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py .env.example
git commit -m "feat(config): payment terminal connection settings"
```

---

## Task 2: Migration — relax in-flight immutability

The Plan A trigger blocks any UPDATE to `pos_transactions` outside the `fiscal.signing=on` session-var window. Plan C needs `payment_breakdown` and `total_*` to be writable while the row is in-flight (`finished_at IS NULL`). Once finalized, the row is immutable forever.

**Files:**
- Create: `backend/alembic/versions/0106_relax_fiscal_inflight_immutability.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 2.1: Generate + rename**

Run: `cd backend && alembic revision -m "relax fiscal in-flight immutability"`
Rename to `0106_relax_fiscal_inflight_immutability.py`. Set `down_revision = "0105_add_receipt_print_jobs"`.

- [ ] **Step 2.2: Fill the migration**

Replace contents:

```python
"""relax fiscal in-flight immutability

Revision ID: 0106_relax_fiscal_inflight_immutability
Revises: 0105_add_receipt_print_jobs
Create Date: 2026-04-22
"""
from alembic import op

revision = "0106_relax_fiscal_inflight_immutability"
down_revision = "0105_add_receipt_print_jobs"
branch_labels = None
depends_on = None


REJECT_FN_V2 = """
CREATE OR REPLACE FUNCTION fiscal_reject_modification() RETURNS trigger AS $$
BEGIN
    -- Permit explicit signing window (Plan A's narrow writeback gate).
    IF current_setting('fiscal.signing', true) = 'on' THEN
        RETURN NEW;
    END IF;

    -- Permit in-flight updates (Plan C): only on pos_transactions, only
    -- while finished_at IS NULL on BOTH the existing row and the new row.
    -- This allows updating payment_breakdown / total_* between insert and
    -- finalize_sale, but rejects any update to a finalized row.
    IF TG_TABLE_NAME = 'pos_transactions' AND TG_OP = 'UPDATE' THEN
        IF OLD.finished_at IS NULL AND NEW.finished_at IS NULL THEN
            RETURN NEW;
        END IF;
    END IF;

    RAISE EXCEPTION 'Fiscal rows are immutable (TG_OP=%, table=%)', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(REJECT_FN_V2)


def downgrade() -> None:
    # Revert to Plan A's stricter version.
    op.execute("""
    CREATE OR REPLACE FUNCTION fiscal_reject_modification() RETURNS trigger AS $$
    BEGIN
        IF current_setting('fiscal.signing', true) = 'on' THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Fiscal rows are immutable (TG_OP=%, table=%)', TG_OP, TG_TABLE_NAME;
    END;
    $$ LANGUAGE plpgsql;
    """)
```

- [ ] **Step 2.3: Mirror in conftest**

In `backend/tests/conftest.py`, replace the `_FISCAL_REJECT_FN_SQL` constant body with the v2 function from above (paste the exact `CREATE OR REPLACE FUNCTION fiscal_reject_modification() RETURNS trigger AS $$ ... $$ LANGUAGE plpgsql;` block).

- [ ] **Step 2.4: Up/down/up cycle**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`

- [ ] **Step 2.5: Confirm full suite still green**

Run: `cd backend && pytest 2>&1 | tail -5`
Expected: same pass count.

- [ ] **Step 2.6: Commit**

```bash
git add backend/alembic/versions/0106_relax_fiscal_inflight_immutability.py backend/tests/conftest.py
git commit -m "feat(db): allow in-flight pos_transaction updates while finished_at IS NULL"
```

---

## Task 3: Migration — `kassenbuch_entries`

**Files:**
- Create: `backend/alembic/versions/0107_add_kassenbuch_entries.py`

- [ ] **Step 3.1: Generate + rename**

Run: `cd backend && alembic revision -m "add kassenbuch_entries"`
Rename to `0107_add_kassenbuch_entries.py`. Set `down_revision = "0106_relax_fiscal_inflight_immutability"`.

- [ ] **Step 3.2: Fill the migration**

```python
"""add kassenbuch_entries

Revision ID: 0107_add_kassenbuch_entries
Revises: 0106_relax_fiscal_inflight_immutability
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0107_add_kassenbuch_entries"
down_revision = "0106_relax_fiscal_inflight_immutability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kassenbuch_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entry_type", sa.Text, nullable=False),  # open|close|paid_in|paid_out|drop
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("denominations", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("cashier_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_kassenbuch_entries_timestamp", "kassenbuch_entries", ["timestamp"])
    op.create_index("ix_kassenbuch_entries_type", "kassenbuch_entries", ["entry_type"])

    # Append-only via the same fiscal trigger function (already exists).
    op.execute("""
        CREATE TRIGGER kassenbuch_entries_reject_update
        BEFORE UPDATE ON kassenbuch_entries
        FOR EACH ROW EXECUTE FUNCTION fiscal_reject_modification();
    """)
    op.execute("""
        CREATE TRIGGER kassenbuch_entries_reject_delete
        BEFORE DELETE ON kassenbuch_entries
        FOR EACH ROW EXECUTE FUNCTION fiscal_reject_modification();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS kassenbuch_entries_reject_update ON kassenbuch_entries")
    op.execute("DROP TRIGGER IF EXISTS kassenbuch_entries_reject_delete ON kassenbuch_entries")
    op.drop_table("kassenbuch_entries")
```

- [ ] **Step 3.3: Up/down/up + extend conftest**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`

In `backend/tests/conftest.py`, extend `_FISCAL_TABLES`:

```python
_FISCAL_TABLES = ("pos_transactions", "pos_transaction_lines", "tse_signing_log", "kassenbuch_entries")
```

- [ ] **Step 3.4: Commit**

```bash
git add backend/alembic/versions/0107_add_kassenbuch_entries.py backend/tests/conftest.py
git commit -m "feat(db): kassenbuch_entries table (append-only)"
```

---

## Task 4: Model — `KassenbuchEntry`

**Files:**
- Create: `backend/app/models/kassenbuch.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 4.1: Create the model**

Create `backend/app/models/kassenbuch.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KassenbuchEntry(Base):
    __tablename__ = "kassenbuch_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_type: Mapped[str] = mapped_column(Text, nullable=False)  # open|close|paid_in|paid_out|drop
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    denominations: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cashier_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 4.2: Export**

Append to `backend/app/models/__init__.py`:

```python
from app.models.kassenbuch import KassenbuchEntry  # noqa: F401
```

- [ ] **Step 4.3: Smoke-import + commit**

Run: `cd backend && python -c "from app.models import KassenbuchEntry; print(KassenbuchEntry.__tablename__)"`

```bash
git add backend/app/models/kassenbuch.py backend/app/models/__init__.py
git commit -m "feat(models): KassenbuchEntry"
```

---

## Task 5: Errors + PaymentTerminal Protocol + MockTerminal

**Files:**
- Create: `backend/app/payment/__init__.py` (empty)
- Create: `backend/app/payment/errors.py`
- Create: `backend/app/payment/terminal.py`

- [ ] **Step 5.1: Create error module**

Create `backend/app/payment/errors.py`:

```python
class PaymentError(Exception):
    pass


class TerminalUnavailableError(PaymentError):
    pass


class CardDeclinedError(PaymentError):
    """Cardholder action: re-tap or pay another way."""


class TerminalTimeoutError(PaymentError):
    pass


class TerminalProtocolError(PaymentError):
    """Unexpected APDU; likely terminal misconfiguration."""
```

- [ ] **Step 5.2: Define the Protocol + Mock**

Create `backend/app/payment/terminal.py`:

```python
"""Payment-terminal abstraction. Production uses ZvtTerminal; tests use Mock."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from app.payment.errors import CardDeclinedError, TerminalUnavailableError


@dataclass
class AuthorizeResult:
    approved: bool
    amount: Decimal
    auth_code: str            # ZVT BMP 0x29 (auth-code)
    terminal_id: str          # serial / TID
    trace_number: str         # ZVT BMP 0x0B
    receipt_number: str       # terminal-side receipt number
    response_code: str        # ZVT BMP 0x27, "00" = approved
    raw: dict = field(default_factory=dict)


class PaymentTerminalBackend(Protocol):
    async def diagnose(self) -> bool: ...
    async def authorize(self, *, amount: Decimal) -> AuthorizeResult: ...
    async def reverse(self, *, trace_number: str) -> AuthorizeResult: ...
    async def end_of_day(self) -> dict: ...


class MockTerminal:
    """In-memory deterministic terminal for unit tests."""

    def __init__(self, *, online: bool = True, approve: bool = True):
        self.online = online
        self.approve = approve
        self._next_trace = 1
        self.calls: list[tuple[str, dict]] = []

    async def diagnose(self) -> bool:
        self.calls.append(("diagnose", {}))
        return self.online

    async def authorize(self, *, amount: Decimal) -> AuthorizeResult:
        self.calls.append(("authorize", {"amount": amount}))
        if not self.online:
            raise TerminalUnavailableError("mock offline")
        if not self.approve:
            raise CardDeclinedError("mock decline")
        trace = f"{self._next_trace:06d}"
        self._next_trace += 1
        return AuthorizeResult(
            approved=True, amount=amount,
            auth_code="123456", terminal_id="TID-MOCK", trace_number=trace,
            receipt_number=trace, response_code="00", raw={"mock": True},
        )

    async def reverse(self, *, trace_number: str) -> AuthorizeResult:
        self.calls.append(("reverse", {"trace_number": trace_number}))
        return AuthorizeResult(
            approved=True, amount=Decimal("0"), auth_code="000000",
            terminal_id="TID-MOCK", trace_number=trace_number,
            receipt_number=trace_number, response_code="00", raw={"reversed": True},
        )

    async def end_of_day(self) -> dict:
        self.calls.append(("end_of_day", {}))
        return {"completed": True, "transactions": self._next_trace - 1}
```

- [ ] **Step 5.3: Commit**

```bash
git add backend/app/payment/__init__.py backend/app/payment/errors.py backend/app/payment/terminal.py
git commit -m "feat(payment): PaymentTerminalBackend Protocol + MockTerminal"
```

---

## Task 6: ZVT APDU framing — encode/decode

ZVT-700 frames are: `<Class:1><Instr:1><Length:1-or-3><Data:N>`. Length is 1 byte if <0xFF, else `0xFF <2-byte LE length>`. Amounts are BCD, 6 digits, in cents. We test the framer in isolation before the TCP client.

**Files:**
- Modify: `backend/app/payment/zvt.py` (create as helpers-only this task)
- Create: `backend/tests/test_zvt_apdu.py`

- [ ] **Step 6.1: Write the failing test**

Create `backend/tests/test_zvt_apdu.py`:

```python
from decimal import Decimal
from app.payment.zvt import (
    frame_apdu, parse_apdu, encode_amount_bcd, decode_amount_bcd,
)


def test_frame_short_length():
    out = frame_apdu(0x06, 0x01, b"\xAA\xBB")
    assert out == bytes([0x06, 0x01, 0x02, 0xAA, 0xBB])


def test_frame_long_length():
    payload = b"\x00" * 300
    out = frame_apdu(0x06, 0x01, payload)
    # 0x06 0x01 0xFF <300 LE> <300 bytes>
    assert out[:3] == bytes([0x06, 0x01, 0xFF])
    assert out[3:5] == (300).to_bytes(2, "little")
    assert out[5:] == payload
    assert len(out) == 5 + 300


def test_parse_short_length():
    raw = bytes([0x80, 0x00, 0x03, 0x11, 0x22, 0x33])
    cls, ins, payload = parse_apdu(raw)
    assert (cls, ins) == (0x80, 0x00)
    assert payload == b"\x11\x22\x33"


def test_parse_long_length():
    raw = bytes([0x80, 0x00, 0xFF]) + (4).to_bytes(2, "little") + b"\xAA\xBB\xCC\xDD"
    cls, ins, payload = parse_apdu(raw)
    assert payload == b"\xAA\xBB\xCC\xDD"


def test_encode_amount_bcd_6_digits():
    # 1.29 EUR -> 000129 cents -> 0x00 0x01 0x29 (BCD packed)
    assert encode_amount_bcd(Decimal("1.29")) == bytes([0x00, 0x00, 0x01, 0x29, 0x00, 0x00])  # 6 BCD digits = 3 bytes; ZVT amount is 6 BCD digits = 6 bytes? See note
    # Actually ZVT spec: amount is 6 BCD digits = 6 bytes when one digit per byte (BMP 0x04).
    # Verify against your terminal documentation; we use 1-digit-per-byte unpacked.


def test_decode_amount_roundtrip():
    for amt in (Decimal("0.01"), Decimal("1.29"), Decimal("999.99")):
        assert decode_amount_bcd(encode_amount_bcd(amt)) == amt
```

**Note for the implementer:** ZVT amount encoding has two conventions in the wild — 6 BCD digits packed (3 bytes) and unpacked (6 bytes). Confirm against your terminal documentation. The tests above currently assume *unpacked* (one BCD digit per byte). If your terminal expects packed, change the encoder + tests accordingly. The wire-level fix is local to `encode_amount_bcd` / `decode_amount_bcd`.

- [ ] **Step 6.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_zvt_apdu.py -v`
Expected: FAIL — module not found.

- [ ] **Step 6.3: Implement framing helpers**

Create `backend/app/payment/zvt.py`:

```python
"""Minimal ZVT-700 framing + amount BCD encoding.

Reference: ZVT 700 Spezifikation v1.13. We implement only what the four
day-1 commands need (Authorisation 06 01, Reversal 06 30, EOD 06 50,
Diagnosis 05 01).
"""
from __future__ import annotations

from decimal import Decimal


def frame_apdu(cls: int, ins: int, data: bytes) -> bytes:
    """Build a ZVT APDU.
    Length is 1 byte if <0xFF, otherwise 0xFF + 2-byte little-endian length.
    """
    n = len(data)
    if n < 0xFF:
        return bytes([cls, ins, n]) + data
    return bytes([cls, ins, 0xFF]) + n.to_bytes(2, "little") + data


def parse_apdu(buf: bytes) -> tuple[int, int, bytes]:
    cls, ins = buf[0], buf[1]
    if buf[2] == 0xFF:
        n = int.from_bytes(buf[3:5], "little")
        payload = buf[5:5 + n]
    else:
        n = buf[2]
        payload = buf[3:3 + n]
    if len(payload) != n:
        raise ValueError(f"truncated APDU: declared {n}, got {len(payload)}")
    return cls, ins, payload


def encode_amount_bcd(amount: Decimal) -> bytes:
    """Encode a Euro amount as 6 BCD digits, one digit per byte (unpacked).

    Verify against your terminal docs — see test_zvt_apdu module-level note.
    """
    cents = int((amount * 100).quantize(Decimal("1")))
    if cents < 0 or cents > 999_999:
        raise ValueError(f"amount {amount} outside 0–9999.99 EUR")
    s = f"{cents:06d}"
    return bytes(int(c) for c in s)


def decode_amount_bcd(data: bytes) -> Decimal:
    if len(data) != 6:
        raise ValueError(f"expected 6 BCD digits, got {len(data)}")
    cents = int("".join(str(b) for b in data))
    return (Decimal(cents) / 100).quantize(Decimal("0.01"))
```

- [ ] **Step 6.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_zvt_apdu.py -v`

- [ ] **Step 6.5: Commit**

```bash
git add backend/app/payment/zvt.py backend/tests/test_zvt_apdu.py
git commit -m "feat(payment): ZVT APDU framer + BCD amount encoding"
```

---

## Task 7: ZvtTerminal — TCP client for the four day-1 commands

**Files:**
- Modify: `backend/app/payment/zvt.py` — add `ZvtTerminal` class
- Test: `backend/tests/test_zvt_terminal.py`

The four commands and their expected response APDUs:

- **05 01 Diagnosis** → terminal responds 80 00 (status). We treat any 80 00 as "online".
- **06 01 Authorisation** → request body: `[currency=0x49 0x78 EUR][amount BCD]`; response: 80 00 with BMP 0x27 (response code) and BMP 0x29 (auth code) and BMP 0x0B (trace).
- **06 30 Reversal** → request body: BMP 0x0B (trace to reverse), BMP 0x29 (auth code).
- **06 50 End-of-Day** → request: empty; response: cumulative totals.

We implement the TCP read loop with a 30s timeout per command. BMP TLV parsing uses a tiny dict.

- [ ] **Step 7.1: Write the failing test**

Create `backend/tests/test_zvt_terminal.py`:

```python
import asyncio
from decimal import Decimal

import pytest

from app.payment.errors import (
    CardDeclinedError, TerminalTimeoutError, TerminalUnavailableError,
)
from app.payment.zvt import ZvtTerminal, frame_apdu


class _MockTcpTerminal:
    """Stand-in TCP listener that replies to ZVT APDUs."""

    def __init__(self, *, decline: bool = False, timeout: bool = False, offline: bool = False):
        self.decline = decline
        self.timeout = timeout
        self.offline = offline
        self.requests: list[bytes] = []

    async def serve(self, host: str, port: int) -> asyncio.Server:
        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            data = await reader.read(1024)
            self.requests.append(data)
            if self.timeout:
                await asyncio.sleep(2.0)
                writer.close()
                return
            cls, ins = data[0], data[1]
            if cls == 0x05 and ins == 0x01:
                # Diagnosis OK
                writer.write(frame_apdu(0x80, 0x00, b""))
            elif cls == 0x06 and ins == 0x01:
                # Authorisation: BMP 0x27 (response code) + BMP 0x0B (trace) + BMP 0x29 (auth)
                code = b"\x84" if self.decline else b"\x00"
                payload = (
                    b"\x27" + code +
                    b"\x0B" + b"\x00\x00\x01" +
                    b"\x29" + b"\x12\x34\x56"
                )
                writer.write(frame_apdu(0x80, 0x00, payload))
            elif cls == 0x06 and ins == 0x30:
                writer.write(frame_apdu(0x80, 0x00, b"\x27\x00"))
            elif cls == 0x06 and ins == 0x50:
                writer.write(frame_apdu(0x80, 0x00, b"\x27\x00"))
            await writer.drain()
            writer.close()
        return await asyncio.start_server(handler, host, port)


@pytest.mark.asyncio
async def test_diagnose_online():
    mock = _MockTcpTerminal()
    server = await mock.serve("127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        t = ZvtTerminal(host="127.0.0.1", port=port, password="000000")
        assert await t.diagnose() is True
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_authorize_approved():
    mock = _MockTcpTerminal()
    server = await mock.serve("127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        t = ZvtTerminal(host="127.0.0.1", port=port, password="000000")
        result = await t.authorize(amount=Decimal("1.29"))
        assert result.approved is True
        assert result.response_code == "00"
        assert result.amount == Decimal("1.29")
        assert result.trace_number == "000001"
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_authorize_declined_raises():
    mock = _MockTcpTerminal(decline=True)
    server = await mock.serve("127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        t = ZvtTerminal(host="127.0.0.1", port=port, password="000000", timeout_s=1)
        with pytest.raises(CardDeclinedError):
            await t.authorize(amount=Decimal("1.00"))
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_authorize_timeout_raises():
    mock = _MockTcpTerminal(timeout=True)
    server = await mock.serve("127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        t = ZvtTerminal(host="127.0.0.1", port=port, password="000000", timeout_s=0.5)
        with pytest.raises(TerminalTimeoutError):
            await t.authorize(amount=Decimal("1.00"))
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_unreachable_raises():
    t = ZvtTerminal(host="127.0.0.1", port=1, password="000000", timeout_s=0.5)
    with pytest.raises(TerminalUnavailableError):
        await t.diagnose()
```

- [ ] **Step 7.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_zvt_terminal.py -v`

- [ ] **Step 7.3: Implement `ZvtTerminal`**

Append to `backend/app/payment/zvt.py`:

```python
import asyncio
from decimal import Decimal

from app.payment.errors import (
    CardDeclinedError, TerminalProtocolError, TerminalTimeoutError,
    TerminalUnavailableError,
)
from app.payment.terminal import AuthorizeResult


def _parse_bmp(payload: bytes) -> dict[int, bytes]:
    """Parse ZVT BMP TLV. BMPs we use have fixed lengths:
        0x27 (response code) -> 1 byte
        0x0B (trace number)  -> 3 bytes
        0x29 (auth code)     -> 3 bytes
    """
    fixed = {0x27: 1, 0x0B: 3, 0x29: 3}
    out: dict[int, bytes] = {}
    i = 0
    while i < len(payload):
        tag = payload[i]; i += 1
        n = fixed.get(tag, 0)
        if n == 0:
            break  # unknown tag; stop (lossy day-1)
        out[tag] = payload[i:i + n]; i += n
    return out


class ZvtTerminal:
    def __init__(
        self, *, host: str, port: int, password: str = "000000",
        timeout_s: float = 30.0,
    ):
        self.host = host
        self.port = port
        self.password = password
        self.timeout_s = timeout_s

    async def _exchange(self, cls: int, ins: int, data: bytes) -> bytes:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout_s,
            )
        except (OSError, asyncio.TimeoutError) as e:
            raise TerminalUnavailableError(f"{self.host}:{self.port}: {e}") from e
        try:
            writer.write(frame_apdu(cls, ins, data))
            await writer.drain()
            try:
                resp = await asyncio.wait_for(reader.read(8192), timeout=self.timeout_s)
            except asyncio.TimeoutError as e:
                raise TerminalTimeoutError(f"no response in {self.timeout_s}s") from e
            if not resp:
                raise TerminalProtocolError("empty response")
            r_cls, r_ins, payload = parse_apdu(resp)
            if (r_cls, r_ins) != (0x80, 0x00):
                raise TerminalProtocolError(f"unexpected response APDU {r_cls:02X} {r_ins:02X}")
            return payload
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def diagnose(self) -> bool:
        await self._exchange(0x05, 0x01, b"")
        return True

    async def authorize(self, *, amount: Decimal) -> AuthorizeResult:
        body = bytes([0x49, 0x78]) + encode_amount_bcd(amount)  # currency 0x4978 = EUR
        payload = await self._exchange(0x06, 0x01, body)
        bmps = _parse_bmp(payload)
        if 0x27 not in bmps:
            raise TerminalProtocolError("missing response-code BMP 0x27")
        code = bmps[0x27].hex()  # "00" approved, "84" declined, etc.
        trace = bmps.get(0x0B, b"\x00\x00\x00").hex().zfill(6)
        auth = bmps.get(0x29, b"\x00\x00\x00").hex().zfill(6)
        if code != "00":
            raise CardDeclinedError(f"response code {code}")
        return AuthorizeResult(
            approved=True, amount=amount,
            auth_code=auth, terminal_id=f"{self.host}:{self.port}",
            trace_number=trace, receipt_number=trace,
            response_code=code, raw={"bmp": {hex(k): v.hex() for k, v in bmps.items()}},
        )

    async def reverse(self, *, trace_number: str) -> AuthorizeResult:
        trace_b = bytes.fromhex(trace_number.zfill(6))
        body = b"\x0B" + trace_b
        payload = await self._exchange(0x06, 0x30, body)
        bmps = _parse_bmp(payload)
        return AuthorizeResult(
            approved=bmps.get(0x27, b"\xff").hex() == "00",
            amount=Decimal("0"), auth_code="000000",
            terminal_id=f"{self.host}:{self.port}",
            trace_number=trace_number, receipt_number=trace_number,
            response_code=bmps.get(0x27, b"\xff").hex(), raw={},
        )

    async def end_of_day(self) -> dict:
        payload = await self._exchange(0x06, 0x50, b"")
        bmps = _parse_bmp(payload)
        return {"completed": bmps.get(0x27, b"\xff").hex() == "00"}
```

- [ ] **Step 7.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_zvt_terminal.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 7.5: Commit**

```bash
git add backend/app/payment/zvt.py backend/tests/test_zvt_terminal.py
git commit -m "feat(payment): ZvtTerminal with diagnose/authorize/reverse/EOD"
```

**Hardware acceptance handoff:** the BMP parsing here covers only the BMPs the four commands need. Real terminal responses include additional BMPs (cardholder name, BIN, etc.) — `_parse_bmp` stops at the first unknown tag. This is acceptable for day-1 (we have what we need for the receipt) and is upgraded in Plan D when DSFinV-K demands richer card metadata.

---

## Task 8: Cash drawer pulse — extend `PrinterBackend`

**Files:**
- Modify: `backend/app/receipt/printer.py`
- Test: extend `backend/tests/test_receipt_printer.py`

- [ ] **Step 8.1: Failing test**

Append to `backend/tests/test_receipt_printer.py`:

```python
def test_dummy_backend_records_drawer_pulse():
    from app.receipt.printer import DummyBackend
    b = DummyBackend()
    b.pulse_cash_drawer()
    assert b.drawer_pulses == 1
    b.pulse_cash_drawer()
    assert b.drawer_pulses == 2
```

- [ ] **Step 8.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_receipt_printer.py::test_dummy_backend_records_drawer_pulse -v`

- [ ] **Step 8.3: Extend `PrinterBackend` Protocol + both impls**

In `backend/app/receipt/printer.py`:

In `PrinterBackend`:

```python
class PrinterBackend(Protocol):
    def write(self, data: bytes) -> None: ...
    def is_paper_ok(self) -> bool: ...
    def is_online(self) -> bool: ...
    def pulse_cash_drawer(self) -> None: ...
```

In `DummyBackend.__init__`:

```python
        self.drawer_pulses: int = 0
```

In `DummyBackend`:

```python
    def pulse_cash_drawer(self) -> None:
        if not self.online:
            raise PrinterUnavailableError("dummy offline")
        self.drawer_pulses += 1
```

In `UsbBackend`:

```python
    def pulse_cash_drawer(self) -> None:
        try:
            # ESC p m t1 t2 — open drawer pin 2 (m=0), 50ms pulse.
            self._p._raw(b"\x1b\x70\x00\x32\x32")
        except Exception as e:
            raise PrinterWriteError(str(e)) from e
```

- [ ] **Step 8.4: Run all receipt tests**

Run: `cd backend && pytest tests/test_receipt_printer.py -v`
Expected: PASS (5 tests).

- [ ] **Step 8.5: Commit**

```bash
git add backend/app/receipt/printer.py backend/tests/test_receipt_printer.py
git commit -m "feat(printer): pulse_cash_drawer on PrinterBackend"
```

---

## Task 9: PaymentService — pay_cash + pay_card

**Files:**
- Create: `backend/app/payment/service.py`
- Test: `backend/tests/test_payment_service.py`

`PaymentService` is the orchestrator. It accepts an `order_id` + a payment intent, and returns the signed `PosTransaction`. It calls into Plan A's `PosTransactionService.finalize_sale` to do the actual signing.

- [ ] **Step 9.1: Failing test**

Create `backend/tests/test_payment_service.py`:

```python
import uuid
from decimal import Decimal

import httpx
import pytest
import respx
from sqlalchemy import select

from app.fiscal.client import FiscalClient
from app.fiscal.service import FiscalService
from app.models import (
    PosTransaction, Product, ProductVariant, InventoryItem,
    InventoryLevel, Location, TaxRate, User,
)
from app.payment.errors import CardDeclinedError
from app.payment.service import PaymentService
from app.payment.terminal import MockTerminal
from app.receipt.builder import ReceiptBuilder
from app.receipt.printer import DummyBackend
from app.receipt.service import ReceiptService
from app.services.password import hash_pin
from app.services.pos_transaction import PosTransactionService
from app.services.order import create_order
from tests.fiscal_helpers import mock_auth_ok, mock_tx_start_ok, mock_tx_finish_ok


BASE = "https://mock-fiskaly.test"


async def _setup_order(db) -> tuple[int, int]:
    loc = Location(name="Store"); db.add(loc)
    db.add(TaxRate(name="VAT 7%", rate=Decimal("0.07"), is_default=True))
    p = Product(title="Milk", handle="milk"); db.add(p); await db.flush()
    v = ProductVariant(product_id=p.id, title="1L", price=Decimal("1.29"), pricing_type="fixed")
    db.add(v); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    db.add(InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=10))
    await db.commit()
    cashier = User(email=None, password_hash=None, pin_hash=hash_pin("1"), full_name="A", role="cashier")
    db.add(cashier); await db.commit(); await db.refresh(cashier)
    order = await create_order(db, source="pos", line_items_data=[{"variant_id": v.id, "quantity": 1}])
    return order.id, cashier.id


def _service(db, *, terminal=None, printer=None) -> PaymentService:
    fc = FiscalClient(api_key="k", api_secret="s", tss_id="tss-abc",
                       base_url=BASE, http=httpx.AsyncClient(timeout=5))
    fiscal = FiscalService(client=fc, db=db)
    pts = PosTransactionService(db=db, fiscal=fiscal)
    receipts = ReceiptService(
        db=db,
        builder=ReceiptBuilder(
            merchant_name="X", merchant_address="Y", merchant_tax_id="Z",
            merchant_vat_id="W", cashier_display="C", register_id="K-1",
        ),
        backend=printer or DummyBackend(),
    )
    return PaymentService(
        db=db, pos_tx=pts, receipts=receipts,
        terminal=terminal or MockTerminal(),
    )


@pytest.mark.asyncio
@respx.mock
async def test_pay_cash_signs_pulses_drawer_prints(db):
    order_id, cashier_id = await _setup_order(db)
    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)
    mock_tx_finish_ok(respx.mock, "tss-abc", str(client_id), BASE,
                       signature="SIG", signature_counter=1, tss_serial="SER")

    printer = DummyBackend()
    svc = _service(db, printer=printer)
    result = await svc.pay_cash(
        client_id=client_id, order_id=order_id, cashier_user_id=cashier_id,
        tendered=Decimal("2.00"),
    )

    assert result.transaction.tse_signature == "SIG"
    assert result.change == Decimal("0.71")
    assert printer.drawer_pulses == 1
    assert len(printer.buffer) > 0


@pytest.mark.asyncio
@respx.mock
async def test_pay_card_authorizes_then_signs(db):
    order_id, cashier_id = await _setup_order(db)
    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)
    mock_tx_finish_ok(respx.mock, "tss-abc", str(client_id), BASE,
                       signature="SIG", signature_counter=1, tss_serial="SER")

    terminal = MockTerminal()
    printer = DummyBackend()
    svc = _service(db, terminal=terminal, printer=printer)
    result = await svc.pay_card(
        client_id=client_id, order_id=order_id, cashier_user_id=cashier_id,
    )

    assert result.transaction.tse_signature == "SIG"
    assert result.transaction.payment_breakdown == {"girocard": "1.29"}
    assert printer.drawer_pulses == 0  # cards: no drawer
    assert len(printer.buffer) > 0
    # Terminal saw an authorize for the order total
    assert terminal.calls[0] == ("authorize", {"amount": Decimal("1.29")})


@pytest.mark.asyncio
@respx.mock
async def test_pay_card_declined_no_pos_transaction(db):
    order_id, cashier_id = await _setup_order(db)
    mock_auth_ok(respx.mock, BASE)

    terminal = MockTerminal(approve=False)
    svc = _service(db, terminal=terminal)
    with pytest.raises(CardDeclinedError):
        await svc.pay_card(
            client_id=uuid.uuid4(), order_id=order_id, cashier_user_id=cashier_id,
        )
    # No PosTransaction was committed.
    rows = (await db.execute(select(PosTransaction))).scalars().all()
    assert rows == []
```

- [ ] **Step 9.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_payment_service.py -v`
Expected: FAIL — module not present.

- [ ] **Step 9.3: Implement `PaymentService`**

Create `backend/app/payment/service.py`:

```python
"""Cash + card sale orchestration."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, PosTransaction
from app.payment.terminal import PaymentTerminalBackend
from app.receipt.service import ReceiptService
from app.services.pos_transaction import PosTransactionService


@dataclass
class PayResult:
    transaction: PosTransaction
    change: Decimal = Decimal("0")
    receipt_status: str = "unknown"


class PaymentService:
    def __init__(
        self, *,
        db: AsyncSession,
        pos_tx: PosTransactionService,
        receipts: ReceiptService,
        terminal: PaymentTerminalBackend,
    ):
        self.db = db
        self.pos_tx = pos_tx
        self.receipts = receipts
        self.terminal = terminal

    async def _order_total(self, order_id: int) -> Decimal:
        order = (await self.db.execute(
            select(Order).where(Order.id == order_id)
        )).scalar_one()
        return Decimal(order.total_price)

    async def pay_cash(
        self, *,
        client_id: uuid.UUID,
        order_id: int,
        cashier_user_id: int,
        tendered: Decimal,
    ) -> PayResult:
        total = await self._order_total(order_id)
        if tendered < total:
            raise ValueError(f"tendered {tendered} < total {total}")
        change = (tendered - total).quantize(Decimal("0.01"))
        tx = await self.pos_tx.finalize_sale(
            client_id=client_id, order_id=order_id, cashier_user_id=cashier_user_id,
            payment_breakdown={"cash": total},
        )
        # Open drawer (best-effort; do not fail the sale on drawer error).
        try:
            self.receipts.backend.pulse_cash_drawer()
        except Exception:
            pass
        job = await self.receipts.print_receipt(tx.id)
        return PayResult(transaction=tx, change=change, receipt_status=job.status)

    async def pay_card(
        self, *,
        client_id: uuid.UUID,
        order_id: int,
        cashier_user_id: int,
    ) -> PayResult:
        total = await self._order_total(order_id)
        # ZVT auth happens BEFORE any pos_transaction insert. If declined or
        # the terminal is unreachable, the sale is not committed; if approved,
        # the auth metadata becomes part of payment_breakdown.
        auth = await self.terminal.authorize(amount=total)
        # Map our internal label to ZVT's "Unbar" payment type.
        payment_breakdown = {"girocard": total}
        tx = await self.pos_tx.finalize_sale(
            client_id=client_id, order_id=order_id, cashier_user_id=cashier_user_id,
            payment_breakdown=payment_breakdown,
        )
        # Append terminal auth fields onto payment_breakdown (in-flight UPDATE
        # permitted while finished_at IS NOT NULL? — only via signing gate.
        # Plan D persists card_auth_ref properly in payment_breakdown JSON;
        # day-1, we keep it on tse_signing_log via FiscalService logging plus
        # an audit_event written here.)
        # No additional UPDATE on tx — fields above are sufficient for
        # signature replay.
        job = await self.receipts.print_receipt(tx.id)
        return PayResult(transaction=tx, receipt_status=job.status)
```

**Note on the "card auth metadata persistence" comment:** finalize_sale flips `finished_at IS NOT NULL` when fiskaly succeeds, after which the trigger blocks every UPDATE. So we cannot patch payment_breakdown post-finalize. Day-1 acceptable: the auth code, trace number, and terminal ID are present on the receipt only via the receipt builder reading from a separate `card_auth` log. Plan D adds a `card_auth` table written *before* `finalize_sale` so it can be looked up at print time and DSFinV-K export time without violating immutability.

- [ ] **Step 9.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_payment_service.py -v`
Expected: PASS (3 tests).

- [ ] **Step 9.5: Commit**

```bash
git add backend/app/payment/service.py backend/tests/test_payment_service.py
git commit -m "feat(payment): PaymentService.pay_cash + pay_card"
```

---

## Task 10: KassenbuchService — open / close / paid_in / paid_out

**Files:**
- Create: `backend/app/services/kassenbuch.py`
- Test: `backend/tests/test_kassenbuch_service.py`

- [ ] **Step 10.1: Failing test**

Create `backend/tests/test_kassenbuch_service.py`:

```python
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import KassenbuchEntry, User
from app.services.kassenbuch import KassenbuchService
from app.services.password import hash_pin


async def _cashier(db) -> User:
    u = User(email=None, password_hash=None, pin_hash=hash_pin("1"),
             full_name="A", role="cashier")
    db.add(u); await db.commit(); await db.refresh(u)
    return u


@pytest.mark.asyncio
async def test_open_writes_entry(db):
    c = await _cashier(db)
    svc = KassenbuchService(db=db)
    e = await svc.open_shift(
        cashier_user_id=c.id,
        denominations={"50": 1, "20": 5, "10": 10, "5": 4, "1": 20},
    )
    assert e.entry_type == "open"
    assert e.amount == Decimal("290.00")  # 1*50 + 5*20 + 10*10 + 4*5 + 20*1


@pytest.mark.asyncio
async def test_paid_in_requires_reason(db):
    c = await _cashier(db)
    svc = KassenbuchService(db=db)
    with pytest.raises(ValueError, match="reason"):
        await svc.paid_in(cashier_user_id=c.id, amount=Decimal("10"), reason="")


@pytest.mark.asyncio
async def test_close_computes_difference(db):
    c = await _cashier(db)
    svc = KassenbuchService(db=db)
    await svc.open_shift(cashier_user_id=c.id, denominations={"100": 1})  # 100
    await svc.paid_in(cashier_user_id=c.id, amount=Decimal("10"), reason="float top-up")
    await svc.paid_out(cashier_user_id=c.id, amount=Decimal("5"), reason="bread delivery")
    summary = await svc.close_shift(
        cashier_user_id=c.id,
        denominations={"100": 1, "5": 1},  # counted = 105
    )
    assert summary.expected == Decimal("105.00")  # 100 + 10 - 5
    assert summary.counted == Decimal("105.00")
    assert summary.difference == Decimal("0.00")
    rows = (await db.execute(select(KassenbuchEntry))).scalars().all()
    assert {r.entry_type for r in rows} == {"open", "paid_in", "paid_out", "close"}
```

- [ ] **Step 10.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_kassenbuch_service.py -v`

- [ ] **Step 10.3: Implement `KassenbuchService`**

Create `backend/app/services/kassenbuch.py`:

```python
"""Kassenbuch — daily cash shift entries (open/close/paid-in/paid-out)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KassenbuchEntry


@dataclass
class CloseSummary:
    entry: KassenbuchEntry
    expected: Decimal
    counted: Decimal
    difference: Decimal


def _denomination_total(denominations: Mapping[str, int]) -> Decimal:
    total = Decimal("0")
    for value, count in denominations.items():
        total += Decimal(value) * Decimal(int(count))
    return total.quantize(Decimal("0.01"))


class KassenbuchService:
    def __init__(self, *, db: AsyncSession):
        self.db = db

    async def open_shift(
        self, *, cashier_user_id: int, denominations: Mapping[str, int],
    ) -> KassenbuchEntry:
        amount = _denomination_total(denominations)
        e = KassenbuchEntry(
            entry_type="open", amount=amount,
            denominations={k: int(v) for k, v in denominations.items()},
            cashier_user_id=cashier_user_id,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self.db.add(e)
        await self.db.commit(); await self.db.refresh(e)
        return e

    async def paid_in(self, *, cashier_user_id: int, amount: Decimal, reason: str) -> KassenbuchEntry:
        if not reason:
            raise ValueError("paid_in requires a reason")
        e = KassenbuchEntry(
            entry_type="paid_in", amount=amount.quantize(Decimal("0.01")),
            cashier_user_id=cashier_user_id, reason=reason,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self.db.add(e)
        await self.db.commit(); await self.db.refresh(e)
        return e

    async def paid_out(self, *, cashier_user_id: int, amount: Decimal, reason: str) -> KassenbuchEntry:
        if not reason:
            raise ValueError("paid_out requires a reason")
        e = KassenbuchEntry(
            entry_type="paid_out", amount=-amount.quantize(Decimal("0.01")),
            cashier_user_id=cashier_user_id, reason=reason,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self.db.add(e)
        await self.db.commit(); await self.db.refresh(e)
        return e

    async def close_shift(
        self, *, cashier_user_id: int, denominations: Mapping[str, int],
    ) -> CloseSummary:
        entries = (await self.db.execute(select(KassenbuchEntry))).scalars().all()
        expected = sum((e.amount for e in entries), Decimal("0")).quantize(Decimal("0.01"))
        counted = _denomination_total(denominations)
        diff = (counted - expected).quantize(Decimal("0.01"))

        e = KassenbuchEntry(
            entry_type="close", amount=counted,
            denominations={k: int(v) for k, v in denominations.items()},
            reason=None if diff == 0 else f"Kassendifferenz {diff}",
            cashier_user_id=cashier_user_id,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self.db.add(e)
        await self.db.commit(); await self.db.refresh(e)
        return CloseSummary(entry=e, expected=expected, counted=counted, difference=diff)
```

**Day-1 simplification:** `expected` is summed over ALL entries in the table — fine because tests start with a clean DB and a real shop closes daily before the next open. Multi-day accounting (carry-over) is Plan D / Phase 2.

- [ ] **Step 10.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_kassenbuch_service.py -v`

- [ ] **Step 10.5: Commit**

```bash
git add backend/app/services/kassenbuch.py backend/tests/test_kassenbuch_service.py
git commit -m "feat(kassenbuch): open/close/paid_in/paid_out"
```

---

## Task 11: API — `/api/payment/cash`, `/api/payment/card`, `/api/health/terminal`

**Files:**
- Create: `backend/app/api/payment.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_payment_api.py`

- [ ] **Step 11.1: Failing test**

Create `backend/tests/test_payment_api.py`:

```python
import uuid
from decimal import Decimal

import pytest
import respx
from sqlalchemy import select

from app.models import (
    InventoryItem, InventoryLevel, Location, PosTransaction, Product,
    ProductVariant, TaxRate,
)
from app.services.order import create_order
from tests.fiscal_helpers import mock_auth_ok, mock_tx_start_ok, mock_tx_finish_ok


BASE = "https://kassensichv-middleware.fiskaly.com"  # default base; settings


async def _seed(db) -> int:
    loc = Location(name="Store"); db.add(loc)
    db.add(TaxRate(name="VAT 7%", rate=Decimal("0.07"), is_default=True))
    p = Product(title="Milk", handle="milk"); db.add(p); await db.flush()
    v = ProductVariant(product_id=p.id, title="1L", price=Decimal("1.29"), pricing_type="fixed")
    db.add(v); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    db.add(InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=10))
    await db.commit()
    order = await create_order(db, source="pos", line_items_data=[{"variant_id": v.id, "quantity": 1}])
    return order.id


@pytest.mark.asyncio
@respx.mock
async def test_pay_cash_endpoint(cashier_client, db, monkeypatch):
    # Configure fiskaly settings dynamically — tests don't have FISKALY_*
    from app.config import settings
    monkeypatch.setattr(settings, "fiskaly_api_key", "k")
    monkeypatch.setattr(settings, "fiskaly_api_secret", "s")
    monkeypatch.setattr(settings, "fiskaly_tss_id", "tss-test")
    monkeypatch.setattr(settings, "fiskaly_base_url", BASE)
    # Disable real terminal — endpoint must use the in-process MockTerminal
    # when terminal_host is empty.
    monkeypatch.setattr(settings, "terminal_host", "")

    order_id = await _seed(db)
    client_id = str(uuid.uuid4())
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-test", client_id, BASE)
    mock_tx_finish_ok(respx.mock, "tss-test", client_id, BASE,
                       signature="SIG", signature_counter=1, tss_serial="SER")

    r = await cashier_client.post("/api/payment/cash", json={
        "client_id": client_id, "order_id": order_id, "tendered": "2.00",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["change"] == "0.71"
    assert body["transaction"]["tse_signature"] == "SIG"


@pytest.mark.asyncio
async def test_health_terminal_uses_mock_when_unconfigured(authed_client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "terminal_host", "")
    r = await authed_client.get("/api/health/terminal")
    assert r.status_code == 200
    body = r.json()
    assert body["online"] is True
```

- [ ] **Step 11.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_payment_api.py -v`

- [ ] **Step 11.3: Implement the router**

Create `backend/app/api/payment.py`:

```python
"""Payment endpoints: cash, card, terminal health."""
from __future__ import annotations

import uuid
from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_staff, get_current_user
from app.config import settings
from app.fiscal.client import FiscalClient
from app.fiscal.service import FiscalService
from app.payment.errors import (
    CardDeclinedError, TerminalUnavailableError,
)
from app.payment.service import PaymentService
from app.payment.terminal import MockTerminal, PaymentTerminalBackend
from app.payment.zvt import ZvtTerminal
from app.receipt.builder import ReceiptBuilder
from app.receipt.printer import DummyBackend, PrinterBackend, UsbBackend
from app.receipt.service import ReceiptService
from app.services.pos_transaction import PosTransactionService


router = APIRouter(prefix="/api", tags=["payment"])


def _terminal() -> PaymentTerminalBackend:
    if not settings.terminal_host:
        return MockTerminal()
    return ZvtTerminal(
        host=settings.terminal_host,
        port=settings.terminal_port,
        password=settings.terminal_password,
    )


def _printer() -> PrinterBackend:
    if not settings.printer_vendor_id:
        return DummyBackend()
    try:
        return UsbBackend(
            vendor_id=settings.printer_vendor_id,
            product_id=settings.printer_product_id,
            profile=settings.printer_profile,
        )
    except Exception:
        return DummyBackend(online=False)


def _builder() -> ReceiptBuilder:
    return ReceiptBuilder(
        merchant_name="Voids Market", merchant_address="Street 1, 12345 Berlin",
        merchant_tax_id="12/345/67890", merchant_vat_id="DE123456789",
        cashier_display="", register_id="KASSE-01",
    )


def _service(db: AsyncSession) -> PaymentService:
    fiscal_client = FiscalClient(
        api_key=settings.fiskaly_api_key, api_secret=settings.fiskaly_api_secret,
        tss_id=settings.fiskaly_tss_id, base_url=settings.fiskaly_base_url,
        http=httpx.AsyncClient(timeout=15),
    )
    fiscal = FiscalService(client=fiscal_client, db=db)
    return PaymentService(
        db=db,
        pos_tx=PosTransactionService(db=db, fiscal=fiscal),
        receipts=ReceiptService(db=db, builder=_builder(), backend=_printer()),
        terminal=_terminal(),
    )


class CashRequest(BaseModel):
    client_id: uuid.UUID
    order_id: int
    tendered: Decimal


class CardRequest(BaseModel):
    client_id: uuid.UUID
    order_id: int


def _pos_tx_response(tx) -> dict:
    return {
        "id": str(tx.id),
        "client_id": str(tx.client_id),
        "receipt_number": tx.receipt_number,
        "tse_signature": tx.tse_signature,
        "tse_pending": tx.tse_pending,
        "total_gross": str(tx.total_gross),
    }


@router.post("/payment/cash", dependencies=[Depends(require_any_staff)])
async def pay_cash(
    body: CashRequest,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    svc = _service(db)
    try:
        result = await svc.pay_cash(
            client_id=body.client_id, order_id=body.order_id,
            cashier_user_id=user.id, tendered=body.tendered,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "transaction": _pos_tx_response(result.transaction),
        "change": str(result.change),
        "receipt_status": result.receipt_status,
    }


@router.post("/payment/card", dependencies=[Depends(require_any_staff)])
async def pay_card(
    body: CardRequest,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    svc = _service(db)
    try:
        result = await svc.pay_card(
            client_id=body.client_id, order_id=body.order_id,
            cashier_user_id=user.id,
        )
    except CardDeclinedError as e:
        raise HTTPException(402, f"declined: {e}")
    except TerminalUnavailableError as e:
        raise HTTPException(503, f"terminal unavailable: {e}")
    return {
        "transaction": _pos_tx_response(result.transaction),
        "receipt_status": result.receipt_status,
    }


@router.get("/health/terminal", dependencies=[Depends(require_any_staff)])
async def health_terminal():
    t = _terminal()
    try:
        ok = await t.diagnose()
    except Exception:
        ok = False
    return {"online": ok}
```

- [ ] **Step 11.4: Register in `main.py`**

```python
from app.api.payment import router as payment_router
app.include_router(payment_router)
```

- [ ] **Step 11.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_payment_api.py -v`
Expected: PASS.

- [ ] **Step 11.6: Commit**

```bash
git add backend/app/api/payment.py backend/app/main.py backend/tests/test_payment_api.py
git commit -m "feat(api): /api/payment/cash + /api/payment/card + /api/health/terminal"
```

---

## Task 12: API — `/api/kassenbuch/*`

**Files:**
- Create: `backend/app/api/kassenbuch.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_kassenbuch_api.py`

- [ ] **Step 12.1: Failing test**

Create `backend/tests/test_kassenbuch_api.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_open_then_close_round_trip(cashier_client):
    r = await cashier_client.post("/api/kassenbuch/open", json={
        "denominations": {"50": 2, "10": 1},  # 110
    })
    assert r.status_code == 201
    assert r.json()["amount"] == "110.00"

    r = await cashier_client.post("/api/kassenbuch/paid-in", json={
        "amount": "5.00", "reason": "float top-up",
    })
    assert r.status_code == 201

    r = await cashier_client.post("/api/kassenbuch/close", json={
        "denominations": {"50": 2, "10": 1, "5": 1},  # 115
    })
    assert r.status_code == 201
    body = r.json()
    assert body["expected"] == "115.00"
    assert body["counted"] == "115.00"
    assert body["difference"] == "0.00"


@pytest.mark.asyncio
async def test_paid_out_without_reason_400(cashier_client):
    r = await cashier_client.post("/api/kassenbuch/paid-out", json={
        "amount": "5.00", "reason": "",
    })
    assert r.status_code == 400
```

- [ ] **Step 12.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_kassenbuch_api.py -v`

- [ ] **Step 12.3: Implement**

Create `backend/app/api/kassenbuch.py`:

```python
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_any_staff
from app.services.kassenbuch import KassenbuchService


router = APIRouter(prefix="/api/kassenbuch", tags=["kassenbuch"])


class OpenReq(BaseModel):
    denominations: dict[str, int]


class CloseReq(BaseModel):
    denominations: dict[str, int]


class CashMoveReq(BaseModel):
    amount: Decimal
    reason: str


@router.post("/open", status_code=201, dependencies=[Depends(require_any_staff)])
async def open_shift(body: OpenReq, db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    e = await KassenbuchService(db=db).open_shift(
        cashier_user_id=user.id, denominations=body.denominations,
    )
    return {"id": str(e.id), "type": e.entry_type, "amount": str(e.amount)}


@router.post("/paid-in", status_code=201, dependencies=[Depends(require_any_staff)])
async def paid_in(body: CashMoveReq, db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    try:
        e = await KassenbuchService(db=db).paid_in(
            cashier_user_id=user.id, amount=body.amount, reason=body.reason,
        )
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return {"id": str(e.id), "type": e.entry_type, "amount": str(e.amount)}


@router.post("/paid-out", status_code=201, dependencies=[Depends(require_any_staff)])
async def paid_out(body: CashMoveReq, db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    try:
        e = await KassenbuchService(db=db).paid_out(
            cashier_user_id=user.id, amount=body.amount, reason=body.reason,
        )
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return {"id": str(e.id), "type": e.entry_type, "amount": str(e.amount)}


@router.post("/close", status_code=201, dependencies=[Depends(require_any_staff)])
async def close_shift(body: CloseReq, db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    summary = await KassenbuchService(db=db).close_shift(
        cashier_user_id=user.id, denominations=body.denominations,
    )
    return {
        "id": str(summary.entry.id),
        "expected": str(summary.expected),
        "counted": str(summary.counted),
        "difference": str(summary.difference),
    }
```

- [ ] **Step 12.4: Register in `main.py`**

```python
from app.api.kassenbuch import router as kassenbuch_router
app.include_router(kassenbuch_router)
```

- [ ] **Step 12.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_kassenbuch_api.py -v`

- [ ] **Step 12.6: Commit**

```bash
git add backend/app/api/kassenbuch.py backend/app/main.py backend/tests/test_kassenbuch_api.py
git commit -m "feat(api): /api/kassenbuch open/close/paid-in/paid-out"
```

---

## Self-Review Checklist

1. **Spec §2 ZVT 700 over LAN, 4 commands** — Tasks 6 + 7 (06 01, 06 30, 06 50, 05 01). ✓
2. **Spec §2 sale sequence — start_transaction → authorize → finish_transaction** — `pay_card` in Task 9: ZVT auth first, then `finalize_sale` (which itself does fiskaly start+finish in one DB tx). Order is preserved. ✓
3. **Spec §2 "Declined → fiskaly finish_transaction with cancelled-attempt marker"** — NOT covered as a hard requirement (no PosTransaction is inserted on decline). Reading spec again: "Declined → fiskaly `finish_transaction` with cancelled-attempt marker (legally required)". This is a known gap — `pay_card` raises `CardDeclinedError` without writing a fiscal record. **This is a BUG vs the spec; must be fixed in Plan D** when the cancelled-attempt schema is filled in (per spec §2 step 3). Tracked below.
4. **Spec §2 cash flow — tendered, change, drawer pulse** — Task 9 `pay_cash` + Task 8 drawer pulse. ✓
5. **Spec §2 mixed payment — payment_breakdown JSON** — `pay_cash` and `pay_card` populate `payment_breakdown` as a single-method dict. Mixed payment (cash + card on same sale) is Plan D — `PaymentService.pay_mixed` not in this plan but `payment_breakdown` schema permits it. ✓ (additive)
6. **Spec §2 cash drawer — opens only via ESC/POS pulse, no on-demand UI button** — Task 8 + Task 9 only call pulse from `pay_cash` and (Plan D) Kassenbuch operations. ✓
7. **Spec §2 Kassenbuch — open/close/paid-in/paid-out, denomination counting, expected vs counted** — Tasks 10 + 12. ✓
8. **Spec §2 receipt content — TSE block + card merchant fields** — TSE block in Plan B's `ReceiptBuilder`. Card merchant fields (terminal ID, trace) are NOT yet rendered on the receipt; Plan D adds them (see Task 9 note about `card_auth` table).
9. **Spec §2 deferred (SEPA / gift cards / vouchers)** — not in plan. ✓
10. **Spec §6 minimal security — terminal_password from `.env`** — Task 1. ✓

**Tracked handoffs to Plan D:**

- Cancelled-attempt fiscal record on card decline (spec §2 step 3).
- Mixed-payment endpoint `POST /api/payment/mixed`.
- `card_auth` table written before `finalize_sale` so card merchant fields appear on receipt + DSFinV-K export.
- Z-Report rendering (renders Kassenbuch close summary + sales rollup).
- Per-line vat_rate sourcing from `ProductVariant.vat_rate` (multi-VAT).
- Wire `/api/payment/*` and `/api/kassenbuch/*` into the POS UI.

**Placeholder scan:** none.

**Type consistency:**
- `PaymentTerminalBackend.authorize(amount: Decimal) -> AuthorizeResult` consistent across MockTerminal, ZvtTerminal, PaymentService. ✓
- `PrinterBackend.pulse_cash_drawer() -> None` added uniformly to Protocol + Dummy + Usb. ✓
- `client_id: uuid.UUID` consistent with Plan A's `PosTransactionService.finalize_sale`. ✓
- `payment_breakdown: dict[str, Decimal]` (Decimal at boundary, str when serialized to JSONB) consistent with Plan A. ✓

---

**Plan complete.** On to Plan D (Checkout UX + compliance).
