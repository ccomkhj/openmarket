"""add auth tables

Revision ID: 0100_add_auth_tables
Revises:
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0100_add_auth_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String, nullable=True),
        sa.Column("password_hash", sa.Text, nullable=True),
        sa.Column("full_name", sa.String, nullable=False, server_default=""),
        sa.Column("role", sa.String, nullable=False),
        sa.Column("pin_hash", sa.Text, nullable=True),
        sa.Column("pin_locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("mfa_totp_secret", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now() + interval '12 hours'")),
        sa.Column("ip", postgresql.INET, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mfa_method", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("ip", postgresql.INET, nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String, nullable=False),
        sa.Column("succeeded", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_login_attempts_key", "login_attempts", ["key"])
    op.create_index("ix_login_attempts_created_at", "login_attempts", ["created_at"])


def downgrade():
    op.drop_index("ix_login_attempts_created_at", table_name="login_attempts")
    op.drop_index("ix_login_attempts_key", table_name="login_attempts")
    op.drop_table("login_attempts")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
