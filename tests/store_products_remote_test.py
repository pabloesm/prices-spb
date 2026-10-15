"""Unit tests for the store flow's response classification and state machine.

No network, no database: HTTP goes through an `httpx.MockTransport` and the outcomes
are applied to `StoringStates` directly.
"""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from src import store_products_remote as store
from src.store_products_remote import (
    AttemptResult,
    Outcome,
    ProductStoringStatus,
    StoringState,
    StoringStates,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

LIVE_ID = 60722.0  # first product in products_full.json
GONE_ID = 1.0
FLAKY_ID = 2.0
BROKEN_ID = 3.0
REJECTED_ID = 4.0


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(store, "SLEEP_BETWEEN_REQUESTS_SECONDS", 0)


def _fixture_product() -> dict:
    with open(FIXTURES_DIR / "products_full.json", encoding="utf-8") as json_file:
        item: dict = json.load(json_file)[0]
    return item


def _api_handler(request: httpx.Request) -> httpx.Response:
    if request.method == "POST":
        payload = json.loads(request.content)
        product_id = payload["product"]["id"]
        if product_id == REJECTED_ID:
            return httpx.Response(400, json={"error": "bad payload"})
        return httpx.Response(200, json={"productId": product_id})

    product_path = request.url.path
    if product_path == "/products/60722/":
        return httpx.Response(200, json=_fixture_product())
    if product_path == "/products/1/":
        return httpx.Response(404, json={"detail": "Not found"})
    if product_path == "/products/2/":
        return httpx.Response(503, text="busy")
    if product_path == "/products/3/":
        return httpx.Response(200, json={"id": None})  # parser cannot handle this
    if product_path == "/products/4/":
        item = _fixture_product()
        item["id"] = str(int(REJECTED_ID))
        return httpx.Response(200, json=item)
    raise AssertionError(f"unexpected request {request.method} {request.url}")


def _run_batch(ids: list[float]) -> dict[float, AttemptResult]:
    batch = [StoringState(product_id=product_id) for product_id in ids]
    results = asyncio.run(
        store.store_product_details(batch, transport=httpx.MockTransport(_api_handler))
    )
    return {result.product_id: result for result in results}


def test_each_response_kind_maps_to_one_outcome():
    results = _run_batch([LIVE_ID, GONE_ID, FLAKY_ID, BROKEN_ID, REJECTED_ID])

    assert results[LIVE_ID].outcome is Outcome.STORED
    assert results[GONE_ID].outcome is Outcome.UNAVAILABLE
    assert results[FLAKY_ID].outcome is Outcome.TRANSIENT
    assert "503" in results[FLAKY_ID].error
    assert results[BROKEN_ID].outcome is Outcome.PERMANENT
    assert results[BROKEN_ID].error.startswith("parse error")
    assert results[REJECTED_ID].outcome is Outcome.PERMANENT
    assert "bad payload" in results[REJECTED_ID].error


def test_results_are_returned_in_batch_order():
    results = asyncio.run(
        store.store_product_details(
            [StoringState(product_id=GONE_ID), StoringState(product_id=LIVE_ID)],
            transport=httpx.MockTransport(_api_handler),
        )
    )
    assert [result.product_id for result in results] == [GONE_ID, LIVE_ID]


def test_transient_failures_retry_until_max_tries_then_fail_once():
    states = StoringStates([StoringState(product_id=FLAKY_ID)])
    for attempt in range(1, store.MAX_STORE_TRIES + 1):
        assert states.pending(), f"should still be pending before attempt {attempt}"
        states.apply([AttemptResult(FLAKY_ID, Outcome.TRANSIENT, "GET status 503")])

    (state,) = states.storing_states
    assert state.status is ProductStoringStatus.FAILED
    assert state.n_tries == store.MAX_STORE_TRIES
    assert state.last_error == "GET status 503"
    assert states.pending() == []


def test_permanent_failures_and_404s_do_not_retry():
    states = StoringStates([StoringState(product_id=BROKEN_ID), StoringState(product_id=GONE_ID)])
    states.apply(
        [
            AttemptResult(BROKEN_ID, Outcome.PERMANENT, "parse error"),
            AttemptResult(GONE_ID, Outcome.UNAVAILABLE),
        ]
    )
    assert states.pending() == []
    assert states.with_status(ProductStoringStatus.FAILED)[0].product_id == BROKEN_ID
    assert states.with_status(ProductStoringStatus.UNAVAILABLE)[0].product_id == GONE_ID


def _states(stored: int, unavailable: int, failed: int) -> StoringStates:
    states = []
    for i in range(stored):
        states.append(StoringState(product_id=float(i), status=ProductStoringStatus.SUCCESS))
    for i in range(unavailable):
        states.append(StoringState(product_id=1000.0 + i, status=ProductStoringStatus.UNAVAILABLE))
    for i in range(failed):
        states.append(StoringState(product_id=2000.0 + i, status=ProductStoringStatus.FAILED))
    return StoringStates(states)


def test_exit_code_ignores_unavailable_products():
    # Saturday's real shape: a third of the catalogue delisted, everything else stored.
    assert store.summarise(_states(stored=2360, unavailable=1174, failed=0)) == 0


def test_exit_code_flags_a_high_failure_rate():
    assert store.summarise(_states(stored=70, unavailable=500, failed=30)) == 1
    assert store.summarise(_states(stored=90, unavailable=500, failed=10)) == 0


def test_exit_code_flags_a_run_that_stored_nothing():
    assert store.summarise(_states(stored=0, unavailable=5, failed=0)) == 1
    assert store.summarise(_states(stored=0, unavailable=0, failed=0)) == 0


def test_partial_halves_split_the_ordered_list():
    states = [StoringState(product_id=float(i)) for i in range(5)]
    first = store._sample_storing_states(states, "first_half")
    second = store._sample_storing_states(states, "second_half")
    assert [s.product_id for s in first] + [s.product_id for s in second] == [
        0.0,
        1.0,
        2.0,
        3.0,
        4.0,
    ]
    with pytest.raises(ValueError):
        store._sample_storing_states(states, "first_quarter")
