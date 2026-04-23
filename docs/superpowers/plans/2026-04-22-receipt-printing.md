# Receipt Printing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a signed `PosTransaction` into an ESC/POS byte stream that a USB thermal receipt printer prints, with deterministic layout, golden-file testing, paper-out buffering, and a reprint flow. No UI wiring in this plan — that's Plan D. This plan delivers a `ReceiptPrinter.print_receipt(pos_transaction_id)` and a buffered-job reprint endpoint the admin can call from anywhere.

**Architecture:** A pure `ReceiptBuilder.render(tx, lines)` returns ESC/POS `bytes`, golden-tested. A thin `ReceiptPrinter` writes those bytes via `python-escpos`'s `Usb` backend (swappable via a `PrinterBackend` Protocol so tests inject `Dummy`). When the printer is unreachable or out of paper, we create a `receipt_print_job` row with `status="buffered"` and return success to the caller — the sale is legally complete at TSE-signing time (spec §5). A `/api/receipts/{tx_id}/reprint` admin route lets the user replay any receipt. A `/api/health/printer` endpoint polls printer status for the POS health dots.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, `python-escpos` for ESC/POS encoding + USB transport, Pillow (optional, transitive dep for `python-escpos` if we ever render QR/barcode images), pytest + hex-byte golden fixtures.

**Spec reference:** `docs/superpowers/specs/2026-04-18-go-live-v1-design.md` §5.

**Starting point:** `main` branch after Plan A (Fiscal Backbone) is merged — this plan depends on `PosTransaction`, `PosTransactionLine`, and `PosTransactionService` existing.

**Explicitly deferred (not this plan):**

- **Z-Report rendering** — depends on Kassenbuch (Plan C) and shift-close flow (Plan D).
- **Digital (email/PDF) receipt** — spec §5 defers to Phase 2.
- **Barcode/QR image on the receipt** — spec §5 shows `[QR code]` but that's "Phase 2 hook." Day-1 prints text only.
- **POS health-dot wiring in UI** — Plan D.
- **Cash-drawer pulse** — logically part of ESC/POS but belongs with payment (Plan C), since it's only triggered by cash flows and Kassenbuch entries.

---

## File Structure

**Backend new:**

- `backend/app/receipt/__init__.py`
- `backend/app/receipt/builder.py` — `ReceiptBuilder.render(tx, lines) -> bytes` (pure)
- `backend/app/receipt/printer.py` — `ReceiptPrinter`, `PrinterBackend` Protocol, `UsbBackend`, `DummyBackend`
- `backend/app/receipt/service.py` — `ReceiptService.print_receipt(pos_transaction_id)` wiring builder + printer + job table
- `backend/app/receipt/errors.py`
- `backend/app/api/receipts.py` — `POST /api/receipts/{tx_id}/reprint`, `GET /api/health/printer`
- `backend/app/models/receipt_job.py` — `ReceiptPrintJob`
- `backend/alembic/versions/0105_add_receipt_print_jobs.py`
- `backend/tests/test_receipt_builder.py` — golden
- `backend/tests/test_receipt_printer.py` — paper-out + buffered job
- `backend/tests/test_receipts_api.py` — reprint + health
- `backend/tests/goldens/receipt_basic_cash.escpos` — golden byte fixture

**Backend modified:**

- `backend/requirements.txt` — add `python-escpos==3.1`, `Pillow==10.4.0`
- `backend/app/models/__init__.py` — export `ReceiptPrintJob`
- `backend/app/main.py` — register `receipts` router
- `backend/app/config.py` — add `printer_vendor_id`, `printer_product_id`, `printer_profile`

---

## Task 1: Dependencies + printer config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1.1: Add dependencies**

Append to `backend/requirements.txt`:

```
python-escpos==3.1
Pillow==10.4.0
```

- [ ] **Step 1.2: Write the failing test**

Append to `backend/tests/test_config.py`:

```python
def test_settings_parses_printer_config_defaults():
    s = Settings(session_secret_key="x" * 48)
    assert s.printer_vendor_id == 0x04b8  # Epson default
    assert s.printer_product_id == 0x0e28  # TM-m30III default
    assert s.printer_profile == "TM-m30III"


def test_settings_parses_printer_config_overrides():
    s = Settings(
        session_secret_key="x" * 48,
        printer_vendor_id=0x0519, printer_product_id=0x0003,
        printer_profile="TSP143",
    )
    assert s.printer_vendor_id == 0x0519
    assert s.printer_product_id == 0x0003
    assert s.printer_profile == "TSP143"
```

