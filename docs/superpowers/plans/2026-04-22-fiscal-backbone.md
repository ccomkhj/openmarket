# Fiscal Backbone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the fiscal primitives that every legal sale in Germany requires — append-only `pos_transaction` / `pos_transaction_line` / `tse_signing_log` tables, a gap-free receipt-number sequence, a `FiscalService` that signs transactions through fiskaly's Cloud-TSE, and a `PosTransactionService.finalize_sale` that wraps an existing `Order` into a signed `PosTransaction`. No UI and no payment integration in this plan — the goal is a backend-only, testable, fiscally compliant transaction primitive that later plans (receipt printing, payment, checkout UX) consume.

**Architecture:** A new thin `FiscalClient` wraps fiskaly's REST API with OAuth2 token caching over `httpx.AsyncClient`. A higher-level `FiscalService` exposes `start_transaction`, `finish_transaction`, and `retry_pending_signatures`. `PosTransactionService.finalize_sale(order_id, cashier_user_id, payment_breakdown)` is the single entry point: it inserts the `pos_transaction` row in OPEN state, calls fiskaly start → finish, writes the TSE signature fields back, and returns the transaction. fiskaly failures leave `tse_pending=True` and a retryable row. Immutability is enforced at the database layer by triggers (same pattern as `audit_events`). All fiskaly calls (success + failure) are persisted to `tse_signing_log` for post-mortems.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Postgres (triggers + sequences), httpx for fiskaly REST, respx for test mocking. No new SDK dependency — fiskaly has no official Python SDK, the REST API is used directly.

**Spec reference:** `docs/superpowers/specs/2026-04-18-go-live-v1-design.md` §1.

**Starting point:** `main` branch after `2026-04-18-foundation-fixups.md` is executed (Plan 0). This plan does NOT depend on Plan 0 code changes — but the two should not be interleaved. If Plan 0 is in flight, finish and merge it first.

**Explicitly deferred (not this plan):**

- **DSFinV-K export** — covered in Plan D.
- **Storno UI / void flow** — Plan D. The schema here supports it (`voids_transaction_id` self-FK), but no endpoint/UI.
- **Receipt printing** — Plan B.
- **Payment integration (ZVT, cash, drawer, Kassenbuch)** — Plan C. `payment_breakdown` is passed in as a dict here; who fills that dict is Plan C's problem.
- **Wiring into POS `SalePage`** — Plan D.
- **Year rotation of `receipt_number_seq`** — Phase 2; day-1 uses a single lifetime sequence with year-prefix formatting at render time.

---

## File Structure

**Backend new:**

- `backend/app/fiscal/__init__.py` — package marker
- `backend/app/fiscal/process_data.py` — canonical `process_data` string builder (pure function, golden-tested)
- `backend/app/fiscal/client.py` — `FiscalClient` (httpx + OAuth2)
- `backend/app/fiscal/service.py` — `FiscalService` (high-level start/finish/retry)
- `backend/app/fiscal/errors.py` — exception hierarchy
- `backend/app/services/pos_transaction.py` — `PosTransactionService.finalize_sale`
- `backend/alembic/versions/0103_add_pos_transaction_tables.py`
- `backend/alembic/versions/0104_fiscal_immutability_triggers.py`
- `backend/app/models/pos_transaction.py` — `PosTransaction`, `PosTransactionLine`, `TseSigningLog`
- `backend/tests/test_process_data.py` — golden test for canonical string
- `backend/tests/test_fiscal_client.py` — OAuth2 + retry, respx-mocked
- `backend/tests/test_fiscal_service.py` — start/finish flow, respx-mocked
- `backend/tests/test_pos_transaction_service.py` — finalize_sale integration (fiskaly mocked, DB real)
- `backend/tests/test_fiscal_immutability.py` — UPDATE/DELETE on fiscal rows is rejected
- `backend/tests/fiscal_helpers.py` — shared respx fixture + sample fiskaly responses

**Backend modified:**

- `backend/requirements.txt` — add `respx==0.22.0` (test-only) and `tenacity==9.0.0` (retry backoff)
- `backend/app/config.py` — add `fiskaly_api_key`, `fiskaly_api_secret`, `fiskaly_tss_id`, `fiskaly_base_url`
- `backend/app/models/__init__.py` — export the three new models
- `backend/app/main.py` — startup hook that calls `retry_pending_signatures()` once on boot
- `backend/tests/conftest.py` — apply fiscal immutability triggers in `setup_db`

**Ops modified:**

- `.env.example` (create if missing) — list the four fiskaly envs with empty values

---

## Task 1: Config, dependencies, and `.env.example`

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config.py`
- Create (if missing): `.env.example` at repo root

- [ ] **Step 1.1: Add dependencies**

Append to `backend/requirements.txt`:

```
tenacity==9.0.0
respx==0.22.0
```

(tenacity is runtime for retry/backoff; respx is test-only but we keep one requirements file — the separation is Plan-2-level polish.)

- [ ] **Step 1.2: Write the failing test**

Append to `backend/tests/test_config.py`:

```python
def test_settings_parses_fiskaly_config():
    s = Settings(
        session_secret_key="x" * 48,
        fiskaly_api_key="key-123",
        fiskaly_api_secret="secret-456",
        fiskaly_tss_id="tss-abc",
    )
    assert s.fiskaly_api_key == "key-123"
    assert s.fiskaly_api_secret == "secret-456"
    assert s.fiskaly_tss_id == "tss-abc"
    assert s.fiskaly_base_url == "https://kassensichv-middleware.fiskaly.com"


def test_settings_fiskaly_base_url_overridable():
    s = Settings(
        session_secret_key="x" * 48,
        fiskaly_api_key="k", fiskaly_api_secret="s", fiskaly_tss_id="t",
        fiskaly_base_url="https://sandbox.example.com",
    )
    assert s.fiskaly_base_url == "https://sandbox.example.com"
```

- [ ] **Step 1.3: Run, confirm fail**

Run: `cd backend && pytest tests/test_config.py -v -k fiskaly`
Expected: FAIL — `fiskaly_*` fields don't exist yet.

- [ ] **Step 1.4: Add fields to `Settings`**

In `backend/app/config.py`, inside the `Settings` class, alongside the other fields:

```python
    fiskaly_api_key: str = ""
    fiskaly_api_secret: str = ""
    fiskaly_tss_id: str = ""
    fiskaly_base_url: str = "https://kassensichv-middleware.fiskaly.com"
```

Note: defaults are empty strings rather than `None` so tests without fiskaly can still construct Settings. The FiscalClient validates non-empty before making calls.

- [ ] **Step 1.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_config.py -v`
Expected: all tests pass (previous + 2 new).

- [ ] **Step 1.6: Create `.env.example`**

Create `.env.example` at the repo root with:

```dotenv
# Database
DB_PASSWORD=changeme
DATABASE_URL=postgresql+asyncpg://openmarket:changeme@db:5432/openmarket

# Session
SESSION_SECRET_KEY=generate-with-openssl-rand-hex-24-exactly-48-hex-chars-min
SESSION_COOKIE_SECURE=true

# Fiskaly (KassenSichV Cloud-TSE)
FISKALY_API_KEY=
FISKALY_API_SECRET=
FISKALY_TSS_ID=
FISKALY_BASE_URL=https://kassensichv-middleware.fiskaly.com
```

If a `.env.example` already exists, instead just append the `# Fiskaly` block.

- [ ] **Step 1.7: Commit**

```bash
git add backend/requirements.txt backend/app/config.py backend/tests/test_config.py .env.example
git commit -m "feat(config): add fiskaly settings + tenacity/respx deps"
```

---

## Task 2: Migration — pos_transaction + pos_transaction_line + receipt_number_seq

**Files:**
- Create: `backend/alembic/versions/0103_add_pos_transaction_tables.py`

- [ ] **Step 2.1: Generate a stub migration**

Run: `cd backend && alembic revision -m "add pos_transaction tables"`
Expected: a new file `backend/alembic/versions/<hash>_add_pos_transaction_tables.py`.

- [ ] **Step 2.2: Rename to conventional prefix**

Rename the file so it begins with `0103_`. Edit the file header so `revision = "0103_add_pos_transaction_tables"` and `down_revision = "0102_add_weighed_produce_columns"`.

- [ ] **Step 2.3: Fill the `upgrade()` body**

Replace the file contents with:

