import pytest
from datetime import datetime, timedelta, timezone


def _discount_payload(code="SAVE10"):
    now = datetime.now(timezone.utc)
    return {
        "code": code,
        "discount_type": "percentage",
        "value": "10.00",
        "starts_at": (now - timedelta(days=1)).isoformat(),
        "ends_at": (now + timedelta(days=30)).isoformat(),
    }


@pytest.mark.asyncio
async def test_create_discount(client):
    resp = await client.post("/api/discounts", json=_discount_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "SAVE10"
    assert data["discount_type"] == "percentage"


@pytest.mark.asyncio
async def test_list_discounts(client):
    await client.post("/api/discounts", json=_discount_payload("A"))
    await client.post("/api/discounts", json=_discount_payload("B"))
    resp = await client.get("/api/discounts")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_update_discount(client):
    create = await client.post("/api/discounts", json=_discount_payload())
    did = create.json()["id"]
    resp = await client.put(f"/api/discounts/{did}", json={"value": "20.00"})
    assert resp.status_code == 200
    assert resp.json()["value"] == "20.00"


@pytest.mark.asyncio
async def test_delete_discount(client):
    create = await client.post("/api/discounts", json=_discount_payload())
    did = create.json()["id"]
    resp = await client.delete(f"/api/discounts/{did}")
    assert resp.status_code == 200
    resp = await client.get("/api/discounts")
    assert len(resp.json()) == 0