- [ ] **Step 1.3: Run, confirm fail**

Run: `cd backend && pytest tests/test_config.py -v -k printer`
Expected: FAIL.

- [ ] **Step 1.4: Add the settings**

In `backend/app/config.py`, inside the `Settings` class:

```python
    printer_vendor_id: int = 0x04b8   # Epson
    printer_product_id: int = 0x0e28  # TM-m30III
    printer_profile: str = "TM-m30III"
```

- [ ] **Step 1.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_config.py -v`

- [ ] **Step 1.6: Commit**

```bash
git add backend/requirements.txt backend/app/config.py backend/tests/test_config.py
git commit -m "feat(config): printer USB vendor/product IDs + profile"
```

---

## Task 2: Migration — `receipt_print_jobs`

**Files:**
- Create: `backend/alembic/versions/0105_add_receipt_print_jobs.py`

- [ ] **Step 2.1: Generate + rename**

Run: `cd backend && alembic revision -m "add receipt_print_jobs"`
Rename to `0105_add_receipt_print_jobs.py`. Set `revision` / `down_revision = "0104_fiscal_immutability_triggers"`.

- [ ] **Step 2.2: Fill the migration**

Replace file contents:

```python
"""add receipt_print_jobs

Revision ID: 0105_add_receipt_print_jobs
Revises: 0104_fiscal_immutability_triggers
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0105_add_receipt_print_jobs"
down_revision = "0104_fiscal_immutability_triggers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "receipt_print_jobs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "pos_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pos_transactions.id"),
            nullable=False,
        ),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_receipt_print_jobs_tx", "receipt_print_jobs", ["pos_transaction_id"])
    op.create_index("ix_receipt_print_jobs_status", "receipt_print_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("receipt_print_jobs")
```

`status` is one of: `pending`, `printed`, `buffered`, `failed`. Kept as text (no enum) so future states don't need a migration.

- [ ] **Step 2.3: Up/down/up cycle**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`

- [ ] **Step 2.4: Commit**

```bash
git add backend/alembic/versions/0105_add_receipt_print_jobs.py
git commit -m "feat(db): receipt_print_jobs table"
```

---

## Task 3: Model — `ReceiptPrintJob`

**Files:**
- Create: `backend/app/models/receipt_job.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 3.1: Create the model file**

Create `backend/app/models/receipt_job.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReceiptPrintJob(Base):
    __tablename__ = "receipt_print_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pos_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_transactions.id"), nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    printed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 3.2: Export from models package**

Append to `backend/app/models/__init__.py`:

```python
from app.models.receipt_job import ReceiptPrintJob  # noqa: F401
```

- [ ] **Step 3.3: Smoke-import**

Run: `cd backend && python -c "from app.models import ReceiptPrintJob; print(ReceiptPrintJob.__tablename__)"`
Expected: `receipt_print_jobs`.

- [ ] **Step 3.4: Commit**

```bash
git add backend/app/models/receipt_job.py backend/app/models/__init__.py
git commit -m "feat(models): ReceiptPrintJob"
```

---

## Task 4: Errors + package skeleton

**Files:**
- Create: `backend/app/receipt/__init__.py`
- Create: `backend/app/receipt/errors.py`

- [ ] **Step 4.1: Create package files**

Create empty `backend/app/receipt/__init__.py`.

Create `backend/app/receipt/errors.py`:

```python
class ReceiptError(Exception):
    """Base for receipt subsystem errors."""


class PrinterUnavailableError(ReceiptError):
    """USB printer not found or unreachable."""


class PrinterPaperOutError(ReceiptError):
    """Printer online but out of paper or cover open."""


class PrinterWriteError(ReceiptError):
    """Write to printer failed mid-stream."""
```

- [ ] **Step 4.2: Commit**

```bash
git add backend/app/receipt/__init__.py backend/app/receipt/errors.py
git commit -m "feat(receipt): error hierarchy + package"
```

---

## Task 5: ReceiptBuilder — golden-tested ESC/POS bytes

The output of `ReceiptBuilder.render(tx, lines)` is bytes that drive an 80mm thermal printer. The layout follows spec §5.

**Files:**
- Create: `backend/app/receipt/builder.py`
- Create: `backend/tests/test_receipt_builder.py`
- Create: `backend/tests/goldens/receipt_basic_cash.escpos` (generated during this task)

**Approach:** The test builds a fixture `PosTransaction` with pinned values, calls `render`, writes the bytes to a fresh golden file on first run (and commits it), then on subsequent runs compares equality. This is the standard "capture then pin" golden pattern.

- [ ] **Step 5.1: Write the failing test**

Create `backend/tests/test_receipt_builder.py`:

```python
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.receipt.builder import ReceiptBuilder
from app.models import PosTransaction, PosTransactionLine


GOLDENS = Path(__file__).parent / "goldens"
UPDATE = os.environ.get("UPDATE_GOLDENS") == "1"


def _fixture_transaction() -> tuple[PosTransaction, list[PosTransactionLine]]:
    tx_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    tx = PosTransaction(
        id=tx_id, client_id=tx_id,
        cashier_user_id=1,
        started_at=datetime(2026, 4, 18, 14, 23, 12, tzinfo=timezone.utc),
        finished_at=datetime(2026, 4, 18, 14, 23, 42, tzinfo=timezone.utc),
        total_gross=Decimal("1.29"),
        total_net=Decimal("1.21"),
        vat_breakdown={"7": {"net": "1.21", "vat": "0.08", "gross": "1.29"}},
        payment_breakdown={"cash": "1.29"},
        receipt_number=847,
        tse_signature="MEUCIQD-fake",
        tse_signature_counter=4728,
        tse_serial="serial-abc123",
        tse_timestamp_start=datetime(2026, 4, 18, 14, 23, 12, 41000, tzinfo=timezone.utc),
        tse_timestamp_finish=datetime(2026, 4, 18, 14, 23, 41, 892000, tzinfo=timezone.utc),
        tse_process_type="Kassenbeleg-V1",
    )
    lines = [
        PosTransactionLine(
            pos_transaction_id=tx_id,
            title="Milch 1L",
            quantity=Decimal("1"),
            quantity_kg=None,
            unit_price=Decimal("1.29"),
            line_total_net=Decimal("1.21"),
            vat_rate=Decimal("7"),
            vat_amount=Decimal("0.08"),
        ),
    ]
    return tx, lines


def test_render_matches_golden():
    tx, lines = _fixture_transaction()
    out = ReceiptBuilder(
        merchant_name="Voids Market",
        merchant_address="Street 1, 12345 Berlin",
        merchant_tax_id="12/345/67890",
        merchant_vat_id="DE123456789",
        cashier_display="Anna M.",
        register_id="KASSE-01",
    ).render(tx, lines)

    golden = GOLDENS / "receipt_basic_cash.escpos"
    if UPDATE or not golden.exists():
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_bytes(out)
        pytest.skip("golden written; re-run without UPDATE_GOLDENS=1")
    assert out == golden.read_bytes(), (
        "Receipt bytes diverged from golden. If intentional, rerun with "
        "UPDATE_GOLDENS=1 and commit the updated golden file."
    )
```

- [ ] **Step 5.2: Run, confirm fail (module missing)**

Run: `cd backend && pytest tests/test_receipt_builder.py -v`
Expected: FAIL — `ReceiptBuilder` not defined.

- [ ] **Step 5.3: Implement `ReceiptBuilder`**

Create `backend/app/receipt/builder.py`:

```python
"""Pure ESC/POS byte-stream builder for an 80mm thermal receipt.

