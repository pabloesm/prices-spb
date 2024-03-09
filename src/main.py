import hashlib

from src import db, stats
from src.config.logger import logger
from src.models import HtmlCategoryDB, PriceDB, ProductDB
from src.scraper import html, parser


def main():
    scraped_categories = html.categories()
    cat_products_tuple = []
    for cat_index, scraped_category in enumerate(scraped_categories):
        products_category = parser.get_products(scraped_category)
        cat_products_tuple.append((cat_index, products_category))

    for cat_index, products in cat_products_tuple:
        scraped_category = scraped_categories[cat_index]
        hash_value = hashlib.sha256(scraped_category.html.encode()).hexdigest()
        html_category_db = HtmlCategoryDB(
            html=scraped_category.html,
            category_name=scraped_category.category_name,
            subcategory_name=scraped_category.subcategory_name,
            hash_value=hash_value,
        )

        logger.info("Checking %s products of %s", len(products), scraped_category.subcategory_name)
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
            _ = db.insert_price(price_db)

    stats.table_count()
