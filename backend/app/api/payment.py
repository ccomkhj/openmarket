"""Payment endpoints: cash, card, terminal health."""
from __future__ import annotations

import uuid
from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_staff, get_current_user
from app.config import settings
from app.fiscal.client import FiscalClient
from app.fiscal.service import FiscalService
from app.payment.errors import (
    CardDeclinedError, TerminalUnavailableError,
)
from app.payment.service import PaymentService
from app.payment.terminal import MockTerminal, PaymentTerminalBackend
from app.payment.zvt import ZvtTerminal
from app.receipt.builder import ReceiptBuilder
from app.receipt.printer import get_backend
from app.receipt.service import ReceiptService
from app.services.pos_transaction import PosTransactionService


router = APIRouter(prefix="/api", tags=["payment"])


def _terminal() -> PaymentTerminalBackend:
    if not settings.terminal_host:
        return MockTerminal()
    return ZvtTerminal(
        host=settings.terminal_host,
        port=settings.terminal_port,
        password=settings.terminal_password,
    )


def _builder() -> ReceiptBuilder:
    return ReceiptBuilder(
        merchant_name=settings.merchant_name, merchant_address=settings.merchant_address,
        merchant_tax_id=settings.merchant_tax_id, merchant_vat_id=settings.merchant_vat_id,
        cashier_display="", register_id=settings.merchant_register_id,
    )


def _service(db: AsyncSession) -> PaymentService:
    fiscal_client = FiscalClient(
        api_key=settings.fiskaly_api_key, api_secret=settings.fiskaly_api_secret,
        tss_id=settings.fiskaly_tss_id, base_url=settings.fiskaly_base_url,
        http=httpx.AsyncClient(timeout=15),
    )
    fiscal = FiscalService(client=fiscal_client, db=db)
    return PaymentService(
        db=db,
        pos_tx=PosTransactionService(db=db, fiscal=fiscal),
        receipts=ReceiptService(db=db, builder=_builder(), backend=get_backend()),
        terminal=_terminal(),
    )


class CashRequest(BaseModel):
    client_id: uuid.UUID
    order_id: int
    tendered: Decimal


class CardRequest(BaseModel):
    client_id: uuid.UUID
    order_id: int


def _pos_tx_response(tx) -> dict:
    return {
        "id": str(tx.id),
        "client_id": str(tx.client_id),
        "receipt_number": tx.receipt_number,
        "tse_signature": tx.tse_signature,
        "tse_pending": tx.tse_pending,
        "total_gross": str(tx.total_gross),
    }


@router.post("/payment/cash", dependencies=[Depends(require_any_staff)])
async def pay_cash(
    body: CashRequest,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    svc = _service(db)
    try:
        result = await svc.pay_cash(
            client_id=body.client_id, order_id=body.order_id,
            cashier_user_id=user.id, tendered=body.tendered,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "transaction": _pos_tx_response(result.transaction),
        "change": str(result.change),
        "receipt_status": result.receipt_status,
    }


@router.post("/payment/card", dependencies=[Depends(require_any_staff)])
async def pay_card(
    body: CardRequest,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    svc = _service(db)
    try:
        result = await svc.pay_card(
            client_id=body.client_id, order_id=body.order_id,
            cashier_user_id=user.id,
        )
    except CardDeclinedError as e:
        raise HTTPException(402, f"declined: {e}")
    except TerminalUnavailableError as e:
        raise HTTPException(503, f"terminal unavailable: {e}")
    return {
        "transaction": _pos_tx_response(result.transaction),
        "receipt_status": result.receipt_status,
    }


@router.get("/health/terminal", dependencies=[Depends(require_any_staff)])
async def health_terminal():
    t = _terminal()
    try:
        ok = await t.diagnose()
    except Exception:
        ok = False
    return {"online": ok}


@router.get("/health/fiskaly", dependencies=[Depends(require_any_staff)])
async def health_fiskaly():
    if not settings.fiskaly_api_key:
        return {"online": False, "configured": False}
    async with httpx.AsyncClient(timeout=5) as http_client:
        fc = FiscalClient(
            api_key=settings.fiskaly_api_key, api_secret=settings.fiskaly_api_secret,
            tss_id=settings.fiskaly_tss_id, base_url=settings.fiskaly_base_url,
            http=http_client,
        )
        try:
            await fc._get_token()
            return {"online": True, "configured": True}
        except Exception as e:
            return {"online": False, "configured": True, "error": str(e)}