```python
"""add pos_transaction tables

Revision ID: 0103_add_pos_transaction_tables
Revises: 0102_add_weighed_produce_columns
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0103_add_pos_transaction_tables"
down_revision = "0102_add_weighed_produce_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS receipt_number_seq START 1")

    op.create_table(
        "pos_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("cashier_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_gross", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total_net", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("vat_breakdown", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("payment_breakdown", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("receipt_number", sa.BigInteger, nullable=False, unique=True),
        sa.Column("linked_order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=True),
        sa.Column(
            "voids_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pos_transactions.id"),
            nullable=True,
        ),
        sa.Column("tse_signature", sa.Text, nullable=True),
        sa.Column("tse_signature_counter", sa.BigInteger, nullable=True),
        sa.Column("tse_serial", sa.Text, nullable=True),
        sa.Column("tse_timestamp_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tse_timestamp_finish", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tse_process_type", sa.Text, nullable=True),
        sa.Column("tse_process_data", sa.Text, nullable=True),
        sa.Column("tse_pending", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_pos_transactions_voids", "pos_transactions", ["voids_transaction_id"])
    op.create_index("ix_pos_transactions_linked_order", "pos_transactions", ["linked_order_id"])
    op.create_index("ix_pos_transactions_pending", "pos_transactions", ["tse_pending"])
    op.create_index("ix_pos_transactions_cashier_finished", "pos_transactions", ["cashier_user_id", "finished_at"])

    op.create_table(
        "pos_transaction_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pos_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pos_transactions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sku", sa.Text, nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column("quantity_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("unit_price", sa.Numeric(10, 4), nullable=False),
        sa.Column("line_total_net", sa.Numeric(10, 2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_pos_transaction_lines_tx", "pos_transaction_lines", ["pos_transaction_id"])

    op.create_table(
        "tse_signing_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "pos_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pos_transactions.id"),
            nullable=True,
        ),
        sa.Column("operation", sa.Text, nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("succeeded", sa.Boolean, nullable=False),
        sa.Column("error_code", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
    )
    op.create_index("ix_tse_signing_log_tx", "tse_signing_log", ["pos_transaction_id"])
    op.create_index("ix_tse_signing_log_attempted", "tse_signing_log", ["attempted_at"])


def downgrade() -> None:
    op.drop_table("tse_signing_log")
    op.drop_table("pos_transaction_lines")
    op.drop_table("pos_transactions")
    op.execute("DROP SEQUENCE IF EXISTS receipt_number_seq")
```

- [ ] **Step 2.4: Run the migration against a throwaway DB**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
Expected: all three commands succeed — the up/down/up cycle proves the migration is reversible.

- [ ] **Step 2.5: Commit**

```bash
git add backend/alembic/versions/0103_add_pos_transaction_tables.py
git commit -m "feat(db): add pos_transaction tables and receipt_number_seq"
```

---

## Task 3: Migration — fiscal immutability triggers

**Files:**
- Create: `backend/alembic/versions/0104_fiscal_immutability_triggers.py`

Pattern mirrors `0101_audit_event_immutable.py` — re-open the existing file first to copy the exact trigger-function name pattern (`audit_reject_modification`) and adapt.

- [ ] **Step 3.1: Read the existing immutability migration**

Run: `cat backend/alembic/versions/0101_audit_event_immutable.py`
(Look for the `CREATE FUNCTION ... RAISE EXCEPTION` pattern and the per-table triggers. Match the style.)

- [ ] **Step 3.2: Generate + rename the new migration**

Run: `cd backend && alembic revision -m "fiscal immutability triggers"`
Rename file to `0104_fiscal_immutability_triggers.py`. Set `revision = "0104_fiscal_immutability_triggers"`, `down_revision = "0103_add_pos_transaction_tables"`.

- [ ] **Step 3.3: Fill the migration**

Replace contents with:

```python
"""fiscal immutability triggers

Revision ID: 0104_fiscal_immutability_triggers
Revises: 0103_add_pos_transaction_tables
Create Date: 2026-04-22
"""
from alembic import op

revision = "0104_fiscal_immutability_triggers"
down_revision = "0103_add_pos_transaction_tables"
branch_labels = None
depends_on = None


REJECT_FN = """
CREATE OR REPLACE FUNCTION fiscal_reject_modification() RETURNS trigger AS $$
BEGIN
    -- Allow only the narrow signature-writeback path: UPDATE permitted when
    -- the caller sets session var `fiscal.signing=on`. Any other UPDATE or
    -- DELETE is rejected — fiscal rows are append-only by KassenSichV.
    IF current_setting('fiscal.signing', true) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Fiscal rows are immutable (TG_OP=%, table=%)', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(REJECT_FN)
    for tbl in ("pos_transactions", "pos_transaction_lines", "tse_signing_log"):
        op.execute(f"""
            CREATE TRIGGER {tbl}_reject_update
            BEFORE UPDATE ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION fiscal_reject_modification();
        """)
        op.execute(f"""
            CREATE TRIGGER {tbl}_reject_delete
            BEFORE DELETE ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION fiscal_reject_modification();
        """)


def downgrade() -> None:
    for tbl in ("pos_transactions", "pos_transaction_lines", "tse_signing_log"):
        op.execute(f"DROP TRIGGER IF EXISTS {tbl}_reject_update ON {tbl}")
        op.execute(f"DROP TRIGGER IF EXISTS {tbl}_reject_delete ON {tbl}")
    op.execute("DROP FUNCTION IF EXISTS fiscal_reject_modification()")
```

**Rationale for the `fiscal.signing` session var:** the signature-writeback UPDATE (one column set per transaction, from null to the fiskaly signature) is the single legitimate mutation of a `pos_transactions` row. We allow it by having `PosTransactionService` call `SET LOCAL fiscal.signing = 'on'` inside the same DB transaction that writes the signature. Every other UPDATE/DELETE is rejected.

- [ ] **Step 3.4: Up/down/up cycle**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
Expected: all succeed.

- [ ] **Step 3.5: Commit**

```bash
git add backend/alembic/versions/0104_fiscal_immutability_triggers.py
git commit -m "feat(db): fiscal immutability triggers on pos_transaction tables"
```

---

## Task 4: SQLAlchemy models

**Files:**
- Create: `backend/app/models/pos_transaction.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 4.1: Create the module**

Create `backend/app/models/pos_transaction.py`:

```python
"""Fiscal transaction models — append-only, DB-trigger-enforced."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PosTransaction(Base):
    __tablename__ = "pos_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    cashier_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    total_gross: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    total_net: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    vat_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    payment_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    receipt_number: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    linked_order_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("orders.id"), nullable=True)
    voids_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_transactions.id"), nullable=True,
    )

    tse_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tse_signature_counter: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    tse_serial: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tse_timestamp_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    tse_timestamp_finish: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    tse_process_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tse_process_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tse_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    lines: Mapped[list["PosTransactionLine"]] = relationship(
        "PosTransactionLine", back_populates="transaction", cascade=None,
    )


class PosTransactionLine(Base):
    __tablename__ = "pos_transaction_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pos_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_transactions.id"), nullable=False,
    )
    sku: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    quantity_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    line_total_net: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))

    transaction: Mapped["PosTransaction"] = relationship("PosTransaction", back_populates="lines")


class TseSigningLog(Base):
    __tablename__ = "tse_signing_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pos_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_transactions.id"), nullable=True,
    )
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 4.2: Export from `backend/app/models/__init__.py`**

Find the existing `__init__.py` and append (or insert next to other imports):

```python
from app.models.pos_transaction import PosTransaction, PosTransactionLine, TseSigningLog  # noqa: F401
```

Also add to `__all__` if the module defines one.

- [ ] **Step 4.3: Smoke-test via import**

Run: `cd backend && python -c "from app.models import PosTransaction, PosTransactionLine, TseSigningLog; print(PosTransaction.__tablename__)"`
Expected: `pos_transactions`.

- [ ] **Step 4.4: Run the full test suite to confirm models import clean**

Run: `cd backend && pytest 2>&1 | tail -10`
Expected: no new failures. (The test DB doesn't have the new tables yet — that's Task 5.)

- [ ] **Step 4.5: Commit**

```bash
git add backend/app/models/pos_transaction.py backend/app/models/__init__.py
git commit -m "feat(models): PosTransaction/PosTransactionLine/TseSigningLog"
```

---

## Task 5: Apply fiscal triggers in the test DB

**Files:**
- Modify: `backend/tests/conftest.py`

The existing `setup_db` fixture creates all tables via `Base.metadata.create_all` then installs the audit-event triggers. We add the fiscal triggers alongside.

- [ ] **Step 5.1: Read current `setup_db` layout**

Open `backend/tests/conftest.py`. Find the `setup_db` fixture and the `_TRIGGER_*_SQL` constants near the top. Note the exact pattern used for audit-event triggers.

- [ ] **Step 5.2: Add fiscal trigger SQL constants**

Near the other `_TRIGGER_*_SQL` constants in `conftest.py`, add:

```python
_FISCAL_REJECT_FN_SQL = """
CREATE OR REPLACE FUNCTION fiscal_reject_modification() RETURNS trigger AS $$
BEGIN
    IF current_setting('fiscal.signing', true) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Fiscal rows are immutable (TG_OP=%, table=%)', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""

