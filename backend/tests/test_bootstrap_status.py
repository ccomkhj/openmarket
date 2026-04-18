import pytest

from app.models import User


@pytest.mark.asyncio
async def test_bootstrap_status_empty_db(client, db):
    r = await client.get("/api/auth/bootstrap-status")
    assert r.status_code == 200
    assert r.json() == {"setup_required": True}


@pytest.mark.asyncio
async def test_bootstrap_status_with_user(client, db):
    u = User(email="owner@shop.de", password_hash="x", full_name="O", role="owner")
    db.add(u); await db.commit()
    r = await client.get("/api/auth/bootstrap-status")
    assert r.status_code == 200
    assert r.json() == {"setup_required": False}
