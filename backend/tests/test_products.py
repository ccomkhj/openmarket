import pytest


@pytest.mark.asyncio
async def test_create_product(client):
    response = await client.post("/api/products", json={
        "title": "Whole Milk",
        "handle": "whole-milk",
        "product_type": "dairy",
        "variants": [
            {"title": "1L", "barcode": "1234567890", "price": "2.99"},
            {"title": "2L", "barcode": "1234567891", "price": "4.99"},
        ],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Whole Milk"
    assert data["handle"] == "whole-milk"
    assert len(data["variants"]) == 2
    assert data["variants"][0]["barcode"] == "1234567890"


@pytest.mark.asyncio
async def test_list_products(client):
    await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    await client.post("/api/products", json={
        "title": "Bread", "handle": "bread", "variants": [{"price": "1.99"}],
    })
    response = await client.get("/api/products")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_product(client):
    create = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    pid = create.json()["id"]
    response = await client.get(f"/api/products/{pid}")
    assert response.status_code == 200
    assert response.json()["title"] == "Milk"


@pytest.mark.asyncio
async def test_update_product(client):
    create = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    pid = create.json()["id"]
    response = await client.put(f"/api/products/{pid}", json={"title": "Organic Milk"})
    assert response.status_code == 200
    assert response.json()["title"] == "Organic Milk"


@pytest.mark.asyncio
async def test_archive_product(client):
    create = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    pid = create.json()["id"]
    response = await client.delete(f"/api/products/{pid}")
    assert response.status_code == 200
    get = await client.get(f"/api/products/{pid}")
    assert get.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_add_variant(client):
    create = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    pid = create.json()["id"]
    response = await client.post(f"/api/products/{pid}/variants", json={
        "title": "500ml", "barcode": "999", "price": "1.49",
    })
    assert response.status_code == 201
    assert response.json()["title"] == "500ml"


@pytest.mark.asyncio
async def test_update_variant(client):
    create = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk", "variants": [{"price": "2.99"}],
    })
    vid = create.json()["variants"][0]["id"]
    response = await client.put(f"/api/variants/{vid}", json={"price": "3.49"})
    assert response.status_code == 200
    assert response.json()["price"] == "3.49"


@pytest.mark.asyncio
async def test_delete_variant(client):
    create = await client.post("/api/products", json={
        "title": "Milk",
        "handle": "milk",
        "variants": [
            {"title": "1L", "price": "2.99"},
            {"title": "2L", "price": "4.99"},
        ],
    })
    vid = create.json()["variants"][0]["id"]
    response = await client.delete(f"/api/variants/{vid}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_lookup_variant_by_barcode(client):
    await client.post("/api/products", json={
        "title": "Milk", "handle": "milk",
        "variants": [{"title": "1L", "barcode": "8801234000001", "price": "2.99"}],
    })
    response = await client.get("/api/variants/lookup?barcode=8801234000001")
    assert response.status_code == 200
    data = response.json()
    assert data["barcode"] == "8801234000001"
    assert data["price"] == "2.99"
    assert "product_title" in data


@pytest.mark.asyncio
async def test_lookup_variant_by_barcode_not_found(client):
    response = await client.get("/api/variants/lookup?barcode=NONEXISTENT")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_products_includes_min_price(client):
    await client.post("/api/products", json={
        "title": "Milk", "handle": "milk",
        "variants": [
            {"title": "1L", "price": "2.99"},
            {"title": "2L", "price": "4.99"},
        ],
    })
    response = await client.get("/api/products")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["min_price"] == "2.99"


@pytest.mark.asyncio
async def test_list_products_includes_image_url(client, db):
    from app.models.product import ProductImage

    # Create a product without an image — image_url should be null
    create = await client.post("/api/products", json={
        "title": "Milk", "handle": "milk",
        "variants": [{"title": "1L", "price": "2.99"}],
    })
    assert create.status_code == 201
    pid = create.json()["id"]

    response = await client.get("/api/products")
    assert response.status_code == 200
    data = response.json()
    product = next(p for p in data if p["id"] == pid)
    assert "image_url" in product
    assert product["image_url"] is None

    # Add an image using the test DB session (same transaction scope as the client)
    img = ProductImage(product_id=pid, src="https://placehold.co/400x300?text=Milk", position=0)
    db.add(img)
    await db.flush()

    response2 = await client.get("/api/products")
    assert response2.status_code == 200
    data2 = response2.json()
    product2 = next(p for p in data2 if p["id"] == pid)
    assert product2["image_url"] == "https://placehold.co/400x300?text=Milk"
