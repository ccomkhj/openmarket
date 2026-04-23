"""Receipt reprint + printer health endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_staff
from app.config import settings
from app.receipt.builder import ReceiptBuilder
from app.receipt.printer import get_backend
from app.receipt.service import ReceiptService


router = APIRouter(prefix="/api", tags=["receipts"])


@router.post(
    "/receipts/{pos_transaction_id}/reprint",
    dependencies=[Depends(require_any_staff)],
)
async def reprint(pos_transaction_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    svc = ReceiptService(db=db, builder=ReceiptBuilder.from_settings(settings), backend=get_backend())
    try:
        job = await svc.print_receipt(pos_transaction_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {
        "id": job.id,
        "pos_transaction_id": str(job.pos_transaction_id),
        "status": job.status,
        "attempts": job.attempts,
        "last_error": job.last_error,
        "printed_at": job.printed_at.isoformat() if job.printed_at else None,
    }


@router.get("/health/printer", dependencies=[Depends(require_any_staff)])
async def health_printer():
    backend = get_backend()
    return {"online": backend.is_online(), "paper_ok": backend.is_paper_ok()}
