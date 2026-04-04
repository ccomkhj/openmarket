from decimal import Decimal

from pydantic import BaseModel


class TaxRateCreate(BaseModel):
    name: str
    rate: Decimal
    region: str = ""
    is_default: bool = False


class TaxRateOut(BaseModel):
    id: int
    name: str
    rate: Decimal
    region: str
    is_default: bool

    model_config = {"from_attributes": True}


class ShippingMethodCreate(BaseModel):
    name: str
    price: Decimal
    min_order_amount: Decimal = Decimal("0")
    is_active: bool = True


class ShippingMethodOut(BaseModel):
    id: int
    name: str
    price: Decimal
    min_order_amount: Decimal
    is_active: bool

    model_config = {"from_attributes": True}
