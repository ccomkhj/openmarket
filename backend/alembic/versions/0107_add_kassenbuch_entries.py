"""add kassenbuch_entries

Revision ID: 0107_add_kassenbuch_entries
Revises: 0106_relax_fiscal_inflight_immutability
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0107_add_kassenbuch_entries"
down_revision = "0106_relax_fiscal_inflight_immutability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kassenbuch_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entry_type", sa.Text, nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("denominations", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("cashier_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_kassenbuch_entries_timestamp", "kassenbuch_entries", ["timestamp"])
    op.create_index("ix_kassenbuch_entries_type", "kassenbuch_entries", ["entry_type"])

    op.execute("""
        CREATE TRIGGER kassenbuch_entries_reject_update
        BEFORE UPDATE ON kassenbuch_entries
        FOR EACH ROW EXECUTE FUNCTION fiscal_reject_modification();
    """)
    op.execute("""
        CREATE TRIGGER kassenbuch_entries_reject_delete
        BEFORE DELETE ON kassenbuch_entries
        FOR EACH ROW EXECUTE FUNCTION fiscal_reject_modification();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS kassenbuch_entries_reject_update ON kassenbuch_entries")
    op.execute("DROP TRIGGER IF EXISTS kassenbuch_entries_reject_delete ON kassenbuch_entries")
    op.drop_table("kassenbuch_entries")
