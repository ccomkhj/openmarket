"""Shared fiskaly respx fixtures."""
import httpx
import respx


def mock_auth_ok(respx_mock: respx.MockRouter, base_url: str = "https://mock-fiskaly.test") -> None:
    respx_mock.post(f"{base_url}/api/v2/auth").respond(
        json={"access_token": "token-abc", "access_token_expires_in": 300, "refresh_token": "rt"}
    )


def mock_tx_start_ok(
    respx_mock: respx.MockRouter,
    tss_id: str, tx_id: str, base_url: str = "https://mock-fiskaly.test",
) -> None:
    respx_mock.put(f"{base_url}/api/v2/tss/{tss_id}/tx/{tx_id}").respond(
        json={
            "_id": tx_id,
            "state": "ACTIVE",
            "number": 1,
            "latest_revision": 1,
            "time_start": 1_745_000_000,
        }
    )


def mock_tx_finish_ok(
    respx_mock: respx.MockRouter,
    tss_id: str, tx_id: str, base_url: str = "https://mock-fiskaly.test",
    signature: str = "MEUCIQD-fake-signature",
    signature_counter: int = 4728,
    tss_serial: str = "serial-abc123",
    time_start: int = 1_745_000_000, time_end: int = 1_745_000_030,
) -> None:
    respx_mock.put(
        url__regex=rf"{base_url}/api/v2/tss/{tss_id}/tx/{tx_id}\?last_revision=.+"
    ).respond(
        json={
            "_id": tx_id,
            "state": "FINISHED",
            "signature": {"value": signature, "counter": signature_counter},
            "tss_serial_number": tss_serial,
            "time_start": time_start,
            "time_end": time_end,
        }
    )
