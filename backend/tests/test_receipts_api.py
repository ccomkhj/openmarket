import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.models import PosTransaction, PosTransactionLine, User
from app.services.password import hash_pin


async def _seed(db) -> uuid.UUID:
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1234"),
             full_name="A", role="cashier")
    db.add(c); await db.commit(); await db.refresh(c)
    tid = uuid.uuid4()
    db.add(PosTransaction(
        id=tid, client_id=tid, cashier_user_id=c.id,
        started_at=datetime.now(tz=timezone.utc),
        finished_at=datetime.now(tz=timezone.utc),
        total_gross=Decimal("1"), total_net=Decimal("1"),
        vat_breakdown={"7": {"net": "0.93", "vat": "0.07", "gross": "1.00"}},
        payment_breakdown={"cash": "1.00"},
        receipt_number=100,
        tse_signature="SIG", tse_signature_counter=1, tse_serial="SER",
        tse_timestamp_start=datetime.now(tz=timezone.utc),
        tse_timestamp_finish=datetime.now(tz=timezone.utc),
        tse_process_type="Kassenbeleg-V1",
    ))
    db.add(PosTransactionLine(
        pos_transaction_id=tid, title="X", quantity=Decimal("1"),
        unit_price=Decimal("1"), line_total_net=Decimal("0.93"),
        vat_rate=Decimal("7"), vat_amount=Decimal("0.07"),
    ))
    await db.commit()
    return tid


@pytest.mark.asyncio
async def test_reprint_requires_staff(client, db):
    tid = await _seed(db)
    r = await client.post(f"/api/receipts/{tid}/reprint")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_reprint_returns_job_status(authed_client, db):
    tid = await _seed(db)
    r = await authed_client.post(f"/api/receipts/{tid}/reprint")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("printed", "buffered")
    assert body["pos_transaction_id"] == str(tid)


@pytest.mark.asyncio
async def test_health_printer_reports_state(authed_client):
    r = await authed_client.get("/api/health/printer")
    assert r.status_code == 200
    body = r.json()
    assert "online" in body and "paper_ok" in body
