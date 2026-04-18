import pytest


@pytest.mark.asyncio
async def test_create_collection(authed_client):
    response = await authed_client.post("/api/collections", json={
        "title": "Dairy", "handle": "dairy",
    })
    assert response.status_code == 201
    assert response.json()["title"] == "Dairy"


@pytest.mark.asyncio
async def test_list_collections(authed_client):
    await authed_client.post("/api/collections", json={"title": "Dairy", "handle": "dairy"})
    await authed_client.post("/api/collections", json={"title": "Bakery", "handle": "bakery"})
    response = await authed_client.get("/api/collections")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_collection_products(authed_client):
    col = await authed_client.post("/api/collections", json={"title": "Dairy", "handle": "dairy"})
    cid = col.json()["id"]
    prod = await authed_client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    pid = prod.json()["id"]
    await authed_client.post(f"/api/collections/{cid}/products", json={"product_id": pid})
    response = await authed_client.get(f"/api/collections/{cid}/products")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Milk"
