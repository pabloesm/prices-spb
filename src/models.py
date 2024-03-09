from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class ScrapedCategory(BaseModel):
    category_name: str
    subcategory_name: str
    html: str


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


class HtmlCategoryDB(BaseModel):
    id: Optional[int] = None
    html: str
    category_name: str
    subcategory_name: str
    hash_value: str
    created_at: Optional[datetime] = None


class ProductDB(BaseModel):
    id: Optional[int] = None
    name: str
    unit: str
    image_url: str
    category_name: str
    subcategory_name: str
    section_name: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PriceDB(BaseModel):
    id: Optional[int] = None
    price: float
    previous_price: Optional[float] = None
    currency: str
    price_quantity: str
    html_category_id: int
    product_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
