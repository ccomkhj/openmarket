from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, model_validator


class LineItemCreate(BaseModel):
    variant_id: int
    quantity: int
    quantity_kg: Decimal | None = None


class LineItemOut(BaseModel):
    id: int
    variant_id: int
    title: str
    quantity: int
    quantity_kg: Decimal | None = None
    price: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _populate_line_total(cls, data: Any) -> Any:
        # When validating from an ORM LineItem (from_attributes), compute
        # line_total from the ORM fields so clients don't have to recompute.
        # For by_weight lines LineItem.price stores the already-computed total;
        # for fixed lines it stores the unit price.
        if isinstance(data, dict):
            return data
        if hasattr(data, "price") and hasattr(data, "quantity"):
            from app.services.order import _line_total

            # Attach as attribute so Pydantic's from_attributes pass picks it up.
            try:
                if getattr(data, "line_total", None) is None:
                    object.__setattr__(data, "line_total", _line_total(data))
            except (AttributeError, TypeError):
                pass
        return data


class OrderCreate(BaseModel):
    source: str
    customer_id: int | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    shipping_address: dict | None = None
    shipping_method_id: int | None = None
    line_items: list[LineItemCreate]


class OrderUpdate(BaseModel):
    fulfillment_status: str | None = None


class OrderOut(BaseModel):
    id: int
    order_number: str
    customer_id: int | None
    source: str
    fulfillment_status: str
    subtotal: Decimal
    tax_amount: Decimal
    shipping_amount: Decimal
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
    customer_name: str | None = None
    customer_email: str | None = None

    model_config = {"from_attributes": True}
