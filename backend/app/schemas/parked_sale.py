from datetime import datetime

from pydantic import BaseModel


class ParkedItem(BaseModel):
    variant_id: int
    product_title: str
    variant_title: str
    price: str
    quantity: int
    quantity_kg: str | None = None


class ParkedSaleCreate(BaseModel):
    items: list[ParkedItem]
    customer_id: int | None = None
    note: str = ""


class ParkedSaleOut(BaseModel):
    id: int
    cashier_user_id: int
    customer_id: int | None
    customer_name: str | None = None
    items: list[ParkedItem]
    note: str
    created_at: datetime
    item_count: int

    model_config = {"from_attributes": True}
