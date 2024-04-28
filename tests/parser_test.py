import json

from src.config.logger import get_logger
from src.models import ScrapedCategory
from src.scraper import parser

logger = get_logger()


# def test_get_products():
#     # Arrange
#     with open("tests/fixtures/scraped_categories.json", "r") as json_file:
#         data = json.load(json_file)

#     scraped_categories = [ScrapedCategory(**item) for item in data]

#     # Act
#     products = []
#     for scraped_category in scraped_categories:
#         products_category = parser.get_products(scraped_category)
#         products.extend(products_category)

#     # Assert
#     serialized_items = [item.model_dump() for item in products]
#     json_data = json.dumps(serialized_items, indent=4, ensure_ascii=False)
#     with open("tests/fixtures/products.json", "w") as json_file:
#         json_file.write(json_data)


# def test_compute_hash():
#     # Arrange
#     with open("tests/fixtures/category_example.html", "r", encoding="utf-8") as file_html:
#         html = file_html.read()

#     with open("tests/fixtures/category_example_2.html", "r", encoding="utf-8") as file_html:
#         html_other_ga_id = file_html.read()

#     hash_1 = parser.compute_hash(
#         ScrapedCategory(
#             category_name="test",
#             subcategory_name="test",
#             html=html,
#         )
#     )

#     hash_2 = parser.compute_hash(
#         ScrapedCategory(
#             category_name="test",
#             subcategory_name="test",
#             html=html_other_ga_id,
#         )
#     )
#     assert hash_1 == hash_2
