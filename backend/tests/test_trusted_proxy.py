from unittest.mock import MagicMock

from app.api.auth import _client_ip


def _request(remote_host: str, xff: str | None):
    req = MagicMock()
    req.client = MagicMock(host=remote_host)
    headers: dict[str, str] = {}
    if xff is not None:
        headers["X-Forwarded-For"] = xff
    req.headers.get = lambda k: headers.get(k)
    return req


def test_direct_caller_uses_remote_host():
    req = _request("8.8.8.8", None)
    assert _client_ip(req) == "8.8.8.8"


def test_ignores_xff_from_untrusted_caller():
    # Attacker on public internet sends XFF: 192.168.1.5
    req = _request("8.8.8.8", "192.168.1.5")
    assert _client_ip(req) == "8.8.8.8"


def test_honors_xff_from_trusted_proxy():
    # Default trusted proxy list is 127.0.0.1/32; simulate loopback forwarding
    req = _request("127.0.0.1", "192.168.1.5, 10.0.0.1")
    assert _client_ip(req) == "192.168.1.5"


def test_honors_xff_with_whitespace():
    req = _request("127.0.0.1", "  192.168.1.23  ")
    assert _client_ip(req) == "192.168.1.23"


def test_handles_missing_client():
    req = MagicMock()
    req.client = None
    req.headers.get = lambda k: None
    assert _client_ip(req) == "0.0.0.0"
