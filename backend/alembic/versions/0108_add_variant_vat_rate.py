"""add product_variant.vat_rate

Revision ID: 0108_add_variant_vat_rate
Revises: 0107_add_kassenbuch_entries
"""
from alembic import op
import sqlalchemy as sa

revision = "0108_add_variant_vat_rate"
down_revision = "0107_add_kassenbuch_entries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_variants",
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False, server_default="19.00"),
    )


def downgrade() -> None:
    op.drop_column("product_variants", "vat_rate")
