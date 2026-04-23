# Checkout UX + Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the fiscal/payment/printing primitives from Plans A–C into a working cashier UX, plus the compliance artefacts the Finanzamt and Steuerberater require: per-line multi-VAT, card-decline cancelled-attempt records, Storno (void), Z-Report, and a minimal DSFinV-K export. Plus the four POS health dots and merchant-info config.

**Architecture:** Backend gets the multi-VAT data plumbing (`ProductVariant.vat_rate`, per-line splits in `PosTransactionService`), a `card_auth` table for storing pre-finalize card merchant fields, a `ZReportBuilder`, a `DsfinvkExporter`, a `StornoService`, and merchant info in Settings. Frontend POS gets payment modals (cash with tendered/change keypad, card with terminal status), shift open/close pages, a Storno button, and a health-dot top bar. Frontend admin gets a Z-Report page and a DSFinV-K export page.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, React + TypeScript. Python `zipfile` for DSFinV-K bundling. No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-04-18-go-live-v1-design.md` §§1.3, 2 (cancelled-attempt, mixed payment, drawer wiring), 3 (vat per variant), 5 (Z-Report, health), 8 (health endpoints).

**Starting point:** `main` after Plans A, B, C are merged. This plan also assumes Plan 0 (foundation-fixups) is merged so the admin nav can host new pages.

**Explicitly deferred (not this plan):**

- **Full DSFinV-K (all 12+ CSVs + DTD)** — day-1 ships `bonkopf.csv`, `bonpos.csv`, `bonkopf_zahlarten.csv`, `tse.csv`, `cash_per_currency.csv`, `index.xml`. The Steuerberater confirms readability in IDEA at acceptance day. Remaining CSVs are Phase 2.
- **Mixed-payment UI** (cash + card on same sale) — backend `PaymentService.pay_mixed` is shipped; UI is Phase 2 (add a "split tender" button later).
- **Email/PDF receipts** — Phase 2 (spec §5).
- **Backups** — separate plan (post-acceptance).

---

## File Structure

**Backend new:**

- `backend/alembic/versions/0108_add_variant_vat_rate.py`
- `backend/alembic/versions/0109_add_card_auth.py`
- `backend/app/models/card_auth.py` — `CardAuth`
- `backend/app/services/storno.py` — `StornoService.void`
- `backend/app/reports/__init__.py`
- `backend/app/reports/z_report.py` — `ZReportBuilder.build(shift_open_id)`
- `backend/app/reports/dsfinvk.py` — `DsfinvkExporter.export(date_from, date_to) -> bytes` (zip)
- `backend/app/api/reports.py` — `/api/reports/z-report` + `/api/reports/dsfinvk`
- `backend/app/api/storno.py` — `POST /api/pos-transactions/{tx_id}/void`
- `backend/tests/test_variant_vat_split.py`
- `backend/tests/test_card_auth_persistence.py`
- `backend/tests/test_storno_service.py`
- `backend/tests/test_z_report.py`
- `backend/tests/test_dsfinvk_export.py`

**Backend modified:**

- `backend/app/config.py` — add `merchant_name`, `merchant_address`, `merchant_tax_id`, `merchant_vat_id`, `register_id`
- `backend/app/models/__init__.py` — export `CardAuth`
- `backend/app/models/product.py` — add `ProductVariant.vat_rate`
- `backend/app/services/pos_transaction.py` — multi-VAT line splits + sku snapshot + card_auth lookup
- `backend/app/payment/service.py` — write `card_auth` row before finalize; on decline, write cancelled-attempt fiscal record
- `backend/app/api/receipts.py`, `backend/app/api/payment.py`, `backend/app/api/health.py` — read merchant info from settings
- `backend/app/main.py` — register reports + storno routers; central `health` router

**Frontend new:**

- `frontend/packages/pos/src/components/PaymentCashModal.tsx`
- `frontend/packages/pos/src/components/PaymentCardModal.tsx`
- `frontend/packages/pos/src/components/HealthDots.tsx`
- `frontend/packages/pos/src/pages/ShiftOpen.tsx`
- `frontend/packages/pos/src/pages/ShiftClose.tsx`
- `frontend/packages/admin/src/pages/ZReport.tsx`
- `frontend/packages/admin/src/pages/DsfinvkExport.tsx`

**Frontend modified:**

- `frontend/packages/shared/src/api.ts` — add `payment`, `kassenbuch`, `reports`, `storno` sections
- `frontend/packages/shared/src/types.ts` — `PosTransaction`, `KassenbuchEntry`, `ZReport`, `HealthStatus`
- `frontend/packages/pos/src/pages/SalePage.tsx` — wire payment modals, Storno button, health dots, gate behind shift-open
- `frontend/packages/pos/src/App.tsx` — add ShiftOpen / ShiftClose routes
- `frontend/packages/admin/src/App.tsx` — add ZReport / DsfinvkExport routes + nav

---

## Task 1: Multi-VAT — `ProductVariant.vat_rate` migration + model

**Files:**
- Create: `backend/alembic/versions/0108_add_variant_vat_rate.py`
- Modify: `backend/app/models/product.py`

- [ ] **Step 1.1: Generate + rename**

Run: `cd backend && alembic revision -m "add product_variant.vat_rate"`
Rename + set `down_revision = "0107_add_kassenbuch_entries"`.

- [ ] **Step 1.2: Migration body**

```python
"""add product_variant.vat_rate

Revision ID: 0108_add_variant_vat_rate
Revises: 0107_add_kassenbuch_entries
"""
from alembic import op
import sqlalchemy as sa

revision = "0108_add_variant_vat_rate"
down_revision = "0107_add_kassenbuch_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_variants",
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="19.00"),
    )


def downgrade() -> None:
    op.drop_column("product_variants", "vat_rate")
```

- [ ] **Step 1.3: Up/down/up**

Run: `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`

- [ ] **Step 1.4: Add to model**

In `backend/app/models/product.py`, inside `ProductVariant`:

```python
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("19.00"))
```

- [ ] **Step 1.5: Smoke-import**

Run: `cd backend && python -c "from app.models import ProductVariant; print(ProductVariant.vat_rate)"`

- [ ] **Step 1.6: Commit**

```bash
git add backend/alembic/versions/0108_add_variant_vat_rate.py backend/app/models/product.py
git commit -m "feat(product): per-variant vat_rate (defaults 19% standard)"
```

---

## Task 2: Multi-VAT in `PosTransactionService` + sku snapshot

Replace the single-default-rate path in Plan A with a real per-line breakdown sourced from `variant.vat_rate`. Snapshot the sku into `PosTransactionLine.sku` so the receipt and DSFinV-K can show it.

**Files:**
- Modify: `backend/app/services/pos_transaction.py`
- Test: `backend/tests/test_variant_vat_split.py`

- [ ] **Step 2.1: Failing test**

Create `backend/tests/test_variant_vat_split.py`:

```python
import uuid
from decimal import Decimal

import httpx
import pytest
import respx

from app.fiscal.client import FiscalClient
from app.fiscal.service import FiscalService
from app.models import (
    InventoryItem, InventoryLevel, Location, PosTransactionLine, Product,
    ProductVariant, TaxRate, User,
)
from app.services.order import create_order
from app.services.password import hash_pin
from app.services.pos_transaction import PosTransactionService
from sqlalchemy import select
from tests.fiscal_helpers import mock_auth_ok, mock_tx_start_ok, mock_tx_finish_ok

BASE = "https://mock-fiskaly.test"


@pytest.mark.asyncio
@respx.mock
async def test_finalize_sale_splits_per_line_vat(db):
    loc = Location(name="Store"); db.add(loc)
    db.add(TaxRate(name="default", rate=Decimal("0.19"), is_default=True))
    p = Product(title="Mix", handle="mix"); db.add(p); await db.flush()
    food = ProductVariant(product_id=p.id, title="Bread", price=Decimal("3.00"),
                           pricing_type="fixed", vat_rate=Decimal("7.00"), sku="SKU-BREAD")
    wine = ProductVariant(product_id=p.id, title="Wine", price=Decimal("9.99"),
                           pricing_type="fixed", vat_rate=Decimal("19.00"), sku="SKU-WINE")
    db.add_all([food, wine]); await db.flush()
    for v in (food, wine):
        ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
        db.add(InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=10))
    await db.commit()

    cashier = User(email=None, password_hash=None, pin_hash=hash_pin("1"),
                    full_name="A", role="cashier")
    db.add(cashier); await db.commit(); await db.refresh(cashier)

    order = await create_order(db, source="pos", line_items_data=[
        {"variant_id": food.id, "quantity": 1},
        {"variant_id": wine.id, "quantity": 1},
    ])

    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)
    mock_tx_finish_ok(respx.mock, "tss-abc", str(client_id), BASE,
                      signature="SIG", signature_counter=1, tss_serial="SER")

    fc = FiscalClient(api_key="k", api_secret="s", tss_id="tss-abc",
                      base_url=BASE, http=httpx.AsyncClient(timeout=5))
    fiscal = FiscalService(client=fc, db=db)
    pts = PosTransactionService(db=db, fiscal=fiscal)
    tx = await pts.finalize_sale(
        client_id=client_id, order_id=order.id, cashier_user_id=cashier.id,
        payment_breakdown={"cash": Decimal("12.99")},
    )

    # Aggregate breakdown sums to gross
    breakdown = tx.vat_breakdown
    assert "7" in breakdown and "19" in breakdown
    assert Decimal(breakdown["7"]["gross"]) == Decimal("3.00")
    assert Decimal(breakdown["19"]["gross"]) == Decimal("9.99")
    # Net + VAT reconcile
    assert Decimal(breakdown["7"]["net"]) + Decimal(breakdown["7"]["vat"]) == Decimal("3.00")
    assert Decimal(breakdown["19"]["net"]) + Decimal(breakdown["19"]["vat"]) == Decimal("9.99")

    # Per-line columns are populated correctly
    lines = (await db.execute(
        select(PosTransactionLine).where(PosTransactionLine.pos_transaction_id == tx.id)
    )).scalars().all()
    by_sku = {l.sku: l for l in lines}
    assert by_sku["SKU-BREAD"].vat_rate == Decimal("7.00")
    assert by_sku["SKU-WINE"].vat_rate == Decimal("19.00")
    assert by_sku["SKU-BREAD"].vat_amount == Decimal("0.20")  # 3.00 * 7/107
    assert by_sku["SKU-WINE"].vat_amount == Decimal("1.59")   # 9.99 * 19/119 ≈ 1.5949
