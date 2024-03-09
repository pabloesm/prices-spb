import re

from bs4 import BeautifulSoup

from src.config.logger import logger
from src.models import Product, ScrapedCategory


def get_products(category: ScrapedCategory) -> list[Product]:
    category_products = []
    soup = BeautifulSoup(category.html, "html.parser")
    content = soup.find("div", class_="category-detail__content")
    sections = content.find_all("section", recursive=False)
    for section in sections:
        section_products = _parse_section(
            section,
            category.category_name,
            category.subcategory_name,
        )
        category_products.extend(section_products)

    logger.info(
        f"{category.category_name} - {category.subcategory_name}: {len(category_products)} products."
    )
    return category_products


def _parse_section(section: BeautifulSoup, category: str, subcategory: str) -> list[Product]:
    section_name = section.find("h2").text
    product_cards = section.find_all("div", class_="product-cell")

    products = []
    for product_card in product_cards:
        img_url = product_card.find("img")["src"]
        name = product_card.find("h4", class_="product-cell__description-name").text
        format = product_card.find("div", class_="product-format").text
        price = product_card.find("div", class_="product-price").text
        unit_price = product_card.find("p", class_="product-price__unit-price").text
        price, currency = _parse_price(unit_price)
        try:
            previous_unit_price = product_card.find(
                "p", class_="product-price__previous-unit-price"
            ).text
            previous_price, _ = _parse_price(previous_unit_price)
        except AttributeError:
            previous_price = None
        price_quantity = product_card.find("p", class_="product-price__extra-price").text
        product = Product(
            name=name,
            price=price,
            previous_price=previous_price,
            currency=currency,
            price_quantity=price_quantity,
            unit=format,
            image_url=img_url,
            category_name=category,
            subcategory_name=subcategory,
            section_name=section_name,
        )
        products.append(product)
        logger.info(f"Scraped product: {name} - {format} - {price} - {currency}")

    return products


def _parse_price(price_string):
    # Define a regular expression pattern to match the price format
    pattern = r"\d+(?:,\d+)*(?:\.\d+)?"

    # Match the pattern against the input string
    match = re.match(pattern, price_string.strip())

    if match:
        # Extract the price and currency
        price = float(match.group(0).replace(",", "."))
        currency = price_string.replace(match.group(0), "").strip()

        return price, currency
    else:
        raise ValueError("Invalid price format")
