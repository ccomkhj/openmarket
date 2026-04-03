import pytest
from app.main import app
from app.ws.manager import manager


def test_websocket_connect():
    from starlette.testclient import TestClient

    with TestClient(app) as tc:
        with tc.websocket_connect("/api/ws") as ws:
            assert len(manager.active_connections) == 1
        assert len(manager.active_connections) == 0
