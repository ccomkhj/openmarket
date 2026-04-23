import httpx
import pytest
import respx

from app.fiscal.client import FiscalClient
from app.fiscal.errors import FiscalAuthError, FiscalNotConfiguredError, FiscalServerError
from tests.fiscal_helpers import mock_auth_ok, mock_tx_start_ok


BASE = "https://mock-fiskaly.test"


def _client(**overrides) -> FiscalClient:
    defaults = dict(
        api_key="key-123", api_secret="secret-456", tss_id="tss-abc",
        base_url=BASE,
    )
    defaults.update(overrides)
    return FiscalClient(**defaults)


@pytest.mark.asyncio
@respx.mock
async def test_authenticate_caches_token():
    mock_auth_ok(respx.mock, BASE)
    c = _client()
    t1 = await c._get_token()
    t2 = await c._get_token()
    assert t1 == t2 == "token-abc"
    assert respx.mock.calls.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_authenticate_failure_raises():
    respx.mock.post(f"{BASE}/api/v2/auth").respond(401, json={"error": "bad creds"})
    with pytest.raises(FiscalAuthError):
        await _client()._get_token()


@pytest.mark.asyncio
async def test_not_configured_raises():
    c = _client(api_key="", api_secret="", tss_id="")
    with pytest.raises(FiscalNotConfiguredError):
        await c._get_token()


@pytest.mark.asyncio
@respx.mock
async def test_retries_on_5xx_then_succeeds():
    mock_auth_ok(respx.mock, BASE)
    route = respx.mock.put(f"{BASE}/api/v2/tss/tss-abc/tx/tx-1")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(503),
        httpx.Response(200, json={"_id": "tx-1", "state": "ACTIVE"}),
    ]
    c = _client()
    result = await c.put(f"/api/v2/tss/tss-abc/tx/tx-1", json={"state": "ACTIVE"})
    assert result["state"] == "ACTIVE"
    assert route.call_count == 3


@pytest.mark.asyncio
@respx.mock
async def test_retries_exhausted_raises_server_error():
    mock_auth_ok(respx.mock, BASE)
    respx.mock.put(f"{BASE}/api/v2/tss/tss-abc/tx/tx-1").respond(503)
    c = _client()
    with pytest.raises(FiscalServerError):
        await c.put("/api/v2/tss/tss-abc/tx/tx-1", json={})
