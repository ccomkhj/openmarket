from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


async def log_event(
    db: AsyncSession,
    *,
    event_type: str,
    actor_user_id: int | None,
    ip: str | None,
    payload: dict[str, Any],
) -> None:
    evt = AuditEvent(
        event_type=event_type,
        actor_user_id=actor_user_id,
        ip=ip,
        payload=payload,
    )
    db.add(evt)
    await db.flush()
