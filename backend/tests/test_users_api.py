import pytest

from app.models import User
from app.services.password import hash_password


@pytest.mark.asyncio
async def test_list_users_owner(authed_client, db):
    r = await authed_client.get("/api/users")
    assert r.status_code == 200
    assert len(r.json()) >= 1


@pytest.mark.asyncio
async def test_list_users_forbidden_for_cashier(cashier_client, db):
    r = await cashier_client.get("/api/users")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_manager(authed_client, db):
    r = await authed_client.post("/api/users", json={
        "email": "mgr@shop.de",
        "password": "manager-passphrase-9",
        "full_name": "Mgr",
        "role": "manager",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "manager"
    assert body["email"] == "mgr@shop.de"


@pytest.mark.asyncio
async def test_create_cashier_with_pin(authed_client, db):
    r = await authed_client.post("/api/users", json={
        "full_name": "Anna M.",
        "role": "cashier",
        "pin": "1234",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "cashier"
    assert body["email"] is None


@pytest.mark.asyncio
async def test_create_owner_as_owner(authed_client, db):
    r = await authed_client.post("/api/users", json={
        "email": "o2@shop.de",
        "password": "second-owner-passphrase-9",
        "full_name": "Backup",
        "role": "owner",
    })
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_deactivate_user(authed_client, db):
    u = User(email="x@shop.de", password_hash=hash_password("password1234"),
            full_name="X", role="manager")
    db.add(u); await db.commit()
    r = await authed_client.patch(f"/api/users/{u.id}/deactivate")
    assert r.status_code == 200
    assert r.json()["active"] is False
