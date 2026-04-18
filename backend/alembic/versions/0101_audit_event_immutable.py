"""make audit_events and login_attempts reject UPDATE/DELETE

Revision ID: 0101_audit_immutable
Revises: 0100_add_auth_tables
Create Date: 2026-04-18
"""
from alembic import op

revision = "0101_audit_immutable"
down_revision = "0100_add_auth_tables"
branch_labels = None
depends_on = None


def upgrade():
    # asyncpg prepares each statement individually, so split into separate
    # op.execute() calls rather than sending one multi-statement string.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_audit_modification() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit rows are append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_no_update
            BEFORE UPDATE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION reject_audit_modification()
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_no_delete
            BEFORE DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION reject_audit_modification()
        """
    )


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events")
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_delete ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_modification()")