_FISCAL_TABLES = ("pos_transactions", "pos_transaction_lines", "tse_signing_log")
```

- [ ] **Step 5.3: Apply them in `setup_db`**

In `setup_db`, after the existing audit-trigger executions and before `yield engine`, add:

```python
        await conn.execute(sa.text(_FISCAL_REJECT_FN_SQL))
        for tbl in _FISCAL_TABLES:
            await conn.execute(sa.text(
                f"CREATE TRIGGER {tbl}_reject_update BEFORE UPDATE ON {tbl} "
                f"FOR EACH ROW EXECUTE FUNCTION fiscal_reject_modification()"
            ))
            await conn.execute(sa.text(
                f"CREATE TRIGGER {tbl}_reject_delete BEFORE DELETE ON {tbl} "
                f"FOR EACH ROW EXECUTE FUNCTION fiscal_reject_modification()"
            ))
        # receipt_number_seq is normally created by Alembic; create here for tests
        await conn.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS receipt_number_seq START 1"))
```

Also add cleanup in the teardown section (after `drop_all`):

```python
        await conn.execute(sa.text("DROP SEQUENCE IF EXISTS receipt_number_seq"))
        await conn.execute(sa.text("DROP FUNCTION IF EXISTS fiscal_reject_modification()"))
```

- [ ] **Step 5.4: Run the existing suite — no regressions**

Run: `cd backend && pytest 2>&1 | tail -10`
Expected: same pass count as before Task 4. The new fixtures are applied but no tests yet exercise them.

- [ ] **Step 5.5: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test(conftest): apply fiscal triggers + receipt_number_seq to test DB"
```

---

## Task 6: Canonical `process_data` string builder

The `process_data` string is what fiskaly hashes into the TSE signature. Its format is prescribed by DSFinV-K (`Kassenbeleg-V1`):
`Beleg^<total_gross formatted>_<VAT rate>^<cash_breakdown>:<card_breakdown>`
plus specific VAT rate ordering and Euro formatting. We build it from a `PosTransaction` + its `lines` and keep it pure for golden-testing.

**Files:**
- Create: `backend/app/fiscal/__init__.py`
- Create: `backend/app/fiscal/process_data.py`
- Test: `backend/tests/test_process_data.py`

- [ ] **Step 6.1: Create the package marker**

Create empty `backend/app/fiscal/__init__.py`.

- [ ] **Step 6.2: Write the failing test**

Create `backend/tests/test_process_data.py`:

```python
from decimal import Decimal
from app.fiscal.process_data import build_process_data


def test_build_cash_only_single_vat():
    # Single line, 1.13 EUR at 7% VAT, paid in cash.
    out = build_process_data(
        vat_breakdown={"7": {"net": Decimal("1.06"), "vat": Decimal("0.07"), "gross": Decimal("1.13")}},
        payment_breakdown={"cash": Decimal("1.13")},
    )
    # DSFinV-K V1 canonical layout (see spec §1):
    #   "Beleg^<A>_<B>_<C>_<D>_<E>^<payments>"
    # Where A=general-reduced=7%, B=general=19%, C=half=10.7%, D=export=0%,
    # E=special=5.5% (always five slots, zeros when unused).
    assert out == "Beleg^1.13_0.00_0.00_0.00_0.00^1.13:Bar"


def test_build_mixed_vat_and_payment():
    out = build_process_data(
        vat_breakdown={
            "7":  {"net": Decimal("3.73"), "vat": Decimal("0.27"), "gross": Decimal("4.00")},
            "19": {"net": Decimal("7.57"), "vat": Decimal("1.44"), "gross": Decimal("9.01")},
        },
        payment_breakdown={"cash": Decimal("5.00"), "girocard": Decimal("8.01")},
    )
    assert out == "Beleg^4.00_9.01_0.00_0.00_0.00^5.00:Bar|8.01:Unbar"


def test_rejects_unknown_vat_rate():
    import pytest as _pytest
    with _pytest.raises(ValueError, match="VAT rate"):
        build_process_data(
            vat_breakdown={"13": {"net": Decimal("1"), "vat": Decimal("0.13"), "gross": Decimal("1.13")}},
            payment_breakdown={"cash": Decimal("1.13")},
        )
```

- [ ] **Step 6.3: Run, confirm fail**

Run: `cd backend && pytest tests/test_process_data.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 6.4: Implement `build_process_data`**

Create `backend/app/fiscal/process_data.py`:

```python
"""Canonical DSFinV-K process_data builder (Kassenbeleg-V1).

The output of this function is what fiskaly hashes into the TSE signature.
The layout is prescribed by DSFinV-K and MUST be byte-identical across
runs for the same logical transaction — hence the golden tests.

Reference: BMF DSFinV-K, section "Kassenbeleg-V1", field `processData`.
"""
from decimal import Decimal
from typing import Mapping

# DSFinV-K mandates five VAT slots in this exact order:
#   A: 7%   (reduced "ermäßigt")
#   B: 19%  (standard "regulär")
#   C: 10.7% (pauschal Landwirte)
#   D: 0%   (nicht steuerbar)
#   E: 5.5% (pauschal)
_VAT_SLOTS = ("7", "19", "10.7", "0", "5.5")

# fiskaly payment-type identifiers per DSFinV-K.
_PAYMENT_LABELS = {
    "cash": "Bar",
    "girocard": "Unbar",
    "card": "Unbar",
    "credit": "Unbar",
}


def _fmt(d: Decimal) -> str:
    # Two decimals, dot separator, no thousands. Decimal quantize for stability.
    return f"{d.quantize(Decimal('0.01')):.2f}"


def build_process_data(
    *,
    vat_breakdown: Mapping[str, Mapping[str, Decimal]],
    payment_breakdown: Mapping[str, Decimal],
) -> str:
    """Return the canonical `process_data` string for a Kassenbeleg-V1 TSE sign.

    `vat_breakdown`: dict keyed by VAT rate percent (as string, no "%"), with
        per-slot `{net, vat, gross}` Decimals. Unknown slots → ValueError.
    `payment_breakdown`: dict keyed by internal method name, Decimal amounts.
    """
    for rate in vat_breakdown:
        if rate not in _VAT_SLOTS:
            raise ValueError(f"unknown VAT rate {rate!r}; expected one of {_VAT_SLOTS}")

    vat_section = "_".join(
        _fmt(vat_breakdown[slot]["gross"]) if slot in vat_breakdown else "0.00"
        for slot in _VAT_SLOTS
    )

    pay_parts = []
    for method, amount in payment_breakdown.items():
        if method not in _PAYMENT_LABELS:
            raise ValueError(f"unknown payment method {method!r}")
        pay_parts.append(f"{_fmt(amount)}:{_PAYMENT_LABELS[method]}")
    pay_section = "|".join(pay_parts)

    return f"Beleg^{vat_section}^{pay_section}"
```

- [ ] **Step 6.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_process_data.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 6.6: Commit**

```bash
git add backend/app/fiscal/__init__.py backend/app/fiscal/process_data.py backend/tests/test_process_data.py
git commit -m "feat(fiscal): canonical process_data builder (Kassenbeleg-V1)"
```

**Note for Plan D:** this function is reused verbatim when building DSFinV-K's `bonkopf.csv`.

---

## Task 7: Exception hierarchy

**Files:**
- Create: `backend/app/fiscal/errors.py`

- [ ] **Step 7.1: Create the module**

Create `backend/app/fiscal/errors.py`:

```python
"""Exception hierarchy for fiskaly/TSE interactions."""


class FiscalError(Exception):
    """Base for all fiscal subsystem errors."""
    error_code: str = "FISCAL_UNKNOWN"


class FiscalAuthError(FiscalError):
    """OAuth2 token acquisition failed — credentials likely misconfigured."""
    error_code = "FISCAL_AUTH"


class FiscalNetworkError(FiscalError):
    """fiskaly unreachable or timed out after retries."""
    error_code = "FISCAL_NETWORK"


class FiscalServerError(FiscalError):
    """fiskaly returned 5xx after retries."""
    error_code = "FISCAL_SERVER"


class FiscalBadRequestError(FiscalError):
    """fiskaly returned 4xx — programmer error or bad config."""
    error_code = "FISCAL_BAD_REQUEST"