The output is deterministic: given the same inputs, byte-identical output.
This is enforced by the golden test in tests/test_receipt_builder.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from escpos.printer import Dummy

from app.models import PosTransaction, PosTransactionLine


_VAT_LETTER_BY_RATE = {
    Decimal("7"): "A",
    Decimal("19"): "B",
    Decimal("10.7"): "C",
    Decimal("0"): "D",
    Decimal("5.5"): "E",
}


@dataclass
class ReceiptBuilder:
    merchant_name: str
    merchant_address: str
    merchant_tax_id: str
    merchant_vat_id: str
    cashier_display: str
    register_id: str

    def render(self, tx: PosTransaction, lines: Sequence[PosTransactionLine]) -> bytes:
        p = Dummy()
        self._header(p)
        p.set(align="center", bold=True)
        p.textln(self.merchant_name)
        p.set(align="center", bold=False)
        p.textln(self.merchant_address)
        p.textln(f"St-Nr: {self.merchant_tax_id}")
        p.textln(f"USt-IdNr: {self.merchant_vat_id}")
        self._sep(p)
        p.set(align="left")
        p.textln(f"Datum:  {_fmt_dt(tx.finished_at or tx.started_at)}")
        p.textln(f"Beleg-Nr: {_fmt_receipt_number(tx.receipt_number, tx.started_at.year)}")
        p.textln(f"Kasse:  {self.register_id}")
        p.textln(f"Bediener: {self.cashier_display}")
        self._sep(p)

        for ln in lines:
            letter = _VAT_LETTER_BY_RATE.get(
                Decimal(ln.vat_rate).quantize(Decimal("0.1")).normalize(), "?"
            )
            p.textln(ln.title)
            if ln.quantity_kg is not None:
                p.textln(
                    f"  {_fmt_qty(ln.quantity_kg)} kg x {_fmt_money(ln.unit_price)} EUR/kg"
                    f"  {_fmt_money(ln.line_total_net + ln.vat_amount)} {letter}"
                )
            else:
                p.textln(
                    f"  {int(ln.quantity)} x {_fmt_money(ln.unit_price)}"
                    f"  {_fmt_money(ln.line_total_net + ln.vat_amount)} {letter}"
                )
        self._sep(p)

        p.set(bold=True)
        p.textln(f"GESAMTSUMME          {_fmt_money(tx.total_gross)} EUR")
        p.set(bold=False)
        p.textln("")
        p.textln("  Netto   USt   Brutto")
        for rate, amounts in tx.vat_breakdown.items():
            letter = _VAT_LETTER_BY_RATE.get(Decimal(rate), "?")
            p.textln(
                f"{letter} {rate}%  {_fmt_money(amounts['vat'])}"
                f"   {_fmt_money(amounts['gross'])}  {_fmt_money(amounts['net'])}"
            )
        p.textln("")
        p.textln("Bezahlt mit:")
        for method, amount in tx.payment_breakdown.items():
            label = {"cash": "Bar", "girocard": "Girocard", "card": "Karte"}.get(method, method)
            p.textln(f"  {label:<20}{_fmt_money(amount)} EUR")
        self._sep(p)
        p.textln("TSE-Signatur")
        p.textln(f"Seriennr: {_truncate(tx.tse_serial or '', 30)}")
        p.textln(f"Sig-Zaehler: {tx.tse_signature_counter or ''}")
        p.textln(f"Start: {_fmt_iso(tx.tse_timestamp_start)}")
        p.textln(f"Ende:  {_fmt_iso(tx.tse_timestamp_finish)}")
        p.textln(f"Typ:   {tx.tse_process_type or ''}")
        p.textln(f"Sig:   {_truncate(tx.tse_signature or '', 40)}")
        self._sep(p)
        p.set(align="center")
        p.textln("Vielen Dank fuer Ihren Einkauf!")
        p.textln("")
        p.cut()
        return p.output

    def _sep(self, p: Dummy) -> None:
        p.set(align="left")
        p.textln("-" * 32)

    def _header(self, p: Dummy) -> None:
        p.hw("INIT")