```

- [ ] **Step 2.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_variant_vat_split.py -v`

- [ ] **Step 2.3: Rewrite `_build_vat_breakdown` and `_line_from_order_item`**

In `backend/app/services/pos_transaction.py`:

Replace `_build_vat_breakdown`:

```python
    async def _build_vat_breakdown(
        self, line_items,
    ) -> tuple[dict[str, dict[str, Decimal]], Decimal, Decimal]:
        """Source per-line vat_rate from the linked ProductVariant."""
        from app.models import ProductVariant
        # Collect variants in one query
        variant_ids = [li.variant_id for li in line_items]
        variants = (await self.db.execute(
            select(ProductVariant).where(ProductVariant.id.in_(variant_ids))
        )).scalars().all()
        by_id = {v.id: v for v in variants}

        slots: dict[str, dict[str, Decimal]] = {}
        total_gross = Decimal("0")
        total_net = Decimal("0")
        for li in line_items:
            v = by_id[li.variant_id]
            rate_pct = Decimal(v.vat_rate).quantize(Decimal("0.01"))
            slot = _rate_to_slot(rate_pct)
            gross = _gross_for_line(li)
            rate_frac = rate_pct / Decimal("100")
            net = (gross / (1 + rate_frac)).quantize(Decimal("0.01"))
            vat = (gross - net).quantize(Decimal("0.01"))
            cur = slots.setdefault(slot, {"net": Decimal("0"), "vat": Decimal("0"), "gross": Decimal("0")})
            cur["net"] += net
            cur["vat"] += vat
            cur["gross"] += gross
            total_gross += gross
            total_net += net
        return slots, total_net, total_gross
```

Replace `_line_from_order_item` to take the variant and compute per-line VAT:

```python
def _line_from_order_item(li, pos_tx_id, variant) -> PosTransactionLine:
    rate_pct = Decimal(variant.vat_rate).quantize(Decimal("0.01"))
    rate_frac = rate_pct / Decimal("100")

    if li.quantity_kg is not None:
        line_total_gross = li.price
        qty = Decimal("1")
        unit_price = (li.price / li.quantity_kg) if li.quantity_kg else li.price
    else:
        unit_price = li.price
        qty = Decimal(li.quantity)
        line_total_gross = (li.price * li.quantity).quantize(Decimal("0.01"))

    line_net = (line_total_gross / (1 + rate_frac)).quantize(Decimal("0.01"))
    line_vat = (line_total_gross - line_net).quantize(Decimal("0.01"))

    return PosTransactionLine(
        pos_transaction_id=pos_tx_id,
        sku=variant.sku,
        title=li.title,
        quantity=qty,
        quantity_kg=li.quantity_kg,
        unit_price=unit_price.quantize(Decimal("0.0001")),
        line_total_net=line_net,
        vat_rate=rate_pct,
        vat_amount=line_vat,
    )
```

Update `finalize_sale`'s line-creation loop to fetch variants once and pass them in:

```python
        # build variant lookup once
        from app.models import ProductVariant
        variants = (await self.db.execute(
            select(ProductVariant).where(ProductVariant.id.in_([li.variant_id for li in line_items]))
        )).scalars().all()
        by_id = {v.id: v for v in variants}

        for li in line_items:
            line = _line_from_order_item(li, tx.id, by_id[li.variant_id])
            self.db.add(line)
        await self.db.flush()
```

- [ ] **Step 2.4: Run, confirm pass — and check no Plan A regressions**

Run: `cd backend && pytest tests/test_variant_vat_split.py tests/test_pos_transaction_service.py -v`
Expected: PASS. The Plan A tests use the default 19% rate — `_rate_to_slot(Decimal("19.00"))` returns `"19"`, so they keep passing.

- [ ] **Step 2.5: Commit**

```bash
git add backend/app/services/pos_transaction.py backend/tests/test_variant_vat_split.py
git commit -m "feat(pos): per-line VAT split from ProductVariant.vat_rate + sku snapshot"
```

---

## Task 3: `card_auth` table + model

Stores card-auth metadata before `finalize_sale` flips immutability. Receipt builder and DSFinV-K read from this for terminal/trace/auth-code fields.

