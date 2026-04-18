import pytest
from app.models.inventory import Location, InventoryItem, InventoryLevel
from app.models.product import Product, ProductVariant


async def seed_for_analytics(db):
    location = Location(name="Main Store", address="123 Main St")
    db.add(location)
    await db.flush()
    product = Product(title="Widget", handle="widget", status="active", tags=[])
    db.add(product)
    await db.flush()
    variant = ProductVariant(product_id=product.id, title="Default", price=10.00, barcode="WIDGET001")
    db.add(variant)
    await db.flush()
    inv_item = InventoryItem(variant_id=variant.id)
    db.add(inv_item)
    await db.flush()
    level = InventoryLevel(inventory_item_id=inv_item.id, location_id=location.id, available=100)
    db.add(level)
    await db.commit()
    return {"variant_id": variant.id, "location_id": location.id}


@pytest.mark.asyncio
async def test_analytics_summary_empty(authed_client):
    response = await authed_client.get("/api/analytics/summary?days=30")
    assert response.status_code == 200
    data = response.json()
    assert data["total_orders"] == 0
    assert data["total_revenue"] == "0"
    assert data["daily_sales"] == []
    assert data["top_products"] == []
    assert data["orders_by_source"] == {}


@pytest.mark.asyncio
async def test_analytics_summary_with_orders(authed_client, db):
    ids = await seed_for_analytics(db)

    # Create 3 POS orders with 2 items each at $10
    for _ in range(3):
        response = await authed_client.post("/api/orders", json={
            "source": "pos",
            "line_items": [{"variant_id": ids["variant_id"], "quantity": 2}],
        })
        assert response.status_code == 201

    response = await authed_client.get("/api/analytics/summary?days=30")
    assert response.status_code == 200
    data = response.json()

    assert data["total_orders"] == 3
    assert float(data["total_revenue"]) == 60.0
    assert float(data["average_order_value"]) == 20.0
    assert len(data["top_products"]) == 1
    assert "Default" in data["top_products"][0]["title"]
    assert data["top_products"][0]["quantity_sold"] == 6
    assert float(data["top_products"][0]["revenue"]) == 60.0
    assert data["orders_by_source"]["pos"] == 3
    assert len(data["daily_sales"]) == 1
    assert data["daily_sales"][0]["order_count"] == 3
