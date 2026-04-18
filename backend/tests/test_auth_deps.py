import pytest
from fastapi import FastAPI, Depends
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db, get_current_user, require_owner, require_any_staff
from app.models import User
from app.services.password import hash_password
from app.services.session import create_session
from app.config import settings


@pytest.mark.asyncio
async def test_get_current_user_without_cookie_is_401(client):
    # make a protected route
    app_: FastAPI = client._transport.app
    @app_.get("/test/me")
    async def _me(user: User = Depends(get_current_user)):
        return {"id": user.id}

    r = await client.get("/test/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_require_owner_blocks_manager(client, db):
    app_: FastAPI = client._transport.app
    @app_.get("/test/owner-only")
    async def _o(user: User = Depends(require_owner)):
        return {"ok": True}

    mgr = User(email="m@e.com", password_hash=hash_password("password1234"), full_name="M", role="manager")
    db.add(mgr); await db.flush()
    s = await create_session(db, user_id=mgr.id, ip="127.0.0.1", user_agent="t", ttl_minutes=60)
    await db.commit()

    client.cookies.set(settings.session_cookie_name, s.id)
    r = await client.get("/test/owner-only")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_require_any_staff_allows_cashier(client, db):
    app_: FastAPI = client._transport.app
    @app_.get("/test/any")
    async def _a(user: User = Depends(require_any_staff)):
        return {"id": user.id}

    c = User(email=None, password_hash=None, pin_hash=hash_password("aaaaaaaaaaaa"), full_name="C", role="cashier")
    db.add(c); await db.flush()
    s = await create_session(db, user_id=c.id, ip="127.0.0.1", user_agent="t", ttl_minutes=60)
    await db.commit()

    client.cookies.set(settings.session_cookie_name, s.id)
    r = await client.get("/test/any")
    assert r.status_code == 200
