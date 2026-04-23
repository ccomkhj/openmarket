from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_any_staff
from app.models import KassenbuchEntry
from app.services.kassenbuch import KassenbuchService


router = APIRouter(prefix="/api/kassenbuch", tags=["kassenbuch"])


class OpenReq(BaseModel):
    denominations: dict[str, int]


class CloseReq(BaseModel):
    denominations: dict[str, int]


class CashMoveReq(BaseModel):
    amount: Decimal
    reason: str


@router.post("/open", status_code=201, dependencies=[Depends(require_any_staff)])
async def open_shift(body: OpenReq, db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    e = await KassenbuchService(db=db).open_shift(
        cashier_user_id=user.id, denominations=body.denominations,
    )
    return {"id": str(e.id), "type": e.entry_type, "amount": str(e.amount)}


@router.post("/paid-in", status_code=201, dependencies=[Depends(require_any_staff)])
async def paid_in(body: CashMoveReq, db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    try:
        e = await KassenbuchService(db=db).paid_in(
            cashier_user_id=user.id, amount=body.amount, reason=body.reason,
        )
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return {"id": str(e.id), "type": e.entry_type, "amount": str(e.amount)}


@router.post("/paid-out", status_code=201, dependencies=[Depends(require_any_staff)])
async def paid_out(body: CashMoveReq, db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    try:
        e = await KassenbuchService(db=db).paid_out(
            cashier_user_id=user.id, amount=body.amount, reason=body.reason,
        )
    except ValueError as ex:
        raise HTTPException(400, str(ex))
    return {"id": str(e.id), "type": e.entry_type, "amount": str(e.amount)}


@router.post("/close", status_code=201, dependencies=[Depends(require_any_staff)])
async def close_shift(body: CloseReq, db: AsyncSession = Depends(get_db), user = Depends(get_current_user)):
    summary = await KassenbuchService(db=db).close_shift(
        cashier_user_id=user.id, denominations=body.denominations,
    )
    return {
        "id": str(summary.entry.id),
        "expected": str(summary.expected),
        "counted": str(summary.counted),
        "difference": str(summary.difference),
    }


@router.get("/status", dependencies=[Depends(require_any_staff)])
async def status(db: AsyncSession = Depends(get_db)):
    last = (await db.execute(
        select(KassenbuchEntry).order_by(desc(KassenbuchEntry.timestamp)).limit(1)
    )).scalar_one_or_none()
    is_open = last is not None and last.entry_type != "close"
    return {"open": is_open}
