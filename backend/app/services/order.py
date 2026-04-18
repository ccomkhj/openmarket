import itertools
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.order import Order, LineItem
from app.models.product import ProductVariant
from app.models.tax_shipping import TaxRate, ShippingMethod
from app.services.weighed import (
    validate_weighed_line,
    validate_weighed_line_quantity,  # new
    compute_weighed_line_price,
    WeightMissingError,
    WeightOutOfRangeError,
    PricingTypeMismatchError,
    QuantityOnWeighedError,  # new
)
from app.ws.manager import manager

_order_counter = itertools.count(1001)


async def create_order(
    db: AsyncSession,
    source: str,
    line_items_data: list[dict],
    customer_id: int | None = None,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    shipping_address: dict | None = None,
    shipping_method_id: int | None = None,
) -> Order:
    # Auto-create or link customer by phone
    if customer_id is None and customer_phone:
        result = await db.execute(
            select(Customer).where(Customer.phone == customer_phone)
        )
        existing = result.scalar_one_or_none()
        if existing:
            customer_id = existing.id
        elif customer_name:
            parts = customer_name.split(" ", 1)
            first = parts[0]
            last = parts[1] if len(parts) > 1 else ""
            new_customer = Customer(first_name=first, last_name=last, phone=customer_phone)
            db.add(new_customer)
            await db.flush()
            customer_id = new_customer.id

    subtotal = Decimal("0")
    line_items = []
    inventory_adjustments = []

    for item_data in line_items_data:
        variant_result = await db.execute(
            select(ProductVariant).where(ProductVariant.id == item_data["variant_id"])
        )
        variant = variant_result.scalar_one()

        raw_quantity_kg = item_data.get("quantity_kg")
        quantity_kg = (
            Decimal(str(raw_quantity_kg)) if raw_quantity_kg is not None else None
        )
        validate_weighed_line_quantity(
            variant=variant,
            quantity=item_data["quantity"],
            quantity_kg=quantity_kg,
        )
        validate_weighed_line(variant=variant, quantity_kg=quantity_kg)

        if variant.pricing_type == "by_weight":
            line_price = compute_weighed_line_price(
                variant=variant, quantity_kg=quantity_kg
            )
            qty = 1
            qty_kg = quantity_kg
            line_total = line_price
        else:
            line_total = Decimal(str(variant.price)) * item_data["quantity"]
            line_price = variant.price
            qty = item_data["quantity"]
            qty_kg = None

        subtotal += line_total

        line_items.append(LineItem(
            variant_id=variant.id,
            title=f"{variant.product_id}:{variant.title}",
            quantity=qty,
            quantity_kg=qty_kg,
            price=line_price,
        ))

        inv_result = await db.execute(
            select(InventoryItem).where(InventoryItem.variant_id == variant.id)
        )
        inv_item = inv_result.scalar_one()
        inventory_adjustments.append((inv_item.id, -qty))

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

    # Compute tax from default tax rate (if any)
    tax_amount = Decimal("0")
    tax_result = await db.execute(
        select(TaxRate).where(TaxRate.is_default == True)  # noqa: E712
    )
    default_tax = tax_result.scalar_one_or_none()
    if default_tax is not None:
        tax_amount = subtotal * Decimal(str(default_tax.rate))

    # Compute shipping from shipping method (if provided)
    shipping_amount = Decimal("0")
    if shipping_method_id is not None:
        sm_result = await db.execute(
            select(ShippingMethod).where(ShippingMethod.id == shipping_method_id)
        )
        shipping_method = sm_result.scalar_one_or_none()
        if shipping_method is not None:
            min_amount = Decimal(str(shipping_method.min_order_amount))
            if min_amount > 0 and subtotal >= min_amount:
                shipping_amount = Decimal("0")
            else:
                shipping_amount = Decimal(str(shipping_method.price))

    total_price = subtotal + tax_amount + shipping_amount

    order_number = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{next(_order_counter)}"

    order = Order(
        order_number=order_number,
        customer_id=customer_id,
        source=source,
        fulfillment_status="fulfilled" if source == "pos" else "unfulfilled",
        subtotal=subtotal,
        tax_amount=tax_amount,
        shipping_amount=shipping_amount,
        total_price=total_price,
        shipping_address=shipping_address,
    )
    for li in line_items:
        order.line_items.append(li)

    db.add(order)
    await db.commit()
    await db.refresh(order, ["line_items"])
    return order
