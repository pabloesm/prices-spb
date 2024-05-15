import asyncio
import os
import time
from pathlib import Path
from typing import Any

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
    Supplier,
)
from src.scraper.info_parser import InfoParser
from src.vpn import AsyncCustomHost, NameSolver, Vpn

FOLDER_PATH = Path("vpn_configs")
API_URL_TEMPLATE = str(os.environ.get("API_URL_TEMPLATE"))
if not os.environ.get("API_URL_TEMPLATE"):
    raise ValueError("API_URL_TEMPLATE environment variable must be provided")

CF_URL = os.environ.get("CF_URL")
if not CF_URL:
    raise ValueError("CF_URL environment variable must be provided")


async def make_request_get(session, product_id: float) -> Any:
    # Get product details
    response = await session.get(API_URL_TEMPLATE.format(id=transform_id(product_id)))
    logger.info("Request product %s: Status Code - %s", product_id, response.status_code)
    return response.json()


async def make_request_post(session, product_details: dict) -> Any:
    # Store product details
    data = parse_product_data(product_details)
    response = await session.post(CF_URL, json=data)
    logger.info("Stored with CF: %s", response.json())
    return response.json()


async def store_product_details(products_ids: list[float]):
    async with httpx.AsyncClient(transport=AsyncCustomHost(NameSolver()), timeout=5.0) as session:
        tasks_get = []
        for product_id in products_ids:
            task = asyncio.create_task(make_request_get(session, product_id))
            tasks_get.append(task)
            await asyncio.sleep(0.1)  # To avoid sending requests too quickly
        products_details = await asyncio.gather(*tasks_get, return_exceptions=True)

        tasks_post = []
        for product_details in products_details:
            if not isinstance(product_details, dict):
                continue
            task = asyncio.create_task(make_request_post(session, product_details))
            tasks_post.append(task)

        posts_responses = await asyncio.gather(*tasks_post, return_exceptions=True)
        logger.info("Posts responses: %s", posts_responses)
        return posts_responses


def warm_up_endpoint():
    for _ in range(3):
        response = httpx.get(CF_URL)
        logger.info("Warm up response: %s", response.json())
        time.sleep(1)


async def main():
    vpn = Vpn(configs_folder=FOLDER_PATH)
    try:
        warm_up_endpoint()
        stored_products_ids = db.get_all_scanned_product_ids()
        # For each `batch_size` products IDS
        batch_size = 35
        for i in range(0, len(stored_products_ids), batch_size):
            vpn.rotate()
            ids_batch = stored_products_ids[i : i + batch_size]
            await store_product_details(ids_batch)
            time.sleep(10)
    finally:
        vpn.kill()


def parse_product_data(item: dict) -> dict:
    badge_data = InfoParser.badge(item)

    supplier_data = InfoParser.supplier(item)

    product_data = InfoParser.product(item)
    product_id = float(product_data["id"])

    photos_data = InfoParser.photo(item)
    for photo_data in photos_data:
        photo_data["product_id"] = product_id

    categories_data = InfoParser.category(item)

    price_data = InfoParser.price_instruction(item)
    price_data["product_id"] = product_id

    nutrition_data = InfoParser.nutrition_information(item)
    nutrition_data["product_id"] = product_id

    full_info = FullInfo(
        product=Product(**product_data),
        badge=Badge(**badge_data),
        supplier=Supplier(**supplier_data),
        photos=[Photo(**photo_data) for photo_data in photos_data],
        categories=[Category(**category_data) for category_data in categories_data],
        price_instruction=PriceInstruction(**price_data),
        nutrition_information=NutritionInformation(**nutrition_data),
    )

    return full_info.model_dump()


def transform_id(product_id: float) -> str:
    """Convert float ID to a suitable string ID, removing trailing zeros.

    Examples:
        12.000 -> "12"
        1453 -> "1453"
        64.1000 -> "64.1"
        64.00 -> "64"
        9.3000 -> "9.3"
    """
    id_str = str(product_id)

    # Strip trailing zeros and the decimal point if it's the last character
    if "." in id_str:
        id_str = id_str.rstrip("0").rstrip(".")

    return id_str