def _fmt_money(v) -> str:
    return f"{Decimal(v).quantize(Decimal('0.01')):>6.2f}"


def _fmt_qty(v) -> str:
    return f"{Decimal(v).quantize(Decimal('0.001'))}"


def _fmt_dt(d) -> str:
    return d.strftime("%d.%m.%Y  %H:%M") if d else ""


def _fmt_iso(d) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z" if d else ""


def _fmt_receipt_number(n: int, year: int) -> str:
    return f"{year}-{n:06d}"


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."
```

Notes on the approach:

- `escpos.printer.Dummy` collects emitted bytes in `.output` — perfect for tests and also for piping into the real USB printer without a coupled layout-vs-transport.
- No umlauts (Ä, Ö, Ü, ß) on the receipt — ESC/POS code page handling is a rabbit hole and spec §5 doesn't mandate them in the layout example beyond the merchant name. Day-1 uses ASCII only; Phase 2 enables codepage 858 and re-golden.
- The signature is truncated to 40 chars to fit 32 characters per line + label. A full ECDSA signature is ~90 chars base64 — truncated display is standard KassenSichV practice; the full signature lives in the DSFinV-K export.

- [ ] **Step 5.4: Run the test to generate the golden, then re-run**

Run: `cd backend && UPDATE_GOLDENS=1 pytest tests/test_receipt_builder.py -v`
Expected: test SKIPS with message "golden written; re-run without UPDATE_GOLDENS=1".

Re-run: `cd backend && pytest tests/test_receipt_builder.py -v`
Expected: PASS.

- [ ] **Step 5.5: Inspect the golden visually (optional sanity check)**

Run: `cd backend && python -c "from pathlib import Path; import re; b = Path('tests/goldens/receipt_basic_cash.escpos').read_bytes(); print(re.sub(rb'\x1b\[?.?', b'', b).decode('ascii', errors='replace'))"`

You should see a human-readable receipt in the terminal (approximately — some ESC/POS control bytes survive the regex).

- [ ] **Step 5.6: Commit (including the golden file)**

```bash
git add backend/app/receipt/builder.py backend/tests/test_receipt_builder.py backend/tests/goldens/receipt_basic_cash.escpos
git commit -m "feat(receipt): ReceiptBuilder with golden-tested ESC/POS output"
```

---

## Task 6: PrinterBackend Protocol + DummyBackend

**Files:**
- Create: `backend/app/receipt/printer.py` (partial; `ReceiptPrinter` added in Task 7)
- Test: `backend/tests/test_receipt_printer.py` (partial)

- [ ] **Step 6.1: Write the backend skeleton**

Create `backend/app/receipt/printer.py`:

```python
"""USB printer transport and the ReceiptPrinter wrapper.

PrinterBackend abstracts the transport so tests inject DummyBackend and
production uses UsbBackend (python-escpos). The wire format (ESC/POS bytes)
is produced by ReceiptBuilder; this module only concerns itself with
pushing bytes and reading status.
"""
from __future__ import annotations

