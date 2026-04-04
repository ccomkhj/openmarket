from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ReturnItemCreate(BaseModel):
    line_item_id: int
    quantity: int


class ReturnCreate(BaseModel):
    order_id: int
    reason: str = ""
    items: list[ReturnItemCreate]


class ReturnItemOut(BaseModel):
    id: int
    line_item_id: int
    quantity: int

    model_config = {"from_attributes": True}


class ReturnOut(BaseModel):
    id: int
    order_id: int
    reason: str
    total_refund: Decimal
    created_at: datetime
    items: list[ReturnItemOut]

    model_config = {"from_attributes": True}
