from decimal import Decimal

from pydantic import BaseModel


class ProductImageOut(BaseModel):
    id: int
    src: str
    position: int

    model_config = {"from_attributes": True}


class VariantCreate(BaseModel):
    title: str = "Default"
    sku: str = ""
    barcode: str = ""
    price: Decimal
    compare_at_price: Decimal | None = None
    position: int = 0


class VariantUpdate(BaseModel):
    title: str | None = None
    sku: str | None = None
    barcode: str | None = None
    price: Decimal | None = None
    compare_at_price: Decimal | None = None
    position: int | None = None


class VariantOut(BaseModel):
    id: int
    product_id: int
    title: str
    sku: str
    barcode: str
    price: Decimal
    compare_at_price: Decimal | None
    position: int

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    title: str
    handle: str
    description: str = ""
    product_type: str = ""
    status: str = "active"
    tags: list[str] = []
    variants: list[VariantCreate] = []


class ProductUpdate(BaseModel):
    title: str | None = None
    handle: str | None = None
    description: str | None = None
    product_type: str | None = None
    status: str | None = None
    tags: list[str] | None = None


class ProductOut(BaseModel):
    id: int
    title: str
    handle: str
    description: str
    product_type: str
    status: str
    tags: list[str]
    variants: list[VariantOut] = []
    images: list[ProductImageOut] = []

    model_config = {"from_attributes": True}


class ProductListOut(BaseModel):
    id: int
    title: str
    handle: str
    product_type: str
    status: str
    tags: list[str]

    model_config = {"from_attributes": True}
