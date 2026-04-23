from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_staff
from app.models import PosTransaction


router = APIRouter(prefix="/api/pos-transactions", tags=["pos-transactions"])


@router.get("", dependencies=[Depends(require_any_staff)])
async def list_pos_transactions(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(PosTransaction)
        .order_by(desc(PosTransaction.receipt_number))
        .limit(limit).offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "receipt_number": r.receipt_number,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "total_gross": str(r.total_gross),
                "payment_breakdown": r.payment_breakdown,
                "tse_pending": r.tse_pending,
                "voids_transaction_id": (
                    str(r.voids_transaction_id) if r.voids_transaction_id else None
                ),
            }
            for r in rows
        ],
        "limit": limit, "offset": offset,
    }
