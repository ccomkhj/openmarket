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
