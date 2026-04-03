from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.inventory import InventoryLevel
from app.schemas.inventory import InventoryLevelOut, InventorySet, InventoryAdjust
from app.services.inventory import set_inventory, adjust_inventory

router = APIRouter(prefix="/api", tags=["inventory"])


@router.get("/inventory-levels", response_model=list[InventoryLevelOut])
async def get_inventory_levels(location_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InventoryLevel).where(InventoryLevel.location_id == location_id)
    )
    return result.scalars().all()


@router.post("/inventory-levels/set", response_model=InventoryLevelOut)
async def set_level(body: InventorySet, db: AsyncSession = Depends(get_db)):
    level = await set_inventory(db, body.inventory_item_id, body.location_id, body.available)
    return level


@router.post("/inventory-levels/adjust", response_model=InventoryLevelOut)
async def adjust_level(body: InventoryAdjust, db: AsyncSession = Depends(get_db)):
    level = await adjust_inventory(db, body.inventory_item_id, body.location_id, body.available_adjustment)
    if level is None:
        raise HTTPException(status_code=409, detail="Insufficient stock")
    return level
