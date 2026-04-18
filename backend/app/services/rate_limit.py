from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LoginAttempt


async def record_attempt(db: AsyncSession, *, key: str, succeeded: bool) -> None:
    db.add(LoginAttempt(key=key, succeeded=succeeded))
    await db.flush()


async def is_locked(db: AsyncSession, *, key: str, window_seconds: int, max_failures: int) -> bool:
    """True if the key has >= max_failures failed attempts since the most recent success,
    within window_seconds."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)

    last_success = await db.execute(
        select(func.max(LoginAttempt.created_at))
        .where(LoginAttempt.key == key, LoginAttempt.succeeded.is_(True))
    )
    last_success_at = last_success.scalar()

    lower_bound = max(cutoff, last_success_at) if last_success_at else cutoff

    fails = await db.execute(
        select(func.count(LoginAttempt.id))
        .where(
            LoginAttempt.key == key,
            LoginAttempt.succeeded.is_(False),
            LoginAttempt.created_at > lower_bound,
        )
    )
    return (fails.scalar() or 0) >= max_failures
