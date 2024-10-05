import os
import time

import httpx

from src import db
from src.config.logger import logger
from src.models import (
    Badge,
    Category,
    FullInfo,
    NutritionInformation,
    Photo,
    PriceInstruction,
    Product,
    ProductCategory,
    Supplier,
)
from src.scraper.info_parser import InfoParser

API_URL_TEMPLATE = os.environ.get("API_URL_TEMPLATE", "empty_url")
if not API_URL_TEMPLATE or API_URL_TEMPLATE == "empty_url":
    raise ValueError("API_URL_TEMPLATE environment variable must be provided")


def main():
    stored_products_ids = db.get_all_scanned_product_ids()
    for product_id in stored_products_ids:
        logger.info("Storing product: %s", product_id)
        try:
            res = httpx.get(API_URL_TEMPLATE.format(id=int(product_id)))
            item = res.json()
            store_product(item)

        except Exception as exp:
            logger.exception("An unexpected error occurred: %s", exp)
        finally:
            time.sleep(10)


def store_product(item: dict) -> None:
    badge_data = InfoParser.badge(item)
    bagde_id = db.insert_badge(Badge(**badge_data))

    supplier_data = InfoParser.supplier(item)
    supplier_id = db.insert_supplier(Supplier(**supplier_data))

    product_data = InfoParser.product(item)
    product_data["badge_id"] = bagde_id
    product_data["supplier_id"] = supplier_id
    product_id = db.insert_product(Product(**product_data))

    photos_data = InfoParser.photo(item)
    for photo_data in photos_data:
        photo_data["product_id"] = product_id
        db.insert_photo(Photo(**photo_data))

    categories_data = InfoParser.category(item)
    categories_ids = []
    for category_data in categories_data:
        categories_ids.append(db.insert_category(Category(**category_data)))

    for category_id in categories_ids:
        db.insert_product_category(
            ProductCategory(
                product_id=product_id,
                category_id=category_id,
            )
        )

    price_data = InfoParser.price_instruction(item)
    price_data["product_id"] = product_id
    db.insert_price_instruction(PriceInstruction(**price_data))

    nutrition_data = InfoParser.nutrition_information(item)
    nutrition_data["product_id"] = product_id
    db.insert_nutrition_information(NutritionInformation(**nutrition_data))

    _ = FullInfo(
        product=Product(**product_data),
        badge=Badge(**badge_data),
        supplier=Supplier(**supplier_data),
        photos=[Photo(**photo_data) for photo_data in photos_data],
        categories=[Category(**category_data) for category_data in categories_data],
        price_instruction=PriceInstruction(**price_data),
        nutrition_information=NutritionInformation(**nutrition_data),
    )