class FiscalNotConfiguredError(FiscalError):
    """FISKALY_* env vars are missing; no network call will be attempted."""
    error_code = "FISCAL_NOT_CONFIGURED"
```

- [ ] **Step 7.2: Commit**

```bash
git add backend/app/fiscal/errors.py
git commit -m "feat(fiscal): error hierarchy"
```

---

## Task 8: FiscalClient — OAuth2 token-cached httpx wrapper

**Files:**
- Create: `backend/app/fiscal/client.py`
- Create: `backend/tests/fiscal_helpers.py`
- Test: `backend/tests/test_fiscal_client.py`

fiskaly's REST API uses OAuth2 client-credentials with short-lived access tokens. `FiscalClient` caches the token, refreshes on 401, and retries transient failures with exponential backoff.

> **API-shape note:** The exact fiskaly paths below reflect the public kassensichv-middleware v2 shape. Before merging, the implementer should re-verify endpoints at `https://developer.fiskaly.com/reference/kassensichv-middleware` and adjust if fiskaly has changed a field name. The tests mock fiskaly entirely so path drift doesn't break CI — but does break real sandbox testing.

- [ ] **Step 8.1: Helper module for test fixtures**

Create `backend/tests/fiscal_helpers.py`:

```python
"""Shared fiskaly respx fixtures."""
import httpx
import respx


def mock_auth_ok(respx_mock: respx.MockRouter, base_url: str = "https://mock-fiskaly.test") -> None:
    respx_mock.post(f"{base_url}/api/v2/auth").respond(
        json={"access_token": "token-abc", "access_token_expires_in": 300, "refresh_token": "rt"}
    )


def mock_tx_start_ok(
    respx_mock: respx.MockRouter,
    tss_id: str, tx_id: str, base_url: str = "https://mock-fiskaly.test",
) -> None:
    respx_mock.put(f"{base_url}/api/v2/tss/{tss_id}/tx/{tx_id}").respond(
        json={
            "_id": tx_id,
            "state": "ACTIVE",
            "number": 1,
            "latest_revision": 1,
            "time_start": 1_745_000_000,
        }
    )


def mock_tx_finish_ok(
    respx_mock: respx.MockRouter,
    tss_id: str, tx_id: str, base_url: str = "https://mock-fiskaly.test",
    signature: str = "MEUCIQD-fake-signature",
    signature_counter: int = 4728,
    tss_serial: str = "serial-abc123",
    time_start: int = 1_745_000_000, time_end: int = 1_745_000_030,
) -> None:
    respx_mock.put(
        url__regex=rf"{base_url}/api/v2/tss/{tss_id}/tx/{tx_id}\?last_revision=.+"
    ).respond(
        json={
            "_id": tx_id,
            "state": "FINISHED",
            "signature": {"value": signature, "counter": signature_counter},
            "tss_serial_number": tss_serial,
            "time_start": time_start,
            "time_end": time_end,
        }
    )
```

- [ ] **Step 8.2: Write the failing test**

Create `backend/tests/test_fiscal_client.py`:

```python
import httpx
import pytest
import respx

from app.fiscal.client import FiscalClient
from app.fiscal.errors import FiscalAuthError, FiscalNotConfiguredError, FiscalServerError
from tests.fiscal_helpers import mock_auth_ok, mock_tx_start_ok


BASE = "https://mock-fiskaly.test"


def _client(**overrides) -> FiscalClient:
    defaults = dict(
        api_key="key-123", api_secret="secret-456", tss_id="tss-abc",
        base_url=BASE,
    )
    defaults.update(overrides)
    return FiscalClient(**defaults)


@pytest.mark.asyncio
@respx.mock
async def test_authenticate_caches_token():
    mock_auth_ok(respx.mock, BASE)
    c = _client()
    t1 = await c._get_token()
    t2 = await c._get_token()
    assert t1 == t2 == "token-abc"
    # Only one auth call despite two _get_token invocations.
    assert respx.mock.calls.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_authenticate_failure_raises():
    respx.mock.post(f"{BASE}/api/v2/auth").respond(401, json={"error": "bad creds"})
    with pytest.raises(FiscalAuthError):
        await _client()._get_token()


@pytest.mark.asyncio
async def test_not_configured_raises():
    c = _client(api_key="", api_secret="", tss_id="")
    with pytest.raises(FiscalNotConfiguredError):
        await c._get_token()


@pytest.mark.asyncio
@respx.mock
async def test_retries_on_5xx_then_succeeds():
    mock_auth_ok(respx.mock, BASE)
    route = respx.mock.put(f"{BASE}/api/v2/tss/tss-abc/tx/tx-1")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(503),
        httpx.Response(200, json={"_id": "tx-1", "state": "ACTIVE"}),
    ]
    c = _client()
    result = await c.put(f"/api/v2/tss/tss-abc/tx/tx-1", json={"state": "ACTIVE"})
    assert result["state"] == "ACTIVE"
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_retries_exhausted_raises_server_error():
    mock_auth_ok(respx.mock, BASE)
    respx.mock.put(f"{BASE}/api/v2/tss/tss-abc/tx/tx-1").respond(503)
    c = _client()
    with pytest.raises(FiscalServerError):
        await c.put("/api/v2/tss/tss-abc/tx/tx-1", json={})
```

- [ ] **Step 8.3: Run, confirm fail**

Run: `cd backend && pytest tests/test_fiscal_client.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 8.4: Implement `FiscalClient`**

Create `backend/app/fiscal/client.py`:

```python
"""Low-level fiskaly REST client with OAuth2 token caching and retry."""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx
from tenacity import (
    retry, retry_if_exception_type, stop_after_attempt, wait_exponential,
    RetryError,
)

from app.fiscal.errors import (
    FiscalAuthError, FiscalBadRequestError, FiscalNetworkError,
    FiscalNotConfiguredError, FiscalServerError,
)


class FiscalClient:
    def __init__(
        self, *,
        api_key: str, api_secret: str, tss_id: str, base_url: str,
        http: Optional[httpx.AsyncClient] = None,
        timeout_s: float = 10.0,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.tss_id = tss_id
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.AsyncClient(timeout=timeout_s)
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def _ensure_configured(self) -> None:
        if not (self.api_key and self.api_secret and self.tss_id):
            raise FiscalNotConfiguredError("fiskaly env vars missing")

    async def _get_token(self) -> str:
        self._ensure_configured()
        now = time.time()
        if self._token and now < self._token_expires_at - 30:
            return self._token
        r = await self._http.post(
            f"{self.base_url}/api/v2/auth",
            json={"api_key": self.api_key, "api_secret": self.api_secret},
        )
        if r.status_code >= 400:
            raise FiscalAuthError(f"auth failed: {r.status_code} {r.text}")
        data = r.json()
        self._token = data["access_token"]
        self._token_expires_at = now + int(data.get("access_token_expires_in", 300))
        return self._token

    async def _request(self, method: str, path: str, **kw) -> dict[str, Any]:
        @retry(
            retry=retry_if_exception_type((httpx.TransportError, _Retryable5xx)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=20),
            reraise=True,
        )
        async def _do() -> dict[str, Any]:
            token = await self._get_token()
            headers = {**kw.pop("headers", {}), "Authorization": f"Bearer {token}"}
            r = await self._http.request(
                method, f"{self.base_url}{path}", headers=headers, **kw,
            )
            if r.status_code == 401:
                # Force re-auth on next attempt
                self._token = None
                raise _Retryable5xx(f"401 re-auth {r.text}")
            if 500 <= r.status_code < 600:
                raise _Retryable5xx(f"{r.status_code} {r.text}")
            if 400 <= r.status_code < 500:
                raise FiscalBadRequestError(f"{r.status_code} {r.text}")
            return r.json() if r.content else {}

        try:
            return await _do()
        except RetryError as e:
            inner = e.last_attempt.exception() if e.last_attempt else None
            if isinstance(inner, _Retryable5xx):
                raise FiscalServerError(str(inner)) from inner
            if isinstance(inner, httpx.TransportError):
                raise FiscalNetworkError(str(inner)) from inner
            raise

    async def put(self, path: str, *, json: dict) -> dict[str, Any]:
        return await self._request("PUT", path, json=json)

    async def post(self, path: str, *, json: dict) -> dict[str, Any]:
        return await self._request("POST", path, json=json)


class _Retryable5xx(Exception):
    """Sentinel to drive tenacity retry on 5xx/401."""
    pass
```

- [ ] **Step 8.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_fiscal_client.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 8.6: Commit**

```bash
git add backend/app/fiscal/client.py backend/tests/fiscal_helpers.py backend/tests/test_fiscal_client.py
git commit -m "feat(fiscal): FiscalClient with OAuth2 token cache + retry"
```

---

## Task 9: FiscalService.start_transaction

**Files:**
- Create: `backend/app/fiscal/service.py`
- Test: `backend/tests/test_fiscal_service.py`

`FiscalService` is the business-facing wrapper. `start_transaction(client_id)` reserves a TSE signature counter even if the sale later fails (legally required: failed sales are still signed as cancelled).

- [ ] **Step 9.1: Write the failing test**

Create `backend/tests/test_fiscal_service.py`:

```python
import uuid
import httpx
import pytest
import respx

from app.fiscal.service import FiscalService, StartResult
from app.fiscal.client import FiscalClient
from tests.fiscal_helpers import mock_auth_ok, mock_tx_start_ok


BASE = "https://mock-fiskaly.test"


def _svc() -> FiscalService:
    client = FiscalClient(
        api_key="k", api_secret="s", tss_id="tss-abc", base_url=BASE,
        http=httpx.AsyncClient(timeout=5),
    )
    return FiscalService(client=client)


@pytest.mark.asyncio
@respx.mock
async def test_start_transaction_returns_fiskaly_tx_id():
    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)

    result = await _svc().start_transaction(client_id=client_id)

    assert isinstance(result, StartResult)
    assert result.tx_id == client_id
    assert result.state == "ACTIVE"
