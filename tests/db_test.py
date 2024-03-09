import hashlib
import json

from src import db
from src.config.logger import logger
from src.models import HtmlCategoryDB, PriceDB, Product, ProductDB


def test_db():
    # Arrange
    with open("tests/fixtures/products.json", "r") as json_file:
        products_dict = json.load(json_file)
    products = [Product(**item) for item in products_dict]

    html_fake = "<html>My fake HTML!</html>"
    hash_value = hashlib.sha256(html_fake.encode()).hexdigest()
    html_category_db = HtmlCategoryDB(
        html=html_fake,
        category_name="category_name",
        subcategory_name="subcategory_name",
        hash_value=hash_value,
    )

    logger.info("Checking %s products of %s", len(products), "subcategory_name")
    for product in products:
        product_db = ProductDB(
            name=product.name,
            unit=product.unit,
            image_url=product.image_url,
            category_name=product.category_name,
            subcategory_name=product.subcategory_name,
            section_name=product.section_name,
        )

        # Act
        html_id = db.insert_html_category(html_category_db)
        product_id = db.insert_product(product_db)

        price_db = PriceDB(
            price=product.price,
            previous_price=product.previous_price,
            currency=product.currency,
            price_quantity=product.price_quantity,
            html_category_id=html_id,
            product_id=product_id,
        )
        price_id = db.insert_price(price_db)

    # Assert
