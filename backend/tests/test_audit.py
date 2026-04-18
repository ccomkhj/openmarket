import pytest
from sqlalchemy import select

from app.models import AuditEvent, User
from app.services.audit import log_event


@pytest.mark.asyncio
async def test_log_event_persists(db):
    u = User(email="a@b.com", password_hash="x", full_name="A", role="owner")
    db.add(u); await db.flush()
    await log_event(db, event_type="product.price_changed", actor_user_id=u.id, ip="127.0.0.1", payload={"variant_id": 5, "old": "1.99", "new": "2.49"})
    await db.commit()
    result = await db.execute(select(AuditEvent).where(AuditEvent.event_type == "product.price_changed"))
    e = result.scalar_one()
    assert e.actor_user_id == u.id
    assert e.payload["variant_id"] == 5


@pytest.mark.asyncio
async def test_audit_event_rejects_update(db):
    await log_event(db, event_type="x", actor_user_id=None, ip=None, payload={})
    await db.commit()
    result = await db.execute(select(AuditEvent))
    e = result.scalar_one()
    e.event_type = "mutated"
    with pytest.raises(Exception):
        await db.commit()
