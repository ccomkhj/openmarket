import uuid
import httpx
import pytest
import respx

from app.fiscal.service import FiscalService, StartResult
from app.fiscal.client import FiscalClient
from tests.fiscal_helpers import mock_auth_ok, mock_tx_start_ok, mock_tx_finish_ok
from datetime import datetime, timezone


BASE = "https://mock-fiskaly.test"


def _svc() -> FiscalService:
    client = FiscalClient(
        api_key="k", api_secret="s", tss_id="tss-abc", base_url=BASE,
        http=httpx.AsyncClient(timeout=5),
    )
    return FiscalService(client=client)


@pytest.mark.asyncio
@respx.mock
async def test_start_transaction_returns_fiskaly_tx_id():
    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)

    result = await _svc().start_transaction(client_id=client_id)

    assert isinstance(result, StartResult)
    assert result.tx_id == client_id
    assert result.state == "ACTIVE"


@pytest.mark.asyncio
@respx.mock
async def test_finish_transaction_returns_signature():
    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)
    mock_tx_finish_ok(
        respx.mock, "tss-abc", str(client_id), BASE,
        signature="MEUCIQD-sig", signature_counter=4728,
        tss_serial="serial-abc123",
        time_start=1_745_000_000, time_end=1_745_000_030,
    )

    svc = _svc()
    start = await svc.start_transaction(client_id=client_id)
    finish = await svc.finish_transaction(
        tx_id=client_id,
        latest_revision=start.latest_revision,
        process_data="Beleg^1.13_0.00_0.00_0.00_0.00^1.13:Bar",
        process_type="Kassenbeleg-V1",
    )

    assert finish.signature == "MEUCIQD-sig"
    assert finish.signature_counter == 4728
    assert finish.tss_serial == "serial-abc123"
    assert finish.time_start == datetime(2025, 4, 18, 16, 53, 20, tzinfo=timezone.utc)
    assert finish.time_end == datetime(2025, 4, 18, 16, 53, 50, tzinfo=timezone.utc)
    assert finish.process_type == "Kassenbeleg-V1"


from sqlalchemy import select
from app.models import TseSigningLog
from app.fiscal.errors import FiscalServerError


def _svc_with_db(db):
    client = FiscalClient(
        api_key="k", api_secret="s", tss_id="tss-abc", base_url=BASE,
        http=httpx.AsyncClient(timeout=5),
    )
    return FiscalService(client=client, db=db)


@pytest.mark.asyncio
@respx.mock
async def test_signing_log_records_success(db):
    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(client_id), BASE)

    svc = _svc_with_db(db)
    await svc.start_transaction(client_id=client_id)

    rows = (await db.execute(select(TseSigningLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].operation == "start_transaction"
    assert rows[0].succeeded is True
    assert rows[0].error_code is None


@pytest.mark.asyncio
@respx.mock
async def test_signing_log_records_failure(db):
    client_id = uuid.uuid4()
    mock_auth_ok(respx.mock, BASE)
    respx.mock.put(f"{BASE}/api/v2/tss/tss-abc/tx/{client_id}").respond(503)

    svc = _svc_with_db(db)
    with pytest.raises(FiscalServerError):
        await svc.start_transaction(client_id=client_id)

    rows = (await db.execute(select(TseSigningLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].succeeded is False
    assert rows[0].error_code == "FISCAL_SERVER"


from app.models import PosTransaction


@pytest.mark.asyncio
@respx.mock
async def test_retry_pending_signatures_completes_pending_rows(db):
    from app.services.password import hash_pin
    from app.models import User
    c = User(email=None, password_hash=None, pin_hash=hash_pin("1234"),
             full_name="C", role="cashier")
    db.add(c); await db.commit(); await db.refresh(c)

    tid = uuid.uuid4()
    db.add(PosTransaction(
        id=tid, client_id=tid, cashier_user_id=c.id,
        started_at=datetime.now(tz=timezone.utc),
        tse_process_data="Beleg^1.29_0.00_0.00_0.00_0.00^1.29:Bar",
        receipt_number=1,
        tse_pending=True,
    ))
    await db.commit()

    mock_auth_ok(respx.mock, BASE)
    mock_tx_start_ok(respx.mock, "tss-abc", str(tid), BASE)
    mock_tx_finish_ok(respx.mock, "tss-abc", str(tid), BASE, signature="LATE-SIG", signature_counter=5001)

    svc = _svc_with_db(db)
    n = await svc.retry_pending_signatures()
    assert n == 1

    refreshed = (await db.execute(select(PosTransaction).where(PosTransaction.id == tid))).scalar_one()
    assert refreshed.tse_pending is False
    assert refreshed.tse_signature == "LATE-SIG"
