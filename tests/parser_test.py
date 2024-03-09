import json

from src.scraper import parser
from src.models import ScrapedCategory
from src.config.logger import get_logger

logger = get_logger()


def test_get_products():
    # Arrange
    with open("tests/fixtures/scraped_categories.json", "r") as json_file:
        data = json.load(json_file)

    scraped_categories = [ScrapedCategory(**item) for item in data]

    # Act
    products = []
    for scraped_category in scraped_categories:
        products_category = parser.get_products(scraped_category)
        products.extend(products_category)

    # Assert
    serialized_items = [item.model_dump() for item in products]
    json_data = json.dumps(serialized_items, indent=4, ensure_ascii=False)
    with open("tests/fixtures/products.json", "w") as json_file:
        json_file.write(json_data)
