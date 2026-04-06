from pydantic import BaseModel


class LocationOut(BaseModel):
    id: int
    name: str
    address: str

    model_config = {"from_attributes": True}
