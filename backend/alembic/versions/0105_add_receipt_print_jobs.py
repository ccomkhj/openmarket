"""add receipt_print_jobs

Revision ID: 0105_add_receipt_print_jobs
Revises: 0104_fiscal_immutability_triggers
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0105_add_receipt_print_jobs"
down_revision = "0104_fiscal_immutability_triggers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "receipt_print_jobs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "pos_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pos_transactions.id"),
            nullable=False,
        ),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("printed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_receipt_print_jobs_tx", "receipt_print_jobs", ["pos_transaction_id"])
    op.create_index("ix_receipt_print_jobs_status", "receipt_print_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("receipt_print_jobs")
