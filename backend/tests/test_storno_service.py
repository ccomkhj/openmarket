"""Test StornoService — creates a signed negative PosTransaction."""
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
from app.services.storno import StornoService
from tests.fiscal_helpers import mock_auth_ok, mock_tx_finish_ok, mock_tx_start_ok


BASE = "https://mock-fiskaly.test"


async def _setup_bread_order(db) -> int:
    """Seed a Bread variant at VAT 7% and return the created order id."""
    loc = Location(name="Store")
    db.add(loc)
    tax = TaxRate(name="VAT 7%", rate=Decimal("0.07"), is_default=True)
    db.add(tax)
    p = Product(title="Bread", handle="bread")
    db.add(p)
    await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Sourdough 500g", price=Decimal("2.50"),
        pricing_type="fixed",
        vat_rate=Decimal("7.00"),
    )
    db.add(v)
    await db.flush()
    ii = InventoryItem(variant_id=v.id)
    db.add(ii)
    await db.flush()
    db.add(InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=20))
    await db.commit()
    order = await create_order(
        db, source="pos",
        line_items_data=[{"variant_id": v.id, "quantity": 1}],
    )
    return order.id


async def _cashier(db) -> User:
    u = User(
        email=None, password_hash=None, pin_hash=hash_pin("9999"),
        full_name="Test Cashier", role="cashier",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def _svc(db) -> PosTransactionService:
    client = FiscalClient(
        api_key="k", api_secret="s", tss_id="tss-abc", base_url=BASE,
        http=httpx.AsyncClient(timeout=5),
    )
    return PosTransactionService(db=db, fiscal=FiscalService(client=client, db=db))


@pytest.mark.asyncio
@respx.mock
async def test_void_creates_negative_storno(db):
    order_id = await _setup_bread_order(db)
    cashier = await _cashier(db)

    # --- create the original sale ---
    orig_cid = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(orig_cid), BASE)
    mock_tx_finish_ok(
        respx.mock, "tss-abc", str(orig_cid), BASE,
        signature="SIG1", signature_counter=1, tss_serial="SER",
        time_start=1_745_000_000, time_end=1_745_000_010,
    )
    original = await _svc(db).finalize_sale(
        client_id=orig_cid,
        order_id=order_id,
        cashier_user_id=cashier.id,
        payment_breakdown={"cash": Decimal("2.50")},
    )
    assert original.tse_pending is False

    # --- void the original ---
    mock_auth_ok(respx.mock, BASE)
    storno_cid_placeholder = str(uuid.uuid4())
    # StornoService generates its own UUID; use regex to match any tx id
    respx.mock.put(url__regex=rf"{BASE}/api/v2/tss/tss-abc/tx/[0-9a-f\-]{{36}}$").respond(
        json={
            "_id": storno_cid_placeholder,
            "state": "ACTIVE",
            "number": 2,
            "latest_revision": 1,
            "time_start": 1_745_000_020,
        }
    )
    respx.mock.put(
        url__regex=rf"{BASE}/api/v2/tss/tss-abc/tx/[0-9a-f\-]{{36}}\?last_revision=.+"
    ).respond(
        json={
            "_id": storno_cid_placeholder,
            "state": "FINISHED",
            "signature": {"value": "SIG2", "counter": 2},
            "tss_serial_number": "SER",
            "time_start": 1_745_000_020,
            "time_end": 1_745_000_030,
        }
    )

    storno = await StornoService(db=db, pos_tx=_svc(db)).void(
        original_id=original.id,
        cashier_user_id=cashier.id,
    )

    # --- assert storno fields ---
    assert storno.voids_transaction_id == original.id
    assert storno.total_gross == -original.total_gross
    assert storno.total_net == -original.total_net
    assert storno.receipt_number > original.receipt_number

    storno_lines = (await db.execute(
        select(PosTransactionLine).where(
            PosTransactionLine.pos_transaction_id == storno.id
        )
    )).scalars().all()
    assert len(storno_lines) == 1
    assert storno_lines[0].quantity < 0
    assert storno_lines[0].line_total_net < 0
    assert storno_lines[0].vat_amount < 0

    # --- original must be untouched ---
    await db.refresh(original)
    assert original.voids_transaction_id is None
    assert original.total_gross == Decimal("2.50")


@pytest.mark.asyncio
@respx.mock
async def test_void_rejects_double_void(db):
    order_id = await _setup_bread_order(db)
    cashier = await _cashier(db)

    orig_cid = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(orig_cid), BASE)
    mock_tx_finish_ok(
        respx.mock, "tss-abc", str(orig_cid), BASE,
        signature="SIG1", signature_counter=1, tss_serial="SER",
        time_start=1_745_000_000, time_end=1_745_000_010,
    )
    original = await _svc(db).finalize_sale(
        client_id=orig_cid,
        order_id=order_id,
        cashier_user_id=cashier.id,
        payment_breakdown={"cash": Decimal("2.50")},
    )

    # First void
    mock_auth_ok(respx.mock, BASE)
    respx.mock.put(url__regex=rf"{BASE}/api/v2/tss/tss-abc/tx/[0-9a-f\-]{{36}}$").respond(503)

    storno = await StornoService(db=db, pos_tx=_svc(db)).void(
        original_id=original.id,
        cashier_user_id=cashier.id,
    )
    assert storno.tse_pending is True

    # Second void attempt should be rejected
    with pytest.raises(ValueError, match="already voided"):
        await StornoService(db=db, pos_tx=_svc(db)).void(
            original_id=original.id,
            cashier_user_id=cashier.id,
        )


@pytest.mark.asyncio
async def test_void_rejects_voiding_a_storno(db):
    """A Storno row (voids_transaction_id IS NOT NULL) cannot itself be voided."""
    cashier = await _cashier(db)

    # Manually create a fake storno row
    orig_id = uuid.uuid4()
    storno_id = uuid.uuid4()
    orig = PosTransaction(
        id=orig_id, client_id=orig_id,
        cashier_user_id=cashier.id,
        started_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        total_gross=Decimal("1.00"), total_net=Decimal("0.93"),
        vat_breakdown={}, payment_breakdown={"cash": "1.00"},
        receipt_number=5001, tse_pending=True,
    )
    db.add(orig)
    await db.flush()

    storno_row = PosTransaction(
        id=storno_id, client_id=storno_id,
        cashier_user_id=cashier.id,
        started_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        total_gross=Decimal("-1.00"), total_net=Decimal("-0.93"),
        vat_breakdown={}, payment_breakdown={"cash": "-1.00"},
        receipt_number=5002, tse_pending=True,
        voids_transaction_id=orig_id,
    )
    db.add(storno_row)
    await db.commit()

    with pytest.raises(ValueError, match="cannot void a Storno row"):
        await StornoService(db=db, pos_tx=_svc(db)).void(
            original_id=storno_id,
            cashier_user_id=cashier.id,
        )
