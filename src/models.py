from datetime import datetime

from pydantic import BaseModel


class ScrapedCategory(BaseModel):
    category_name: str
    subcategory_name: str
    html: str


class ScannedProduct(BaseModel):
    product_id: float
    category_name: str
    subcategory_name: str
    scanned_at: datetime


class HtmlCategoryDB(BaseModel):
    id: int | None = None
    html: str
    category_name: str
    subcategory_name: str
    hash_value: str
    created_at: datetime | None = None


class ProductDB(BaseModel):
    id: int | None = None
    name: str
    unit: str
    image_url: str
    category_name: str
    subcategory_name: str
    section_name: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PriceDB(BaseModel):
    id: int | None = None
    price: float
    previous_price: float | None = None
    currency: str
    price_quantity: str
    html_category_id: int
    product_id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


# Product Table
class Product(BaseModel):
    id: float
    ean: str | None = None
    slug: str | None = None
    brand: str | None = None
    limit_value: int | None = None
    origin: str | None = None
    packaging: str | None = None
    published: bool | None = None
    share_url: str | None = None
    thumbnail: str | None = None
    display_name: str | None = None
    unavailable_from: str | None = None
    is_variable_weight: bool | None = None
    legal_name: str | None = None
    description: str | None = None
    counter_info: str | None = None
    danger_mentions: str | None = None
    alcohol_by_volume: float | None = None
    mandatory_mentions: str | None = None
    product_variant: str | None = None
    usage_instructions: str | None = None
    storage_instructions: str | None = None
    badge_id: int | None = None
    supplier_id: int | None = None


# Badge Table
class Badge(BaseModel):
    id: int | None = None
    is_water: bool | None = None
    requires_age_check: bool | None = None


# Supplier Table
class Supplier(BaseModel):
    id: int | None = None
    name: str | None = None


# Photo Table
class Photo(BaseModel):
    id: int | None = None
    product_id: float
    zoom: str | None = None
    regular: str | None = None
    thumbnail: str | None = None
    perspective: int | None = None


# Category Table
class Category(BaseModel):
    id: int
    name: str | None = None
    level: int | None = None
    order_value: int | None = None


# Product_Category Table
class ProductCategory(BaseModel):
    product_id: float
    category_id: int


# Price_Instruction Table
class PriceInstruction(BaseModel):
    id: int | None = None
    product_id: float
    iva: float | None = None
    is_new: bool | None = None
    is_pack: bool | None = None
    pack_size: float | None = None
    unit_name: str | None = None
    unit_size: float | None = None
    bulk_price: float | None = None
    unit_price: float | None = None
    approx_size: bool | None = None
    size_format: str | None = None
    total_units: int | None = None
    unit_selector: bool | None = None
    bunch_selector: bool | None = None
    drained_weight: float | None = None
    selling_method: int | None = None
    price_decreased: bool | None = None
    reference_price: float | None = None
    min_bunch_amount: float | None = None
    reference_format: str | None = None
    previous_unit_price: float | None = None
    increment_bunch_amount: float | None = None
    created_at: str | None = None


# Nutrition_Information Table
class NutritionInformation(BaseModel):
    id: int | None = None
    product_id: float
    allergens: str | None = None
    ingredients: str | None = None


class FullInfo(BaseModel):
    product: Product
    badge: Badge
    supplier: Supplier
    photos: list[Photo]
    categories: list[Category]
    price_instruction: PriceInstruction
    nutrition_information: NutritionInformation
