import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings

from app.api.deps import get_db, require_manager_or_above, require_owner
from app.models.product import Product, ProductVariant, ProductImage
from app.models.inventory import InventoryItem
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductOut, ProductListOut,
    VariantCreate, VariantUpdate, VariantOut,
    ProductListWithPriceOut, VariantLookupOut, ProductImageOut,
)

router = APIRouter(
    prefix="/api",
    tags=["products"],
    dependencies=[Depends(require_manager_or_above)],
)


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


@router.get("/products", response_model=list[ProductListWithPriceOut])
async def list_products(
    status: str | None = None,
    search: str | None = None,
    product_type: str | None = None,
    sort_by: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            Product.id, Product.title, Product.handle, Product.product_type,
            Product.status, Product.tags,
            sqlfunc.min(ProductVariant.price).label("min_price"),
        )
        .outerjoin(ProductVariant, ProductVariant.product_id == Product.id)
        .group_by(Product.id)
    )
    if status:
        query = query.where(Product.status == status)
    if search:
        query = query.where(Product.title.ilike(f"%{search}%"))
    if product_type:
        query = query.where(Product.product_type == product_type)
    if sort_by == "title":
        query = query.order_by(Product.title)
    elif sort_by == "price_asc":
        query = query.order_by(sqlfunc.min(ProductVariant.price).asc())
    elif sort_by == "price_desc":
        query = query.order_by(sqlfunc.min(ProductVariant.price).desc())
    elif sort_by == "newest":
        query = query.order_by(Product.id.desc())
    else:
        query = query.order_by(Product.id)
    query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    result = await db.execute(query)
    rows = result.all()

    # Load first image for each product
    product_ids = [r.id for r in rows]
    image_map: dict[int, str | None] = {}
    if product_ids:
        img_result = await db.execute(
            select(ProductImage.product_id, ProductImage.src)
            .where(ProductImage.product_id.in_(product_ids))
            .order_by(ProductImage.product_id, ProductImage.position)
        )
        for img_row in img_result.all():
            if img_row.product_id not in image_map:
                image_map[img_row.product_id] = img_row.src

    return [
        ProductListWithPriceOut(
            id=r.id, title=r.title, handle=r.handle,
            product_type=r.product_type, status=r.status,
            tags=r.tags, min_price=r.min_price,
            image_url=image_map.get(r.id),
        )
        for r in rows
    ]


@router.get("/variants/lookup", response_model=VariantLookupOut)
async def lookup_variant_by_barcode(barcode: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProductVariant)
        .where(ProductVariant.barcode == barcode)
        .options(selectinload(ProductVariant.product))
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return VariantLookupOut(
        id=variant.id,
        product_id=variant.product_id,
        product_title=variant.product.title,
        title=variant.title,
        sku=variant.sku,
        barcode=variant.barcode,
        price=variant.price,
        compare_at_price=variant.compare_at_price,
        pricing_type=variant.pricing_type,
        weight_unit=variant.weight_unit,
        min_weight_kg=variant.min_weight_kg,
        max_weight_kg=variant.max_weight_kg,
        tare_kg=variant.tare_kg,
        barcode_format=variant.barcode_format,
    )


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


@router.delete(
    "/products/{product_id}",
    response_model=ProductOut,
    dependencies=[Depends(require_owner)],
)
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


@router.post("/products/{product_id}/images", response_model=ProductImageOut, status_code=201)
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(exist_ok=True)
    filepath = upload_dir / filename

    content = await file.read()
    filepath.write_bytes(content)

    count_result = await db.execute(
        select(sqlfunc.count()).select_from(ProductImage).where(ProductImage.product_id == product_id)
    )
    position = count_result.scalar() or 0

    image = ProductImage(product_id=product_id, src=f"/api/uploads/{filename}", position=position)
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image
