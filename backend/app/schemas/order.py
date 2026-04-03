from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class LineItemCreate(BaseModel):
    variant_id: int
    quantity: int


class LineItemOut(BaseModel):
    id: int
    variant_id: int
    title: str
    quantity: int
    price: Decimal

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    source: str
    customer_id: int | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    shipping_address: dict | None = None
    line_items: list[LineItemCreate]


class OrderUpdate(BaseModel):
    fulfillment_status: str | None = None


class OrderOut(BaseModel):
    id: int
    order_number: str
    customer_id: int | None
    source: str
    fulfillment_status: str
    total_price: Decimal
    shipping_address: dict | None
    created_at: datetime
    line_items: list[LineItemOut] = []

    model_config = {"from_attributes": True}


class OrderListOut(BaseModel):
    id: int
    order_number: str
    source: str
    fulfillment_status: str
    total_price: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}
