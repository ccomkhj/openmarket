import pytest
from decimal import Decimal

from app.models import Product, ProductVariant
from app.services.weighed import (
    validate_weighed_line, compute_weighed_line_price,
    WeightOutOfRangeError, WeightMissingError, PricingTypeMismatchError,
)


@pytest.mark.asyncio
async def test_validate_rejects_missing_weight_for_by_weight(db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(product_id=p.id, title="Gala", price=Decimal("2.49"), pricing_type="by_weight")
    db.add(v); await db.flush()
    with pytest.raises(WeightMissingError):
        validate_weighed_line(variant=v, quantity_kg=None)


@pytest.mark.asyncio
async def test_validate_rejects_weight_below_min(db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", min_weight_kg=Decimal("0.050"),
    )
    db.add(v); await db.flush()
    with pytest.raises(WeightOutOfRangeError):
        validate_weighed_line(variant=v, quantity_kg=Decimal("0.030"))


@pytest.mark.asyncio
async def test_validate_rejects_weight_above_max(db):
    p = Product(title="Apples", handle="apples"); db.add(p); await db.flush()
    v = ProductVariant(
        product_id=p.id, title="Gala", price=Decimal("2.49"),
        pricing_type="by_weight", max_weight_kg=Decimal("5.000"),
    )
    db.add(v); await db.flush()
    with pytest.raises(WeightOutOfRangeError):
        validate_weighed_line(variant=v, quantity_kg=Decimal("5.500"))


@pytest.mark.asyncio
async def test_validate_rejects_quantity_kg_on_fixed(db):
    p = Product(title="Milk", handle="milk"); db.add(p); await db.flush()
    v = ProductVariant(product_id=p.id, title="1L", price=Decimal("1.29"), pricing_type="fixed")
    db.add(v); await db.flush()
    with pytest.raises(PricingTypeMismatchError):
        validate_weighed_line(variant=v, quantity_kg=Decimal("0.500"))


def test_compute_weighed_line_price_rounds_to_cents():
    # 0.452 kg × 2.49 €/kg = 1.12548 → 1.13
    p = ProductVariant(price=Decimal("2.49"), pricing_type="by_weight", tare_kg=None)
    total = compute_weighed_line_price(variant=p, quantity_kg=Decimal("0.452"))
    assert total == Decimal("1.13")


def test_compute_subtracts_tare_when_set():
    # gross 0.500 kg, tare 0.050 kg, net 0.450 kg × 2.00 €/kg = 0.90
    p = ProductVariant(price=Decimal("2.00"), pricing_type="by_weight", tare_kg=Decimal("0.050"))
    total = compute_weighed_line_price(variant=p, quantity_kg=Decimal("0.500"))
    assert total == Decimal("0.90")
