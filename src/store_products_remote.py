import asyncio
import os
import time
from pathlib import Path

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
API_URL_TEMPLATE = os.environ.get("API_URL_TEMPLATE")
if not API_URL_TEMPLATE:
    raise ValueError("API_URL_TEMPLATE environment variable must be provided")

CF_URL = os.environ.get("CF_URL")
if not CF_URL:
    raise ValueError("CF_URL environment variable must be provided")


async def make_request(session, product_id):
    # Get product details
    response = await session.get(API_URL_TEMPLATE.format(id=int(product_id)))
    logger.info("Request product %s: Status Code - %s", product_id, response.status_code)

    # Store product details
    data = parse_product_data(response.json())
    response_2 = await session.post(CF_URL, json=data)
    logger.info("Stored with CF: %s", response_2.json())
    return response.json()


async def store_product_details(products_ids: list[float]):
    async with httpx.AsyncClient(transport=AsyncCustomHost(NameSolver())) as session:
        tasks = []
        request_number = 1

        for product_id in products_ids:
            task = asyncio.create_task(make_request(session, product_id))
            tasks.append(task)
            request_number += 1
            await asyncio.sleep(0.1)  # To avoid sending requests too quickly

        response = await asyncio.gather(*tasks, return_exceptions=True)
        return response


async def main():
    vpn = Vpn(configs_folder=FOLDER_PATH)
    try:
        stored_products_ids = db.get_all_scanned_product_ids()
        # For each `batch_size` products IDS
        batch_size = 50
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
