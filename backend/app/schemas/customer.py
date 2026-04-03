from pydantic import BaseModel


class AddressCreate(BaseModel):
    address1: str
    city: str
    zip: str
    is_default: bool = False


class AddressOut(BaseModel):
    id: int
    address1: str
    city: str
    zip: str
    is_default: bool

    model_config = {"from_attributes": True}


class CustomerCreate(BaseModel):
    email: str | None = None
    first_name: str
    last_name: str
    phone: str = ""
    addresses: list[AddressCreate] = []


class CustomerOut(BaseModel):
    id: int
    email: str | None
    first_name: str
    last_name: str
    phone: str
    addresses: list[AddressOut] = []

    model_config = {"from_attributes": True}
