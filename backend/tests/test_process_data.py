from decimal import Decimal
from app.fiscal.process_data import build_process_data


def test_build_cash_only_single_vat():
    out = build_process_data(
        vat_breakdown={"7": {"net": Decimal("1.06"), "vat": Decimal("0.07"), "gross": Decimal("1.13")}},
        payment_breakdown={"cash": Decimal("1.13")},
    )
    assert out == "Beleg^1.13_0.00_0.00_0.00_0.00^1.13:Bar"


def test_build_mixed_vat_and_payment():
    out = build_process_data(
        vat_breakdown={
            "7":  {"net": Decimal("3.73"), "vat": Decimal("0.27"), "gross": Decimal("4.00")},
            "19": {"net": Decimal("7.57"), "vat": Decimal("1.44"), "gross": Decimal("9.01")},
        },
        payment_breakdown={"cash": Decimal("5.00"), "girocard": Decimal("8.01")},
    )
    assert out == "Beleg^4.00_9.01_0.00_0.00_0.00^5.00:Bar|8.01:Unbar"


def test_rejects_unknown_vat_rate():
    import pytest as _pytest
    with _pytest.raises(ValueError, match="VAT rate"):
        build_process_data(
            vat_breakdown={"13": {"net": Decimal("1"), "vat": Decimal("0.13"), "gross": Decimal("1.13")}},
            payment_breakdown={"cash": Decimal("1.13")},
        )
