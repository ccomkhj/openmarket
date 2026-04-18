from decimal import Decimal, ROUND_HALF_UP

from app.models import ProductVariant


class WeightMissingError(ValueError):
    pass


class WeightOutOfRangeError(ValueError):
    pass


class PricingTypeMismatchError(ValueError):
    pass


def validate_weighed_line(*, variant: ProductVariant, quantity_kg: Decimal | None) -> None:
    if variant.pricing_type == "by_weight":
        if quantity_kg is None:
            raise WeightMissingError("by_weight variant requires quantity_kg")
        if variant.min_weight_kg is not None and quantity_kg < variant.min_weight_kg:
            raise WeightOutOfRangeError(f"weight below min ({variant.min_weight_kg} kg)")
        if variant.max_weight_kg is not None and quantity_kg > variant.max_weight_kg:
            raise WeightOutOfRangeError(f"weight above max ({variant.max_weight_kg} kg)")
    else:
        if quantity_kg is not None:
            raise PricingTypeMismatchError("quantity_kg only valid for by_weight variants")


def compute_weighed_line_price(*, variant: ProductVariant, quantity_kg: Decimal) -> Decimal:
    net_kg = quantity_kg - (variant.tare_kg or Decimal("0"))
    raw = net_kg * variant.price
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