from typing import Protocol

from app.receipt.errors import (
    PrinterUnavailableError, PrinterPaperOutError, PrinterWriteError,
)


class PrinterBackend(Protocol):
    def write(self, data: bytes) -> None: ...
    def is_paper_ok(self) -> bool: ...
    def is_online(self) -> bool: ...


class DummyBackend:
    """In-memory printer for tests. Configurable fault injection."""

    def __init__(self, *, online: bool = True, paper_ok: bool = True):
        self.online = online
        self.paper_ok = paper_ok
        self.buffer: bytearray = bytearray()

    def write(self, data: bytes) -> None:
        if not self.online:
            raise PrinterUnavailableError("dummy offline")
        if not self.paper_ok:
            raise PrinterPaperOutError("dummy out of paper")
        self.buffer.extend(data)

    def is_paper_ok(self) -> bool:
        return self.paper_ok

    def is_online(self) -> bool:
        return self.online


class UsbBackend:
    """Real python-escpos USB transport. Not exercised in CI."""

    def __init__(self, vendor_id: int, product_id: int, profile: str):
        from escpos.printer import Usb
        try:
            self._p = Usb(vendor_id, product_id, profile=profile)
        except Exception as e:
            raise PrinterUnavailableError(f"USB open failed: {e}") from e

    def write(self, data: bytes) -> None:
        try:
            self._p._raw(data)
        except Exception as e:
            raise PrinterWriteError(str(e)) from e

    def is_paper_ok(self) -> bool:
        try:
            return bool(self._p.paper_status())
        except Exception:
            return False

    def is_online(self) -> bool:
        try:
            return self._p.is_online()
        except Exception:
            return False
