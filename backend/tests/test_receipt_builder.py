import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.receipt.builder import ReceiptBuilder
from app.models import PosTransaction, PosTransactionLine


GOLDENS = Path(__file__).parent / "goldens"
UPDATE = os.environ.get("UPDATE_GOLDENS") == "1"


def _fixture_transaction() -> tuple[PosTransaction, list[PosTransactionLine]]:
    tx_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    tx = PosTransaction(
        id=tx_id, client_id=tx_id,
        cashier_user_id=1,
        started_at=datetime(2026, 4, 18, 14, 23, 12, tzinfo=timezone.utc),
        finished_at=datetime(2026, 4, 18, 14, 23, 42, tzinfo=timezone.utc),
        total_gross=Decimal("1.29"),
        total_net=Decimal("1.21"),
        vat_breakdown={"7": {"net": "1.21", "vat": "0.08", "gross": "1.29"}},
        payment_breakdown={"cash": "1.29"},
        receipt_number=847,
        tse_signature="MEUCIQD-fake",
        tse_signature_counter=4728,
        tse_serial="serial-abc123",
        tse_timestamp_start=datetime(2026, 4, 18, 14, 23, 12, 41000, tzinfo=timezone.utc),
        tse_timestamp_finish=datetime(2026, 4, 18, 14, 23, 41, 892000, tzinfo=timezone.utc),
        tse_process_type="Kassenbeleg-V1",
    )
    lines = [
        PosTransactionLine(
            pos_transaction_id=tx_id,
            title="Milch 1L",
            quantity=Decimal("1"),
            quantity_kg=None,
            unit_price=Decimal("1.29"),
            line_total_net=Decimal("1.21"),
            vat_rate=Decimal("7"),
            vat_amount=Decimal("0.08"),
        ),
    ]
    return tx, lines


def test_render_matches_golden():
    tx, lines = _fixture_transaction()
    out = ReceiptBuilder(
        merchant_name="Voids Market",
        merchant_address="Street 1, 12345 Berlin",
        merchant_tax_id="12/345/67890",
        merchant_vat_id="DE123456789",
        cashier_display="Anna M.",
        register_id="KASSE-01",
    ).render(tx, lines)

    golden = GOLDENS / "receipt_basic_cash.escpos"
    if UPDATE or not golden.exists():
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_bytes(out)
        pytest.skip("golden written; re-run without UPDATE_GOLDENS=1")
    assert out == golden.read_bytes(), (
        "Receipt bytes diverged from golden. If intentional, rerun with "
        "UPDATE_GOLDENS=1 and commit the updated golden file."
    )
