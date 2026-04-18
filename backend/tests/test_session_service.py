import pytest
from datetime import datetime, timedelta, timezone

from app.models import User
from app.services.session import create_session, get_active_session, revoke_session


@pytest.mark.asyncio
async def test_create_session_returns_id(db):
    u = User(email="a@b.com", password_hash="x", full_name="A", role="manager")
    db.add(u)
    await db.flush()
    sess = await create_session(db, user_id=u.id, ip="127.0.0.1", user_agent="test", ttl_minutes=60)
    assert len(sess.id) >= 32
    assert sess.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_get_active_session_returns_session(db):
    u = User(email="a@b.com", password_hash="x", full_name="A", role="manager")
    db.add(u); await db.flush()
    s = await create_session(db, user_id=u.id, ip="127.0.0.1", user_agent="t", ttl_minutes=60)
    await db.commit()
    found = await get_active_session(db, s.id)
    assert found is not None
    assert found.user_id == u.id


@pytest.mark.asyncio
async def test_get_active_session_rejects_revoked(db):
    u = User(email="a@b.com", password_hash="x", full_name="A", role="manager")
    db.add(u); await db.flush()
    s = await create_session(db, user_id=u.id, ip="127.0.0.1", user_agent="t", ttl_minutes=60)
    await db.commit()
    await revoke_session(db, s.id)
    await db.commit()
    assert await get_active_session(db, s.id) is None


@pytest.mark.asyncio
async def test_get_active_session_rejects_expired(db):
    u = User(email="a@b.com", password_hash="x", full_name="A", role="manager")
    db.add(u); await db.flush()
    s = await create_session(db, user_id=u.id, ip="127.0.0.1", user_agent="t", ttl_minutes=-1)
    await db.commit()
    assert await get_active_session(db, s.id) is None
