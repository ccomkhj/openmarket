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
    assert tx.total_gross == Decimal("1.29")
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
    assert tx.receipt_number >= 1
