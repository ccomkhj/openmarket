import pytest
from decimal import Decimal

from app.models import Product, ProductVariant, InventoryItem, InventoryLevel, Location


@pytest.mark.asyncio
async def test_order_response_includes_line_total_for_fixed(cashier_client, db):
    p = Product(title="Milk", handle="milk"); db.add(p); await db.flush()
    v = ProductVariant(product_id=p.id, title="1L", price=Decimal("1.29"), pricing_type="fixed")
    db.add(v); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    loc = Location(name="Store"); db.add(loc); await db.flush()
    lvl = InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=10)
    db.add(lvl); await db.commit()

    r = await cashier_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": v.id, "quantity": 3}],
    })
    assert r.status_code == 201
    line = r.json()["line_items"][0]
    assert Decimal(line["line_total"]) == Decimal("3.87")  # 3 × 1.29


@pytest.mark.asyncio
async def test_order_response_includes_line_total_for_weighed(cashier_client, db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", min_weight_kg=Decimal("0.05"),
    )
    db.add(v); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    loc = Location(name="Store"); db.add(loc); await db.flush()
    lvl = InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=100)
    db.add(lvl); await db.commit()

    r = await cashier_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": v.id, "quantity": 1, "quantity_kg": "0.452"}],
    })
    assert r.status_code == 201
    line = r.json()["line_items"][0]
    assert Decimal(line["line_total"]) == Decimal("1.13")
