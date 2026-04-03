from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.discount import Discount
from app.schemas.discount import DiscountOut

router = APIRouter(prefix="/api", tags=["discounts"])


@router.post("/discounts/lookup", response_model=DiscountOut)
async def lookup_discount(code: str, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Discount).where(
            Discount.code == code,
            Discount.starts_at <= now,
            Discount.ends_at >= now,
        )
    )
    discount = result.scalar_one_or_none()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found or expired")
    return discount
