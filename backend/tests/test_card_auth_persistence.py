"""Tests for CardAuth persistence on approved and declined card payments."""
import uuid
from decimal import Decimal

import httpx
import pytest
import respx
from sqlalchemy import select

from app.fiscal.client import FiscalClient
from app.fiscal.service import FiscalService
from app.models import (
    CardAuth, InventoryItem, InventoryLevel, Location,
    PosTransaction, Product, ProductVariant, TaxRate, User,
)
from app.payment.errors import CardDeclinedError
from app.payment.service import PaymentService
from app.payment.terminal import MockTerminal
from app.receipt.builder import ReceiptBuilder
from app.receipt.printer import DummyBackend
from app.receipt.service import ReceiptService
from app.services.order import create_order
from app.services.password import hash_pin
from app.services.pos_transaction import PosTransactionService
from tests.fiscal_helpers import mock_auth_ok, mock_tx_finish_ok, mock_tx_start_ok

BASE = "https://mock-fiskaly.test"


async def _setup_order(db) -> tuple[int, int]:
    loc = Location(name="Store")
    db.add(loc)
    db.add(TaxRate(name="VAT 19%", rate=Decimal("0.19"), is_default=True))
    p = Product(title="Beer", handle="beer")
    db.add(p)
    await db.flush()
    v = ProductVariant(product_id=p.id, title="500ml", price=Decimal("3.50"), pricing_type="fixed")
    db.add(v)
    await db.flush()
    ii = InventoryItem(variant_id=v.id)
    db.add(ii)
    await db.flush()
    db.add(InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=10))
    await db.commit()
    cashier = User(email=None, password_hash=None, pin_hash=hash_pin("1234"), full_name="C", role="cashier")
    db.add(cashier)
    await db.commit()
    await db.refresh(cashier)
    order = await create_order(db, source="pos", line_items_data=[{"variant_id": v.id, "quantity": 1}])
    return order.id, cashier.id


def _service(db, *, terminal=None) -> PaymentService:
    fc = FiscalClient(
        api_key="k", api_secret="s", tss_id="tss-abc",
        base_url=BASE, http=httpx.AsyncClient(timeout=5),
    )
    fiscal = FiscalService(client=fc, db=db)
    pts = PosTransactionService(db=db, fiscal=fiscal)
    receipts = ReceiptService(
        db=db,
        builder=ReceiptBuilder(
            merchant_name="X", merchant_address="Y", merchant_tax_id="Z",
            merchant_vat_id="W", cashier_display="C", register_id="K-1",
        ),
        backend=DummyBackend(),
    )
    return PaymentService(
        db=db, pos_tx=pts, receipts=receipts,
        terminal=terminal or MockTerminal(),
    )


@pytest.mark.asyncio
@respx.mock
async def test_approved_card_writes_card_auth_approved(db):
    """A successful card authorization writes 1 CardAuth with approved=True."""
    order_id, cashier_id = await _setup_order(db)
    cid = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(cid), BASE)
    mock_tx_finish_ok(
        respx.mock, "tss-abc", str(cid), BASE,
        signature="ASIG", signature_counter=1, tss_serial="SER",
    )

    terminal = MockTerminal(approve=True)
    svc = _service(db, terminal=terminal)
    result = await svc.pay_card(
        client_id=cid, order_id=order_id, cashier_user_id=cashier_id,
    )

    assert result.transaction.tse_signature == "ASIG"
    assert result.transaction.payment_breakdown == {"girocard": "3.50"}

    auth_rows = (await db.execute(select(CardAuth))).scalars().all()
    assert len(auth_rows) == 1
    ca = auth_rows[0]
    assert ca.approved is True
    assert ca.amount == Decimal("3.50")
    assert ca.auth_code == "123456"
    assert ca.terminal_id == "TID-MOCK"
    assert ca.pos_transaction_id == result.transaction.id


@pytest.mark.asyncio
@respx.mock
async def test_declined_card_writes_pos_transaction_signed_and_card_auth_declined(db):
    """A declined card writes 1 TSE-signed PosTransaction and 1 CardAuth with approved=False."""
    order_id, cashier_id = await _setup_order(db)
    cid = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(cid), BASE)
    mock_tx_finish_ok(
        respx.mock, "tss-abc", str(cid), BASE,
        signature="DSIG", signature_counter=2, tss_serial="SER",
    )

    terminal = MockTerminal(approve=False)
    svc = _service(db, terminal=terminal)
    with pytest.raises(CardDeclinedError):
        await svc.pay_card(
            client_id=cid, order_id=order_id, cashier_user_id=cashier_id,
        )

    tx_rows = (await db.execute(select(PosTransaction))).scalars().all()
    assert len(tx_rows) == 1
    tx = tx_rows[0]
    assert tx.tse_signature == "DSIG"
    assert tx.payment_breakdown == {}

    auth_rows = (await db.execute(select(CardAuth))).scalars().all()
    assert len(auth_rows) == 1
    ca = auth_rows[0]
    assert ca.approved is False
    assert ca.amount == Decimal("3.50")
    assert ca.pos_transaction_id == tx.id
    assert ca.response_code == "decline"
