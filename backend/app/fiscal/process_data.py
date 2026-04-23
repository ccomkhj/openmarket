"""Canonical DSFinV-K process_data builder (Kassenbeleg-V1).

The output of this function is what fiskaly hashes into the TSE signature.
The layout is prescribed by DSFinV-K and MUST be byte-identical across
runs for the same logical transaction — hence the golden tests.

Reference: BMF DSFinV-K, section "Kassenbeleg-V1", field `processData`.
"""
from decimal import Decimal
from typing import Mapping

# DSFinV-K mandates five VAT slots in this exact order:
#   A: 7%   (reduced "ermäßigt")
#   B: 19%  (standard "regulär")
#   C: 10.7% (pauschal Landwirte)
#   D: 0%   (nicht steuerbar)
#   E: 5.5% (pauschal)
_VAT_SLOTS = ("7", "19", "10.7", "0", "5.5")

# fiskaly payment-type identifiers per DSFinV-K.
_PAYMENT_LABELS = {
    "cash": "Bar",
    "girocard": "Unbar",
    "card": "Unbar",
    "credit": "Unbar",
}


def _fmt(d: Decimal) -> str:
    return f"{d.quantize(Decimal('0.01')):.2f}"


def build_process_data(
    *,
    vat_breakdown: Mapping[str, Mapping[str, Decimal]],
    payment_breakdown: Mapping[str, Decimal],
) -> str:
    for rate in vat_breakdown:
        if rate not in _VAT_SLOTS:
            raise ValueError(f"unknown VAT rate {rate!r}; expected one of {_VAT_SLOTS}")

    vat_section = "_".join(
        _fmt(vat_breakdown[slot]["gross"]) if slot in vat_breakdown else "0.00"
        for slot in _VAT_SLOTS
    )

    pay_parts = []
    for method, amount in payment_breakdown.items():
        if method not in _PAYMENT_LABELS:
            raise ValueError(f"unknown payment method {method!r}")
        pay_parts.append(f"{_fmt(amount)}:{_PAYMENT_LABELS[method]}")
    pay_section = "|".join(pay_parts)

    return f"Beleg^{vat_section}^{pay_section}"