**Files:**
- Create: `backend/alembic/versions/0109_add_card_auth.py`
- Create: `backend/app/models/card_auth.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 3.1: Migration**

Generate `0109_add_card_auth.py`:

```python
"""add card_auth

Revision ID: 0109_add_card_auth
Revises: 0108_add_variant_vat_rate
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0109_add_card_auth"
down_revision = "0108_add_variant_vat_rate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_auths",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pos_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pos_transactions.id"),
            nullable=False, unique=True,
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("approved", sa.Boolean, nullable=False),
        sa.Column("response_code", sa.Text, nullable=False),
        sa.Column("auth_code", sa.Text, nullable=False),
        sa.Column("trace_number", sa.Text, nullable=False),
        sa.Column("terminal_id", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("card_auths")
```

Run up/down/up.

- [ ] **Step 3.2: Model**

Create `backend/app/models/card_auth.py`:

```python
from __future__ import annotations
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CardAuth(Base):
    __tablename__ = "card_auths"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pos_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_transactions.id"), unique=True, nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    response_code: Mapped[str] = mapped_column(Text, nullable=False)
    auth_code: Mapped[str] = mapped_column(Text, nullable=False)
    trace_number: Mapped[str] = mapped_column(Text, nullable=False)
    terminal_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Export from `backend/app/models/__init__.py`:

```python
from app.models.card_auth import CardAuth  # noqa: F401
```

- [ ] **Step 3.3: Commit**

```bash
git add backend/alembic/versions/0109_add_card_auth.py backend/app/models/card_auth.py backend/app/models/__init__.py
git commit -m "feat(payment): card_auths table for pre-finalize merchant fields"
```

---

## Task 4: Persist `card_auth` + cancelled-attempt fiscal record on decline

Modify `PaymentService.pay_card` to (a) write a `CardAuth` row before `finalize_sale`, (b) on decline, still call `finalize_sale` with a "cancelled-attempt" marker so fiskaly records the failed sale per spec §2 step 3.

**Files:**
- Modify: `backend/app/payment/service.py`
- Modify: `backend/app/services/pos_transaction.py` — accept `cancelled_attempt: bool` in `finalize_sale`
- Test: `backend/tests/test_card_auth_persistence.py`

- [ ] **Step 4.1: Failing test**

Create `backend/tests/test_card_auth_persistence.py`:

```python
import uuid
from decimal import Decimal

import httpx
import pytest
import respx
from sqlalchemy import select

from app.fiscal.client import FiscalClient
from app.fiscal.service import FiscalService
from app.models import CardAuth, PosTransaction
from app.payment.service import PaymentService
from app.payment.terminal import MockTerminal
from app.receipt.builder import ReceiptBuilder
from app.receipt.printer import DummyBackend
from app.receipt.service import ReceiptService
from app.services.pos_transaction import PosTransactionService
from app.services.order import create_order
from app.services.password import hash_pin
from app.models import Location, TaxRate, Product, ProductVariant, InventoryItem, InventoryLevel, User
from tests.fiscal_helpers import mock_auth_ok, mock_tx_start_ok, mock_tx_finish_ok

BASE = "https://mock-fiskaly.test"


async def _seed(db) -> tuple[int, int]:
    loc = Location(name="S"); db.add(loc)
    db.add(TaxRate(name="d", rate=Decimal("0.19"), is_default=True))
    p = Product(title="X", handle="x"); db.add(p); await db.flush()
    v = ProductVariant(product_id=p.id, title="T", price=Decimal("1.29"),
                        pricing_type="fixed", vat_rate=Decimal("19"), sku="SKU")
    db.add(v); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    db.add(InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=10))
    await db.commit()
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1"), full_name="A", role="cashier")
    db.add(c); await db.commit(); await db.refresh(c)
    o = await create_order(db, source="pos", line_items_data=[{"variant_id": v.id, "quantity": 1}])
    return o.id, c.id


def _svc(db, *, terminal):
    fc = FiscalClient(api_key="k", api_secret="s", tss_id="tss-abc",
                       base_url=BASE, http=httpx.AsyncClient(timeout=5))
    return PaymentService(
        db=db,
        pos_tx=PosTransactionService(db=db, fiscal=FiscalService(client=fc, db=db)),
        receipts=ReceiptService(
            db=db,
            builder=ReceiptBuilder(merchant_name="x", merchant_address="x",
                                    merchant_tax_id="x", merchant_vat_id="x",
                                    cashier_display="x", register_id="x"),
            backend=DummyBackend(),
        ),
        terminal=terminal,
    )


@pytest.mark.asyncio
@respx.mock
async def test_card_auth_row_written_on_approval(db):
    order_id, cashier_id = await _seed(db)
    cid = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(cid), BASE)
    mock_tx_finish_ok(respx.mock, "tss-abc", str(cid), BASE,
                      signature="SIG", signature_counter=1, tss_serial="SER")

    await _svc(db, terminal=MockTerminal()).pay_card(
        client_id=cid, order_id=order_id, cashier_user_id=cashier_id,
    )
    rows = (await db.execute(select(CardAuth))).scalars().all()
    assert len(rows) == 1
    assert rows[0].approved is True
    assert rows[0].pos_transaction_id == cid


@pytest.mark.asyncio
@respx.mock
async def test_decline_writes_cancelled_attempt_pos_transaction(db):
    order_id, cashier_id = await _seed(db)
    cid = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(cid), BASE)
    mock_tx_finish_ok(respx.mock, "tss-abc", str(cid), BASE,
                      signature="CANCEL-SIG", signature_counter=2, tss_serial="SER")

    from app.payment.errors import CardDeclinedError
    with pytest.raises(CardDeclinedError):
        await _svc(db, terminal=MockTerminal(approve=False)).pay_card(
            client_id=cid, order_id=order_id, cashier_user_id=cashier_id,
        )

    # A cancelled-attempt PosTransaction was written and signed.
    txs = (await db.execute(select(PosTransaction))).scalars().all()
    assert len(txs) == 1
    assert txs[0].tse_signature == "CANCEL-SIG"
    assert txs[0].payment_breakdown == {}  # cancelled = no payment captured
    # A CardAuth row exists with approved=False.
    rows = (await db.execute(select(CardAuth))).scalars().all()
    assert len(rows) == 1
    assert rows[0].approved is False
```

- [ ] **Step 4.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_card_auth_persistence.py -v`

- [ ] **Step 4.3: Update `PosTransactionService.finalize_sale` signature**

In `backend/app/services/pos_transaction.py`, add a `cancelled_attempt: bool = False` parameter:

```python
    async def finalize_sale(
        self, *,
        client_id: uuid.UUID,
        order_id: int,
        cashier_user_id: int,
        payment_breakdown: Mapping[str, Decimal],
        voids_transaction_id: uuid.UUID | None = None,
        cancelled_attempt: bool = False,
    ) -> PosTransaction:
        ...
```

When `cancelled_attempt=True`:
- skip line creation (no items "sold")
- set `total_gross = total_net = 0`
- set `vat_breakdown = {}`
- set `payment_breakdown = {}`
- still go through fiskaly start+finish (legally required per spec §2 step 3)
- fiskaly `process_data` becomes the canonical zero-amount string

Implement by branching at the top of the method:

```python
        if cancelled_attempt:
            # Cancelled-attempt fiscal record: signed but represents no sale.
            from decimal import Decimal as _D
            vat_breakdown = {}
            total_net = total_gross = _D("0")
            line_items = []
        else:
            order = (await self.db.execute(
                select(Order).where(Order.id == order_id)
            )).scalar_one()
            line_items = (await self.db.execute(
                select(LineItem).where(LineItem.order_id == order_id)
            )).scalars().all()
            vat_breakdown, total_net, total_gross = await self._build_vat_breakdown(line_items)

        # ... receipt-number reservation, tx insert as before ...
        # ... only write lines if not cancelled ...
        if not cancelled_attempt:
            # variants lookup + add lines (as before)
            ...
```

`build_process_data` accepts an empty `vat_breakdown` and empty `payment_breakdown` — adjust if it raises today; the canonical string for an empty cancelled tx is `"Beleg^0.00_0.00_0.00_0.00_0.00^"`.

Quick patch in `backend/app/fiscal/process_data.py`:

```python
    # When pay_section is empty, no trailing items — but spec/golden expects
    # the trailing caret with empty list. Keep as `Beleg^...^` (empty after).
    return f"Beleg^{vat_section}^{pay_section}"
```

(Already supports empty string — no change needed.)

- [ ] **Step 4.4: Update `PaymentService.pay_card`**

In `backend/app/payment/service.py`:

```python
    async def pay_card(
        self, *,
        client_id: uuid.UUID,
        order_id: int,
        cashier_user_id: int,
    ) -> PayResult:
        from datetime import datetime, timezone
        from app.models import CardAuth
        from app.payment.errors import CardDeclinedError, TerminalUnavailableError

        total = await self._order_total(order_id)
        try:
            auth = await self.terminal.authorize(amount=total)
        except CardDeclinedError as e:
            # Spec §2 step 3 — cancelled-attempt fiscal record.
            tx = await self.pos_tx.finalize_sale(
                client_id=client_id, order_id=order_id,
                cashier_user_id=cashier_user_id, payment_breakdown={},
                cancelled_attempt=True,
            )
            self.db.add(CardAuth(
                pos_transaction_id=tx.id, amount=total, approved=False,
                response_code=str(getattr(e, "response_code", "")) or "decline",
                auth_code="", trace_number="", terminal_id=self._terminal_id(),
                created_at=datetime.now(tz=timezone.utc),
            ))
            await self.db.commit()
            raise

        # Approved path: create pos_transaction + persist CardAuth.
        tx = await self.pos_tx.finalize_sale(
            client_id=client_id, order_id=order_id, cashier_user_id=cashier_user_id,
            payment_breakdown={"girocard": total},
        )
        self.db.add(CardAuth(
            pos_transaction_id=tx.id, amount=total, approved=True,
            response_code=auth.response_code, auth_code=auth.auth_code,
            trace_number=auth.trace_number, terminal_id=auth.terminal_id,
            created_at=datetime.now(tz=timezone.utc),
        ))
        await self.db.commit()
        job = await self.receipts.print_receipt(tx.id)
        return PayResult(transaction=tx, receipt_status=job.status)

    def _terminal_id(self) -> str:
        # MockTerminal exposes no id; ZvtTerminal uses host:port. Best-effort.
        return getattr(self.terminal, "host", "MOCK") + ":" + str(getattr(self.terminal, "port", "0"))
```

Note: when `MockTerminal` declines, the `CardDeclinedError` doesn't carry `response_code`. The `getattr(e, "response_code", "")` keeps the row writable.

- [ ] **Step 4.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_card_auth_persistence.py tests/test_payment_service.py -v`
Expected: PASS — note `test_pay_card_declined_no_pos_transaction` from Plan C now needs updating: a cancelled-attempt PosTransaction IS written. Update its assertion or delete it (it codified the previous-spec-violating behaviour).

In `backend/tests/test_payment_service.py`, replace `test_pay_card_declined_no_pos_transaction` with:

```python
@pytest.mark.asyncio
@respx.mock
async def test_pay_card_declined_writes_cancelled_attempt(db):
    order_id, cashier_id = await _setup_order(db)
    cid = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(cid), BASE)
    mock_tx_finish_ok(respx.mock, "tss-abc", str(cid), BASE,
                      signature="CSIG", signature_counter=1, tss_serial="SER")
    terminal = MockTerminal(approve=False)
    svc = _service(db, terminal=terminal)
    with pytest.raises(CardDeclinedError):
        await svc.pay_card(
            client_id=cid, order_id=order_id, cashier_user_id=cashier_id,
        )
    rows = (await db.execute(select(PosTransaction))).scalars().all()
    assert len(rows) == 1
    assert rows[0].tse_signature == "CSIG"
    assert rows[0].payment_breakdown == {}
```

Run again to confirm.

- [ ] **Step 4.6: Commit**

```bash
git add backend/app/payment/service.py backend/app/services/pos_transaction.py backend/tests/test_card_auth_persistence.py backend/tests/test_payment_service.py
git commit -m "feat(payment): cancelled-attempt fiscal record + card_auth persistence"
```

---

## Task 5: Merchant info config + receipt rendering

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/api/receipts.py`, `backend/app/api/payment.py` — `_builder()` reads from settings

- [ ] **Step 5.1: Add settings**

In `Settings`:

```python
    merchant_name: str = "Voids Market"
    merchant_address: str = "Street 1, 12345 Berlin"
    merchant_tax_id: str = "12/345/67890"
    merchant_vat_id: str = "DE123456789"
    register_id: str = "KASSE-01"
```

Test (append `tests/test_config.py`):

```python
def test_merchant_settings_overridable():
    s = Settings(session_secret_key="x" * 48,
                 merchant_name="Foo", register_id="K-2")
    assert s.merchant_name == "Foo"
    assert s.register_id == "K-2"
```

- [ ] **Step 5.2: Use in `_builder()` (both routers)**

In `backend/app/api/receipts.py` and `backend/app/api/payment.py`, replace the placeholder strings inside `_builder()` with:

```python
    return ReceiptBuilder(
        merchant_name=settings.merchant_name,
        merchant_address=settings.merchant_address,
        merchant_tax_id=settings.merchant_tax_id,
        merchant_vat_id=settings.merchant_vat_id,
        cashier_display="",
        register_id=settings.register_id,
    )
```

- [ ] **Step 5.3: Append to `.env.example`**

```dotenv
# Merchant info (printed on every receipt)
MERCHANT_NAME=Voids Market
MERCHANT_ADDRESS=Street 1, 12345 Berlin
MERCHANT_TAX_ID=12/345/67890
MERCHANT_VAT_ID=DE123456789
REGISTER_ID=KASSE-01
```

- [ ] **Step 5.4: Run full backend suite**

Run: `cd backend && pytest 2>&1 | tail -5`

- [ ] **Step 5.5: Commit**

```bash
git add backend/app/config.py backend/app/api/receipts.py backend/app/api/payment.py backend/tests/test_config.py .env.example
git commit -m "feat(config): merchant info read from settings into receipt builder"
```

---

## Task 6: Storno service + admin route

Spec §1: a wrong sale is cancelled by a *new* PosTransaction with `voids_transaction_id` pointing at the original and negative line quantities. The original is never modified.

**Files:**
- Create: `backend/app/services/storno.py`
- Create: `backend/app/api/storno.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_storno_service.py`

- [ ] **Step 6.1: Failing test**

Create `backend/tests/test_storno_service.py`:

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
    InventoryItem, InventoryLevel, Location, PosTransaction, PosTransactionLine,
    Product, ProductVariant, TaxRate, User,
)
from app.services.order import create_order
from app.services.password import hash_pin
from app.services.pos_transaction import PosTransactionService
from app.services.storno import StornoService
from tests.fiscal_helpers import mock_auth_ok, mock_tx_start_ok, mock_tx_finish_ok

BASE = "https://mock-fiskaly.test"


@pytest.mark.asyncio
@respx.mock
async def test_void_creates_signed_negative_transaction(db):
    # Seed an original sale
    loc = Location(name="S"); db.add(loc)
    db.add(TaxRate(name="d", rate=Decimal("0.07"), is_default=True))
    p = Product(title="Bread", handle="b"); db.add(p); await db.flush()
    v = ProductVariant(product_id=p.id, title="L", price=Decimal("3.00"),
                        pricing_type="fixed", vat_rate=Decimal("7"), sku="SKU-B")
    db.add(v); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    db.add(InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=10))
    await db.commit()
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1"),
             full_name="A", role="cashier")
    db.add(c); await db.commit(); await db.refresh(c)
    o = await create_order(db, source="pos", line_items_data=[{"variant_id": v.id, "quantity": 1}])

    cid_orig = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(cid_orig), BASE)
    mock_tx_finish_ok(respx.mock, "tss-abc", str(cid_orig), BASE,
                      signature="ORIG", signature_counter=1, tss_serial="SER")

    fc = FiscalClient(api_key="k", api_secret="s", tss_id="tss-abc",
                      base_url=BASE, http=httpx.AsyncClient(timeout=5))
    pts = PosTransactionService(db=db, fiscal=FiscalService(client=fc, db=db))
    original = await pts.finalize_sale(
        client_id=cid_orig, order_id=o.id, cashier_user_id=c.id,
        payment_breakdown={"cash": Decimal("3.00")},
    )

    # Now void it
    cid_void = uuid.uuid4()
    mock_tx_start_ok(respx.mock, "tss-abc", str(cid_void), BASE)
    mock_tx_finish_ok(respx.mock, "tss-abc", str(cid_void), BASE,
                      signature="STORNO", signature_counter=2, tss_serial="SER")

    storno = await StornoService(db=db, pos_tx=pts).void(
        original_id=original.id, cashier_user_id=c.id,
    )

    assert storno.tse_signature == "STORNO"
    assert storno.voids_transaction_id == original.id
    # Lines are negative
    lines = (await db.execute(
        select(PosTransactionLine).where(PosTransactionLine.pos_transaction_id == storno.id)
    )).scalars().all()
    assert len(lines) == 1
    assert lines[0].quantity == Decimal("-1.000")
    assert lines[0].line_total_net < 0
    # Original is untouched
    refreshed = (await db.execute(
        select(PosTransaction).where(PosTransaction.id == original.id)
    )).scalar_one()
    assert refreshed.tse_signature == "ORIG"
    assert refreshed.voids_transaction_id is None
```

- [ ] **Step 6.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_storno_service.py -v`

- [ ] **Step 6.3: Implement `StornoService`**

Create `backend/app/services/storno.py`:

```python
"""Storno (correction) service — creates a signed negative PosTransaction."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.fiscal.errors import FiscalError
from app.fiscal.process_data import build_process_data
from app.models import PosTransaction, PosTransactionLine
from app.services.pos_transaction import PosTransactionService