```

- [ ] **Step 9.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_fiscal_service.py::test_start_transaction_returns_fiskaly_tx_id -v`
Expected: FAIL — module does not exist.

- [ ] **Step 9.3: Implement `start_transaction`**

Create `backend/app/fiscal/service.py`:

```python
"""High-level fiskaly interactions: start/finish/retry."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.fiscal.client import FiscalClient


@dataclass
class StartResult:
    tx_id: uuid.UUID
    state: str
    latest_revision: int


@dataclass
class FinishResult:
    signature: str
    signature_counter: int
    tss_serial: str
    time_start: datetime
    time_end: datetime
    process_type: str


class FiscalService:
    def __init__(self, client: FiscalClient):
        self.client = client

    async def start_transaction(self, *, client_id: uuid.UUID) -> StartResult:
        """Open a TSE transaction. The `client_id` is also the tx id on
        fiskaly's side — using the same UUID for both gives idempotency:
        retrying with the same id is safe.
        """
        body = {"state": "ACTIVE", "client_id": str(client_id)}
        resp = await self.client.put(
            f"/api/v2/tss/{self.client.tss_id}/tx/{client_id}",
            json=body,
        )
        return StartResult(
            tx_id=client_id,
            state=resp.get("state", "ACTIVE"),
            latest_revision=int(resp.get("latest_revision", 1)),
        )
```

- [ ] **Step 9.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_fiscal_service.py -v`
Expected: PASS.

- [ ] **Step 9.5: Commit**

```bash
git add backend/app/fiscal/service.py backend/tests/test_fiscal_service.py
git commit -m "feat(fiscal): FiscalService.start_transaction"
```

---

## Task 10: FiscalService.finish_transaction

Finish binds the `process_data` string into the TSE signature.

**Files:**
- Modify: `backend/app/fiscal/service.py`
- Modify: `backend/tests/test_fiscal_service.py`

- [ ] **Step 10.1: Write the failing test**

Append to `backend/tests/test_fiscal_service.py`:

```python
from tests.fiscal_helpers import mock_tx_finish_ok
from datetime import datetime, timezone


@pytest.mark.asyncio
@respx.mock
async def test_finish_transaction_returns_signature():
    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)
    mock_tx_finish_ok(
        respx.mock, "tss-abc", str(client_id), BASE,
        signature="MEUCIQD-sig", signature_counter=4728,
        tss_serial="serial-abc123",
        time_start=1_745_000_000, time_end=1_745_000_030,
    )

    svc = _svc()
    start = await svc.start_transaction(client_id=client_id)
    finish = await svc.finish_transaction(
        tx_id=client_id,
        latest_revision=start.latest_revision,
        process_data="Beleg^1.13_0.00_0.00_0.00_0.00^1.13:Bar",
        process_type="Kassenbeleg-V1",
    )

    assert finish.signature == "MEUCIQD-sig"
    assert finish.signature_counter == 4728
    assert finish.tss_serial == "serial-abc123"
    assert finish.time_start == datetime(2025, 4, 18, 16, 53, 20, tzinfo=timezone.utc)
    assert finish.time_end == datetime(2025, 4, 18, 16, 53, 50, tzinfo=timezone.utc)
    assert finish.process_type == "Kassenbeleg-V1"
```

- [ ] **Step 10.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_fiscal_service.py::test_finish_transaction_returns_signature -v`
Expected: FAIL — `finish_transaction` not defined.

- [ ] **Step 10.3: Implement `finish_transaction`**

Append to the `FiscalService` class in `backend/app/fiscal/service.py`:

```python
    async def finish_transaction(
        self, *,
        tx_id: uuid.UUID,
        latest_revision: int,
        process_data: str,
        process_type: str = "Kassenbeleg-V1",
    ) -> FinishResult:
        """Sign and finalize the TSE transaction. Returns the signature
        fields to persist on `pos_transactions`.
        """
        body = {
            "state": "FINISHED",
            "client_id": str(tx_id),
            "schema": {
                "standard_v1": {
                    "receipt": {
                        "receipt_type": "RECEIPT",
                        "amounts_per_vat_rate": [],  # filled by Plan D with per-rate rows
                        "amounts_per_payment_type": [],  # filled by Plan C
                    },
                },
            },
            "process_type": process_type,
            "process_data": _b64(process_data),
        }
        resp = await self.client.put(
            f"/api/v2/tss/{self.client.tss_id}/tx/{tx_id}?last_revision={latest_revision}",
            json=body,
        )
        sig = resp.get("signature") or {}
        return FinishResult(
            signature=sig.get("value", ""),
            signature_counter=int(sig.get("counter", 0)),
            tss_serial=resp.get("tss_serial_number", ""),
            time_start=_utc_from_epoch(resp.get("time_start")),
            time_end=_utc_from_epoch(resp.get("time_end")),
            process_type=process_type,
        )
```

Then, below the class, add the two helpers at module scope:

```python
import base64


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def _utc_from_epoch(v: Any) -> datetime:
    if v is None:
        raise ValueError("missing timestamp in fiskaly response")
    return datetime.fromtimestamp(int(v), tz=timezone.utc)
```

**Note on the empty schema arrays:** fiskaly's `amounts_per_vat_rate` and `amounts_per_payment_type` are consumed by DSFinV-K export. Plan D fills them from `vat_breakdown` / `payment_breakdown`. For day-one of this plan, an empty list still produces a valid signature — fiskaly signs whatever we send.

- [ ] **Step 10.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_fiscal_service.py -v`
Expected: PASS (both tests).

- [ ] **Step 10.5: Commit**

```bash
git add backend/app/fiscal/service.py backend/tests/test_fiscal_service.py
git commit -m "feat(fiscal): FiscalService.finish_transaction returns TSE signature"
```

---

## Task 11: tse_signing_log — observe every call

Every fiskaly interaction — successful or failed — writes one row to `tse_signing_log`. This is the post-mortem trail when a shift has a discrepancy.

**Files:**
- Modify: `backend/app/fiscal/service.py`
- Modify: `backend/tests/test_fiscal_service.py`

- [ ] **Step 11.1: Write the failing test**

Append to `backend/tests/test_fiscal_service.py`:

```python
from sqlalchemy import select
from app.models import TseSigningLog
from app.fiscal.errors import FiscalServerError


