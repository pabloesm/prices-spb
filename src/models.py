from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ScrapedCategory(BaseModel):
    category_name: str
    subcategory_name: str
    html: str


class Product_DEPRECATED(BaseModel):
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


class ScannedProduct(BaseModel):
    product_id: float
    category_name: str
    subcategory_name: str
    scanned_at: datetime


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


# Product Table
class Product(BaseModel):
    id: float
    ean: Optional[str] = None
    slug: Optional[str] = None
    brand: Optional[str] = None
    limit_value: Optional[int] = None
    origin: Optional[str] = None
    packaging: Optional[str] = None
    published: Optional[bool] = None
    share_url: Optional[str] = None
    thumbnail: Optional[str] = None
    display_name: Optional[str] = None
    unavailable_from: Optional[str] = None
    is_variable_weight: Optional[bool] = None
    legal_name: Optional[str] = None
    description: Optional[str] = None
    counter_info: Optional[str] = None
    danger_mentions: Optional[str] = None
    alcohol_by_volume: Optional[float] = None
    mandatory_mentions: Optional[str] = None
    product_variant: Optional[str] = None
    usage_instructions: Optional[str] = None
    storage_instructions: Optional[str] = None
    badge_id: Optional[int] = None
    supplier_id: Optional[int] = None


# Badge Table
class Badge(BaseModel):
    id: Optional[int] = None
    is_water: Optional[bool] = None
    requires_age_check: Optional[bool] = None


# Supplier Table
class Supplier(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None


# Photo Table
class Photo(BaseModel):
    id: Optional[int] = None
    product_id: float
    zoom: Optional[str] = None
    regular: Optional[str] = None
    thumbnail: Optional[str] = None
    perspective: Optional[int] = None


# Category Table
class Category(BaseModel):
    id: int
    name: Optional[str] = None
    level: Optional[int] = None
    order_value: Optional[int] = None


# Product_Category Table
class ProductCategory(BaseModel):
    product_id: float
    category_id: int


# Price_Instruction Table
class PriceInstruction(BaseModel):
    id: Optional[int] = None
    product_id: float
    iva: Optional[float] = None
    is_new: Optional[bool] = None
    is_pack: Optional[bool] = None
    pack_size: Optional[float] = None
    unit_name: Optional[str] = None
    unit_size: Optional[float] = None
    bulk_price: Optional[float] = None
    unit_price: Optional[float] = None
    approx_size: Optional[bool] = None
    size_format: Optional[str] = None
    total_units: Optional[int] = None
    unit_selector: Optional[bool] = None
    bunch_selector: Optional[bool] = None
    drained_weight: Optional[float] = None
    selling_method: Optional[int] = None
    price_decreased: Optional[bool] = None
    reference_price: Optional[float] = None
    min_bunch_amount: Optional[float] = None
    reference_format: Optional[str] = None
    previous_unit_price: Optional[float] = None
    increment_bunch_amount: Optional[float] = None
    created_at: Optional[str] = None


# Nutrition_Information Table
class NutritionInformation(BaseModel):
    id: Optional[int] = None
    product_id: float
    allergens: Optional[str] = None
    ingredients: Optional[str] = None


class FullInfo(BaseModel):
    product: Product
    badge: Badge
    supplier: Supplier
    photos: list[Photo]
    categories: list[Category]
    price_instruction: PriceInstruction
    nutrition_information: NutritionInformation
