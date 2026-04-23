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
    assert printer.drawer_pulses == 0
    assert len(printer.buffer) > 0
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
    rows = (await db.execute(select(PosTransaction))).scalars().all()
    assert rows == []
