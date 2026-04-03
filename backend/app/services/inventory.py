from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryLevel
from app.ws.manager import manager


async def set_inventory(db: AsyncSession, inventory_item_id: int, location_id: int, available: int) -> InventoryLevel:
    result = await db.execute(
        select(InventoryLevel).where(
            InventoryLevel.inventory_item_id == inventory_item_id,
            InventoryLevel.location_id == location_id,
        )
    )
    level = result.scalar_one()
    level.available = available
    await db.commit()
    await db.refresh(level)
    await _broadcast(level)
    return level


async def adjust_inventory(db: AsyncSession, inventory_item_id: int, location_id: int, delta: int) -> InventoryLevel | None:
    result = await db.execute(
        text("""
            UPDATE inventory_levels
            SET available = available + :delta
            WHERE inventory_item_id = :inv_id AND location_id = :loc_id
              AND available + :delta >= 0
            RETURNING id
        """),
        {"delta": delta, "inv_id": inventory_item_id, "loc_id": location_id},
    )
    row = result.fetchone()
    if row is None:
        return None
    await db.commit()

    level_result = await db.execute(
        select(InventoryLevel).where(InventoryLevel.id == row.id)
    )
    level = level_result.scalar_one()
    await _broadcast(level)
    return level


async def _broadcast(level: InventoryLevel):
    await manager.broadcast({
        "type": "inventory_updated",
        "inventory_item_id": level.inventory_item_id,
        "location_id": level.location_id,
        "available": level.available,
    })