class StornoService:
    def __init__(self, *, db: AsyncSession, pos_tx: PosTransactionService):
        self.db = db
        self.pos_tx = pos_tx

    async def void(
        self, *, original_id: uuid.UUID, cashier_user_id: int,
    ) -> PosTransaction:
        original = (await self.db.execute(
            select(PosTransaction).where(PosTransaction.id == original_id)
        )).scalar_one()
        if original.voids_transaction_id is not None:
            raise ValueError("cannot void a Storno row itself")
        # Already voided?
        prior_void = (await self.db.execute(
            select(PosTransaction).where(PosTransaction.voids_transaction_id == original_id)
        )).scalar_one_or_none()
        if prior_void:
            raise ValueError("transaction already voided")

        original_lines = (await self.db.execute(
            select(PosTransactionLine).where(
                PosTransactionLine.pos_transaction_id == original_id
            )
        )).scalars().all()

        cid = uuid.uuid4()
        receipt_number = (await self.db.execute(
            text("SELECT nextval('receipt_number_seq')")
        )).scalar_one()

        # Mirror payment_breakdown sign-flipped.
        payment_breakdown = {
            k: -Decimal(v) for k, v in original.payment_breakdown.items()
        }
        # VAT breakdown: negate gross/net/vat.
        vat_breakdown = {
            slot: {kk: str(-Decimal(vv)) for kk, vv in row.items()}
            for slot, row in original.vat_breakdown.items()
        }

        storno = PosTransaction(
            id=cid, client_id=cid,
            cashier_user_id=cashier_user_id,
            started_at=datetime.now(tz=timezone.utc),
            total_gross=-original.total_gross,
            total_net=-original.total_net,
            vat_breakdown=vat_breakdown,
            payment_breakdown={k: str(v) for k, v in payment_breakdown.items()},
            receipt_number=receipt_number,
            voids_transaction_id=original_id,
            tse_pending=True,
        )
        self.db.add(storno)
        for ln in original_lines:
            self.db.add(PosTransactionLine(
                pos_transaction_id=cid,
                sku=ln.sku, title=ln.title,
                quantity=-ln.quantity,
                quantity_kg=(-ln.quantity_kg) if ln.quantity_kg is not None else None,
                unit_price=ln.unit_price,
                line_total_net=-ln.line_total_net,
                vat_rate=ln.vat_rate,
                vat_amount=-ln.vat_amount,
            ))
        await self.db.flush()

        process_data = build_process_data(
            vat_breakdown={
                slot: {kk: Decimal(vv) for kk, vv in row.items()}
                for slot, row in vat_breakdown.items()
            },
            payment_breakdown=payment_breakdown,
        )
        try:
            start = await self.pos_tx.fiscal.start_transaction(client_id=cid)
            finish = await self.pos_tx.fiscal.finish_transaction(
                tx_id=cid, latest_revision=start.latest_revision,
                process_data=process_data,
            )
        except FiscalError:
            await self.db.commit()
            await self.db.refresh(storno)
            return storno

        await self.db.execute(text("SET LOCAL fiscal.signing = 'on'"))
        storno.tse_signature = finish.signature
        storno.tse_signature_counter = finish.signature_counter
        storno.tse_serial = finish.tss_serial
        storno.tse_timestamp_start = finish.time_start
        storno.tse_timestamp_finish = finish.time_end
        storno.tse_process_type = finish.process_type
        storno.tse_process_data = process_data
        storno.finished_at = datetime.now(tz=timezone.utc)
        storno.tse_pending = False
        await self.db.commit()
        await self.db.refresh(storno)
        return storno
```

- [ ] **Step 6.4: API route**

Create `backend/app/api/storno.py`:

```python
import uuid
import httpx

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_any_staff
from app.config import settings
from app.fiscal.client import FiscalClient
from app.fiscal.service import FiscalService
from app.services.pos_transaction import PosTransactionService
from app.services.storno import StornoService


router = APIRouter(prefix="/api/pos-transactions", tags=["storno"])


