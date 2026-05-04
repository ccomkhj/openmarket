"""add parked_sales table

Revision ID: 0111_parked_sales
Revises: 0110_variant_barcode_index
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0111_parked_sales"
down_revision = "0110_variant_barcode_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parked_sales",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "cashier_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Integer,
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("items", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("note", sa.String, nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_parked_sales_cashier", "parked_sales", ["cashier_user_id"])
    op.create_index("ix_parked_sales_created_at", "parked_sales", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_parked_sales_created_at", table_name="parked_sales")
    op.drop_index("ix_parked_sales_cashier", table_name="parked_sales")
    op.drop_table("parked_sales")