```

**Note:** `python-escpos`'s `Usb` requires libusb to be installed on the host — it's a dev-time hurdle for contributors without hardware. The `DummyBackend` is the default in tests; `UsbBackend` is only constructed in `ReceiptService` when `FISKALY_*` and `PRINTER_*` env vars indicate a real deployment.

- [ ] **Step 6.2: Commit**

```bash
git add backend/app/receipt/printer.py
git commit -m "feat(receipt): PrinterBackend Protocol + Dummy/Usb implementations"
```

---

## Task 7: ReceiptService.print_receipt — happy path

**Files:**
- Create: `backend/app/receipt/service.py`
- Test: `backend/tests/test_receipt_printer.py`

- [ ] **Step 7.1: Write the failing test**

Create `backend/tests/test_receipt_printer.py`:

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import (
    PosTransaction, PosTransactionLine, ReceiptPrintJob, User,
)
from app.receipt.builder import ReceiptBuilder
from app.receipt.printer import DummyBackend
from app.receipt.service import ReceiptService
from app.services.password import hash_pin


def _builder() -> ReceiptBuilder:
    return ReceiptBuilder(
        merchant_name="Voids Market", merchant_address="Street 1",
        merchant_tax_id="12/345/67890", merchant_vat_id="DE123456789",
        cashier_display="Anna", register_id="KASSE-01",
    )


async def _seed_tx(db, *, receipt_number: int = 1) -> PosTransaction:
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1"),
             full_name="A", role="cashier")
    db.add(c); await db.commit(); await db.refresh(c)
    tid = uuid.uuid4()
    tx = PosTransaction(
        id=tid, client_id=tid, cashier_user_id=c.id,
        started_at=datetime.now(tz=timezone.utc),
        finished_at=datetime.now(tz=timezone.utc),
        total_gross=Decimal("1.29"), total_net=Decimal("1.21"),
        vat_breakdown={"7": {"net": "1.21", "vat": "0.08", "gross": "1.29"}},
        payment_breakdown={"cash": "1.29"},
        receipt_number=receipt_number,
        tse_signature="SIG", tse_signature_counter=1, tse_serial="SER",
        tse_timestamp_start=datetime.now(tz=timezone.utc),
        tse_timestamp_finish=datetime.now(tz=timezone.utc),
        tse_process_type="Kassenbeleg-V1",
    )
    db.add(tx)
    db.add(PosTransactionLine(
        pos_transaction_id=tid, title="Milk", quantity=Decimal("1"),
        unit_price=Decimal("1.29"), line_total_net=Decimal("1.21"),
        vat_rate=Decimal("7"), vat_amount=Decimal("0.08"),
    ))
    await db.commit()
    return tx


@pytest.mark.asyncio
async def test_print_receipt_happy_path(db):
    tx = await _seed_tx(db)
    backend = DummyBackend()
    svc = ReceiptService(db=db, builder=_builder(), backend=backend)

    job = await svc.print_receipt(tx.id)

    assert job.status == "printed"
    assert len(backend.buffer) > 0
    assert job.printed_at is not None


@pytest.mark.asyncio
async def test_print_receipt_buffers_on_paper_out(db):
    tx = await _seed_tx(db, receipt_number=2)
    backend = DummyBackend(paper_ok=False)
    svc = ReceiptService(db=db, builder=_builder(), backend=backend)

    job = await svc.print_receipt(tx.id)

    assert job.status == "buffered"
    assert "paper" in (job.last_error or "").lower()
    # The sale is not rolled back — the job just awaits reprint.


@pytest.mark.asyncio
async def test_print_receipt_buffers_on_offline(db):
    tx = await _seed_tx(db, receipt_number=3)
    backend = DummyBackend(online=False)
    svc = ReceiptService(db=db, builder=_builder(), backend=backend)

    job = await svc.print_receipt(tx.id)

    assert job.status == "buffered"


@pytest.mark.asyncio
async def test_reprint_runs_pending_and_buffered(db):
    tx = await _seed_tx(db, receipt_number=4)
    offline = DummyBackend(online=False)
    svc_off = ReceiptService(db=db, builder=_builder(), backend=offline)
    await svc_off.print_receipt(tx.id)

    online = DummyBackend()
    svc_on = ReceiptService(db=db, builder=_builder(), backend=online)
    job = await svc_on.reprint(tx.id)

    assert job.status == "printed"
    assert len(online.buffer) > 0
    jobs = (await db.execute(
        select(ReceiptPrintJob).where(ReceiptPrintJob.pos_transaction_id == tx.id)
    )).scalars().all()
    # Two jobs total: the original buffered + the successful reprint.
    assert len(jobs) == 2
    assert {j.status for j in jobs} == {"buffered", "printed"}
```

