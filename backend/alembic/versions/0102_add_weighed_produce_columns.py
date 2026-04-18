"""add weighed-produce columns to product_variants and line_items

Revision ID: 0102_add_weighed
Revises: 0101_audit_immutable
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0102_add_weighed"
down_revision = "0101_audit_immutable"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("product_variants", sa.Column("pricing_type", sa.String, nullable=False, server_default="fixed"))
    op.add_column("product_variants", sa.Column("weight_unit", sa.String, nullable=True))
    op.add_column("product_variants", sa.Column("min_weight_kg", sa.Numeric(10, 3), nullable=True))
    op.add_column("product_variants", sa.Column("max_weight_kg", sa.Numeric(10, 3), nullable=True))
    op.add_column("product_variants", sa.Column("tare_kg", sa.Numeric(10, 3), nullable=True))
    op.add_column("product_variants", sa.Column("barcode_format", sa.String, nullable=False, server_default="standard"))
    op.add_column("line_items", sa.Column("quantity_kg", sa.Numeric(10, 3), nullable=True))


def downgrade():
    op.drop_column("line_items", "quantity_kg")
    op.drop_column("product_variants", "barcode_format")
    op.drop_column("product_variants", "tare_kg")
    op.drop_column("product_variants", "max_weight_kg")
    op.drop_column("product_variants", "min_weight_kg")
    op.drop_column("product_variants", "weight_unit")
    op.drop_column("product_variants", "pricing_type")
