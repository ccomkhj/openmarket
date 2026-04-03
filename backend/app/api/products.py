from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models.product import Product, ProductVariant
from app.models.inventory import InventoryItem
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductOut, ProductListOut,
    VariantCreate, VariantUpdate, VariantOut,
)

router = APIRouter(prefix="/api", tags=["products"])


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(body: ProductCreate, db: AsyncSession = Depends(get_db)):
    product = Product(
        title=body.title,
        handle=body.handle,
        description=body.description,
        product_type=body.product_type,
        status=body.status,
        tags=body.tags,
    )
    for v in body.variants:
        variant = ProductVariant(**v.model_dump())
        variant.inventory_item = InventoryItem()
        product.variants.append(variant)
    db.add(product)
    await db.commit()
    await db.refresh(product, ["variants", "images"])
    return product


@router.get("/products", response_model=list[ProductListOut])
async def list_products(
    status: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Product)
    if status:
        query = query.where(Product.status == status)
    if search:
        query = query.where(Product.title.ilike(f"%{search}%"))
    result = await db.execute(query.order_by(Product.id))
    return result.scalars().all()


@router.get("/products/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    query = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants), selectinload(Product.images))
    )
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(product_id: int, body: ProductUpdate, db: AsyncSession = Depends(get_db)):
    query = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants), selectinload(Product.images))
    )
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    await db.commit()
    await db.refresh(product, ["variants", "images"])
    return product


@router.delete("/products/{product_id}", response_model=ProductOut)
async def archive_product(product_id: int, db: AsyncSession = Depends(get_db)):
    query = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants), selectinload(Product.images))
    )
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.status = "archived"
    await db.commit()
    await db.refresh(product, ["variants", "images"])
    return product


@router.post("/products/{product_id}/variants", response_model=VariantOut, status_code=201)
async def add_variant(product_id: int, body: VariantCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    variant = ProductVariant(product_id=product_id, **body.model_dump())
    variant.inventory_item = InventoryItem()
    db.add(variant)
    await db.commit()
    await db.refresh(variant)
    return variant


@router.put("/variants/{variant_id}", response_model=VariantOut)
async def update_variant(variant_id: int, body: VariantUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(variant, key, value)
    await db.commit()
    await db.refresh(variant)
    return variant


@router.delete("/variants/{variant_id}")
async def delete_variant(variant_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    await db.delete(variant)
    await db.commit()
    return {"ok": True}
