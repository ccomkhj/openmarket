from pydantic import BaseModel


class InventoryLevelOut(BaseModel):
    id: int
    inventory_item_id: int
    location_id: int
    available: int
    low_stock_threshold: int

    model_config = {"from_attributes": True}


class InventorySet(BaseModel):
    inventory_item_id: int
    location_id: int
    available: int


class InventoryAdjust(BaseModel):
    inventory_item_id: int
    location_id: int
    available_adjustment: int
