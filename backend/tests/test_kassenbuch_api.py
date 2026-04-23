import pytest


@pytest.mark.asyncio
async def test_open_then_close_round_trip(cashier_client):
    r = await cashier_client.post("/api/kassenbuch/open", json={
        "denominations": {"50": 2, "10": 1},
    })
    assert r.status_code == 201
    assert r.json()["amount"] == "110.00"

    r = await cashier_client.post("/api/kassenbuch/paid-in", json={
        "amount": "5.00", "reason": "float top-up",
    })
    assert r.status_code == 201

    r = await cashier_client.post("/api/kassenbuch/close", json={
        "denominations": {"50": 2, "10": 1, "5": 1},
    })
    assert r.status_code == 201
    body = r.json()
    assert body["expected"] == "115.00"
    assert body["counted"] == "115.00"
    assert body["difference"] == "0.00"


@pytest.mark.asyncio
async def test_paid_out_without_reason_400(cashier_client):
    r = await cashier_client.post("/api/kassenbuch/paid-out", json={
        "amount": "5.00", "reason": "",
    })
    assert r.status_code == 400
