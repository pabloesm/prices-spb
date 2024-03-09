from typing import Optional
from pydantic import BaseModel


class HtmlCategory(BaseModel):
    html: str
    category_name: str
    subcategory_name: str


class Product(BaseModel):
    name: str
    price: float
    previous_price: Optional[float]
    currency: str
    price_quantity: str
    unit: str
    image_url: str
    category_name: str
    subcategory_name: str
    section_name: str
    created_at: str
    updated_at: str


class Price(BaseModel):
    price: float
    html_source: HtmlCategory
    product: Product
    created_at: str
    updated_at: str
