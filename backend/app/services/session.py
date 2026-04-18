import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session


def _token() -> str:
    return secrets.token_urlsafe(32)[:48]


async def create_session(
    db: AsyncSession,
    *,
    user_id: int,
    ip: str | None,
    user_agent: str | None,
    ttl_minutes: int,
    mfa_method: str | None = None,
) -> Session:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    s = Session(
        id=_token(),
        user_id=user_id,
        expires_at=expires,
        ip=ip,
        user_agent=user_agent,
        mfa_method=mfa_method,
    )
    db.add(s)
    await db.flush()
    return s


async def get_active_session(db: AsyncSession, session_id: str) -> Session | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.revoked_at.is_(None),
            Session.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def revoke_session(db: AsyncSession, session_id: str) -> None:
    await db.execute(
        update(Session)
        .where(Session.id == session_id)
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def revoke_all_for_user(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(Session)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
