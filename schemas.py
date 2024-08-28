from pydantic import BaseModel, ConfigDict
from typing import Optional


class ProductSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    productId: str
    name: str
    price: int
    brandName: Optional[str] = None
    category: str
    productUrl: str


class ProductDetailsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    productId: str
    description: str
    imageUrls: list
    details: dict
    name: str
    price: int
    brandName: Optional[str] = None
    category: str
    productUrl: str

    
class ParsingItemCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    link: str

