from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_manager_or_above
from app.models.collection import Collection, CollectionProduct
from app.models.product import Product
from app.schemas.collection import CollectionCreate, CollectionUpdate, CollectionOut, CollectionProductAdd
from app.schemas.product import ProductListOut

router = APIRouter(
    prefix="/api",
    tags=["collections"],
    dependencies=[Depends(require_manager_or_above)],
)


@router.post("/collections", response_model=CollectionOut, status_code=201)
async def create_collection(body: CollectionCreate, db: AsyncSession = Depends(get_db)):
    collection = Collection(**body.model_dump())
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return collection


@router.get("/collections", response_model=list[CollectionOut])
async def list_collections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Collection).order_by(Collection.id))
    return result.scalars().all()


@router.put("/collections/{collection_id}", response_model=CollectionOut)
async def update_collection(collection_id: int, body: CollectionUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(collection, key, value)
    await db.commit()
    await db.refresh(collection)
    return collection


@router.post("/collections/{collection_id}/products", status_code=201)
async def add_product_to_collection(
    collection_id: int, body: CollectionProductAdd, db: AsyncSession = Depends(get_db),
):
    cp = CollectionProduct(collection_id=collection_id, product_id=body.product_id, position=body.position)
    db.add(cp)
    await db.commit()
    return {"ok": True}


@router.get("/collections/{collection_id}/products", response_model=list[ProductListOut])
async def get_collection_products(collection_id: int, db: AsyncSession = Depends(get_db)):
    query = (
        select(Product)
        .join(CollectionProduct, CollectionProduct.product_id == Product.id)
        .where(CollectionProduct.collection_id == collection_id)
        .order_by(CollectionProduct.position)
    )
    result = await db.execute(query)
    return result.scalars().all()