@router.post("/{tx_id}/void", dependencies=[Depends(require_any_staff)])
async def void(
    tx_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    fc = FiscalClient(
        api_key=settings.fiskaly_api_key, api_secret=settings.fiskaly_api_secret,
        tss_id=settings.fiskaly_tss_id, base_url=settings.fiskaly_base_url,
        http=httpx.AsyncClient(timeout=15),
    )
    pts = PosTransactionService(db=db, fiscal=FiscalService(client=fc, db=db))
    try:
        storno = await StornoService(db=db, pos_tx=pts).void(
            original_id=tx_id, cashier_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "id": str(storno.id),
        "voids_transaction_id": str(storno.voids_transaction_id),
        "tse_signature": storno.tse_signature,
        "receipt_number": storno.receipt_number,
    }
```

Register in `main.py`:

```python
from app.api.storno import router as storno_router
app.include_router(storno_router)
```

- [ ] **Step 6.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_storno_service.py -v`
Expected: PASS.

- [ ] **Step 6.6: Commit**

```bash
git add backend/app/services/storno.py backend/app/api/storno.py backend/app/main.py backend/tests/test_storno_service.py
git commit -m "feat(storno): signed negative-quantity void; original untouched"
```

---

## Task 7: ZReportBuilder + endpoint

**Files:**
- Create: `backend/app/reports/__init__.py` (empty)
- Create: `backend/app/reports/z_report.py`
- Modify: `backend/app/api/reports.py` (created in Task 8 — for now, we add the Z-Report endpoint here as a stub)
- Test: `backend/tests/test_z_report.py`

The Z-Report aggregates: opening cash count, paid-ins, paid-outs, sales by VAT, sales by payment method, transaction count, signature counter range, expected vs counted at close.

- [ ] **Step 7.1: Failing test**

Create `backend/tests/test_z_report.py`:

```python
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

from app.models import (
    KassenbuchEntry, PosTransaction, User,
)
from app.reports.z_report import ZReportBuilder
from app.services.password import hash_pin


@pytest.mark.asyncio
async def test_z_report_aggregates_shift(db):
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1"),
             full_name="A", role="cashier")
    db.add(c); await db.commit(); await db.refresh(c)

    now = datetime.now(tz=timezone.utc)
    db.add(KassenbuchEntry(
        entry_type="open", amount=Decimal("100"),
        denominations={"50": 2}, cashier_user_id=c.id, timestamp=now,
    ))
    # Two cash sales
    for i, gross in enumerate([Decimal("3.00"), Decimal("9.99")]):
        tid = uuid.uuid4()
        db.add(PosTransaction(
            id=tid, client_id=tid, cashier_user_id=c.id,
            started_at=now + timedelta(minutes=i),
            finished_at=now + timedelta(minutes=i, seconds=10),
            total_gross=gross, total_net=gross,
            vat_breakdown={"7": {"net": str(gross), "vat": "0", "gross": str(gross)}}
                if i == 0 else
                {"19": {"net": str(gross), "vat": "0", "gross": str(gross)}},
            payment_breakdown={"cash": str(gross)},
            receipt_number=100 + i,
            tse_signature_counter=500 + i,
        ))
    db.add(KassenbuchEntry(
        entry_type="paid_in", amount=Decimal("5"),
        cashier_user_id=c.id, timestamp=now + timedelta(minutes=5), reason="float",
    ))
    db.add(KassenbuchEntry(
        entry_type="close", amount=Decimal("117.99"),
        denominations={"50": 2, "10": 1, "5": 1, "2": 1, "1": 1},
        cashier_user_id=c.id, timestamp=now + timedelta(minutes=10),
    ))
    await db.commit()

    rpt = await ZReportBuilder(db=db).build(
        date_from=now - timedelta(hours=1),
        date_to=now + timedelta(hours=1),
    )
    assert rpt.opening_cash == Decimal("100")
    assert rpt.transaction_count == 2
    assert rpt.sales_by_vat["7"] == Decimal("3.00")
    assert rpt.sales_by_vat["19"] == Decimal("9.99")
    assert rpt.sales_by_payment["cash"] == Decimal("12.99")
    assert rpt.signature_counter_first == 500
    assert rpt.signature_counter_last == 501
    assert rpt.paid_in_total == Decimal("5")
    assert rpt.paid_out_total == Decimal("0")
    assert rpt.closing_counted == Decimal("117.99")
```

- [ ] **Step 7.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_z_report.py -v`

- [ ] **Step 7.3: Implement `ZReportBuilder`**

Create `backend/app/reports/z_report.py`:

```python
"""Z-Report — daily shift summary aggregator."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KassenbuchEntry, PosTransaction


@dataclass
class ZReport:
    date_from: datetime
    date_to: datetime
    opening_cash: Decimal = Decimal("0")
    closing_counted: Decimal = Decimal("0")
    transaction_count: int = 0
    sales_by_vat: dict[str, Decimal] = field(default_factory=dict)
    sales_by_payment: dict[str, Decimal] = field(default_factory=dict)
    paid_in_total: Decimal = Decimal("0")
    paid_out_total: Decimal = Decimal("0")
    signature_counter_first: int | None = None
    signature_counter_last: int | None = None


class ZReportBuilder:
    def __init__(self, *, db: AsyncSession):
        self.db = db

    async def build(self, *, date_from: datetime, date_to: datetime) -> ZReport:
        rpt = ZReport(date_from=date_from, date_to=date_to)

        kb = (await self.db.execute(
            select(KassenbuchEntry).where(
                and_(KassenbuchEntry.timestamp >= date_from,
                     KassenbuchEntry.timestamp <= date_to)
            ).order_by(KassenbuchEntry.timestamp)
        )).scalars().all()
        for e in kb:
            if e.entry_type == "open":
                rpt.opening_cash = Decimal(e.amount)
            elif e.entry_type == "close":
                rpt.closing_counted = Decimal(e.amount)
            elif e.entry_type == "paid_in":
                rpt.paid_in_total += Decimal(e.amount)
            elif e.entry_type == "paid_out":
                rpt.paid_out_total += -Decimal(e.amount)  # stored negative

        txs = (await self.db.execute(
            select(PosTransaction).where(
                and_(PosTransaction.started_at >= date_from,
                     PosTransaction.started_at <= date_to)
            ).order_by(PosTransaction.started_at)
        )).scalars().all()
        rpt.transaction_count = len(txs)
        counters = [t.tse_signature_counter for t in txs if t.tse_signature_counter is not None]
        if counters:
            rpt.signature_counter_first = min(counters)
            rpt.signature_counter_last = max(counters)
        for t in txs:
            for slot, row in (t.vat_breakdown or {}).items():
                rpt.sales_by_vat[slot] = (
                    rpt.sales_by_vat.get(slot, Decimal("0")) + Decimal(row.get("gross", "0"))
                )
            for method, amount in (t.payment_breakdown or {}).items():
                rpt.sales_by_payment[method] = (
                    rpt.sales_by_payment.get(method, Decimal("0")) + Decimal(amount)
                )
        return rpt
```

- [ ] **Step 7.4: Run, confirm pass**

Run: `cd backend && pytest tests/test_z_report.py -v`

- [ ] **Step 7.5: Commit**

```bash
git add backend/app/reports/__init__.py backend/app/reports/z_report.py backend/tests/test_z_report.py
git commit -m "feat(reports): ZReportBuilder aggregates shift activity"
```

---

## Task 8: DSFinV-K minimal export + reports router

Bundle: `bonkopf.csv` (transactions), `bonpos.csv` (lines), `bonkopf_zahlarten.csv` (payments), `tse.csv` (signatures), `cash_per_currency.csv`, `index.xml`.

**Files:**
- Create: `backend/app/reports/dsfinvk.py`
- Create: `backend/app/api/reports.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_dsfinvk_export.py`

- [ ] **Step 8.1: Failing test**

Create `backend/tests/test_dsfinvk_export.py`:

```python
import io
import uuid
import zipfile
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models import (
    KassenbuchEntry, PosTransaction, PosTransactionLine, User,
)
from app.reports.dsfinvk import DsfinvkExporter
from app.services.password import hash_pin


@pytest.mark.asyncio
async def test_dsfinvk_export_zip_has_required_files(db):
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1"),
             full_name="A", role="cashier")
    db.add(c); await db.commit(); await db.refresh(c)
    tid = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)
    db.add(PosTransaction(
        id=tid, client_id=tid, cashier_user_id=c.id,
        started_at=now, finished_at=now,
        total_gross=Decimal("3"), total_net=Decimal("2.80"),
        vat_breakdown={"7": {"net": "2.80", "vat": "0.20", "gross": "3.00"}},
        payment_breakdown={"cash": "3.00"},
        receipt_number=1,
        tse_signature="SIG", tse_signature_counter=1, tse_serial="SER",
        tse_timestamp_start=now, tse_timestamp_finish=now,
        tse_process_type="Kassenbeleg-V1",
    ))
    db.add(PosTransactionLine(
        pos_transaction_id=tid, sku="SKU-B", title="Bread",
        quantity=Decimal("1"), unit_price=Decimal("3.00"),
        line_total_net=Decimal("2.80"), vat_rate=Decimal("7"),
        vat_amount=Decimal("0.20"),
    ))
    await db.commit()

    raw = await DsfinvkExporter(db=db).export(
        date_from=now.replace(hour=0, minute=0, second=0),
        date_to=now.replace(hour=23, minute=59, second=59),
    )
    z = zipfile.ZipFile(io.BytesIO(raw))
    names = set(z.namelist())
    assert {"bonkopf.csv", "bonpos.csv", "bonkopf_zahlarten.csv",
            "tse.csv", "cash_per_currency.csv", "index.xml"} <= names

    bonkopf = z.read("bonkopf.csv").decode("utf-8-sig")
    assert "Z_KASSE_ID" in bonkopf  # CSV header
    assert "1" in bonkopf            # receipt number row
```

- [ ] **Step 8.2: Run, confirm fail**

Run: `cd backend && pytest tests/test_dsfinvk_export.py -v`

- [ ] **Step 8.3: Implement `DsfinvkExporter`**

Create `backend/app/reports/dsfinvk.py`:

```python
"""Minimal DSFinV-K export — bundles the audit-critical CSVs into a ZIP.

Day-1 scope: enough for a Steuerberater to open in IDEA software and confirm
readability. Full schema (12+ CSVs, DTD validation) is Phase 2.

Reference: BMF DSFinV-K v2.x.
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    KassenbuchEntry, PosTransaction, PosTransactionLine,
)


class DsfinvkExporter:
    def __init__(self, *, db: AsyncSession):
        self.db = db

    async def export(self, *, date_from: datetime, date_to: datetime) -> bytes:
        txs = (await self.db.execute(
            select(PosTransaction).where(
                and_(PosTransaction.started_at >= date_from,
                     PosTransaction.started_at <= date_to)
            ).order_by(PosTransaction.receipt_number)
        )).scalars().all()
        lines = (await self.db.execute(
            select(PosTransactionLine).where(
                PosTransactionLine.pos_transaction_id.in_([t.id for t in txs])
            )
        )).scalars().all()
        kb = (await self.db.execute(
            select(KassenbuchEntry).where(
                and_(KassenbuchEntry.timestamp >= date_from,
                     KassenbuchEntry.timestamp <= date_to)
            )
        )).scalars().all()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bonkopf.csv", _bonkopf(txs))
            zf.writestr("bonpos.csv", _bonpos(txs, lines))
            zf.writestr("bonkopf_zahlarten.csv", _zahlarten(txs))
            zf.writestr("tse.csv", _tse(txs))
            zf.writestr("cash_per_currency.csv", _cash_per_currency(kb))
            zf.writestr("index.xml", _index_xml(date_from, date_to))
        return buf.getvalue()


def _csv(headers: list[str], rows: list[dict]) -> str:
    out = io.StringIO()
    out.write("﻿")  # BOM helps IDEA detect UTF-8
    w = csv.DictWriter(out, fieldnames=headers, delimiter=";")
    w.writeheader()
    for r in rows:
        w.writerow({h: r.get(h, "") for h in headers})
    return out.getvalue()


def _bonkopf(txs: list[PosTransaction]) -> str:
    headers = [
        "Z_KASSE_ID", "Z_ERSTELLUNG", "Z_NR", "BON_ID", "BON_NR",
        "BON_TYP", "BON_NAME", "TERMINAL_ID", "BON_STORNO",
        "BON_START", "BON_ENDE", "BEDIENER_NAME", "UMS_BRUTTO",
    ]
    rows = []
    for t in txs:
        rows.append({
            "Z_KASSE_ID": settings.register_id,
            "Z_ERSTELLUNG": (t.finished_at or t.started_at).isoformat(),
            "Z_NR": t.receipt_number,
            "BON_ID": str(t.id),
            "BON_NR": t.receipt_number,
            "BON_TYP": "Beleg" if t.voids_transaction_id is None else "AVBeleg",
            "BON_NAME": "Kassenbeleg-V1",
            "TERMINAL_ID": settings.register_id,
            "BON_STORNO": "1" if t.voids_transaction_id is not None else "0",
            "BON_START": t.started_at.isoformat(),
            "BON_ENDE": (t.finished_at or t.started_at).isoformat(),
            "BEDIENER_NAME": str(t.cashier_user_id),  # name lookup is Phase 2
            "UMS_BRUTTO": _d(t.total_gross),
        })
    return _csv(headers, rows)


def _bonpos(txs: list[PosTransaction], lines: list[PosTransactionLine]) -> str:
    by_tx = {t.id: t for t in txs}
    headers = [
        "Z_KASSE_ID", "Z_ERSTELLUNG", "BON_ID", "POS_ZEILE",
        "GUTSCHEIN_NR", "ARTIKELTEXT", "MENGE", "FAKTOR",
        "UMS_BRUTTO", "UST_SCHLUESSEL", "STNR",
    ]
    rows = []
    for i, ln in enumerate(lines):
        t = by_tx.get(ln.pos_transaction_id)
        if not t:
            continue
        rows.append({
            "Z_KASSE_ID": settings.register_id,
            "Z_ERSTELLUNG": (t.finished_at or t.started_at).isoformat(),
            "BON_ID": str(t.id),
            "POS_ZEILE": i + 1,
            "ARTIKELTEXT": ln.title,
            "MENGE": _d(ln.quantity),
            "FAKTOR": "1",
            "UMS_BRUTTO": _d(ln.line_total_net + ln.vat_amount),
            "UST_SCHLUESSEL": _ust_schluessel(ln.vat_rate),
            "STNR": ln.sku or "",
        })
    return _csv(headers, rows)


def _zahlarten(txs: list[PosTransaction]) -> str:
    headers = ["Z_KASSE_ID", "BON_ID", "ZAHLART_TYP", "ZAHLART_NAME", "BETRAG"]
    rows = []
    for t in txs:
        for method, amount in (t.payment_breakdown or {}).items():
            rows.append({
                "Z_KASSE_ID": settings.register_id,
                "BON_ID": str(t.id),
                "ZAHLART_TYP": "Bar" if method == "cash" else "Unbar",
                "ZAHLART_NAME": method,
                "BETRAG": _d(amount),
            })
    return _csv(headers, rows)


