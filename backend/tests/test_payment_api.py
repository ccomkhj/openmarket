import uuid
from decimal import Decimal

import pytest
import respx

from app.models import (
    InventoryItem, InventoryLevel, Location, Product, ProductVariant, TaxRate,
)
from app.services.order import create_order


BASE = "https://kassensichv-middleware.fiskaly.com"


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
    from app.config import settings
    monkeypatch.setattr(settings, "fiskaly_api_key", "k")
    monkeypatch.setattr(settings, "fiskaly_api_secret", "s")
    monkeypatch.setattr(settings, "fiskaly_tss_id", "tss-test")
    monkeypatch.setattr(settings, "fiskaly_base_url", BASE)
    monkeypatch.setattr(settings, "terminal_host", "")

    from tests.fiscal_helpers import mock_auth_ok, mock_tx_start_ok, mock_tx_finish_ok

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
