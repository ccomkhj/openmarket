"""DSFinV-K VAT slot keys."""
from decimal import Decimal

VAT_SLOTS: tuple[str, ...] = ("7", "19", "10.7", "0", "5.5")

VAT_SLOT_BY_PCT: dict[Decimal, str] = {
    Decimal("7.00"): "7",
    Decimal("19.00"): "19",
    Decimal("10.70"): "10.7",
    Decimal("0.00"): "0",
    Decimal("5.50"): "5.5",
}
