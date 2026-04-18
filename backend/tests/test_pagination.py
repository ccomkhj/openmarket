import pytest


@pytest.mark.asyncio
async def test_products_pagination(authed_client):
    for i in range(5):
        await authed_client.post("/api/products", json={
            "title": f"Product {i}", "handle": f"product-{i}",
            "variants": [{"price": "1.00"}],
        })
    resp = await authed_client.get("/api/products")
    assert resp.status_code == 200
    assert len(resp.json()) == 5

    resp = await authed_client.get("/api/products?limit=2&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = await authed_client.get("/api/products?limit=2&offset=3")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = await authed_client.get("/api/products?limit=2&offset=5")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_orders_pagination(authed_client):
    prod = await authed_client.post("/api/products", json={
        "title": "Item", "handle": "item",
        "variants": [{"price": "5.00"}],
    })
    vid = prod.json()["variants"][0]["id"]
    await authed_client.post("/api/inventory-levels/set", json={
        "inventory_item_id": vid, "location_id": 1, "available": 100,
    })
    for _ in range(3):
        await authed_client.post("/api/orders", json={
            "source": "web",
            "line_items": [{"variant_id": vid, "quantity": 1}],
        })
    resp = await authed_client.get("/api/orders?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_customers_pagination(authed_client):
    for i in range(4):
        await authed_client.post("/api/customers", json={
            "first_name": f"User{i}", "last_name": "Test", "phone": f"555-000{i}",
        })
    resp = await authed_client.get("/api/customers?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2
