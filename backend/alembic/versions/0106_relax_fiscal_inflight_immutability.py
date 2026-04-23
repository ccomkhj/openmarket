"""relax fiscal in-flight immutability

Revision ID: 0106_relax_fiscal_inflight_immutability
Revises: 0105_add_receipt_print_jobs
Create Date: 2026-04-22
"""
from alembic import op

revision = "0106_relax_fiscal_inflight_immutability"
down_revision = "0105_add_receipt_print_jobs"
branch_labels = None
depends_on = None


REJECT_FN_V2 = """
CREATE OR REPLACE FUNCTION fiscal_reject_modification() RETURNS trigger AS $$
BEGIN
    IF current_setting('fiscal.signing', true) = 'on' THEN
        RETURN NEW;
    END IF;
    IF TG_TABLE_NAME = 'pos_transactions' AND TG_OP = 'UPDATE' THEN
        IF OLD.finished_at IS NULL AND NEW.finished_at IS NULL THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'Fiscal rows are immutable (TG_OP=%, table=%)', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(REJECT_FN_V2)


def downgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION fiscal_reject_modification() RETURNS trigger AS $$
    BEGIN
        IF current_setting('fiscal.signing', true) = 'on' THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Fiscal rows are immutable (TG_OP=%, table=%)', TG_OP, TG_TABLE_NAME;
    END;
    $$ LANGUAGE plpgsql;
    """)
