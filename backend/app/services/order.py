import itertools
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryItem
from app.models.order import Order, LineItem
from app.models.product import ProductVariant
from app.ws.manager import manager

_order_counter = itertools.count(1001)


async def create_order(
    db: AsyncSession,
    source: str,
    line_items_data: list[dict],
    customer_id: int | None = None,
    shipping_address: dict | None = None,
) -> Order:
    total = 0
    line_items = []
    inventory_adjustments = []

    for item_data in line_items_data:
        variant_result = await db.execute(
            select(ProductVariant).where(ProductVariant.id == item_data["variant_id"])
        )
        variant = variant_result.scalar_one()
        line_total = variant.price * item_data["quantity"]
        total += line_total

        line_items.append(LineItem(
            variant_id=variant.id,
            title=f"{variant.product_id}:{variant.title}",
            quantity=item_data["quantity"],
            price=variant.price,
        ))

        inv_result = await db.execute(
            select(InventoryItem).where(InventoryItem.variant_id == variant.id)
        )
        inv_item = inv_result.scalar_one()
        inventory_adjustments.append((inv_item.id, -item_data["quantity"]))

    for inv_item_id, delta in inventory_adjustments:
        result = await db.execute(
            text("""
                UPDATE inventory_levels
                SET available = available + :delta
                WHERE inventory_item_id = :inv_id AND available + :delta >= 0
                RETURNING id, available, location_id
            """),
            {"delta": delta, "inv_id": inv_item_id},
        )
        row = result.fetchone()
        if row is None:
            await db.rollback()
            raise ValueError("Insufficient stock")

        await manager.broadcast({
            "type": "inventory_updated",
            "inventory_item_id": inv_item_id,
            "location_id": row.location_id,
            "available": row.available,
        })

    order_number = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{next(_order_counter)}"

    order = Order(
        order_number=order_number,
        customer_id=customer_id,
        source=source,
        fulfillment_status="fulfilled" if source == "pos" else "unfulfilled",
        total_price=total,
        shipping_address=shipping_address,
    )
    for li in line_items:
        order.line_items.append(li)

    db.add(order)
    await db.commit()
    await db.refresh(order, ["line_items"])
    return order
