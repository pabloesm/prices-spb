import asyncio
import os
from pathlib import Path

import httpx

from src import db
from src.config.logger import logger
from src.store_products import store_product
from src.vpn import AsyncCustomHost, NameSolver, Vpn

FOLDER_PATH = Path("vpn_configs")
API_URL_TEMPLATE = os.environ.get("API_URL_TEMPLATE")
if not API_URL_TEMPLATE:
    raise ValueError("API_URL_TEMPLATE environment variable must be provided")


async def make_request(session, product_id):
    response = await session.get(API_URL_TEMPLATE.format(id=int(product_id)))
    logger.info("Request product %s: Status Code - %s", product_id, response.status_code)
    return response.json()


async def get_product_details(products_ids: list[float]):
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
        # For each 100 products IDS
        batch_size = 50
        details = []
        for i in range(0, len(stored_products_ids), batch_size):
            vpn.rotate()
            ids_batch = stored_products_ids[i : i + batch_size]
            details_batch = await get_product_details(ids_batch)
            details.extend(details_batch)
            for item in details_batch:
                store_product(item)

            breakpoint()
    finally:
        vpn.kill()
