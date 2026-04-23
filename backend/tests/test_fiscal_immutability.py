import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, update
from sqlalchemy.exc import DBAPIError

from app.models import PosTransaction, TseSigningLog, User
from app.services.password import hash_pin


async def _cashier(db):
    u = User(email=None, password_hash=None, pin_hash=hash_pin("1234"),
             full_name="A", role="cashier")
    db.add(u); await db.commit(); await db.refresh(u)
    return u


async def _seed_tx(db) -> uuid.UUID:
    c = await _cashier(db)
    tid = uuid.uuid4()
    db.add(PosTransaction(
        id=tid, client_id=tid, cashier_user_id=c.id,
        started_at=datetime.now(tz=timezone.utc),
        receipt_number=9999,
    ))
    await db.commit()
    return tid


@pytest.mark.asyncio
async def test_update_on_pos_transaction_rejected(db):
    tid = await _seed_tx(db)
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute(
            update(PosTransaction)
            .where(PosTransaction.id == tid)
            .values(total_gross=Decimal("999"))
        )
        await db.commit()


@pytest.mark.asyncio
async def test_delete_on_pos_transaction_rejected(db):
    tid = await _seed_tx(db)
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute(delete(PosTransaction).where(PosTransaction.id == tid))
        await db.commit()


@pytest.mark.asyncio
async def test_delete_on_tse_signing_log_rejected(db):
    tid = await _seed_tx(db)
    db.add(TseSigningLog(
        pos_transaction_id=tid, operation="start_transaction",
        attempted_at=datetime.now(tz=timezone.utc), succeeded=True,
    ))
    await db.commit()
    with pytest.raises(DBAPIError, match="immutable"):
        await db.execute(delete(TseSigningLog))
        await db.commit()
