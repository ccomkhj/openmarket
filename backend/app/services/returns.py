from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import InventoryItem
from app.models.order import Order, LineItem, Return, ReturnItem
from app.ws.manager import manager


async def create_return(
    db: AsyncSession,
    order_id: int,
    return_items: list[dict],
    reason: str = "",
) -> Return:
    # Load order with line items
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.line_items))
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise ValueError(f"Order {order_id} not found")

    line_item_map = {li.id: li for li in order.line_items}

    total_refund = Decimal("0")
    validated_items = []

    for item in return_items:
        li_id = item["line_item_id"]
        qty = item["quantity"]

        if li_id not in line_item_map:
            raise ValueError(f"LineItem {li_id} does not belong to order {order_id}")

        li = line_item_map[li_id]
        if qty > li.quantity:
            raise ValueError(
                f"Return quantity {qty} exceeds ordered quantity {li.quantity} for line item {li_id}"
            )
        if qty <= 0:
            raise ValueError(f"Return quantity must be positive, got {qty}")

        total_refund += Decimal(str(li.price)) * qty
        validated_items.append((li, qty))

    # Restore inventory and broadcast
    for li, qty in validated_items:
        inv_result = await db.execute(
            select(InventoryItem).where(InventoryItem.variant_id == li.variant_id)
        )
        inv_item = inv_result.scalar_one_or_none()
        if inv_item is not None:
            row_result = await db.execute(
                text("""
                    UPDATE inventory_levels
                    SET available = available + :qty
                    WHERE inventory_item_id = :inv_id
                    RETURNING id, available, location_id
                """),
                {"qty": qty, "inv_id": inv_item.id},
            )
            row = row_result.fetchone()
            if row is not None:
                await manager.broadcast({
                    "type": "inventory_updated",
                    "inventory_item_id": inv_item.id,
                    "location_id": row.location_id,
                    "available": row.available,
                })

    # Create Return record
    return_record = Return(
        order_id=order_id,
        reason=reason,
        total_refund=total_refund,
    )
    for li, qty in validated_items:
        return_record.items.append(ReturnItem(line_item_id=li.id, quantity=qty))

    db.add(return_record)
    await db.commit()
    await db.refresh(return_record, ["items"])
    return return_record
