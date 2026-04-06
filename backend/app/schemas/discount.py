from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DiscountCreate(BaseModel):
    code: str
    discount_type: str
    value: Decimal
    starts_at: datetime
    ends_at: datetime


class DiscountUpdate(BaseModel):
    code: str | None = None
    discount_type: str | None = None
    value: Decimal | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class DiscountOut(BaseModel):
    id: int
    code: str
    discount_type: str
    value: Decimal
    starts_at: datetime
    ends_at: datetime

    model_config = {"from_attributes": True}
