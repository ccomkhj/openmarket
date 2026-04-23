"""Receipt reprint + printer health endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_staff
from app.config import settings
from app.receipt.builder import ReceiptBuilder
from app.receipt.errors import PrinterUnavailableError
from app.receipt.printer import DummyBackend, PrinterBackend, UsbBackend
from app.receipt.service import ReceiptService


router = APIRouter(prefix="/api", tags=["receipts"])


def _builder() -> ReceiptBuilder:
    return ReceiptBuilder(
        merchant_name="Voids Market",
        merchant_address="Street 1, 12345 Berlin",
        merchant_tax_id="12/345/67890",
        merchant_vat_id="DE123456789",
        cashier_display="",
        register_id="KASSE-01",
    )


def _backend() -> PrinterBackend:
    if not settings.printer_vendor_id:
        return DummyBackend()
    try:
        return UsbBackend(
            vendor_id=settings.printer_vendor_id,
            product_id=settings.printer_product_id,
            profile=settings.printer_profile,
        )
    except PrinterUnavailableError:
        return DummyBackend(online=False)


@router.post(
    "/receipts/{pos_transaction_id}/reprint",
    dependencies=[Depends(require_any_staff)],
)
async def reprint(pos_transaction_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    svc = ReceiptService(db=db, builder=_builder(), backend=_backend())
    try:
        job = await svc.reprint(pos_transaction_id)
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
    backend = _backend()
    return {"online": backend.is_online(), "paper_ok": backend.is_paper_ok()}
