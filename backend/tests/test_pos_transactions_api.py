"""Tests for GET /api/pos-transactions (paginated listing)."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.models import PosTransaction, User
from app.services.password import hash_password
from app.services.session import create_session
from app.config import settings


async def _make_tx(db, cashier_id: int, receipt_number: int) -> PosTransaction:
    tx = PosTransaction(
        id=uuid.uuid4(),
        client_id=uuid.uuid4(),
        cashier_user_id=cashier_id,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        total_gross=Decimal("9.99"),
        total_net=Decimal("8.40"),
        vat_breakdown={},
        payment_breakdown={"cash": "9.99"},
        receipt_number=receipt_number,
        tse_pending=False,
    )
    db.add(tx)
    await db.commit()
    return tx


@pytest.mark.asyncio
async def test_list_pos_transactions_most_recent_first(authed_client, db, owner):
    tx1 = await _make_tx(db, owner.id, 1)
    tx2 = await _make_tx(db, owner.id, 2)
    tx3 = await _make_tx(db, owner.id, 3)

    r = await authed_client.get("/api/pos-transactions")
    assert r.status_code == 200
    data = r.json()
    receipt_numbers = [item["receipt_number"] for item in data["items"]]
    # Should be most-recent first (descending receipt_number)
    assert receipt_numbers == sorted(receipt_numbers, reverse=True)
    assert len(receipt_numbers) == 3
    assert tx3.receipt_number in receipt_numbers


@pytest.mark.asyncio
async def test_list_pos_transactions_requires_staff(client, db):
    r = await client.get("/api/pos-transactions")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_pos_transactions_pagination(authed_client, db, owner):
    for i in range(1, 6):
        await _make_tx(db, owner.id, i)

    r = await authed_client.get("/api/pos-transactions?limit=2&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0
    # First page should have highest receipt numbers
    first_page_nums = [it["receipt_number"] for it in data["items"]]
    assert max(first_page_nums) == 5

    r2 = await authed_client.get("/api/pos-transactions?limit=2&offset=2")
    data2 = r2.json()
    assert len(data2["items"]) == 2
    second_page_nums = [it["receipt_number"] for it in data2["items"]]
    # Second page should not overlap with first
    assert not set(first_page_nums) & set(second_page_nums)
