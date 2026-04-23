"""Test DsfinvkExporter — produces a valid ZIP with expected files."""
import io
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

from app.models import KassenbuchEntry, PosTransaction, PosTransactionLine, User
from app.reports.dsfinvk import DsfinvkExporter
from app.services.password import hash_pin


EXPECTED_FILES = {
    "bonkopf.csv",
    "bonpos.csv",
    "bonkopf_zahlarten.csv",
    "tse.csv",
    "cash_per_currency.csv",
    "index.xml",
}


def _ts(offset_minutes: int = 0) -> datetime:
    base = datetime(2026, 4, 1, 8, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(minutes=offset_minutes)


async def _cashier(db) -> User:
    u = User(
        email=None, password_hash=None, pin_hash=hash_pin("7777"),
        full_name="DSFinV-K Cashier", role="cashier",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.mark.asyncio
async def test_dsfinvk_export_produces_valid_zip(db):
    cashier = await _cashier(db)

    # One transaction with one line
    tx_id = uuid.uuid4()
    tx = PosTransaction(
        id=tx_id, client_id=tx_id,
        cashier_user_id=cashier.id,
        started_at=_ts(10),
        total_gross=Decimal("2.50"), total_net=Decimal("2.34"),
        vat_breakdown={"reduced": {"net": "2.34", "vat": "0.16", "gross": "2.50"}},
        payment_breakdown={"cash": "2.50"},
        receipt_number=2001,
        tse_pending=False,
        tse_signature="SIG-TEST",
        tse_signature_counter=42,
        tse_serial="SERIAL-XYZ",
    )
    db.add(tx)
    await db.flush()

    ln = PosTransactionLine(
        pos_transaction_id=tx_id,
        sku="BREAD-001", title="Sourdough 500g",
        quantity=Decimal("1.000"), quantity_kg=None,
        unit_price=Decimal("2.5000"),
        line_total_net=Decimal("2.34"),
        vat_rate=Decimal("7.00"),
        vat_amount=Decimal("0.16"),
    )
    db.add(ln)

    # One kassenbuch entry
    db.add(KassenbuchEntry(
        entry_type="open", amount=Decimal("100.00"),
        denominations={}, cashier_user_id=cashier.id, timestamp=_ts(0),
    ))
    await db.commit()

    exporter = DsfinvkExporter(db=db)
    raw = await exporter.export(date_from=_ts(-1), date_to=_ts(60))

    # Must be a valid ZIP
    assert zipfile.is_zipfile(io.BytesIO(raw))

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert names == EXPECTED_FILES

        bonkopf_content = zf.read("bonkopf.csv").decode("utf-8-sig")
        assert "Z_KASSE_ID" in bonkopf_content
        assert "BON_ID" in bonkopf_content
        assert str(tx_id) in bonkopf_content

        bonpos_content = zf.read("bonpos.csv").decode("utf-8-sig")
        assert "Sourdough 500g" in bonpos_content

        zahlarten_content = zf.read("bonkopf_zahlarten.csv").decode("utf-8-sig")
        assert "cash" in zahlarten_content
        assert "Bar" in zahlarten_content

        tse_content = zf.read("tse.csv").decode("utf-8-sig")
        assert "SIG-TEST" in tse_content

        index_content = zf.read("index.xml").decode("utf-8")
        assert "bonkopf.csv" in index_content
        assert "DSFinV-K" in index_content


@pytest.mark.asyncio
async def test_dsfinvk_export_empty_range_still_produces_zip(db):
    """Even with no data, a valid ZIP with all 6 files must be returned."""
    exporter = DsfinvkExporter(db=db)
    raw = await exporter.export(date_from=_ts(0), date_to=_ts(480))

    assert zipfile.is_zipfile(io.BytesIO(raw))
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        assert set(zf.namelist()) == EXPECTED_FILES