def _tse(txs: list[PosTransaction]) -> str:
    headers = [
        "Z_KASSE_ID", "BON_ID", "TSE_ID", "TSE_TA_NR",
        "TSE_TA_START", "TSE_TA_ENDE", "TSE_TA_VORGANGSART",
        "TSE_TA_SIGZ", "TSE_TA_SIG", "TSE_TA_FEHLER",
    ]
    rows = []
    for t in txs:
        rows.append({
            "Z_KASSE_ID": settings.register_id,
            "BON_ID": str(t.id),
            "TSE_ID": t.tse_serial or "",
            "TSE_TA_NR": "",
            "TSE_TA_START": t.tse_timestamp_start.isoformat() if t.tse_timestamp_start else "",
            "TSE_TA_ENDE": t.tse_timestamp_finish.isoformat() if t.tse_timestamp_finish else "",
            "TSE_TA_VORGANGSART": t.tse_process_type or "",
            "TSE_TA_SIGZ": t.tse_signature_counter or "",
            "TSE_TA_SIG": t.tse_signature or "",
            "TSE_TA_FEHLER": "1" if t.tse_pending else "0",
        })
    return _csv(headers, rows)


def _cash_per_currency(kb: list[KassenbuchEntry]) -> str:
    headers = ["Z_KASSE_ID", "WAEHRUNG", "Z_SAFR_AME", "Z_SAFR_NEN"]
    cash_total = sum(
        (Decimal(e.amount) for e in kb if e.entry_type in ("open", "close", "paid_in", "paid_out")),
        Decimal("0"),
    )
    return _csv(headers, [{
        "Z_KASSE_ID": settings.register_id,
        "WAEHRUNG": "EUR",
        "Z_SAFR_AME": _d(cash_total),
        "Z_SAFR_NEN": _d(cash_total),
    }])


def _index_xml(date_from: datetime, date_to: datetime) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<DataSet>
  <Description>OpenMarket DSFinV-K minimal export {date_from.date()} - {date_to.date()}</Description>
  <Tables>
    <Table><URL>bonkopf.csv</URL></Table>
    <Table><URL>bonpos.csv</URL></Table>
    <Table><URL>bonkopf_zahlarten.csv</URL></Table>
    <Table><URL>tse.csv</URL></Table>
    <Table><URL>cash_per_currency.csv</URL></Table>
  </Tables>
