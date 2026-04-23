import uuid
import httpx
import pytest
import respx

from app.fiscal.service import FiscalService, StartResult
from app.fiscal.client import FiscalClient
from tests.fiscal_helpers import mock_auth_ok, mock_tx_start_ok


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
