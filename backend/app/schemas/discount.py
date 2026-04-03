from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DiscountOut(BaseModel):
    id: int
    code: str
    discount_type: str
    value: Decimal
    starts_at: datetime
    ends_at: datetime

    model_config = {"from_attributes": True}
