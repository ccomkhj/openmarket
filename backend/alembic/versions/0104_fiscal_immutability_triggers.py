"""fiscal immutability triggers

Revision ID: 0104_fiscal_immutability_triggers
Revises: 0103_add_pos_transaction_tables
Create Date: 2026-04-22
"""
from alembic import op

revision = "0104_fiscal_immutability_triggers"
down_revision = "0103_add_pos_transaction_tables"
branch_labels = None
depends_on = None


REJECT_FN = """
CREATE OR REPLACE FUNCTION fiscal_reject_modification() RETURNS trigger AS $$
BEGIN
    -- Allow only the narrow signature-writeback path: UPDATE permitted when
    -- the caller sets session var `fiscal.signing=on`. Any other UPDATE or
    -- DELETE is rejected — fiscal rows are append-only by KassenSichV.
    IF current_setting('fiscal.signing', true) = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Fiscal rows are immutable (TG_OP=%, table=%)', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(REJECT_FN)
    for tbl in ("pos_transactions", "pos_transaction_lines", "tse_signing_log"):
        op.execute(f"""
            CREATE TRIGGER {tbl}_reject_update
            BEFORE UPDATE ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION fiscal_reject_modification();
        """)
        op.execute(f"""
            CREATE TRIGGER {tbl}_reject_delete
            BEFORE DELETE ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION fiscal_reject_modification();
        """)


def downgrade() -> None:
    for tbl in ("pos_transactions", "pos_transaction_lines", "tse_signing_log"):
        op.execute(f"DROP TRIGGER IF EXISTS {tbl}_reject_update ON {tbl}")
        op.execute(f"DROP TRIGGER IF EXISTS {tbl}_reject_delete ON {tbl}")
    op.execute("DROP FUNCTION IF EXISTS fiscal_reject_modification()")
