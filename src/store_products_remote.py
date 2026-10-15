"""Store flow: fetch each scanned product from the Mercadona API and POST it to the worker.

Outcome model (per product, per run):

- ``STORED``: fetched, parsed and accepted by the worker.
- ``UNAVAILABLE``: the API answered 404. The product is delisted; it is recorded in
  ``scanned_products.unavailable_since`` and only re-checked every
  ``RECHECK_UNAVAILABLE_AFTER_DAYS`` instead of on every run.
- ``FAILED``: a transient error (timeout, 429, 5xx, bad JSON) that persisted for
  ``MAX_STORE_TRIES`` passes, or a permanent one (our parser rejected the payload, the
  worker rejected the request). Logged once, with the reason, when the product gives up.

The run exits non-zero only when the failure pattern looks systemic (nothing stored, or
more than ``FAILURE_RATE_THRESHOLD`` of the attempted products failed), never because of
the expected churn of delisted products.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
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
REQUEST_TIMEOUT_SECONDS = 5.0
# A product the API answered 404 for is re-checked this often instead of on every run.
RECHECK_UNAVAILABLE_AFTER_DAYS = 7
# Exit non-zero when more than this share of the attempted products (404s excluded)
# failed. That signals a broken API, worker or parser rather than delisted products.
FAILURE_RATE_THRESHOLD = 0.2


class StoreError(Exception):
    """Base class for one product's store failure."""


class TransientError(StoreError):
    """Worth retrying on a later pass: network errors, 429, 5xx, malformed bodies."""


class PermanentError(StoreError):
    """Retrying will not help: our parser rejected the payload or the worker rejected it."""


class ProductUnavailableError(StoreError):
    """The API answered 404: the product is not in the catalogue right now."""


class ProductStoringStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class Outcome(Enum):
    """Result of one attempt at one product."""

    STORED = "stored"
    UNAVAILABLE = "unavailable"
    TRANSIENT = "transient"
    PERMANENT = "permanent"


@dataclass
class AttemptResult:
    product_id: float
    outcome: Outcome
    error: str | None = None


class StoringState(BaseModel):
    product_id: float
    status: ProductStoringStatus = ProductStoringStatus.PENDING
    n_tries: int = 0
    last_error: str | None = None


class StoringStates:
    def __init__(self, storing_initial_state: list[StoringState]) -> None:
        self.storing_states: list[StoringState] = storing_initial_state
        self._by_id = {state.product_id: state for state in storing_initial_state}

    def pending(self) -> list[StoringState]:
        return self.with_status(ProductStoringStatus.PENDING)

    def with_status(self, status: ProductStoringStatus) -> list[StoringState]:
        return [state for state in self.storing_states if state.status == status]

    def apply(self, results: list[AttemptResult]) -> None:
        """Fold one batch of attempt results into the states.

        A product is logged exactly once, at the moment it reaches a terminal state.
        """
        for result in results:
            state = self._by_id[result.product_id]
            if result.outcome is Outcome.STORED:
                state.status = ProductStoringStatus.SUCCESS
            elif result.outcome is Outcome.UNAVAILABLE:
                state.status = ProductStoringStatus.UNAVAILABLE
                logger.debug("Product %s unavailable (404)", state.product_id)
            else:
                state.n_tries += 1
                state.last_error = result.error
                gave_up = result.outcome is Outcome.PERMANENT or state.n_tries >= MAX_STORE_TRIES
                if gave_up:
                    state.status = ProductStoringStatus.FAILED
                    logger.warning(
                        "Product %s failed to store after %s tries: %s",
                        state.product_id,
                        state.n_tries,
                        state.last_error,
                    )

    def counts(self) -> str:
        return (
            f"Pending: {len(self.pending())} -- "
            f"Stored: {len(self.with_status(ProductStoringStatus.SUCCESS))} -- "
            f"Unavailable: {len(self.with_status(ProductStoringStatus.UNAVAILABLE))} -- "
            f"Failed: {len(self.with_status(ProductStoringStatus.FAILED))}"
        )


async def main(partial_store: str | None = None) -> int:
    """Run the store flow; return the process exit code (0 = healthy run)."""
    vpn = Vpn(configs_folder=VPN_CFG_FOLDER_PATH)
    try:
        warm_up_endpoint()
        candidate_ids = db.get_product_ids_to_store(RECHECK_UNAVAILABLE_AFTER_DAYS)
        states = [StoringState(product_id=product_id) for product_id in candidate_ids]
        states = _sample_storing_states(states, partial_store)
        storing_states = StoringStates(states)
        logger.info("Products to store: %s (candidates: %s)", len(states), len(candidate_ids))

        # Each pass processes every currently-pending product once, in batches. Products
        # with transient failures stay pending and are retried on the next pass.
        while pending := storing_states.pending():
            for start in range(0, len(pending), BATCH_SIZE):
                vpn.rotate()
                batch = pending[start : start + BATCH_SIZE]
                results = await store_product_details(batch)
                storing_states.apply(results)
                _persist_outcomes(results)
                logger.info(storing_states.counts())
                await asyncio.sleep(SLEEP_BETWEEN_BATCHES_SECONDS)
    finally:
        vpn.kill()

    return summarise(storing_states)


