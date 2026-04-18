import pytest
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


async def seed_for_order(db):
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
    return {"variant_id": variant.id, "location_id": location.id, "inv_item_id": inv_item.id}


@pytest.mark.asyncio
async def test_create_web_order(authed_client, db):
    ids = await seed_for_order(db)
    response = await authed_client.post("/api/orders", json={
        "source": "web",
        "customer_name": "John Doe",
        "customer_phone": "555-1234",
        "shipping_address": {"address1": "123 Main St", "city": "Seoul", "zip": "12345"},
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 2}],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "web"
    assert data["fulfillment_status"] == "unfulfilled"
    assert data["total_price"] == "5.98"
    assert len(data["line_items"]) == 1


@pytest.mark.asyncio
async def test_create_pos_order(cashier_client, db):
    ids = await seed_for_order(db)
    response = await cashier_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 3}],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "pos"
    assert data["fulfillment_status"] == "fulfilled"


@pytest.mark.asyncio
async def test_order_deducts_inventory(authed_client, db):
    ids = await seed_for_order(db)
    await authed_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 5}],
    })
    inv = await authed_client.get(f"/api/inventory-levels?location_id={ids['location_id']}")
    assert inv.json()[0]["available"] == 45


@pytest.mark.asyncio
async def test_order_fails_on_insufficient_stock(cashier_client, db):
    ids = await seed_for_order(db)
    response = await cashier_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 999}],
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_orders(authed_client, db):
    ids = await seed_for_order(db)
    await authed_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    response = await authed_client.get("/api/orders")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_get_order(authed_client, db):
    ids = await seed_for_order(db)
    create = await authed_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    oid = create.json()["id"]
    response = await authed_client.get(f"/api/orders/{oid}")
    assert response.status_code == 200
    assert len(response.json()["line_items"]) == 1


@pytest.mark.asyncio
async def test_lookup_order_by_number(authed_client, db):
    ids = await seed_for_order(db)
    create = await authed_client.post("/api/orders", json={
        "source": "pos",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    order_number = create.json()["order_number"]
    response = await authed_client.get(f"/api/orders/lookup?order_number={order_number}")
    assert response.status_code == 200
    assert response.json()["order_number"] == order_number
    assert len(response.json()["line_items"]) == 1


@pytest.mark.asyncio
async def test_lookup_order_not_found(authed_client):
    response = await authed_client.get("/api/orders/lookup?order_number=NOPE")
    assert response.status_code == 404
