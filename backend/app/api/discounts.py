from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.discount import Discount
from app.schemas.discount import DiscountCreate, DiscountUpdate, DiscountOut

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


@router.get("/discounts", response_model=list[DiscountOut])
async def list_discounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Discount).order_by(Discount.id))
    return result.scalars().all()


@router.post("/discounts", response_model=DiscountOut, status_code=201)
async def create_discount(body: DiscountCreate, db: AsyncSession = Depends(get_db)):
    discount = Discount(**body.model_dump())
    db.add(discount)
    await db.commit()
    await db.refresh(discount)
    return discount


@router.put("/discounts/{discount_id}", response_model=DiscountOut)
async def update_discount(discount_id: int, body: DiscountUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Discount).where(Discount.id == discount_id))
    discount = result.scalar_one_or_none()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(discount, key, value)
    await db.commit()
    await db.refresh(discount)
    return discount


@router.delete("/discounts/{discount_id}")
async def delete_discount(discount_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Discount).where(Discount.id == discount_id))
    discount = result.scalar_one_or_none()
    if not discount:
        raise HTTPException(status_code=404, detail="Discount not found")
    await db.delete(discount)
    await db.commit()
    return {"ok": True}
