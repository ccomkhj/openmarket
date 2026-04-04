import pytest
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


async def seed_for_return(db):
    location = Location(name="Main Store", address="123 Main St")
    db.add(location)
    await db.flush()
    product = Product(title="Widget", handle="widget", status="active", tags=[])
    db.add(product)
    await db.flush()
    variant = ProductVariant(product_id=product.id, title="Default", price=10.00, barcode="WIDGET-1")
    db.add(variant)
    await db.flush()
    inv_item = InventoryItem(variant_id=variant.id)
    db.add(inv_item)
    await db.flush()
    level = InventoryLevel(inventory_item_id=inv_item.id, location_id=location.id, available=50)
    db.add(level)
    await db.commit()
    return {
        "variant_id": variant.id,
        "location_id": location.id,
        "inv_item_id": inv_item.id,
    }


async def create_pos_order(client, variant_id: int, quantity: int):
    response = await client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": variant_id, "quantity": quantity}],
    })
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_create_return(client, db):
    ids = await seed_for_return(db)
    order = await create_pos_order(client, ids["variant_id"], 3)
    line_item_id = order["line_items"][0]["id"]

    response = await client.post("/api/returns", json={
        "order_id": order["id"],
        "reason": "damaged",
        "items": [{"line_item_id": line_item_id, "quantity": 1}],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["order_id"] == order["id"]
    assert data["reason"] == "damaged"
    assert data["total_refund"] == "10.00"
    assert len(data["items"]) == 1
    assert data["items"][0]["line_item_id"] == line_item_id
    assert data["items"][0]["quantity"] == 1


@pytest.mark.asyncio
async def test_return_restores_inventory(client, db):
    ids = await seed_for_return(db)
    # Start at 50, sell 3 -> 47
    order = await create_pos_order(client, ids["variant_id"], 3)
    line_item_id = order["line_items"][0]["id"]

    inv_after_sale = await client.get(f"/api/inventory-levels?location_id={ids['location_id']}")
    assert inv_after_sale.json()[0]["available"] == 47

    # Return 2 -> should restore to 49
    response = await client.post("/api/returns", json={
        "order_id": order["id"],
        "reason": "changed mind",
        "items": [{"line_item_id": line_item_id, "quantity": 2}],
    })
    assert response.status_code == 201

    inv_after_return = await client.get(f"/api/inventory-levels?location_id={ids['location_id']}")
    assert inv_after_return.json()[0]["available"] == 49


@pytest.mark.asyncio
async def test_return_over_quantity_fails(client, db):
    ids = await seed_for_return(db)
    order = await create_pos_order(client, ids["variant_id"], 3)
    line_item_id = order["line_items"][0]["id"]

    response = await client.post("/api/returns", json={
        "order_id": order["id"],
        "reason": "test",
        "items": [{"line_item_id": line_item_id, "quantity": 999}],
    })
    assert response.status_code == 400
    assert "exceeds" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_returns_for_order(client, db):
    ids = await seed_for_return(db)
    order = await create_pos_order(client, ids["variant_id"], 3)
    line_item_id = order["line_items"][0]["id"]

    await client.post("/api/returns", json={
        "order_id": order["id"],
        "reason": "test",
        "items": [{"line_item_id": line_item_id, "quantity": 1}],
    })

    response = await client.get(f"/api/orders/{order['id']}/returns")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["order_id"] == order["id"]
