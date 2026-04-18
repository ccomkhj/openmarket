import pytest
from app.models.discount import Discount
from datetime import datetime, timezone, timedelta


@pytest.mark.asyncio
async def test_lookup_valid_discount(authed_client, db):
    discount = Discount(
        code="SAVE10",
        discount_type="percentage",
        value=10,
        starts_at=datetime.now(timezone.utc) - timedelta(days=1),
        ends_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(discount)
    await db.commit()
    response = await authed_client.post("/api/discounts/lookup?code=SAVE10")
    assert response.status_code == 200
    assert response.json()["code"] == "SAVE10"


@pytest.mark.asyncio
async def test_lookup_expired_discount(authed_client, db):
    discount = Discount(
        code="OLD10",
        discount_type="percentage",
        value=10,
        starts_at=datetime.now(timezone.utc) - timedelta(days=60),
        ends_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    db.add(discount)
    await db.commit()
    response = await authed_client.post("/api/discounts/lookup?code=OLD10")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_lookup_nonexistent_discount(authed_client):
    response = await authed_client.post("/api/discounts/lookup?code=NOPE")
    assert response.status_code == 404
