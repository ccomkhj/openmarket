"""Test ZReportBuilder aggregation."""
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

from app.models import KassenbuchEntry, PosTransaction, User
from app.reports.z_report import ZReportBuilder
from app.services.password import hash_pin


async def _cashier(db) -> User:
    u = User(
        email=None, password_hash=None, pin_hash=hash_pin("0000"),
        full_name="Z-Report Cashier", role="cashier",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def _ts(offset_minutes: int = 0) -> datetime:
    base = datetime(2026, 4, 1, 8, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(minutes=offset_minutes)


@pytest.mark.asyncio
async def test_z_report_full_shift(db):
    cashier = await _cashier(db)

    # Kassenbuch entries
    db.add(KassenbuchEntry(
        entry_type="open", amount=Decimal("200.00"),
        denominations={}, cashier_user_id=cashier.id, timestamp=_ts(0),
    ))
    db.add(KassenbuchEntry(
        entry_type="paid_in", amount=Decimal("50.00"),
        denominations={}, reason="coins", cashier_user_id=cashier.id, timestamp=_ts(30),
    ))
    db.add(KassenbuchEntry(
        entry_type="paid_out", amount=Decimal("-30.00"),
        denominations={}, reason="safe drop", cashier_user_id=cashier.id, timestamp=_ts(60),
    ))
    db.add(KassenbuchEntry(
        entry_type="close", amount=Decimal("315.00"),
        denominations={}, cashier_user_id=cashier.id, timestamp=_ts(480),
    ))

    # Two sales with different VAT rates
    receipt_seq = [1001, 1002]
    tx1_id = uuid.uuid4()
    tx1 = PosTransaction(
        id=tx1_id, client_id=tx1_id,
        cashier_user_id=cashier.id,
        started_at=_ts(10),
        total_gross=Decimal("2.50"), total_net=Decimal("2.34"),
        vat_breakdown={"normal": {"net": "2.34", "vat": "0.16", "gross": "2.50"}},
        payment_breakdown={"cash": "2.50"},
        receipt_number=receipt_seq[0],
        tse_pending=False,
        tse_signature_counter=10,
    )
    db.add(tx1)

    tx2_id = uuid.uuid4()
    tx2 = PosTransaction(
        id=tx2_id, client_id=tx2_id,
        cashier_user_id=cashier.id,
        started_at=_ts(20),
        total_gross=Decimal("1.29"), total_net=Decimal("1.21"),
        vat_breakdown={"reduced": {"net": "1.21", "vat": "0.08", "gross": "1.29"}},
        payment_breakdown={"card": "1.29"},
        receipt_number=receipt_seq[1],
        tse_pending=False,
        tse_signature_counter=11,
    )
    db.add(tx2)
    await db.commit()

    builder = ZReportBuilder(db=db)
    rpt = await builder.build(date_from=_ts(-1), date_to=_ts(490))

    assert rpt.opening_cash == Decimal("200.00")
    assert rpt.closing_counted == Decimal("315.00")
    assert rpt.paid_in_total == Decimal("50.00")
    assert rpt.paid_out_total == Decimal("30.00")

    assert rpt.transaction_count == 2

    assert "normal" in rpt.sales_by_vat
    assert rpt.sales_by_vat["normal"] == Decimal("2.50")
    assert "reduced" in rpt.sales_by_vat
    assert rpt.sales_by_vat["reduced"] == Decimal("1.29")

    assert rpt.sales_by_payment["cash"] == Decimal("2.50")
    assert rpt.sales_by_payment["card"] == Decimal("1.29")

    assert rpt.signature_counter_first == 10
    assert rpt.signature_counter_last == 11


@pytest.mark.asyncio
async def test_z_report_empty_shift(db):
    """Build a report for a window with no entries — should return zero defaults."""
    builder = ZReportBuilder(db=db)
    rpt = await builder.build(date_from=_ts(0), date_to=_ts(480))

    assert rpt.transaction_count == 0
    assert rpt.opening_cash == Decimal("0")
    assert rpt.closing_counted == Decimal("0")
    assert rpt.paid_in_total == Decimal("0")
    assert rpt.paid_out_total == Decimal("0")
    assert rpt.signature_counter_first is None
    assert rpt.signature_counter_last is None
    assert rpt.sales_by_vat == {}
    assert rpt.sales_by_payment == {}
