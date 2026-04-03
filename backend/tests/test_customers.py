import pytest


@pytest.mark.asyncio
async def test_create_customer(client):
    response = await client.post("/api/customers", json={
        "first_name": "John",
        "last_name": "Doe",
        "phone": "555-1234",
        "addresses": [{"address1": "123 Main St", "city": "Seoul", "zip": "12345", "is_default": True}],
    })
    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "John"
    assert len(data["addresses"]) == 1


@pytest.mark.asyncio
async def test_list_customers(client):
    await client.post("/api/customers", json={"first_name": "John", "last_name": "Doe"})
    response = await client.get("/api/customers")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_get_customer(client):
    create = await client.post("/api/customers", json={"first_name": "John", "last_name": "Doe"})
    cid = create.json()["id"]
    response = await client.get(f"/api/customers/{cid}")
    assert response.status_code == 200
    assert response.json()["first_name"] == "John"
