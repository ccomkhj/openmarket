import pytest
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


async def seed_and_create_order(client, db):
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
    order = await client.post("/api/orders", json={
        "source": "web",
        "shipping_address": {"address1": "123 Main St", "city": "Seoul", "zip": "12345"},
        "line_items": [{"variant_id": variant.id, "quantity": 1}],
    })
    return order.json()["id"]


@pytest.mark.asyncio
async def test_create_fulfillment(client, db):
    order_id = await seed_and_create_order(client, db)
    response = await client.post(f"/api/orders/{order_id}/fulfillments", json={"status": "pending"})
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_update_fulfillment(client, db):
    order_id = await seed_and_create_order(client, db)
    create = await client.post(f"/api/orders/{order_id}/fulfillments", json={"status": "pending"})
    fid = create.json()["id"]
    response = await client.put(f"/api/fulfillments/{fid}", json={"status": "delivered"})
    assert response.status_code == 200
    assert response.json()["status"] == "delivered"
