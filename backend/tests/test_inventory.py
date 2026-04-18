import pytest
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


async def seed_product_with_inventory(db):
    location = Location(name="Main Store", address="123 Main St")
    db.add(location)
    await db.flush()
    product = Product(title="Milk", handle="milk", status="active", tags=[])
    db.add(product)
    await db.flush()
    variant = ProductVariant(product_id=product.id, title="1L", price=2.99, barcode="123")
    db.add(variant)
    await db.flush()
    inv_item = InventoryItem(variant_id=variant.id)
    db.add(inv_item)
    await db.flush()
    level = InventoryLevel(inventory_item_id=inv_item.id, location_id=location.id, available=50)
    db.add(level)
    await db.commit()
    return {"location_id": location.id, "inventory_item_id": inv_item.id, "variant_id": variant.id}


@pytest.mark.asyncio
async def test_get_inventory_levels(authed_client, db):
    ids = await seed_product_with_inventory(db)
    response = await authed_client.get(f"/api/inventory-levels?location_id={ids['location_id']}")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["available"] == 50


@pytest.mark.asyncio
async def test_set_inventory(authed_client, db):
    ids = await seed_product_with_inventory(db)
    response = await authed_client.post("/api/inventory-levels/set", json={
        "inventory_item_id": ids["inventory_item_id"],
        "location_id": ids["location_id"],
        "available": 100,
    })
    assert response.status_code == 200
    assert response.json()["available"] == 100


@pytest.mark.asyncio
async def test_adjust_inventory(authed_client, db):
    ids = await seed_product_with_inventory(db)
    response = await authed_client.post("/api/inventory-levels/adjust", json={
        "inventory_item_id": ids["inventory_item_id"],
        "location_id": ids["location_id"],
        "available_adjustment": -5,
    })
    assert response.status_code == 200
    assert response.json()["available"] == 45


@pytest.mark.asyncio
async def test_adjust_inventory_prevents_oversell(authed_client, db):
    ids = await seed_product_with_inventory(db)
    response = await authed_client.post("/api/inventory-levels/adjust", json={
        "inventory_item_id": ids["inventory_item_id"],
        "location_id": ids["location_id"],
        "available_adjustment": -999,
    })
    assert response.status_code == 409
