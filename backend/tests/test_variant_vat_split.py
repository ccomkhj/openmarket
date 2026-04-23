"""Test that per-variant VAT rates produce correct split breakdowns."""
import uuid
from decimal import Decimal

import httpx
import pytest
import respx
from sqlalchemy import select

from app.fiscal.client import FiscalClient
from app.fiscal.service import FiscalService
from app.models import (
    PosTransaction, PosTransactionLine, Product, ProductVariant,
    InventoryItem, InventoryLevel, Location, TaxRate, User,
)
from app.services.order import create_order
from app.services.password import hash_pin
from app.services.pos_transaction import PosTransactionService
from tests.fiscal_helpers import mock_auth_ok, mock_tx_finish_ok, mock_tx_start_ok

BASE = "https://mock-fiskaly.test"


def _svc(db) -> PosTransactionService:
    client = FiscalClient(
        api_key="k", api_secret="s", tss_id="tss-abc", base_url=BASE,
        http=httpx.AsyncClient(timeout=5),
    )
    return PosTransactionService(db=db, fiscal=FiscalService(client=client, db=db))


async def _cashier(db) -> User:
    u = User(email=None, password_hash=None, pin_hash=hash_pin("1234"),
             full_name="Cashier", role="cashier")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _setup_mixed_vat_order(db) -> tuple[int, uuid.UUID, uuid.UUID]:
    """Create order with a 7% bread and 19% wine variant. Returns (order_id, bread_variant_id, wine_variant_id)."""
    loc = Location(name="Store")
    db.add(loc)
    await db.flush()

    # Bread at 7%
    bread_product = Product(title="Bread", handle="bread")
    db.add(bread_product)
    await db.flush()
    bread_variant = ProductVariant(
        product_id=bread_product.id, title="Loaf", sku="SKU-BREAD",
        price=Decimal("2.00"), pricing_type="fixed",
    )
    bread_variant.vat_rate = Decimal("7.00")
    db.add(bread_variant)
    await db.flush()
    bread_ii = InventoryItem(variant_id=bread_variant.id)
    db.add(bread_ii)
    await db.flush()
    db.add(InventoryLevel(inventory_item_id=bread_ii.id, location_id=loc.id, available=20))

    # Wine at 19%
    wine_product = Product(title="Wine", handle="wine")
    db.add(wine_product)
    await db.flush()
    wine_variant = ProductVariant(
        product_id=wine_product.id, title="Bottle", sku="SKU-WINE",
        price=Decimal("10.00"), pricing_type="fixed",
    )
    wine_variant.vat_rate = Decimal("19.00")
    db.add(wine_variant)
    await db.flush()
    wine_ii = InventoryItem(variant_id=wine_variant.id)
    db.add(wine_ii)
    await db.flush()
    db.add(InventoryLevel(inventory_item_id=wine_ii.id, location_id=loc.id, available=10))

    await db.commit()

    order = await create_order(
        db, source="pos",
        line_items_data=[
            {"variant_id": bread_variant.id, "quantity": 1},
            {"variant_id": wine_variant.id, "quantity": 1},
        ],
    )
    return order.id, bread_variant.id, wine_variant.id


@pytest.mark.asyncio
@respx.mock
async def test_mixed_vat_split_produces_two_slots(db):
    """Two variants at different VAT rates should produce separate DSFinV-K slots."""
    order_id, bread_vid, wine_vid = await _setup_mixed_vat_order(db)
    cashier = await _cashier(db)

    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)
    mock_tx_finish_ok(
        respx.mock, "tss-abc", str(client_id), BASE,
        signature="SIG", signature_counter=1, tss_serial="SER",
    )

    tx = await _svc(db).finalize_sale(
        client_id=client_id,
        order_id=order_id,
        cashier_user_id=cashier.id,
        payment_breakdown={"cash": Decimal("12.00")},
    )

    # Two VAT slots: "7" for bread, "19" for wine
    assert "7" in tx.vat_breakdown
    assert "19" in tx.vat_breakdown

    # Bread: 2.00 gross at 7% -> net = 2.00/1.07 = 1.87, vat = 0.13
    bread_slot = tx.vat_breakdown["7"]
    assert Decimal(bread_slot["gross"]) == Decimal("2.00")
    assert Decimal(bread_slot["net"]) == Decimal("1.87")
    assert Decimal(bread_slot["vat"]) == Decimal("0.13")

    # Wine: 10.00 gross at 19% -> net = 10.00/1.19 = 8.40, vat = 1.60
    wine_slot = tx.vat_breakdown["19"]
    assert Decimal(wine_slot["gross"]) == Decimal("10.00")
    assert Decimal(wine_slot["net"]) == Decimal("8.40")
    assert Decimal(wine_slot["vat"]) == Decimal("1.60")

    assert tx.total_gross == Decimal("12.00")


@pytest.mark.asyncio
@respx.mock
async def test_pos_transaction_lines_have_sku_snapshot(db):
    """PosTransactionLine.sku should be snapshotted from variant at sale time."""
    order_id, bread_vid, wine_vid = await _setup_mixed_vat_order(db)
    cashier = await _cashier(db)

    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)
    mock_tx_finish_ok(
        respx.mock, "tss-abc", str(client_id), BASE,
        signature="SIG2", signature_counter=2, tss_serial="SER",
    )

    tx = await _svc(db).finalize_sale(
        client_id=client_id,
        order_id=order_id,
        cashier_user_id=cashier.id,
        payment_breakdown={"cash": Decimal("12.00")},
    )

    lines = (await db.execute(
        select(PosTransactionLine).where(PosTransactionLine.pos_transaction_id == tx.id)
    )).scalars().all()

    skus = {line.sku for line in lines}
    assert "SKU-BREAD" in skus
    assert "SKU-WINE" in skus

    for line in lines:
        assert line.vat_rate in (Decimal("7.00"), Decimal("19.00"))
        assert line.vat_amount > Decimal("0")
