from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=True)
    password_hash = Column(Text, nullable=True)
    full_name = Column(String, nullable=False, default="")
    role = Column(String, nullable=False)  # 'owner' | 'manager' | 'cashier'
    pin_hash = Column(Text, nullable=True)
    pin_locked_until = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    mfa_totp_secret = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    id = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now() + interval '12 hours'"),
    )
    ip = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    mfa_method = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="sessions")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_event_type", "event_type"),
        Index("ix_audit_events_actor_user_id", "actor_user_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    event_type = Column(String, nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ip = Column(INET, nullable=True)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_attempts_key", "key"),
        Index("ix_login_attempts_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False)  # "pin:<user_id>" or "pw:<ip>"
    succeeded = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
