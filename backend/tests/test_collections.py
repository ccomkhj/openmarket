import pytest


@pytest.mark.asyncio
async def test_create_collection(client):
    response = await client.post("/api/collections", json={
        "title": "Dairy", "handle": "dairy",
    })
    assert response.status_code == 201
    assert response.json()["title"] == "Dairy"


@pytest.mark.asyncio
async def test_list_collections(client):
    await client.post("/api/collections", json={"title": "Dairy", "handle": "dairy"})
    await client.post("/api/collections", json={"title": "Bakery", "handle": "bakery"})
    response = await client.get("/api/collections")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_collection_products(client):
    col = await client.post("/api/collections", json={"title": "Dairy", "handle": "dairy"})
    cid = col.json()["id"]
    prod = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    pid = prod.json()["id"]
    await client.post(f"/api/collections/{cid}/products", json={"product_id": pid})
    response = await client.get(f"/api/collections/{cid}/products")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Milk"
