from pydantic import BaseModel


class CollectionCreate(BaseModel):
    title: str
    handle: str
    collection_type: str = "manual"
    rules: dict | None = None


class CollectionUpdate(BaseModel):
    title: str | None = None
    handle: str | None = None
    rules: dict | None = None


class CollectionOut(BaseModel):
    id: int
    title: str
    handle: str
    collection_type: str
    rules: dict | None

    model_config = {"from_attributes": True}


class CollectionProductAdd(BaseModel):
    product_id: int
    position: int = 0
