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
    pricing_type: str = "fixed"
    weight_unit: str | None = None
    min_weight_kg: Decimal | None = None
    max_weight_kg: Decimal | None = None
    tare_kg: Decimal | None = None
    barcode_format: str = "standard"


class VariantUpdate(BaseModel):
    title: str | None = None
    sku: str | None = None
    barcode: str | None = None
    price: Decimal | None = None
    compare_at_price: Decimal | None = None
    position: int | None = None
    pricing_type: str | None = None
    weight_unit: str | None = None
    min_weight_kg: Decimal | None = None
    max_weight_kg: Decimal | None = None
    tare_kg: Decimal | None = None
    barcode_format: str | None = None


class VariantOut(BaseModel):
    id: int
    product_id: int
    title: str
    sku: str
    barcode: str
    price: Decimal
    compare_at_price: Decimal | None
    position: int
    pricing_type: str = "fixed"
    weight_unit: str | None = None
    min_weight_kg: Decimal | None = None
    max_weight_kg: Decimal | None = None
    tare_kg: Decimal | None = None
    barcode_format: str = "standard"

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


class ProductListWithPriceOut(BaseModel):
    id: int
    title: str
    handle: str
    product_type: str
    status: str
    tags: list[str]
    min_price: Decimal | None = None
    image_url: str | None = None

    model_config = {"from_attributes": True}


class VariantLookupOut(BaseModel):
    id: int
    product_id: int
    product_title: str
    title: str
    sku: str
    barcode: str
    price: Decimal
    compare_at_price: Decimal | None

    model_config = {"from_attributes": True}
