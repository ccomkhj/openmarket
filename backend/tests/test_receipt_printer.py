import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import (
    PosTransaction, PosTransactionLine, ReceiptPrintJob, User,
)
from app.receipt.builder import ReceiptBuilder
from app.receipt.printer import DummyBackend
from app.receipt.service import ReceiptService
from app.services.password import hash_pin


def _builder() -> ReceiptBuilder:
    return ReceiptBuilder(
        merchant_name="Voids Market", merchant_address="Street 1",
        merchant_tax_id="12/345/67890", merchant_vat_id="DE123456789",
        cashier_display="Anna", register_id="KASSE-01",
    )


async def _seed_tx(db, *, receipt_number: int = 1) -> PosTransaction:
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1234"),
             full_name="A", role="cashier")
    db.add(c); await db.commit(); await db.refresh(c)
    tid = uuid.uuid4()
    tx = PosTransaction(
        id=tid, client_id=tid, cashier_user_id=c.id,
        started_at=datetime.now(tz=timezone.utc),
        finished_at=datetime.now(tz=timezone.utc),
        total_gross=Decimal("1.29"), total_net=Decimal("1.21"),
        vat_breakdown={"7": {"net": "1.21", "vat": "0.08", "gross": "1.29"}},
        payment_breakdown={"cash": "1.29"},
        receipt_number=receipt_number,
        tse_signature="SIG", tse_signature_counter=1, tse_serial="SER",
        tse_timestamp_start=datetime.now(tz=timezone.utc),
        tse_timestamp_finish=datetime.now(tz=timezone.utc),
        tse_process_type="Kassenbeleg-V1",
    )
    db.add(tx)
    db.add(PosTransactionLine(
        pos_transaction_id=tid, title="Milk", quantity=Decimal("1"),
        unit_price=Decimal("1.29"), line_total_net=Decimal("1.21"),
        vat_rate=Decimal("7"), vat_amount=Decimal("0.08"),
    ))
    await db.commit()
    return tx


@pytest.mark.asyncio
async def test_print_receipt_happy_path(db):
    tx = await _seed_tx(db)
    backend = DummyBackend()
    svc = ReceiptService(db=db, builder=_builder(), backend=backend)

    job = await svc.print_receipt(tx.id)

    assert job.status == "printed"
    assert len(backend.buffer) > 0
    assert job.printed_at is not None


@pytest.mark.asyncio
async def test_print_receipt_buffers_on_paper_out(db):
    tx = await _seed_tx(db, receipt_number=2)
    backend = DummyBackend(paper_ok=False)
    svc = ReceiptService(db=db, builder=_builder(), backend=backend)

    job = await svc.print_receipt(tx.id)

    assert job.status == "buffered"
    assert "paper" in (job.last_error or "").lower()


@pytest.mark.asyncio
async def test_print_receipt_buffers_on_offline(db):
    tx = await _seed_tx(db, receipt_number=3)
    backend = DummyBackend(online=False)
    svc = ReceiptService(db=db, builder=_builder(), backend=backend)

    job = await svc.print_receipt(tx.id)

    assert job.status == "buffered"


@pytest.mark.asyncio
async def test_reprint_runs_pending_and_buffered(db):
    tx = await _seed_tx(db, receipt_number=4)
    offline = DummyBackend(online=False)
    svc_off = ReceiptService(db=db, builder=_builder(), backend=offline)
    await svc_off.print_receipt(tx.id)

    online = DummyBackend()
    svc_on = ReceiptService(db=db, builder=_builder(), backend=online)
    job = await svc_on.print_receipt(tx.id)

    assert job.status == "printed"
    assert len(online.buffer) > 0
    jobs = (await db.execute(
        select(ReceiptPrintJob).where(ReceiptPrintJob.pos_transaction_id == tx.id)
    )).scalars().all()
    assert len(jobs) == 2
    assert {j.status for j in jobs} == {"buffered", "printed"}


def test_dummy_backend_records_drawer_pulse():
    from app.receipt.printer import DummyBackend
    b = DummyBackend()
    b.pulse_cash_drawer()
    assert b.drawer_pulses == 1
    b.pulse_cash_drawer()
    assert b.drawer_pulses == 2
