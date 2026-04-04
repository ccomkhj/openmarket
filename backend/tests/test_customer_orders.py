import pytest
from app.models.customer import Customer
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


async def seed_for_order(db):
    location = Location(name="Main Store", address="123 Main St")
    db.add(location)
    await db.flush()
    product = Product(title="Milk", handle="milk", status="active", tags=[])
    db.add(product)
    await db.flush()
    variant = ProductVariant(product_id=product.id, title="1L", price=2.99, barcode="456")
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
async def test_update_customer(client, db):
    create_resp = await client.post("/api/customers", json={
        "first_name": "Jane",
        "last_name": "Doe",
        "phone": "555-0001",
    })
    assert create_resp.status_code == 201
    customer_id = create_resp.json()["id"]

    update_resp = await client.put(f"/api/customers/{customer_id}", json={
        "first_name": "Janet",
    })
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["first_name"] == "Janet"
    assert data["last_name"] == "Doe"


@pytest.mark.asyncio
async def test_customer_order_history(client, db):
    ids = await seed_for_order(db)

    create_resp = await client.post("/api/customers", json={
        "first_name": "Bob",
        "last_name": "Smith",
        "phone": "555-0002",
    })
    assert create_resp.status_code == 201
    customer_id = create_resp.json()["id"]

    order_resp = await client.post("/api/orders", json={
        "source": "web",
        "customer_id": customer_id,
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    assert order_resp.status_code == 201

    history_resp = await client.get(f"/api/customers/{customer_id}/orders")
    assert history_resp.status_code == 200
    orders = history_resp.json()
    assert len(orders) == 1
    assert orders[0]["source"] == "web"


@pytest.mark.asyncio
async def test_lookup_customer_by_phone(client, db):
    create_resp = await client.post("/api/customers", json={
        "first_name": "Alice",
        "last_name": "Wonder",
        "phone": "555-0003",
    })
    assert create_resp.status_code == 201

    lookup_resp = await client.get("/api/customers/lookup?phone=555-0003")
    assert lookup_resp.status_code == 200
    data = lookup_resp.json()
    assert data["first_name"] == "Alice"
    assert data["phone"] == "555-0003"


@pytest.mark.asyncio
async def test_lookup_customer_missing_params(client):
    resp = await client.get("/api/customers/lookup")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_order_auto_creates_customer(client, db):
    ids = await seed_for_order(db)

    order_resp = await client.post("/api/orders", json={
        "source": "web",
        "customer_name": "New Person",
        "customer_phone": "555-9999",
        "line_items": [{"variant_id": ids["variant_id"], "quantity": 1}],
    })
    assert order_resp.status_code == 201
    order_data = order_resp.json()
    assert order_data["customer_id"] is not None

    # Verify customer was created and can be looked up
    lookup_resp = await client.get("/api/customers/lookup?phone=555-9999")
    assert lookup_resp.status_code == 200
    customer_data = lookup_resp.json()
    assert customer_data["first_name"] == "New"
    assert customer_data["last_name"] == "Person"
    assert customer_data["id"] == order_data["customer_id"]
