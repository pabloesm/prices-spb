import asyncio
import time
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from src import db
from src.config.logger import logger
from src.config.settings import settings
from src.dns_override import AsyncCustomHost, NameSolver
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
from src.vpn import Vpn

# Set to Path("vpn_configs") to route the store run through the VPN; None disables it.
VPN_CFG_FOLDER_PATH: Path | None = None

API_URL_TEMPLATE = settings.api_url_template
CF_URL = settings.cf_url

MAX_STORE_TRIES = 3
BATCH_SIZE = 35
SLEEP_BETWEEN_BATCHES_SECONDS = 10
SLEEP_BETWEEN_REQUESTS_SECONDS = 0.1


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
            if state.n_tries >= MAX_STORE_TRIES:
                state.status = ProductStoringStatus.FAILED
                logger.warning(
                    "Product %s failed to store after %s tries",
                    state.product_id,
                    MAX_STORE_TRIES,
                )

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

        store_product_states = [
            StoringState(product_id=product_id) for product_id in stored_products_ids
        ]

        store_product_states = _sample_storing_states(store_product_states, partial_store)

        # Notice that states are mutated during the storing process
        storing_states = StoringStates(store_product_states)

        # Each pass processes every currently-pending product once, in batches.
        # Products that fail stay pending and are retried on the next pass (until MAX_STORE_TRIES).
        while storing_states.get_pending():
            pending = storing_states.get_pending()
            for start in range(0, len(pending), BATCH_SIZE):
                vpn.rotate()
                batch = pending[start : start + BATCH_SIZE]
                await store_product_details(batch)

                logger.info(
                    "Pending: %s -- Failed: %s -- Success: %s",
                    len(storing_states.get_pending()),
                    len(storing_states.get_failed()),
                    len(storing_states.get_success()),
                )
                await asyncio.sleep(SLEEP_BETWEEN_BATCHES_SECONDS)
    finally:
        vpn.kill()


async def make_request_get(session, product_id: float) -> Any:
    # Get product details
    response = await session.get(API_URL_TEMPLATE.format(id=transform_id(product_id)), timeout=5.0)
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
        product_details = await _fetch_all(session, products_state)
        posts_responses = await _post_all(session, product_details)
        success_ids = _extract_success_ids(posts_responses)
        _update_states(products_state, success_ids)

        logger.debug("Posts responses: %s", posts_responses)
        logger.info("Tried: %s -- Stored: %s", len(products_state), len(success_ids))


async def _fetch_all(session, products_state: list[StoringState]) -> list[Any]:
    """Fetch product details for the batch, one GET per product."""
    tasks = []
    for product_state in products_state:
        tasks.append(asyncio.create_task(make_request_get(session, product_state.product_id)))
        await asyncio.sleep(SLEEP_BETWEEN_REQUESTS_SECONDS)  # avoid sending requests too quickly
    return await asyncio.gather(*tasks, return_exceptions=True)


async def _post_all(session, product_details: list[Any]) -> list[Any]:
    """Store each successfully-fetched product via the Cloudflare endpoint."""
    tasks = [
        asyncio.create_task(make_request_post(session, details))
        for details in product_details
        if isinstance(details, dict)
    ]
    return await asyncio.gather(*tasks, return_exceptions=True)


def _extract_success_ids(posts_responses: list[Any]) -> list:
    """Pull the productId out of each successful POST response."""
    success_ids = []
    for response in posts_responses:
        if not isinstance(response, dict):
            continue
        product_id = response.get("productId")
        if product_id is None:
            logger.warning("POST response missing 'productId': %s", response)
            continue
        success_ids.append(product_id)
    return success_ids


def _update_states(products_state: list[StoringState], success_ids: list) -> None:
    """Mark stored products as SUCCESS; bump the try counter for the rest."""
    for product_state in products_state:
        if product_state.product_id in success_ids:
            product_state.status = ProductStoringStatus.SUCCESS
        else:
            product_state.n_tries += 1


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