@pytest.mark.asyncio
@respx.mock
async def test_signing_log_records_success(db, authed_client):
    # authed_client is unused; we just need the session factory.
    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)

    svc = _svc_with_db(db)  # helper defined below
    await svc.start_transaction(client_id=client_id)

    rows = (await db.execute(select(TseSigningLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].operation == "start_transaction"
    assert rows[0].succeeded is True
    assert rows[0].error_code is None


@pytest.mark.asyncio
@respx.mock
async def test_signing_log_records_failure(db):
    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    respx.mock.put(f"{BASE}/api/v2/tss/tss-abc/tx/{client_id}").respond(503)

    svc = _svc_with_db(db)
    with pytest.raises(FiscalServerError):
        await svc.start_transaction(client_id=client_id)

    rows = (await db.execute(select(TseSigningLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].succeeded is False
    assert rows[0].error_code == "FISCAL_SERVER"
```

Add at the top of the test file (next to `_svc`):

```python
def _svc_with_db(db):
    client = FiscalClient(
        api_key="k", api_secret="s", tss_id="tss-abc", base_url=BASE,
        http=httpx.AsyncClient(timeout=5),
    )
    return FiscalService(client=client, db=db)
```

- [ ] **Step 11.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_fiscal_service.py -v`
Expected: the two new tests FAIL — `FiscalService` has no `db` kwarg and doesn't write to `tse_signing_log`.

- [ ] **Step 11.3: Extend `FiscalService`**

In `backend/app/fiscal/service.py`:

```python
# imports at top
import time as _time
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import TseSigningLog
from app.fiscal.errors import FiscalError
```

Update `__init__`:

```python
    def __init__(self, client: FiscalClient, db: Optional[AsyncSession] = None):
        self.client = client
        self.db = db
```

Add a helper method:

```python
    async def _log(
        self, *,
        operation: str,
        pos_transaction_id: Optional[uuid.UUID],
        started_at: float,
        succeeded: bool,
        error: Optional[FiscalError] = None,
    ) -> None:
        if self.db is None:
            return
        self.db.add(TseSigningLog(
            pos_transaction_id=pos_transaction_id,
            operation=operation,
            attempted_at=datetime.now(tz=timezone.utc),
            succeeded=succeeded,
            error_code=error.error_code if error else None,
            error_message=str(error) if error else None,
            duration_ms=int((_time.time() - started_at) * 1000),
        ))
        # Do NOT commit here — the caller owns the transaction boundary.
        # Flush so row is visible to read-after-write in same session.
        await self.db.flush()
```

Wrap `start_transaction` and `finish_transaction` with logging:

```python
    async def start_transaction(self, *, client_id: uuid.UUID) -> StartResult:
        started = _time.time()
        try:
            body = {"state": "ACTIVE", "client_id": str(client_id)}
            resp = await self.client.put(
                f"/api/v2/tss/{self.client.tss_id}/tx/{client_id}",
                json=body,
            )
            result = StartResult(
                tx_id=client_id,
                state=resp.get("state", "ACTIVE"),
                latest_revision=int(resp.get("latest_revision", 1)),
            )
        except FiscalError as e:
            await self._log(
                operation="start_transaction", pos_transaction_id=None,
                started_at=started, succeeded=False, error=e,
            )
            raise
        await self._log(
            operation="start_transaction", pos_transaction_id=None,
            started_at=started, succeeded=True,
        )
        return result
```

Do the same for `finish_transaction`, passing `pos_transaction_id=tx_id` (the client_id is the pos_transaction_id in this codebase — they're the same UUID).

- [ ] **Step 11.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_fiscal_service.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 11.5: Commit**

```bash
git add backend/app/fiscal/service.py backend/tests/test_fiscal_service.py
git commit -m "feat(fiscal): log every TSE call to tse_signing_log"
```

---

## Task 12: PosTransactionService.finalize_sale

The single backend entry point that turns an `Order` into a signed `PosTransaction`. This is what Plan C (payment) and Plan D (checkout UI) will call.

**Files:**
- Create: `backend/app/services/pos_transaction.py`
- Test: `backend/tests/test_pos_transaction_service.py`

- [ ] **Step 12.1: Write the failing test**

Create `backend/tests/test_pos_transaction_service.py`:

```python
import uuid
from decimal import Decimal

import httpx
import pytest
import respx
from sqlalchemy import select

from app.fiscal.client import FiscalClient
from app.fiscal.service import FiscalService
from app.services.pos_transaction import PosTransactionService
from app.services.order import create_order
from app.models import (
    PosTransaction, PosTransactionLine, Product, ProductVariant,
    InventoryItem, InventoryLevel, Location, TaxRate, User,
)
from app.services.password import hash_pin
from tests.fiscal_helpers import mock_auth_ok, mock_tx_start_ok, mock_tx_finish_ok


BASE = "https://mock-fiskaly.test"


async def _setup_fixed_price_order(db) -> int:
    """Returns the created Order id."""
    loc = Location(name="Store"); db.add(loc)
    tax = TaxRate(name="VAT 7%", rate=Decimal("0.07"), is_default=True)
    db.add(tax)
    p = Product(title="Milk", handle="milk"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="1L", price=Decimal("1.29"),
        pricing_type="fixed",
    )
    db.add(v); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    db.add(InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=10))
    await db.commit()
    order = await create_order(
        db, source="pos",
        line_items_data=[{"variant_id": v.id, "quantity": 1}],
    )
    return order.id


async def _cashier(db) -> User:
    u = User(email=None, password_hash=None, pin_hash=hash_pin("1234"),
             full_name="Anna M.", role="cashier")
    db.add(u); await db.commit(); await db.refresh(u)
    return u


def _svc(db) -> PosTransactionService:
    client = FiscalClient(
        api_key="k", api_secret="s", tss_id="tss-abc", base_url=BASE,
        http=httpx.AsyncClient(timeout=5),
    )
    return PosTransactionService(db=db, fiscal=FiscalService(client=client, db=db))


@pytest.mark.asyncio
@respx.mock
async def test_finalize_sale_writes_signed_pos_transaction(db):
    order_id = await _setup_fixed_price_order(db)
    cashier = await _cashier(db)

    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)
    mock_tx_finish_ok(
        respx.mock, "tss-abc", str(client_id), BASE,
        signature="SIG", signature_counter=100, tss_serial="SER",
        time_start=1_745_000_000, time_end=1_745_000_010,
    )

    tx = await _svc(db).finalize_sale(
        client_id=client_id,
        order_id=order_id,
        cashier_user_id=cashier.id,
        payment_breakdown={"cash": Decimal("1.29")},
    )

    assert tx.tse_pending is False
    assert tx.tse_signature == "SIG"
    assert tx.tse_signature_counter == 100
    assert tx.tse_serial == "SER"
    assert tx.receipt_number >= 1
    assert tx.total_gross == Decimal("1.29")  # (will equal gross after VAT calc)
    lines = (await db.execute(
        select(PosTransactionLine).where(PosTransactionLine.pos_transaction_id == tx.id)
    )).scalars().all()
    assert len(lines) == 1
    assert lines[0].title == "1L"
    assert lines[0].quantity == Decimal("1.000")


@pytest.mark.asyncio
@respx.mock
async def test_finalize_sale_marks_tse_pending_on_fiskaly_failure(db):
    order_id = await _setup_fixed_price_order(db)
    cashier = await _cashier(db)

    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    # start ok, finish fails with 503
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)
    respx.mock.put(
        url__regex=rf"{BASE}/api/v2/tss/tss-abc/tx/{client_id}\?last_revision=.+"
    ).respond(503)

    tx = await _svc(db).finalize_sale(
        client_id=client_id,
        order_id=order_id,
        cashier_user_id=cashier.id,
        payment_breakdown={"cash": Decimal("1.29")},
    )

    assert tx.tse_pending is True
    assert tx.tse_signature is None
    assert tx.receipt_number >= 1  # number still reserved — gap-free requires it
```

- [ ] **Step 12.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_pos_transaction_service.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 12.3: Implement `PosTransactionService`**

Create `backend/app/services/pos_transaction.py`:

```python
"""Bind an Order + payment_breakdown into a TSE-signed PosTransaction."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.fiscal.errors import FiscalError
from app.fiscal.process_data import build_process_data
from app.fiscal.service import FiscalService
from app.models import (
    LineItem, Order, PosTransaction, PosTransactionLine, TaxRate,
)


class PosTransactionService:
    def __init__(self, *, db: AsyncSession, fiscal: FiscalService):
        self.db = db
        self.fiscal = fiscal

    async def finalize_sale(
        self, *,
        client_id: uuid.UUID,
        order_id: int,
        cashier_user_id: int,
        payment_breakdown: Mapping[str, Decimal],
        voids_transaction_id: uuid.UUID | None = None,
    ) -> PosTransaction:
        """The single TSE-signed sale entry point.

        Idempotency: if a PosTransaction with the same `client_id` already
        exists, it is returned unchanged. Retry-safe.
        """
        existing = (await self.db.execute(
            select(PosTransaction).where(PosTransaction.client_id == client_id)
        )).scalar_one_or_none()
        if existing:
            return existing

        order = (await self.db.execute(
            select(Order).where(Order.id == order_id)
        )).scalar_one()
        line_items = (await self.db.execute(
            select(LineItem).where(LineItem.order_id == order_id)
        )).scalars().all()

        # Derive VAT breakdown from the default TaxRate. Plan D will extend
        # this to multi-rate. Day-1 German grocery: either 7% or 19%, and
        # tests use a single default rate.
        vat_breakdown, total_net, total_gross = await self._build_vat_breakdown(line_items)

        # Reserve a receipt number (gap-free). Inside the same DB tx as the
        # PosTransaction insert, so fiskaly-failure rollback would release it.
        receipt_number = (await self.db.execute(
            text("SELECT nextval('receipt_number_seq')")
        )).scalar_one()

        started_at = datetime.now(tz=timezone.utc)
        tx = PosTransaction(
            id=client_id,
            client_id=client_id,
            cashier_user_id=cashier_user_id,
            started_at=started_at,
            total_gross=total_gross,
            total_net=total_net,
            vat_breakdown={k: {kk: str(vv) for kk, vv in v.items()} for k, v in vat_breakdown.items()},
            payment_breakdown={k: str(v) for k, v in payment_breakdown.items()},
            receipt_number=receipt_number,
            linked_order_id=order_id,
            voids_transaction_id=voids_transaction_id,
            tse_pending=True,  # optimistic; flipped False after finish
        )
        self.db.add(tx)

        for li in line_items:
            line = _line_from_order_item(li, tx.id)
            self.db.add(line)
        await self.db.flush()

        # fiskaly roundtrip
        process_data = build_process_data(
            vat_breakdown=vat_breakdown,
            payment_breakdown=dict(payment_breakdown),
        )
        try:
            start = await self.fiscal.start_transaction(client_id=client_id)
            finish = await self.fiscal.finish_transaction(
                tx_id=client_id,
                latest_revision=start.latest_revision,
                process_data=process_data,
            )
        except FiscalError:
            # Sale stays committed with tse_pending=True. Background retry job
            # will resume signing. Receipt number already reserved — gap-free.
            await self.db.commit()
            await self.db.refresh(tx)
            return tx

        # Write back signature via the narrow UPDATE path guarded by
        # fiscal.signing=on — the only permitted mutation of a fiscal row.
        await self.db.execute(text("SET LOCAL fiscal.signing = 'on'"))
        tx.tse_signature = finish.signature
        tx.tse_signature_counter = finish.signature_counter
        tx.tse_serial = finish.tss_serial
        tx.tse_timestamp_start = finish.time_start
        tx.tse_timestamp_finish = finish.time_end
        tx.tse_process_type = finish.process_type
        tx.tse_process_data = process_data
        tx.finished_at = datetime.now(tz=timezone.utc)
        tx.tse_pending = False
        await self.db.commit()
        await self.db.refresh(tx)
        return tx

    async def _build_vat_breakdown(
        self, line_items: list[LineItem],
    ) -> tuple[dict[str, dict[str, Decimal]], Decimal, Decimal]:
        """Aggregate line_items into {rate: {net, vat, gross}}.

        Day-1 simplification: use the default TaxRate for every line. Plan D
        adds per-variant vat_rate and splits into multiple slots.
        """
        default_rate = (await self.db.execute(
            select(TaxRate).where(TaxRate.is_default.is_(True))
        )).scalar_one_or_none()
        rate = default_rate.rate if default_rate else Decimal("0")
        rate_pct = (rate * 100).quantize(Decimal("0.01"))
        slot = _rate_to_slot(rate_pct)

        total_gross = sum((_gross_for_line(li) for li in line_items), Decimal("0"))
        total_net = (total_gross / (1 + rate)).quantize(Decimal("0.01")) if rate else total_gross
        total_vat = (total_gross - total_net).quantize(Decimal("0.01"))

        return (
            {slot: {"net": total_net, "vat": total_vat, "gross": total_gross}},
            total_net,
            total_gross,
        )


_VAT_SLOT_BY_PCT = {
    Decimal("7.00"): "7",
    Decimal("19.00"): "19",
    Decimal("10.70"): "10.7",
    Decimal("0.00"): "0",
    Decimal("5.50"): "5.5",
}


def _rate_to_slot(rate_pct: Decimal) -> str:
    if rate_pct not in _VAT_SLOT_BY_PCT:
        raise ValueError(f"no DSFinV-K slot for VAT rate {rate_pct}")
    return _VAT_SLOT_BY_PCT[rate_pct]


def _gross_for_line(li: LineItem) -> Decimal:
    # LineItem.price stores unit price for fixed, or computed line total for
    # by_weight (per Plan 1's compute_weighed_line_price). Mirror the
    # convention used by Plan 0 Task 11's `_line_total` helper.
    if li.quantity_kg is not None:
        return li.price
    return (li.price * li.quantity).quantize(Decimal("0.01"))


def _line_from_order_item(li: LineItem, pos_tx_id: uuid.UUID) -> PosTransactionLine:
    if li.quantity_kg is not None:
        line_total_gross = li.price
        qty = Decimal("1")
        unit_price = li.price / li.quantity_kg if li.quantity_kg else li.price
    else:
        unit_price = li.price
        qty = Decimal(li.quantity)
        line_total_gross = (li.price * li.quantity).quantize(Decimal("0.01"))

    # Single-rate day-1: compute against the default rate inside
    # `_build_vat_breakdown` — per-line rate is replayed from there. For
    # the line row we still need a rate+amount: read it back in Plan D.
    # Day-1: leave vat_rate=0, vat_amount=0 (NOT legally complete, but
    # sufficient for signing; fiskaly doesn't enforce per-line rates).
    return PosTransactionLine(
        pos_transaction_id=pos_tx_id,
        sku=None,  # LineItem doesn't carry sku snapshot in current schema
        title=li.title,
        quantity=qty,
        quantity_kg=li.quantity_kg,
        unit_price=unit_price.quantize(Decimal("0.0001")),
        line_total_net=line_total_gross,  # day-1 net==gross placeholder; Plan D splits
        vat_rate=Decimal("0"),
        vat_amount=Decimal("0"),
    )
```

**Known day-1 limitations (called out above, fixed in Plan D):**

- Per-line `vat_rate` + `vat_amount` are placeholder zeros; only the transaction-level breakdown is correct. Plan D adds `ProductVariant.vat_rate` and splits per-line.
- `sku` on `PosTransactionLine` is null — the existing `LineItem` doesn't snapshot it. Plan D adds a snapshot.

These are tracked in Plan D and don't affect TSE signing correctness today.

- [ ] **Step 12.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_pos_transaction_service.py -v`
Expected: both tests PASS.

- [ ] **Step 12.5: Commit**

```bash
git add backend/app/services/pos_transaction.py backend/tests/test_pos_transaction_service.py
git commit -m "feat(pos): PosTransactionService.finalize_sale wraps Order→TSE-signed tx"
```

---

## Task 13: Immutability integration test

Prove the triggers actually reject modifications from application code.

**Files:**
- Test: `backend/tests/test_fiscal_immutability.py`

- [ ] **Step 13.1: Write the test**

Create `backend/tests/test_fiscal_immutability.py`:

```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, update
from sqlalchemy.exc import DBAPIError

from app.models import PosTransaction, TseSigningLog, User
from app.services.password import hash_pin


async def _cashier(db):
    u = User(email=None, password_hash=None, pin_hash=hash_pin("1234"),
             full_name="A", role="cashier")
    db.add(u); await db.commit(); await db.refresh(u)
    return u


async def _seed_tx(db) -> uuid.UUID:
    c = await _cashier(db)
    tid = uuid.uuid4()
    db.add(PosTransaction(
        id=tid, client_id=tid, cashier_user_id=c.id,
        started_at=datetime.now(tz=timezone.utc),
        receipt_number=9999,
    ))
    await db.commit()
    return tid


@pytest.mark.asyncio
async def test_update_on_pos_transaction_rejected(db):
    tid = await _seed_tx(db)
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute(
            update(PosTransaction)
            .where(PosTransaction.id == tid)
            .values(total_gross=Decimal("999"))
        )
        await db.commit()


@pytest.mark.asyncio
async def test_delete_on_pos_transaction_rejected(db):
    tid = await _seed_tx(db)
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute(delete(PosTransaction).where(PosTransaction.id == tid))
        await db.commit()


@pytest.mark.asyncio
async def test_delete_on_tse_signing_log_rejected(db):
    tid = await _seed_tx(db)
    db.add(TseSigningLog(
        pos_transaction_id=tid, operation="start_transaction",
        attempted_at=datetime.now(tz=timezone.utc), succeeded=True,
    ))
    await db.commit()
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute(delete(TseSigningLog))
        await db.commit()
```

- [ ] **Step 13.2: Run, confirm pass**

Run: `cd backend && pytest tests/test_fiscal_immutability.py -v`
Expected: all 3 tests PASS (the triggers raise, the ORM surfaces as `DBAPIError`).

- [ ] **Step 13.3: Commit**

```bash
git add backend/tests/test_fiscal_immutability.py
git commit -m "test(fiscal): prove UPDATE/DELETE on fiscal rows is rejected"
```

---

## Task 14: Startup recovery — retry_pending_signatures

A NUC power-cut mid-fiskaly-call leaves a `pos_transaction` with `tse_pending=True`. On next startup, the background job picks them up and resumes signing.

**Files:**
- Modify: `backend/app/fiscal/service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_fiscal_service.py` (append)

- [ ] **Step 14.1: Write the failing test**

Append to `backend/tests/test_fiscal_service.py`:

```python
from app.models import PosTransaction
from datetime import datetime, timezone


@pytest.mark.asyncio
@respx.mock
async def test_retry_pending_signatures_completes_pending_rows(db):
    # Seed a PosTransaction with tse_pending=True and no signature.
    from app.services.password import hash_pin
    from app.models import User
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1"),
             full_name="C", role="cashier")
    db.add(c); await db.commit(); await db.refresh(c)

    tid = uuid.uuid4()
    db.add(PosTransaction(
        id=tid, client_id=tid, cashier_user_id=c.id,
        started_at=datetime.now(tz=timezone.utc),
        tse_process_data="Beleg^1.29_0.00_0.00_0.00_0.00^1.29:Bar",
        receipt_number=1,
        tse_pending=True,
    ))
    await db.commit()

    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(tid), BASE)
    mock_tx_finish_ok(respx.mock, "tss-abc", str(tid), BASE, signature="LATE-SIG", signature_counter=5001)

    svc = _svc_with_db(db)
    n = await svc.retry_pending_signatures()
    assert n == 1

    refreshed = (await db.execute(select(PosTransaction).where(PosTransaction.id == tid))).scalar_one()
    assert refreshed.tse_pending is False
    assert refreshed.tse_signature == "LATE-SIG"
```

- [ ] **Step 14.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_fiscal_service.py::test_retry_pending_signatures_completes_pending_rows -v`
Expected: FAIL — method not defined.

- [ ] **Step 14.3: Implement `retry_pending_signatures`**

Append to `FiscalService` in `backend/app/fiscal/service.py`:

```python
    async def retry_pending_signatures(self) -> int:
        """Re-sign every PosTransaction with tse_pending=True. Returns count
        of rows successfully signed. Caller (startup hook or admin route)
        is responsible for scheduling.
        """
        from app.models import PosTransaction  # local to avoid circular
        if self.db is None:
            raise RuntimeError("retry_pending_signatures requires db session")

        pending = (await self.db.execute(
            select(PosTransaction).where(PosTransaction.tse_pending.is_(True))
        )).scalars().all()

        signed = 0
        for tx in pending:
            if not tx.tse_process_data:
                # Can't resume without the canonical string; skip.
                continue
            try:
                start = await self.start_transaction(client_id=tx.client_id)
                finish = await self.finish_transaction(
                    tx_id=tx.client_id,
                    latest_revision=start.latest_revision,
                    process_data=tx.tse_process_data,
                )
            except FiscalError:
                continue
            await self.db.execute(text("SET LOCAL fiscal.signing = 'on'"))
            tx.tse_signature = finish.signature
            tx.tse_signature_counter = finish.signature_counter
            tx.tse_serial = finish.tss_serial
            tx.tse_timestamp_start = finish.time_start
            tx.tse_timestamp_finish = finish.time_end
            tx.tse_process_type = finish.process_type
            tx.finished_at = datetime.now(tz=timezone.utc)
            tx.tse_pending = False
            await self.db.commit()
            signed += 1
        return signed
```

- [ ] **Step 14.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_fiscal_service.py -v`
Expected: PASS.

- [ ] **Step 14.5: Wire into FastAPI startup**

In `backend/app/main.py`, find the existing lifespan/startup handler (or create one if absent). Add:

```python
from contextlib import asynccontextmanager

import httpx

from app.config import settings
from app.database import async_session
from app.fiscal.client import FiscalClient
from app.fiscal.service import FiscalService


@asynccontextmanager
async def lifespan(app):
    # Startup: try to finish any TSE-pending transactions left by a crash.
    if settings.fiskaly_api_key:
        async with async_session() as db:
            fc = FiscalClient(
                api_key=settings.fiskaly_api_key,
                api_secret=settings.fiskaly_api_secret,
                tss_id=settings.fiskaly_tss_id,
                base_url=settings.fiskaly_base_url,
                http=httpx.AsyncClient(timeout=15),
            )
            try:
                n = await FiscalService(client=fc, db=db).retry_pending_signatures()
                if n:
                    app.logger.info(f"fiscal: re-signed {n} pending transactions on startup")
            except Exception as e:
                app.logger.warning(f"fiscal startup retry failed: {e}")
    yield
    # Shutdown: nothing fiscal-specific yet.
```

Pass `lifespan=lifespan` into the existing `FastAPI(...)` constructor call. If the existing `main.py` already has a lifespan, extend it instead of replacing.

- [ ] **Step 14.6: Run backend suite — confirm no regressions**

Run: `cd backend && pytest 2>&1 | tail -10`
Expected: same pass count as before.

- [ ] **Step 14.7: Commit**

```bash
git add backend/app/fiscal/service.py backend/app/main.py backend/tests/test_fiscal_service.py
git commit -m "feat(fiscal): startup retry of TSE-pending transactions"
```

---

## Self-Review Checklist

1. **Spec §1 `pos_transaction` table** — Task 2 creates it with every column from spec table lines 52–76. ✓
2. **Spec §1 `pos_transaction_line` table** — Task 2 creates it with every column from spec table lines 77–91. ✓
3. **Spec §1 `tse_signing_log` table** — Task 2 creates it with every column from spec table lines 105–117. ✓
4. **Spec §1 `FiscalService` methods** — Task 9 (`start_transaction`), Task 10 (`finish_transaction`), Task 14 (`retry_pending_signatures`). `export_dsfinvk` is Plan D. ✓
5. **Spec §1 append-only via triggers** — Tasks 3 + 5 + 13. Narrow signature-writeback gate via `fiscal.signing=on` session var. ✓
6. **Spec §1 "sale flow" — start before finish, same DB transaction, receipt reserved** — Task 12 encodes this: receipt_number reserved, row inserted with tse_pending=True, fiskaly roundtrip, signature writeback all inside one commit on happy path. ✓
7. **Spec §1 fiskaly outage handling — tse_pending=True, retry job** — Task 12 (pending path) + Task 14 (retry). ✓
8. **Spec §1 Storno — voids_transaction_id self-FK, original never modified** — Task 2 adds the column; triggers (Task 3) prevent modification of the original. Storno *flow* is Plan D. ✓
9. **Spec §1 receipt number allocation — gap-free Postgres sequence** — Task 2 creates `receipt_number_seq`, Task 12 calls `nextval`. ✓
10. **Spec §9 "immutability tests"** — Task 13. ✓
11. **Spec §9 "migration tests — up + down against fresh Postgres"** — Tasks 2 + 3 run up/down/up cycles in-plan. CI-level enforcement is separate. ✓

**Placeholder scan:** no "TBD" / "TODO" / "appropriate" / "similar to task N" in code steps. The only "Plan D" / "Plan C" references are in Notes sections where they justify day-1 simplifications — explicit handoff, not placeholders.

**Type consistency:**
- `client_id: uuid.UUID` consistent across `PosTransaction` model, `FiscalService.start_transaction`, `PosTransactionService.finalize_sale`, `StartResult.tx_id`. ✓
- `receipt_number: BigInteger` / `int` consistent between migration and model. ✓
- `vat_breakdown` / `payment_breakdown`: serialized as JSONB with Decimals stringified at boundary. Consistent across model, service, and `build_process_data` (which takes Decimal-valued dicts, so the service converts Decimal→str when persisting, reconstructs Decimal when retrieving). ✓
- `FiscalError.error_code` consistent across the hierarchy (Task 7) and used uniformly by `_log` (Task 11). ✓
- `PosTransactionService.finalize_sale` signature: `client_id`, `order_id`, `cashier_user_id`, `payment_breakdown`, `voids_transaction_id`. All callers in Plans C and D must match. ✓

**Explicitly day-1-lossy (tracked for Plan D):**

- Per-line `vat_rate` and `vat_amount` placeholder zeros on `PosTransactionLine` (Task 12 `_line_from_order_item` note).
- `sku` snapshot missing on `PosTransactionLine` (Task 12 note).
- `amounts_per_vat_rate` / `amounts_per_payment_type` empty in fiskaly schema body (Task 10 note).
- DSFinV-K export not yet implemented (spec §1.3 — Plan D).
- Storno UI + admin void route (spec §1 — Plan D).

None of these block TSE signing correctness — they are DSFinV-K export completeness concerns picked up in Plan D.

---

**Plan complete.** On to Plan B (Receipt Printing).
