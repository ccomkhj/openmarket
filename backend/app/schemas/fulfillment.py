from datetime import datetime

from pydantic import BaseModel


class FulfillmentCreate(BaseModel):
    status: str = "pending"


class FulfillmentUpdate(BaseModel):
    status: str


class FulfillmentOut(BaseModel):
    id: int
    order_id: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
