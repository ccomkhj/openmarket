import pytest

from app.models import User, Session, AuditEvent, LoginAttempt


@pytest.mark.asyncio
async def test_create_user(db):
    u = User(
        email="owner@example.com",
        password_hash="dummy",
        full_name="The Owner",
        role="owner",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    assert u.id is not None
    assert u.active is True
    assert u.role == "owner"


@pytest.mark.asyncio
async def test_create_session(db):
    u = User(email="a@b.com", password_hash="x", full_name="X", role="manager")
    db.add(u)
    await db.flush()
    s = Session(id="s" * 32, user_id=u.id, ip="127.0.0.1", user_agent="test")
    db.add(s)
    await db.commit()
    assert s.revoked_at is None


@pytest.mark.asyncio
async def test_create_audit_event(db):
    e = AuditEvent(event_type="login.success", actor_user_id=None, payload={"ip": "1.2.3.4"})
    db.add(e)
    await db.commit()
    assert e.id is not None
