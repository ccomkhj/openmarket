import uuid
import httpx

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_any_staff
from app.config import settings
from app.fiscal.client import FiscalClient
from app.fiscal.service import FiscalService
from app.services.pos_transaction import PosTransactionService
from app.services.storno import StornoService


router = APIRouter(prefix="/api/pos-transactions", tags=["storno"])


@router.post("/{tx_id}/void", dependencies=[Depends(require_any_staff)])
async def void(
    tx_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    fc = FiscalClient(
        api_key=settings.fiskaly_api_key, api_secret=settings.fiskaly_api_secret,
        tss_id=settings.fiskaly_tss_id, base_url=settings.fiskaly_base_url,
        http=httpx.AsyncClient(timeout=15),
    )
    pts = PosTransactionService(db=db, fiscal=FiscalService(client=fc, db=db))
    try:
        storno = await StornoService(db=db, pos_tx=pts).void(
            original_id=tx_id, cashier_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "id": str(storno.id),
        "voids_transaction_id": str(storno.voids_transaction_id),
        "tse_signature": storno.tse_signature,
        "receipt_number": storno.receipt_number,
    }
