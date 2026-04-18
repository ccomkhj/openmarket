import ipaddress
import pytest

from app.config import settings
from app.models import User
from app.services.password import hash_password, hash_pin


@pytest.mark.asyncio
async def test_setup_creates_first_owner(client, db):
    r = await client.post("/api/auth/setup", json={
        "email": "owner@shop.de",
        "password": "opening-day-passphrase-42",
        "full_name": "Shop Owner",
    })
    assert r.status_code == 200
    assert r.json()["role"] == "owner"


@pytest.mark.asyncio
async def test_setup_refuses_second_call(client, db):
    await client.post("/api/auth/setup", json={"email": "a@b.de", "password": "opening-day-passphrase-42", "full_name": "A"})
    r = await client.post("/api/auth/setup", json={"email": "c@d.de", "password": "opening-day-passphrase-43", "full_name": "C"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_login_success_sets_cookie(client, db):
    u = User(email="m@shop.de", password_hash=hash_password("manager-passphrase-9"), full_name="M", role="manager")
    db.add(u); await db.commit()
    r = await client.post("/api/auth/login", json={"email": "m@shop.de", "password": "manager-passphrase-9"})
    assert r.status_code == 200
    assert settings.session_cookie_name in r.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_is_401(client, db):
    u = User(email="m@shop.de", password_hash=hash_password("correct-passphrase-x"), full_name="M", role="manager")
    db.add(u); await db.commit()
    r = await client.post("/api/auth/login", json={"email": "m@shop.de", "password": "wrong-wrong-wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_locks_after_5_failures(client, db):
    u = User(email="m@shop.de", password_hash=hash_password("correct-passphrase-x"), full_name="M", role="manager")
    db.add(u); await db.commit()
    for _ in range(5):
        await client.post("/api/auth/login", json={"email": "m@shop.de", "password": "wrong"})
    r = await client.post("/api/auth/login", json={"email": "m@shop.de", "password": "correct-passphrase-x"})
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_pos_login_with_pin(client, db):
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1234"), full_name="Anna", role="cashier")
    db.add(c); await db.flush()
    await db.commit()
    r = await client.post(
        "/api/auth/pos-login",
        json={"user_id": c.id, "pin": "1234"},
        headers={"X-Forwarded-For": "192.168.1.23"},
    )
    assert r.status_code == 200
    assert settings.session_cookie_name in r.cookies


@pytest.mark.asyncio
async def test_pos_login_rejects_non_lan_ip(client, db):
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1234"), full_name="Anna", role="cashier")
    db.add(c); await db.flush()
    await db.commit()
    r = await client.post(
        "/api/auth/pos-login",
        json={"user_id": c.id, "pin": "1234"},
        headers={"X-Forwarded-For": "8.8.8.8"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_logout_revokes_session(client, db):
    u = User(email="m@shop.de", password_hash=hash_password("correct-passphrase-x"), full_name="M", role="manager")
    db.add(u); await db.commit()
    await client.post("/api/auth/login", json={"email": "m@shop.de", "password": "correct-passphrase-x"})
    me1 = await client.get("/api/auth/me")
    assert me1.status_code == 200
    await client.post("/api/auth/logout")
    me2 = await client.get("/api/auth/me")
    assert me2.status_code == 401


@pytest.mark.asyncio
async def test_list_cashiers(client, db):
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1234"),
             full_name="Anna M.", role="cashier")
    m = User(email="mgr@x.de", password_hash="x", full_name="Manager X", role="manager")
    db.add_all([c, m])
    await db.commit()

    r = await client.get("/api/auth/cashiers")
    assert r.status_code == 200
    body = r.json()
    names = [row["full_name"] for row in body]
    assert "Anna M." in names
    assert "Manager X" not in names  # managers excluded


@pytest.mark.asyncio
async def test_cors_rejects_unknown_origin(client):
    r = await client.options(
        "/api/auth/me",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


@pytest.mark.asyncio
async def test_cors_accepts_admin_origin(client):
    r = await client.options(
        "/api/auth/me",
        headers={
            "Origin": "https://admin.local",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-origin") == "https://admin.local"