- [ ] **Step 7.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_receipt_printer.py -v`
Expected: FAIL — `ReceiptService` not defined.

- [ ] **Step 7.3: Implement `ReceiptService`**

Create `backend/app/receipt/service.py`:

```python
"""Bind a PosTransaction to a physical print + a ReceiptPrintJob row."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PosTransaction, PosTransactionLine, ReceiptPrintJob,
)
from app.receipt.builder import ReceiptBuilder
from app.receipt.errors import (
    PrinterPaperOutError, PrinterUnavailableError, PrinterWriteError, ReceiptError,
)
from app.receipt.printer import PrinterBackend


class ReceiptService:
    def __init__(
        self, *,
        db: AsyncSession,
        builder: ReceiptBuilder,
        backend: PrinterBackend,
    ):
        self.db = db
        self.builder = builder
        self.backend = backend

    async def print_receipt(self, pos_transaction_id: uuid.UUID) -> ReceiptPrintJob:
        tx, lines = await self._load(pos_transaction_id)
        data = self.builder.render(tx, lines)

        job = ReceiptPrintJob(
            pos_transaction_id=pos_transaction_id,
            status="pending", attempts=0,
            created_at=datetime.now(tz=timezone.utc),
        )
        self.db.add(job)
        await self.db.flush()
        return await self._attempt(job, data)

    async def reprint(self, pos_transaction_id: uuid.UUID) -> ReceiptPrintJob:
        """Create a new print job and attempt printing. Used by the admin
        reprint route and by any paper-resolved retry workflow.
        """
        tx, lines = await self._load(pos_transaction_id)
        data = self.builder.render(tx, lines)
        job = ReceiptPrintJob(
            pos_transaction_id=pos_transaction_id,
            status="pending", attempts=0,
            created_at=datetime.now(tz=timezone.utc),
        )
        self.db.add(job)
        await self.db.flush()
        return await self._attempt(job, data)

    async def _attempt(self, job: ReceiptPrintJob, data: bytes) -> ReceiptPrintJob:
        job.attempts = job.attempts + 1
        try:
            self.backend.write(data)
        except (PrinterPaperOutError, PrinterUnavailableError, PrinterWriteError) as e:
            job.status = "buffered"
            job.last_error = str(e)
            await self.db.commit()
            await self.db.refresh(job)
            return job
        except ReceiptError as e:
            job.status = "failed"
            job.last_error = str(e)
            await self.db.commit()
            await self.db.refresh(job)
            return job

        job.status = "printed"
        job.printed_at = datetime.now(tz=timezone.utc)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def _load(self, pos_transaction_id: uuid.UUID):
        tx = (await self.db.execute(
            select(PosTransaction).where(PosTransaction.id == pos_transaction_id)
        )).scalar_one()
        lines = (await self.db.execute(
            select(PosTransactionLine).where(PosTransactionLine.pos_transaction_id == pos_transaction_id)
        )).scalars().all()
        return tx, lines
```

- [ ] **Step 7.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_receipt_printer.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 7.5: Commit**

```bash
git add backend/app/receipt/service.py backend/tests/test_receipt_printer.py
git commit -m "feat(receipt): ReceiptService.print_receipt + reprint, buffers on fault"
```

---

## Task 8: API — reprint + printer health

**Files:**
- Create: `backend/app/api/receipts.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_receipts_api.py`

- [ ] **Step 8.1: Write the failing test**

Create `backend/tests/test_receipts_api.py`:

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models import PosTransaction, PosTransactionLine, User
from app.services.password import hash_pin


async def _seed(db) -> uuid.UUID:
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1"),
             full_name="A", role="cashier")
    db.add(c); await db.commit(); await db.refresh(c)
    tid = uuid.uuid4()
    db.add(PosTransaction(
        id=tid, client_id=tid, cashier_user_id=c.id,
        started_at=datetime.now(tz=timezone.utc),
        finished_at=datetime.now(tz=timezone.utc),
        total_gross=Decimal("1"), total_net=Decimal("1"),
        vat_breakdown={"7": {"net": "0.93", "vat": "0.07", "gross": "1.00"}},
        payment_breakdown={"cash": "1.00"},
        receipt_number=100,
        tse_signature="SIG", tse_signature_counter=1, tse_serial="SER",
        tse_timestamp_start=datetime.now(tz=timezone.utc),
        tse_timestamp_finish=datetime.now(tz=timezone.utc),
        tse_process_type="Kassenbeleg-V1",
    ))
    db.add(PosTransactionLine(
        pos_transaction_id=tid, title="X", quantity=Decimal("1"),
        unit_price=Decimal("1"), line_total_net=Decimal("0.93"),
        vat_rate=Decimal("7"), vat_amount=Decimal("0.07"),
    ))
    await db.commit()
    return tid


@pytest.mark.asyncio
async def test_reprint_requires_staff(client, db):
    tid = await _seed(db)
    r = await client.post(f"/api/receipts/{tid}/reprint")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_reprint_returns_job_status(authed_client, db):
    tid = await _seed(db)
    r = await authed_client.post(f"/api/receipts/{tid}/reprint")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("printed", "buffered")
    assert body["pos_transaction_id"] == str(tid)


@pytest.mark.asyncio
async def test_health_printer_reports_state(authed_client):
    r = await authed_client.get("/api/health/printer")
    assert r.status_code == 200
    body = r.json()
    assert "online" in body and "paper_ok" in body
```

- [ ] **Step 8.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_receipts_api.py -v`
Expected: FAIL.

- [ ] **Step 8.3: Create the router**

Create `backend/app/api/receipts.py`:

```python
"""Receipt reprint + printer health endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_staff
from app.config import settings
from app.receipt.builder import ReceiptBuilder
from app.receipt.errors import PrinterUnavailableError
from app.receipt.printer import DummyBackend, PrinterBackend, UsbBackend
from app.receipt.service import ReceiptService


router = APIRouter(prefix="/api", tags=["receipts"])


