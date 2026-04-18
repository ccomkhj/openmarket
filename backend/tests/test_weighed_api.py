import pytest
from decimal import Decimal

from app.models import Product, ProductVariant, InventoryItem, InventoryLevel, Location


@pytest.mark.asyncio
async def test_create_order_with_weighed_line(cashier_client, db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", weight_unit="kg",
        min_weight_kg=Decimal("0.050"), max_weight_kg=Decimal("5.000"),
    )
    db.add(v); await db.flush()
    loc = Location(name="Store"); db.add(loc); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    lvl = InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=100)
    db.add(lvl); await db.commit()

    r = await cashier_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": v.id, "quantity": 1, "quantity_kg": "0.452"}],
    })
    assert r.status_code == 201
    body = r.json()
    assert Decimal(body["line_items"][0]["price"]) == Decimal("1.13")
    assert Decimal(body["line_items"][0]["quantity_kg"]) == Decimal("0.452")


@pytest.mark.asyncio
async def test_create_order_rejects_underweight(cashier_client, db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", min_weight_kg=Decimal("0.100"),
    )
    db.add(v); await db.flush()
    ii = InventoryItem(variant_id=v.id); db.add(ii); await db.flush()
    loc = Location(name="Store"); db.add(loc); await db.flush()
    lvl = InventoryLevel(inventory_item_id=ii.id, location_id=loc.id, available=100); db.add(lvl)
    await db.commit()

    r = await cashier_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": v.id, "quantity": 1, "quantity_kg": "0.030"}],
    })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_order_rejects_quantity_not_one_on_by_weight(cashier_client, db):
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
        "line_items": [
            {"variant_id": v.id, "quantity": 3, "quantity_kg": "0.452"},
        ],
    })
    assert r.status_code == 400
    assert "quantity" in r.json()["detail"].lower()
