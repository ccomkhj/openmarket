from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import KassenbuchEntry, User
from app.services.kassenbuch import KassenbuchService
from app.services.password import hash_pin


async def _cashier(db) -> User:
    u = User(email=None, password_hash=None, pin_hash=hash_pin("1234"),
             full_name="A", role="cashier")
    db.add(u); await db.commit(); await db.refresh(u)
    return u


@pytest.mark.asyncio
async def test_open_writes_entry(db):
    c = await _cashier(db)
    svc = KassenbuchService(db=db)
    e = await svc.open_shift(
        cashier_user_id=c.id,
        denominations={"50": 1, "20": 5, "10": 10, "5": 4, "1": 20},
    )
    assert e.entry_type == "open"
    assert e.amount == Decimal("290.00")


@pytest.mark.asyncio
async def test_paid_in_requires_reason(db):
    c = await _cashier(db)
    svc = KassenbuchService(db=db)
    with pytest.raises(ValueError, match="reason"):
        await svc.paid_in(cashier_user_id=c.id, amount=Decimal("10"), reason="")


@pytest.mark.asyncio
async def test_close_computes_difference(db):
    c = await _cashier(db)
    svc = KassenbuchService(db=db)
    await svc.open_shift(cashier_user_id=c.id, denominations={"100": 1})
    await svc.paid_in(cashier_user_id=c.id, amount=Decimal("10"), reason="float top-up")
    await svc.paid_out(cashier_user_id=c.id, amount=Decimal("5"), reason="bread delivery")
    summary = await svc.close_shift(
        cashier_user_id=c.id,
        denominations={"100": 1, "5": 1},
    )
    assert summary.expected == Decimal("105.00")
    assert summary.counted == Decimal("105.00")
    assert summary.difference == Decimal("0.00")
    rows = (await db.execute(select(KassenbuchEntry))).scalars().all()
    assert {r.entry_type for r in rows} == {"open", "paid_in", "paid_out", "close"}
