from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_any_staff, require_manager_or_above
from app.models import ProductVariant


router = APIRouter(prefix="/api/variants", tags=["variants"])


class VariantOut(BaseModel):
    id: int
    product_id: int
    title: str
    sku: str | None
    barcode: str | None
    price: Decimal
    pricing_type: str
    vat_rate: Decimal
    min_weight_kg: Decimal | None
    max_weight_kg: Decimal | None
    tare_kg: Decimal | None


class VariantUpdate(BaseModel):
    title: str | None = None
    sku: str | None = None
    barcode: str | None = None
    price: Decimal | None = None
    vat_rate: Decimal | None = None
    pricing_type: str | None = None
    min_weight_kg: Decimal | None = None
    max_weight_kg: Decimal | None = None
    tare_kg: Decimal | None = None


def _out(v: ProductVariant) -> VariantOut:
    return VariantOut(
        id=v.id, product_id=v.product_id, title=v.title,
        sku=v.sku, barcode=v.barcode, price=v.price,
        pricing_type=v.pricing_type, vat_rate=v.vat_rate,
        min_weight_kg=v.min_weight_kg, max_weight_kg=v.max_weight_kg, tare_kg=v.tare_kg,
    )


@router.get("/lookup", response_model=VariantOut, dependencies=[Depends(require_any_staff)])
async def lookup(barcode: str = Query(..., min_length=1), db: AsyncSession = Depends(get_db)):
    v = (await db.execute(
        select(ProductVariant).where(ProductVariant.barcode == barcode)
    )).scalar_one_or_none()
    if not v:
        raise HTTPException(404, "no variant with that barcode")
    return _out(v)


@router.put("/{variant_id}", response_model=VariantOut, dependencies=[Depends(require_manager_or_above)])
async def update_variant(
    variant_id: int, body: VariantUpdate, db: AsyncSession = Depends(get_db),
):
    v = await db.get(ProductVariant, variant_id)
    if not v:
        raise HTTPException(404, "variant not found")
    data = body.model_dump(exclude_unset=True)
    for k, value in data.items():
        setattr(v, k, value)
    try:
        await db.commit()
    except Exception as e:
        raise HTTPException(400, f"update failed: {e}") from e
    await db.refresh(v)
    return _out(v)
