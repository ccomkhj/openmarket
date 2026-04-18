import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ws_rejects_unauthenticated(client: AsyncClient):
    # Without a session cookie, the upgrade should be rejected with 401/403.
    # httpx AsyncClient doesn't follow ws upgrades; we probe via direct GET.
    r = await client.get("/api/ws", headers={"Connection": "Upgrade", "Upgrade": "websocket"})
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ws_allows_authenticated(authed_client: AsyncClient):
    r = await authed_client.get(
        "/api/ws", headers={"Connection": "Upgrade", "Upgrade": "websocket"}
    )
    # An authed GET with no real ws handshake returns 400 or 426 (not 401/403).
    assert r.status_code not in (401, 403)
