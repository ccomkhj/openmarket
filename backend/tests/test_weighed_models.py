import pytest
from decimal import Decimal

from app.models import Product, ProductVariant, Order, LineItem


@pytest.mark.asyncio
async def test_create_by_weight_variant(db):
    p = Product(title="Apples", handle="apples")
    db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", weight_unit="kg",
        min_weight_kg=Decimal("0.05"), max_weight_kg=Decimal("5.000"),
    )
    db.add(v); await db.commit(); await db.refresh(v)
    assert v.pricing_type == "by_weight"
    assert v.min_weight_kg == Decimal("0.050")


@pytest.mark.asyncio
async def test_line_item_carries_quantity_kg(db):
    p = Product(title="Apples", handle="apples")
    db.add(p); await db.flush()
    v = ProductVariant(product_id=p.id, title="Gala", price=Decimal("2.49"), pricing_type="by_weight", weight_unit="kg")
    db.add(v); await db.flush()
    o = Order(order_number="T-1", source="pos", total_price=Decimal("1.13"))
    db.add(o); await db.flush()
    li = LineItem(order_id=o.id, variant_id=v.id, title="Apples Gala",
                  quantity=1, quantity_kg=Decimal("0.452"), price=Decimal("1.13"))
    db.add(li); await db.commit()
    assert li.quantity_kg == Decimal("0.452")
