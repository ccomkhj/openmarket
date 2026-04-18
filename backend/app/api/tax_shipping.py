from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_manager_or_above, require_owner
from app.models.tax_shipping import TaxRate, ShippingMethod
from app.schemas.tax_shipping import (
    TaxRateCreate, TaxRateOut,
    ShippingMethodCreate, ShippingMethodOut,
)

router = APIRouter(
    prefix="/api",
    tags=["tax-shipping"],
    dependencies=[Depends(require_manager_or_above)],
)


@router.get("/tax-rates", response_model=list[TaxRateOut])
async def list_tax_rates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TaxRate))
    return result.scalars().all()


@router.post(
    "/tax-rates",
    response_model=TaxRateOut,
    status_code=201,
    dependencies=[Depends(require_owner)],
)
async def create_tax_rate(body: TaxRateCreate, db: AsyncSession = Depends(get_db)):
    tax_rate = TaxRate(**body.model_dump())
    db.add(tax_rate)
    await db.commit()
    await db.refresh(tax_rate)
    return tax_rate


@router.get("/shipping-methods", response_model=list[ShippingMethodOut])
async def list_shipping_methods(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ShippingMethod).where(ShippingMethod.is_active == True)  # noqa: E712
    )
    return result.scalars().all()


@router.post("/shipping-methods", response_model=ShippingMethodOut, status_code=201)
async def create_shipping_method(body: ShippingMethodCreate, db: AsyncSession = Depends(get_db)):
    shipping_method = ShippingMethod(**body.model_dump())
    db.add(shipping_method)
    await db.commit()
    await db.refresh(shipping_method)
    return shipping_method
