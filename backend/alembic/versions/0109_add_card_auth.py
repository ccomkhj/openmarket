"""add card_auths table

Revision ID: 0109_add_card_auth
Revises: 0108_add_variant_vat_rate
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0109_add_card_auth"
down_revision = "0108_add_variant_vat_rate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_auths",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pos_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pos_transactions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("approved", sa.Boolean, nullable=False),
        sa.Column("response_code", sa.Text, nullable=False),
        sa.Column("auth_code", sa.Text, nullable=False),
        sa.Column("trace_number", sa.Text, nullable=False),
        sa.Column("terminal_id", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("card_auths")