def _builder() -> ReceiptBuilder:
    # Merchant info lives in Settings — added in Plan D; for now, placeholders
    # so the router is wirable. Plan D replaces with settings.merchant_*.
    return ReceiptBuilder(
        merchant_name="Voids Market",
        merchant_address="Street 1, 12345 Berlin",
        merchant_tax_id="12/345/67890",
        merchant_vat_id="DE123456789",
        cashier_display="",
        register_id="KASSE-01",
    )


def _backend() -> PrinterBackend:
    if not settings.printer_vendor_id:
        return DummyBackend()
    try:
        return UsbBackend(
            vendor_id=settings.printer_vendor_id,
            product_id=settings.printer_product_id,
            profile=settings.printer_profile,
        )
    except PrinterUnavailableError:
        return DummyBackend(online=False)


@router.post(
    "/receipts/{pos_transaction_id}/reprint",
    dependencies=[Depends(require_any_staff)],
)
async def reprint(pos_transaction_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    svc = ReceiptService(db=db, builder=_builder(), backend=_backend())
    try:
        job = await svc.reprint(pos_transaction_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {
        "id": job.id,
        "pos_transaction_id": str(job.pos_transaction_id),
        "status": job.status,
        "attempts": job.attempts,
        "last_error": job.last_error,
        "printed_at": job.printed_at.isoformat() if job.printed_at else None,
    }


@router.get("/health/printer", dependencies=[Depends(require_any_staff)])
async def health_printer():
    backend = _backend()
    return {"online": backend.is_online(), "paper_ok": backend.is_paper_ok()}
```

- [ ] **Step 8.4: Register in `main.py`**

In `backend/app/main.py`, alongside the other `app.include_router(...)` calls:

```python
from app.api.receipts import router as receipts_router
# ...
app.include_router(receipts_router)
```

- [ ] **Step 8.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_receipts_api.py -v`
Expected: PASS.

- [ ] **Step 8.6: Commit**

```bash
git add backend/app/api/receipts.py backend/app/main.py backend/tests/test_receipts_api.py
git commit -m "feat(api): receipt reprint + /api/health/printer"
```

---

## Self-Review Checklist

1. **Spec §5 `python-escpos`, direct USB, no CUPS** — Task 1 adds dependency; Task 6 uses `escpos.printer.Usb`. ✓
2. **Spec §5 `ReceiptPrinter.print_receipt(pos_transaction_id)`** — Task 7. ✓
3. **Spec §5 paper-out / offline → sale not rolled back, buffered for reprint** — Task 7 `_attempt` catches printer errors and sets `status="buffered"`; Task 8 reprint route exists. ✓
4. **Spec §5 layout (merchant header, date, receipt number, lines, totals, VAT table, TSE block, thank-you)** — Task 5. ✓
5. **Spec §5 80mm thermal, ESC/POS** — `Dummy` + `Usb` (python-escpos) both emit same byte stream. ✓
6. **Spec §5 receipt-number format (year-prefixed)** — `_fmt_receipt_number` in Task 5. ✓
7. **Spec §5 TSE block on receipt** — Task 5 emits serial, counter, timestamps, type, truncated signature. ✓
8. **Spec §5 "Offer to print is logged in `audit_event`"** — NOT covered; Plan D owns audit-event wiring for receipts (since Plan D has the full receipt UX including "Beleg erneut drucken" button). Tracked below.
9. **Spec §5 Z-Report** — Explicitly deferred (see header).
10. **Spec §8 `/api/health/printer`** — Task 8. ✓
11. **Spec §9 golden-file receipt tests** — Task 5. ✓

**Placeholder scan:** no TBD/TODO/appropriate.

**Type consistency:**
- `pos_transaction_id: uuid.UUID` matches PosTransaction.id from Plan A. ✓
- `ReceiptPrintJob.status` values (`pending`, `printed`, `buffered`, `failed`) consistent between model (Task 3), service (Task 7), and tests. ✓
- `PrinterBackend.write(bytes) -> None`, `is_online() -> bool`, `is_paper_ok() -> bool` consistent between Protocol (Task 6), DummyBackend, UsbBackend, ReceiptService, and receipts router. ✓

**Tracked handoffs to later plans:**

- Plan D: replace placeholder merchant info in `_builder()` with `settings.merchant_*` fields; wire health-dots into POS UI; audit-event log on every print offer.
- Plan C: cash-drawer ESC/POS pulse uses the same `PrinterBackend.write` transport — Plan C adds a helper `backend.pulse_cash_drawer()` method.

---

**Plan complete.** On to Plan C (Payment Flow).
