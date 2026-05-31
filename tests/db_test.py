import json

from src import db
from src.config.logger import logger
from src.models import (
    Badge,
    Category,
    NutritionInformation,
    Photo,
    PriceInstruction,
    Product,
    ProductCategory,
    ScannedProduct,
    Supplier,
)
from src.scraper.info_parser import InfoParser


def test_count_elements_in_table():
    # Act
    result = db.count_elements_in_table("product")
    logger.info("Table %s has %s elements", "html_category", result)


def test_insert_scanned_product():
    # Arrange
    with open("tests/fixtures/scanned_products.json", encoding="utf-8") as json_file:
        scanned_products_dict = json.load(json_file)

    scanned_products = [ScannedProduct(**item) for item in scanned_products_dict]

    # Act
    for scanned_product in scanned_products:
        pid = db.insert_scanned_product(scanned_product)
        logger.info("Inserted scanned product: %s", pid)
    logger.info("Inserted %s products", len(scanned_products))


def test_insert_product_full():
    # Arrange
    with open("tests/fixtures/products_full.json", encoding="utf-8") as json_file:
        products_full_dict = json.load(json_file)

    products = []
    for item in products_full_dict:
        badge_data = InfoParser.badge(item)
        bagde_id = db.insert_badge(Badge(**badge_data))

        supplier_data = InfoParser.supplier(item)
        supplier_id = db.insert_supplier(Supplier(**supplier_data))

        product_data = InfoParser.product(item)
        product_data["badge_id"] = bagde_id
        product_data["supplier_id"] = supplier_id
        products.append(Product(**product_data))
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

    # Act
    # Assert
