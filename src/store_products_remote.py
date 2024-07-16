import asyncio
import os
import time
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

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

VPN_CFG_FOLDER_PATH: Path | None = Path("vpn_configs")
VPN_CFG_FOLDER_PATH = None

API_URL_TEMPLATE = str(os.environ.get("API_URL_TEMPLATE"))
if not os.environ.get("API_URL_TEMPLATE"):
    raise ValueError("API_URL_TEMPLATE environment variable must be provided")

CF_URL = os.environ.get("CF_URL")
if not CF_URL:
    raise ValueError("CF_URL environment variable must be provided")


class ProductStoringStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class StoringState(BaseModel):
    product_id: float
    status: ProductStoringStatus = ProductStoringStatus.PENDING
    n_tries: int = 0


class StoringStates:
    def __init__(self, storing_initial_state: list[StoringState]) -> None:
        self.storing_states: list[StoringState] = storing_initial_state
        self._is_finished = False

    @property
    def is_finished(self) -> bool:
        return bool(self._is_finished)

    @is_finished.setter
    def is_finished(self, value: bool) -> None:
        self._is_finished = value

    def get_pending(self) -> list[StoringState]:
        # Set failed states if necessary
        for state in self.storing_states:
            if state.n_tries >= 3:
                state.status = ProductStoringStatus.FAILED
                logger.warning("Product %s failed to store after 3 tries", state.product_id)

        return [
            state for state in self.storing_states if state.status == ProductStoringStatus.PENDING
        ]

    def get_failed(self) -> list[StoringState]:
        return [
            state for state in self.storing_states if state.status == ProductStoringStatus.FAILED
        ]

    def get_success(self) -> list[StoringState]:
        return [
            state for state in self.storing_states if state.status == ProductStoringStatus.SUCCESS
        ]


async def main(partial_store: str | None = None):
    vpn = Vpn(configs_folder=VPN_CFG_FOLDER_PATH)
    try:
        warm_up_endpoint()
        stored_products_ids = db.get_all_scanned_product_ids()
        # stored_products_ids = db.get_scanned_non_stored_product_ids()

        store_product_states = [
            StoringState(product_id=product_id) for product_id in stored_products_ids
        ]

        store_product_states = _sample_storing_states(store_product_states, partial_store)

        # Notice that states are mutated during the storing process
        storing_states = StoringStates(store_product_states)

        # For each `batch_size` products IDS
        batch_size = 35
        while storing_states.get_pending():
            for i in range(0, len(storing_states.get_pending()), batch_size):
                vpn.rotate()

                storings_pending = storing_states.get_pending()
                storings_batch = storings_pending[i : i + batch_size]

                await store_product_details(storings_batch)
                n_pending = len(storing_states.get_pending())
                n_failed = len(storing_states.get_failed())
                n_success = len(storing_states.get_success())
                logger.info(
                    "Pending: %s -- Failed: %s -- Success: %s", n_pending, n_failed, n_success
                )
                time.sleep(10)
    finally:
        vpn.kill()


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


async def store_product_details(products_state: list[StoringState]):
    async with httpx.AsyncClient(transport=AsyncCustomHost(NameSolver()), timeout=5.0) as session:
        tasks_get = []
        for product_state in products_state:
            task = asyncio.create_task(make_request_get(session, product_state.product_id))
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
        success_ids = []
        for pr in posts_responses:
            try:
                if not isinstance(pr, dict):
                    continue
                success_ids.append(pr["productId"])
            except Exception:
                pass

        for product_state in products_state:
            if product_state.product_id in success_ids:
                product_state.status = ProductStoringStatus.SUCCESS
            else:
                product_state.n_tries += 1

        logger.debug("Posts responses: %s", posts_responses)
        logger.info("Tried: %s -- Stored: %s", len(products_state), len(success_ids))
        return posts_responses


def warm_up_endpoint():
    for _ in range(3):
        if not CF_URL:
            raise ValueError("CF_URL environment variable must be provided")
        response = httpx.get(CF_URL)
        logger.info("Warm up response: %s", response.json())
        time.sleep(1)


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


def _sample_storing_states(
    storing_states: list[StoringState],
    partial_store: str | None = None,
) -> list[StoringState]:
    if partial_store is None:
        return storing_states

    if partial_store == "first_half":
        return storing_states[: len(storing_states) // 2]
    if partial_store == "second_half":
        return storing_states[len(storing_states) // 2 :]

    raise ValueError("Invalid value for `partial_store`")
