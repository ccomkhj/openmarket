"""add pos_transaction tables

Revision ID: 0103_add_pos_transaction_tables
Revises: 0102_add_weighed
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0103_add_pos_transaction_tables"
down_revision = "0102_add_weighed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS receipt_number_seq START 1")

    op.create_table(
        "pos_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("cashier_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_gross", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total_net", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("vat_breakdown", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("payment_breakdown", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("receipt_number", sa.BigInteger, nullable=False, unique=True),
        sa.Column("linked_order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=True),
        sa.Column(
            "voids_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pos_transactions.id"),
            nullable=True,
        ),
        sa.Column("tse_signature", sa.Text, nullable=True),
        sa.Column("tse_signature_counter", sa.BigInteger, nullable=True),
        sa.Column("tse_serial", sa.Text, nullable=True),
        sa.Column("tse_timestamp_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tse_timestamp_finish", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tse_process_type", sa.Text, nullable=True),
        sa.Column("tse_process_data", sa.Text, nullable=True),
        sa.Column("tse_pending", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_pos_transactions_voids", "pos_transactions", ["voids_transaction_id"])
    op.create_index("ix_pos_transactions_linked_order", "pos_transactions", ["linked_order_id"])
    op.create_index("ix_pos_transactions_pending", "pos_transactions", ["tse_pending"])
    op.create_index("ix_pos_transactions_cashier_finished", "pos_transactions", ["cashier_user_id", "finished_at"])

    op.create_table(
        "pos_transaction_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pos_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pos_transactions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sku", sa.Text, nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column("quantity_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("unit_price", sa.Numeric(10, 4), nullable=False),
        sa.Column("line_total_net", sa.Numeric(10, 2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_pos_transaction_lines_tx", "pos_transaction_lines", ["pos_transaction_id"])

    op.create_table(
        "tse_signing_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "pos_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pos_transactions.id"),
            nullable=True,
        ),
        sa.Column("operation", sa.Text, nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("succeeded", sa.Boolean, nullable=False),
        sa.Column("error_code", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
    )
    op.create_index("ix_tse_signing_log_tx", "tse_signing_log", ["pos_transaction_id"])
    op.create_index("ix_tse_signing_log_attempted", "tse_signing_log", ["attempted_at"])


def downgrade() -> None:
    op.drop_table("tse_signing_log")
    op.drop_table("pos_transaction_lines")
    op.drop_table("pos_transactions")
    op.execute("DROP SEQUENCE IF EXISTS receipt_number_seq")