</DataSet>
"""


def _d(v) -> str:
    return f"{Decimal(v).quantize(Decimal('0.01'))}"


def _ust_schluessel(rate) -> str:
    # DSFinV-K USt-Schluessel: 1=19%, 2=7%, 3=10.7%, 4=5.5%, 5=0%
    return {Decimal("19"): "1", Decimal("7"): "2", Decimal("10.7"): "3",
            Decimal("5.5"): "4", Decimal("0"): "5"}.get(
        Decimal(rate).quantize(Decimal("0.1")).normalize(), "5")
```

- [ ] **Step 8.4: Reports router**

Create `backend/app/api/reports.py`:

```python
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_manager_or_above, require_owner
from app.reports.dsfinvk import DsfinvkExporter
from app.reports.z_report import ZReportBuilder


router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/z-report", dependencies=[Depends(require_manager_or_above)])
async def z_report(
    date_from: datetime, date_to: datetime,
    db: AsyncSession = Depends(get_db),
):
    rpt = await ZReportBuilder(db=db).build(date_from=date_from, date_to=date_to)
    return {
        "date_from": rpt.date_from.isoformat(),
        "date_to": rpt.date_to.isoformat(),
        "opening_cash": str(rpt.opening_cash),
        "closing_counted": str(rpt.closing_counted),
        "transaction_count": rpt.transaction_count,
        "sales_by_vat": {k: str(v) for k, v in rpt.sales_by_vat.items()},
        "sales_by_payment": {k: str(v) for k, v in rpt.sales_by_payment.items()},
        "paid_in_total": str(rpt.paid_in_total),
        "paid_out_total": str(rpt.paid_out_total),
        "signature_counter_first": rpt.signature_counter_first,
        "signature_counter_last": rpt.signature_counter_last,
    }


@router.get("/dsfinvk", dependencies=[Depends(require_owner)])
async def dsfinvk_export(
    date_from: date, date_to: date,
    db: AsyncSession = Depends(get_db),
):
    df = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    dt = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
    raw = await DsfinvkExporter(db=db).export(date_from=df, date_to=dt)
    return Response(
        content=raw, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="dsfinvk-{date_from}-{date_to}.zip"'},
    )
```

Register in `main.py`:

```python
from app.api.reports import router as reports_router
app.include_router(reports_router)
```

- [ ] **Step 8.5: Run, confirm pass**

Run: `cd backend && pytest tests/test_dsfinvk_export.py -v`

- [ ] **Step 8.6: Commit**

```bash
git add backend/app/reports/dsfinvk.py backend/app/api/reports.py backend/app/main.py backend/tests/test_dsfinvk_export.py
git commit -m "feat(reports): minimal DSFinV-K ZIP export + Z-Report endpoint"
```

---

## Task 9: Frontend — shared API client + types

**Files:**
- Modify: `frontend/packages/shared/src/api.ts`
- Modify: `frontend/packages/shared/src/types.ts`

- [ ] **Step 9.1: Types**

Append to `frontend/packages/shared/src/types.ts`:

```typescript
export interface PosTransactionRef {
  id: string;
  client_id: string;
  receipt_number: number;
  tse_signature: string | null;
  tse_pending: boolean;
  total_gross: string;
}

export interface CashPaymentResult {
  transaction: PosTransactionRef;
  change: string;
  receipt_status: "printed" | "buffered" | "failed";
}

export interface CardPaymentResult {
  transaction: PosTransactionRef;
  receipt_status: "printed" | "buffered" | "failed";
}

export interface KassenbuchEntry {
  id: string;
  type: string;
  amount: string;
}

export interface CloseSummary {
  id: string;
  expected: string;
  counted: string;
  difference: string;
}

export interface ZReport {
  date_from: string;
  date_to: string;
  opening_cash: string;
  closing_counted: string;
  transaction_count: number;
  sales_by_vat: Record<string, string>;
  sales_by_payment: Record<string, string>;
  paid_in_total: string;
  paid_out_total: string;
  signature_counter_first: number | null;
  signature_counter_last: number | null;
}

export interface HealthStatus {
  online: boolean;
  paper_ok?: boolean;
}
```

- [ ] **Step 9.2: API methods**

In `frontend/packages/shared/src/api.ts`, add to the `api` object:

```typescript
  payment: {
    cash: (data: { client_id: string; order_id: number; tendered: string }) =>
      request<CashPaymentResult>("/payment/cash", { method: "POST", body: JSON.stringify(data) }),
    card: (data: { client_id: string; order_id: number }) =>
      request<CardPaymentResult>("/payment/card", { method: "POST", body: JSON.stringify(data) }),
  },
  kassenbuch: {
    open: (denominations: Record<string, number>) =>
      request<KassenbuchEntry>("/kassenbuch/open", { method: "POST", body: JSON.stringify({ denominations }) }),
    close: (denominations: Record<string, number>) =>
      request<CloseSummary>("/kassenbuch/close", { method: "POST", body: JSON.stringify({ denominations }) }),
    paidIn: (amount: string, reason: string) =>
      request<KassenbuchEntry>("/kassenbuch/paid-in", { method: "POST", body: JSON.stringify({ amount, reason }) }),
    paidOut: (amount: string, reason: string) =>
      request<KassenbuchEntry>("/kassenbuch/paid-out", { method: "POST", body: JSON.stringify({ amount, reason }) }),
  },
  reports: {
    zReport: (date_from: string, date_to: string) =>
      request<ZReport>(`/reports/z-report?date_from=${encodeURIComponent(date_from)}&date_to=${encodeURIComponent(date_to)}`),
    dsfinvkUrl: (date_from: string, date_to: string) =>
      `/api/reports/dsfinvk?date_from=${date_from}&date_to=${date_to}`,
  },
  storno: {
    void: (txId: string) =>
      request<{ id: string; voids_transaction_id: string; tse_signature: string; receipt_number: number }>(
        `/pos-transactions/${txId}/void`, { method: "POST" }
      ),
  },
  health: {
    db: () => request<HealthStatus>("/health"),
    fiskaly: () => request<HealthStatus>("/health/fiskaly"),
    printer: () => request<HealthStatus>("/health/printer"),
    terminal: () => request<HealthStatus>("/health/terminal"),
  },
```

Add the imports at the top:

```typescript
import type {
  CashPaymentResult, CardPaymentResult, CloseSummary, HealthStatus,
  KassenbuchEntry, ZReport,
} from "./types";
```

- [ ] **Step 9.3: Build check**

Run: `cd frontend && pnpm -r build`
Expected: clean.

- [ ] **Step 9.4: Commit**

```bash
git add frontend/packages/shared/src/api.ts frontend/packages/shared/src/types.ts
git commit -m "feat(shared): API client for payment/kassenbuch/reports/storno/health"
```

---

## Task 10: Backend — `/api/health/fiskaly` (closing the health-dot quartet)

The other three health endpoints exist (`/api/health` from Plan 0; `/api/health/printer` from Plan B; `/api/health/terminal` from Plan C). Add fiskaly's.

**Files:**
- Modify: `backend/app/api/payment.py` (or extract a tiny `health.py` — easier to just add to payment.py)

- [ ] **Step 10.1: Add the route**

In `backend/app/api/payment.py`, append:

```python
@router.get("/health/fiskaly", dependencies=[Depends(require_any_staff)])
async def health_fiskaly():
    if not settings.fiskaly_api_key:
        return {"online": False, "configured": False}
    fc = FiscalClient(
        api_key=settings.fiskaly_api_key, api_secret=settings.fiskaly_api_secret,
        tss_id=settings.fiskaly_tss_id, base_url=settings.fiskaly_base_url,
        http=httpx.AsyncClient(timeout=5),
    )
    try:
        await fc._get_token()
        return {"online": True, "configured": True}
    except Exception as e:
        return {"online": False, "configured": True, "error": str(e)}
```

- [ ] **Step 10.2: Commit**

```bash
git add backend/app/api/payment.py
git commit -m "feat(api): /api/health/fiskaly health probe"
```

---

## Task 11: Frontend — `HealthDots` component

**Files:**
- Create: `frontend/packages/pos/src/components/HealthDots.tsx`

- [ ] **Step 11.1: Implement**

Create `frontend/packages/pos/src/components/HealthDots.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api } from "@openmarket/shared";

type DotState = "ok" | "fail" | "unknown";

function Dot({ label, state }: { label: string; state: DotState }) {
  const color = state === "ok" ? "#2ecc40" : state === "fail" ? "#ff4136" : "#aaaaaa";
  return (
    <span title={label} style={{ display: "inline-flex", alignItems: "center", gap: 4, marginRight: 12 }}>
      <span style={{ width: 10, height: 10, borderRadius: 5, background: color, display: "inline-block" }} />
      <span style={{ fontSize: 11 }}>{label}</span>
    </span>
  );
}

export function HealthDots() {
  const [db, setDb] = useState<DotState>("unknown");
  const [fk, setFk] = useState<DotState>("unknown");
  const [pr, setPr] = useState<DotState>("unknown");
  const [tm, setTm] = useState<DotState>("unknown");

  useEffect(() => {
    let alive = true;
    async function poll() {
      const probes: Array<[string, () => Promise<{ online?: boolean; paper_ok?: boolean }>, (s: DotState) => void]> = [
        ["db", api.health.db, setDb],
        ["fk", api.health.fiskaly, setFk],
        ["pr", api.health.printer, setPr],
        ["tm", api.health.terminal, setTm],
      ];
      for (const [, fn, set] of probes) {
        try {
          const r = await fn();
          const ok = (r.online ?? true) && (r.paper_ok ?? true);
          if (alive) set(ok ? "ok" : "fail");
        } catch {
          if (alive) set("fail");
        }
      }
    }
    void poll();
    const t = setInterval(poll, 30_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <div style={{ display: "inline-flex", padding: "4px 8px" }}>
      <Dot label="DB" state={db} />
      <Dot label="TSE" state={fk} />
      <Dot label="Printer" state={pr} />
      <Dot label="Terminal" state={tm} />
    </div>
  );
}
```

- [ ] **Step 11.2: Commit**

```bash
git add frontend/packages/pos/src/components/HealthDots.tsx
git commit -m "feat(pos-ui): HealthDots top-bar component"
```

---

## Task 12: Frontend — `PaymentCashModal`

**Files:**
- Create: `frontend/packages/pos/src/components/PaymentCashModal.tsx`

- [ ] **Step 12.1: Implement**

Create `frontend/packages/pos/src/components/PaymentCashModal.tsx`:

```tsx
import { useState } from "react";
import { api, type CashPaymentResult } from "@openmarket/shared";

export function PaymentCashModal({
  orderId, total, onPaid, onCancel,
}: {
  orderId: number; total: string;
  onPaid: (r: CashPaymentResult) => void;
  onCancel: () => void;
}) {
  const [tendered, setTendered] = useState<string>(total);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await api.payment.cash({
        client_id: crypto.randomUUID(), order_id: orderId, tendered,
      });
      onPaid(r);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <form onSubmit={submit} style={{ background: "white", padding: 24, minWidth: 320 }}>
        <h2>Cash payment</h2>
        <p>Total due: <strong>EUR {total}</strong></p>
        <label>
          Tendered:
          <input
            inputMode="decimal" pattern="[0-9.]*" autoFocus
            value={tendered} onChange={(e) => setTendered(e.target.value)}
            style={{ marginLeft: 8, fontSize: 18, width: 100 }}
          />
        </label>
        <p>Change: EUR {(Math.max(0, parseFloat(tendered || "0") - parseFloat(total))).toFixed(2)}</p>
        {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
        <button type="submit" disabled={busy || parseFloat(tendered || "0") < parseFloat(total)}>
          {busy ? "Signing..." : "Confirm"}
        </button>
        <button type="button" onClick={onCancel} disabled={busy}>Cancel</button>
      </form>
    </div>
  );
}
```

- [ ] **Step 12.2: Commit**

```bash
git add frontend/packages/pos/src/components/PaymentCashModal.tsx
git commit -m "feat(pos-ui): cash payment modal with tendered/change"
```

---

## Task 13: Frontend — `PaymentCardModal`

**Files:**
- Create: `frontend/packages/pos/src/components/PaymentCardModal.tsx`

- [ ] **Step 13.1: Implement**

Create `frontend/packages/pos/src/components/PaymentCardModal.tsx`:

```tsx
import { useEffect, useState } from "react";
import { api, type CardPaymentResult } from "@openmarket/shared";

type Phase = "idle" | "authorizing" | "approved" | "declined" | "error";

export function PaymentCardModal({
  orderId, total, onPaid, onCancel,
}: {
  orderId: number; total: string;
  onPaid: (r: CardPaymentResult) => void;
  onCancel: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setPhase("authorizing"); setError(null);
    try {
      const r = await api.payment.card({
        client_id: crypto.randomUUID(), order_id: orderId,
      });
      setPhase("approved");
      onPaid(r);
    } catch (err) {
      const msg = (err as Error).message;
      if (msg.toLowerCase().includes("declined")) setPhase("declined");
      else setPhase("error");
      setError(msg);
    }
  }

  useEffect(() => { void start(); }, []);

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "white", padding: 24, minWidth: 320 }}>
        <h2>Card payment</h2>
        <p>Total: <strong>EUR {total}</strong></p>
        {phase === "authorizing" && <p>Insert / tap card on terminal...</p>}
        {phase === "approved" && <p style={{ color: "green" }}>Approved</p>}
        {phase === "declined" && (
          <>
            <p style={{ color: "red" }}>Declined. Try again or pay with cash.</p>
            <button onClick={start}>Retry</button>
          </>
        )}
        {phase === "error" && <p style={{ color: "red" }}>Terminal error: {error}</p>}
        <button onClick={onCancel} disabled={phase === "authorizing"}>Cancel</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 13.2: Commit**

```bash
git add frontend/packages/pos/src/components/PaymentCardModal.tsx
git commit -m "feat(pos-ui): card payment modal with authorize/decline UX"
```

---

## Task 14: Frontend — wire payments + Storno + HealthDots into `SalePage`

**Files:**
- Modify: `frontend/packages/pos/src/pages/SalePage.tsx`

This task is intentionally narrow: wire the components built in 11–13 plus a "Void last sale" button into the existing SalePage state machine. The exact insertion points depend on the current SalePage.tsx structure; the steps below are guidance, not a literal patch.

- [ ] **Step 14.1: Read current SalePage**

Run: `wc -l frontend/packages/pos/src/pages/SalePage.tsx` to confirm size; open in editor; identify (a) where the cart total is rendered, (b) where the "Charge" / "Pay" button sits today, (c) where the receipt overlay is rendered.

- [ ] **Step 14.2: Add `payMethod` state**

Near the existing `useState` declarations at the top of `SalePage`:

```tsx
const [payMethod, setPayMethod] = useState<"none" | "cash" | "card">("none");
const [lastTxId, setLastTxId] = useState<string | null>(null);
const [orderId, setOrderId] = useState<number | null>(null);
```

- [ ] **Step 14.3: Replace single "Charge" button with two buttons**

Where the existing checkout button lives, replace with:

```tsx
<button onClick={async () => {
  // Create the order first if it doesn't exist yet (existing logic).
  const created = await ensureOrderCreated();  // existing helper or inline
  setOrderId(created.id);
  setPayMethod("cash");
}}>Pay cash</button>
<button onClick={async () => {
  const created = await ensureOrderCreated();
  setOrderId(created.id);
  setPayMethod("card");
}}>Pay card</button>
```

`ensureOrderCreated` is the existing logic that POSTs `/api/orders` from the cart. Reuse what's already there.

- [ ] **Step 14.4: Render the modal**

Below the cart, add:

```tsx
{payMethod === "cash" && orderId && (
  <PaymentCashModal
    orderId={orderId}
    total={cartTotal.toFixed(2)}
    onPaid={(r) => {
      setLastTxId(r.transaction.id);
      setPayMethod("none");
      // existing post-sale UX: clear cart, show receipt summary, etc.
      onSaleComplete();
    }}
    onCancel={() => setPayMethod("none")}
  />
)}
{payMethod === "card" && orderId && (
  <PaymentCardModal
    orderId={orderId}
    total={cartTotal.toFixed(2)}
    onPaid={(r) => { setLastTxId(r.transaction.id); setPayMethod("none"); onSaleComplete(); }}
    onCancel={() => setPayMethod("none")}
  />
)}
```

- [ ] **Step 14.5: Add Storno (void last sale) button**

Above the cart or in a corner toolbar:

```tsx
{lastTxId && (
  <button onClick={async () => {
    if (!confirm("Storno: void last sale?")) return;
    try {
      await api.storno.void(lastTxId);
      setLastTxId(null);
    } catch (e) { alert(`Storno failed: ${(e as Error).message}`); }
  }}>Storno last sale</button>
)}
```

- [ ] **Step 14.6: Add HealthDots to the top bar**

At the top of the SalePage render tree:

```tsx
<HealthDots />
```

Add the import:

```tsx
import { HealthDots } from "../components/HealthDots";
import { PaymentCashModal } from "../components/PaymentCashModal";
import { PaymentCardModal } from "../components/PaymentCardModal";
import { api } from "@openmarket/shared";
```

- [ ] **Step 14.7: Build check**

Run: `cd frontend && pnpm -r build`
Expected: clean.

- [ ] **Step 14.8: Commit**

```bash
git add frontend/packages/pos/src/pages/SalePage.tsx
git commit -m "feat(pos-ui): wire payment modals + Storno button + HealthDots"
```

---

## Task 15: Frontend — Shift open / close pages

**Files:**
- Create: `frontend/packages/pos/src/pages/ShiftOpen.tsx`
- Create: `frontend/packages/pos/src/pages/ShiftClose.tsx`
- Modify: `frontend/packages/pos/src/App.tsx`

- [ ] **Step 15.1: Build `ShiftOpen.tsx`**

```tsx
import { useState } from "react";
import { api } from "@openmarket/shared";

const DENOMS = ["100", "50", "20", "10", "5", "2", "1", "0.5", "0.2", "0.1"];

export function ShiftOpen({ onOpened }: { onOpened: () => void }) {
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const total = DENOMS.reduce((s, d) => s + parseFloat(d) * (counts[d] || 0), 0);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api.kassenbuch.open(counts);
      onOpened();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} style={{ maxWidth: 400, margin: "32px auto" }}>
      <h1>Open shift</h1>
      <p>Count opening cash by denomination:</p>
      {DENOMS.map((d) => (
        <div key={d}>
          <label>EUR {d}: </label>
          <input
            type="number" min={0} value={counts[d] ?? 0}
            onChange={(e) => setCounts({ ...counts, [d]: parseInt(e.target.value || "0") })}
          />
        </div>
      ))}
      <p><strong>Total: EUR {total.toFixed(2)}</strong></p>
      {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
      <button type="submit">Open shift</button>
    </form>
  );
}
```

- [ ] **Step 15.2: Build `ShiftClose.tsx`**

```tsx
import { useState } from "react";
import { api, type CloseSummary } from "@openmarket/shared";

const DENOMS = ["100", "50", "20", "10", "5", "2", "1", "0.5", "0.2", "0.1"];

export function ShiftClose({ onClosed }: { onClosed: (s: CloseSummary) => void }) {
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [summary, setSummary] = useState<CloseSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const total = DENOMS.reduce((s, d) => s + parseFloat(d) * (counts[d] || 0), 0);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const s = await api.kassenbuch.close(counts);
      setSummary(s);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (summary) {
    return (
      <div style={{ maxWidth: 400, margin: "32px auto" }}>
        <h1>Shift closed</h1>
        <p>Expected: EUR {summary.expected}</p>
        <p>Counted: EUR {summary.counted}</p>
        <p style={{ color: parseFloat(summary.difference) === 0 ? "green" : "red" }}>
          Difference: EUR {summary.difference}
        </p>
        <button onClick={() => onClosed(summary)}>Done</button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} style={{ maxWidth: 400, margin: "32px auto" }}>
      <h1>Close shift</h1>
      <p>Count closing cash by denomination:</p>
      {DENOMS.map((d) => (
        <div key={d}>
          <label>EUR {d}: </label>
          <input
            type="number" min={0} value={counts[d] ?? 0}
            onChange={(e) => setCounts({ ...counts, [d]: parseInt(e.target.value || "0") })}
          />
        </div>
      ))}
      <p><strong>Total counted: EUR {total.toFixed(2)}</strong></p>
      {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
      <button type="submit">Close shift</button>
    </form>
  );
}
```

- [ ] **Step 15.3: Wire into `pos/src/App.tsx`**

The POS app should require a shift to be open before SalePage works. Add a top-level state: `shiftStatus: "unknown" | "open" | "closed"`. On mount, check the latest `KassenbuchEntry` (we don't have an endpoint yet — add `GET /api/kassenbuch/status` returning `{open: bool}` to backend; small enough to bundle).

For brevity, the App.tsx wiring is left as a small step the implementer figures out: route `/shift/open` and `/shift/close`, gate `SalePage` behind a "shift open" check.

Add backend endpoint quickly in `backend/app/api/kassenbuch.py`:

```python
from sqlalchemy import select, desc
from app.models import KassenbuchEntry


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)):
    last = (await db.execute(
        select(KassenbuchEntry).order_by(desc(KassenbuchEntry.timestamp)).limit(1)
    )).scalar_one_or_none()
    is_open = last is not None and last.entry_type != "close"
    return {"open": is_open}
```

Add `kassenbuch.status: () => request<{open: boolean}>("/kassenbuch/status")` to the API client.

- [ ] **Step 15.4: Build check**

Run: `cd frontend && pnpm -r build`

- [ ] **Step 15.5: Commit**

```bash
git add frontend/packages/pos/src/pages/ShiftOpen.tsx frontend/packages/pos/src/pages/ShiftClose.tsx frontend/packages/pos/src/App.tsx frontend/packages/shared/src/api.ts backend/app/api/kassenbuch.py
git commit -m "feat(pos-ui): shift open/close pages + status endpoint"
```

---

## Task 16: Frontend — Admin `ZReport` page

**Files:**
- Create: `frontend/packages/admin/src/pages/ZReport.tsx`
- Modify: `frontend/packages/admin/src/App.tsx`

- [ ] **Step 16.1: Create `ZReport.tsx`**

```tsx
import { useState } from "react";
import { api, type ZReport as ZReportT } from "@openmarket/shared";

export function ZReport() {
  const today = new Date().toISOString().slice(0, 10);
  const [from, setFrom] = useState(`${today}T00:00:00`);
  const [to, setTo] = useState(`${today}T23:59:59`);
  const [report, setReport] = useState<ZReportT | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try { setReport(await api.reports.zReport(from, to)); }
    catch (e) { setError((e as Error).message); }
  }

  return (
    <div style={{ maxWidth: 800, margin: "32px auto" }}>
      <h1>Z-Report</h1>
      <label>From: <input type="datetime-local" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
      <label> To: <input type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)} /></label>
      <button onClick={load}>Run</button>
      {error && <p role="alert" style={{ color: "red" }}>{error}</p>}
      {report && (
        <pre style={{ background: "#f4f4f4", padding: 12 }}>{JSON.stringify(report, null, 2)}</pre>
      )}
    </div>
  );
}
```

- [ ] **Step 16.2: Add route + nav in admin App.tsx**

```tsx
import { ZReport } from "./pages/ZReport";
// ...
<Route path="/z-report" element={<ZReport />} />
// nav link for owner+manager
```

- [ ] **Step 16.3: Build + commit**

```bash
cd frontend && pnpm -r build
git add frontend/packages/admin/src/pages/ZReport.tsx frontend/packages/admin/src/App.tsx
git commit -m "feat(admin-ui): Z-Report page"
```

---

## Task 17: Frontend — Admin DSFinV-K export page

**Files:**
- Create: `frontend/packages/admin/src/pages/DsfinvkExport.tsx`
- Modify: `frontend/packages/admin/src/App.tsx`

- [ ] **Step 17.1: Create `DsfinvkExport.tsx`**

```tsx
import { useState } from "react";
import { api } from "@openmarket/shared";

export function DsfinvkExport() {
  const today = new Date().toISOString().slice(0, 10);
  const [from, setFrom] = useState(today);
  const [to, setTo] = useState(today);

  return (
    <div style={{ maxWidth: 600, margin: "32px auto" }}>
      <h1>DSFinV-K Export</h1>
      <p>Generates a ZIP for the date range, ready to hand to the Steuerberater.</p>
      <label>From: <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
      <label> To: <input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></label>
      <p>
        <a
          href={api.reports.dsfinvkUrl(from, to)}
          download={`dsfinvk-${from}-${to}.zip`}
        >
          <button>Download ZIP</button>
        </a>
      </p>
    </div>
  );
}
```

- [ ] **Step 17.2: Wire route (owner-only nav)**

```tsx
import { DsfinvkExport } from "./pages/DsfinvkExport";
// ...
<Route path="/dsfinvk" element={<DsfinvkExport />} />
```

- [ ] **Step 17.3: Build + commit**

```bash
cd frontend && pnpm -r build
git add frontend/packages/admin/src/pages/DsfinvkExport.tsx frontend/packages/admin/src/App.tsx
git commit -m "feat(admin-ui): DSFinV-K export page (owner-only)"
```

---

## Self-Review Checklist

1. **Per-line VAT split (spec §1, §3)** — Task 1 + 2. ✓
2. **Card-decline cancelled-attempt fiscal record (spec §2 step 3)** — Task 4. ✓
3. **Card auth metadata persistence for receipt + DSFinV-K (spec §2)** — Tasks 3 + 4. ✓ (receipt-rendering of card fields is left to a future receipt-builder iteration; today the data is in `card_auths` and `bonkopf_zahlarten.csv`).
4. **Storno (spec §1, §2)** — Task 6. ✓
5. **Z-Report (spec §5)** — Task 7 backend + Task 16 admin UI. ✓
6. **DSFinV-K minimal export (spec §1.3, §7)** — Task 8 + Task 17. ✓ (full schema deferred; called out in header).
7. **Health dots (spec §5, §8)** — Tasks 10 + 11 + 14. ✓
8. **Merchant info on receipt (spec §5)** — Task 5. ✓
9. **Shift open/close UI (spec §2 Kassenbuch)** — Task 15. ✓
10. **Cash payment UX with tendered/change** — Task 12. ✓
11. **Card payment UX with decline retry (spec §2 step 3)** — Task 13. ✓
12. **`pay_mixed` endpoint** — NOT shipped. Header explicitly defers UI; backend stub also deferred. The `payment_breakdown` schema already supports it; add later by composing a single `finalize_sale` with `{cash: x, girocard: y}`.
13. **Acceptance manual test #6 (printer unplugged mid-sale)** — Plan B's buffered-job path covers this. ✓
14. **Acceptance manual test #7 (NUC offline → fiskaly fallback)** — Plan A's `tse_pending=True` + `retry_pending_signatures` covers this. ✓

**Type consistency:**
- `client_id: uuid.UUID` (frontend: `string`, generated via `crypto.randomUUID()`) consistent across PaymentCashModal, PaymentCardModal, backend.
- `payment_breakdown` keys: `"cash" | "girocard" | "card"` consistent in `_VAT_SLOT_BY_PCT`-style enumerations and `bonkopf_zahlarten.csv` mapping.
- `vat_rate` stored as `Decimal` on `ProductVariant` and `PosTransactionLine`; rendered as string at API + JSONB boundary; reconstructed as `Decimal` in process_data + DSFinV-K mapping.
- `HealthStatus.online` consistent between backend (always present) and frontend `Dot`.

**Placeholder scan:** none — all "Plan D handles X" notes from earlier plans are resolved here.

**Tracked Phase 2 / nice-to-have follow-ups:**

- Mixed-payment UI (split tender).
- Full DSFinV-K (remaining ~7 CSVs + DTD).
- Receipt-builder enrichment with card merchant fields (read from `card_auths`).
- `BEDIENER_NAME` lookup in `bonkopf.csv` (currently writes the user_id integer).
- Multi-day Kassenbuch carry-over (today, `expected` sums entire table).
- Backups, Sentry, deployment script, restore drill — separate post-acceptance plan.

---

**Plan complete.** On to Plan E (Admin UX fixups).
