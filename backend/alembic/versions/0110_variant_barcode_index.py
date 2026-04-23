"""variant barcode unique partial index

Revision ID: 0110_variant_barcode_index
Revises: 0109_add_card_auth
"""
from alembic import op

revision = "0110_variant_barcode_index"
down_revision = "0109_add_card_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_product_variants_barcode")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
            ix_product_variants_barcode_unique
        ON product_variants (barcode)
        WHERE barcode IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_product_variants_barcode_unique")
    op.execute("CREATE INDEX IF NOT EXISTS ix_product_variants_barcode ON product_variants (barcode)")