def summarise(storing_states: StoringStates) -> int:
    """Log the run summary and decide the exit code."""
    stored = storing_states.with_status(ProductStoringStatus.SUCCESS)
    unavailable = storing_states.with_status(ProductStoringStatus.UNAVAILABLE)
    failed = storing_states.with_status(ProductStoringStatus.FAILED)
    candidates = len(storing_states.storing_states)
    attempted = len(stored) + len(failed)

    logger.info(
        "Store summary: candidates=%s stored=%s unavailable=%s failed=%s",
        candidates,
        len(stored),
        len(unavailable),
        len(failed),
    )
    if failed:
        logger.warning(
            "Failed product ids: %s", ", ".join(str(state.product_id) for state in failed)
        )

    if candidates > 0 and not stored:
        logger.error("Nothing was stored out of %s candidates", candidates)
        return 1
    failure_rate = len(failed) / attempted if attempted else 0.0
    if failure_rate > FAILURE_RATE_THRESHOLD:
        logger.error(
            "Failure rate %.0f%% exceeds the %.0f%% threshold",
            failure_rate * 100,
            FAILURE_RATE_THRESHOLD * 100,
        )
        return 1
    return 0


def _persist_outcomes(results: list[AttemptResult]) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    available = [r.product_id for r in results if r.outcome is Outcome.STORED]
    unavailable = [r.product_id for r in results if r.outcome is Outcome.UNAVAILABLE]
    db.record_store_outcome(available, unavailable, checked_at=now)


async def store_product_details(
    products_state: list[StoringState],
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[AttemptResult]:
    """Fetch, parse and POST every product in the batch; one result per product."""
    transport = transport or AsyncCustomHost(NameSolver())
    async with httpx.AsyncClient(transport=transport, timeout=REQUEST_TIMEOUT_SECONDS) as session:
        tasks = []
        for product_state in products_state:
            tasks.append(asyncio.create_task(_store_one(session, product_state.product_id)))
            await asyncio.sleep(SLEEP_BETWEEN_REQUESTS_SECONDS)  # avoid bursts
        return list(await asyncio.gather(*tasks))


async def _store_one(session: httpx.AsyncClient, product_id: float) -> AttemptResult:
    try:
        details = await fetch_product(session, product_id)
    except ProductUnavailableError:
        return AttemptResult(product_id, Outcome.UNAVAILABLE)
    except TransientError as exc:
        return AttemptResult(product_id, Outcome.TRANSIENT, str(exc))

    try:
        data = parse_product_data(details)
    except Exception as exc:  # any parser/validation error is final for this payload
        return AttemptResult(
            product_id, Outcome.PERMANENT, f"parse error: {type(exc).__name__}: {exc}"
        )

    try:
        stored_id = await post_product(session, data)
    except TransientError as exc:
        return AttemptResult(product_id, Outcome.TRANSIENT, str(exc))
    except PermanentError as exc:
        return AttemptResult(product_id, Outcome.PERMANENT, str(exc))

    if stored_id != product_id:
        logger.warning("Worker stored %s but %s was requested", stored_id, product_id)
    return AttemptResult(product_id, Outcome.STORED)


async def fetch_product(session: httpx.AsyncClient, product_id: float) -> dict:
    """GET the product from the API, classifying the response."""
    url = API_URL_TEMPLATE.format(id=transform_id(product_id))
    try:
        response = await session.get(url)
    except httpx.HTTPError as exc:
        raise TransientError(f"GET failed: {type(exc).__name__}: {exc}") from exc
    logger.debug("Request product %s: Status Code - %s", product_id, response.status_code)

    if response.status_code == 404:
        raise ProductUnavailableError(str(product_id))
    if response.status_code != 200:
        raise TransientError(f"GET status {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise TransientError("GET returned a non-JSON body") from exc
    if not isinstance(payload, dict):
        raise TransientError("GET returned a non-object JSON body")
    return payload


async def post_product(session: httpx.AsyncClient, data: dict) -> float:
    """POST the parsed product to the worker; return the product id it confirms."""
    try:
        response = await session.post(CF_URL, json=data)
    except httpx.HTTPError as exc:
        raise TransientError(f"POST failed: {type(exc).__name__}: {exc}") from exc

    body: Any
    try:
        body = response.json()
    except ValueError:
        body = {}
    detail = body.get("error") if isinstance(body, dict) else None
    detail = detail or response.text[:200]

    if response.status_code >= 500:
        raise TransientError(f"worker status {response.status_code}: {detail}")
    if response.status_code >= 400:
        raise PermanentError(f"worker status {response.status_code}: {detail}")
    if not isinstance(body, dict) or body.get("productId") is None:
        raise TransientError(f"worker response missing productId: {detail}")
    logger.debug("Stored with CF: %s", body)
    return float(body["productId"])


def warm_up_endpoint() -> None:
    if not CF_URL:
        raise ValueError("CF_URL environment variable must be provided")
    for _ in range(3):
        response = httpx.get(CF_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code != 200:
            raise RuntimeError(f"Worker warm-up failed with status {response.status_code}")
        logger.info("Warm up response: %s", response.text[:200])
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
