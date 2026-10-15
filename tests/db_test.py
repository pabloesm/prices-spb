"""Integration tests for the DB layer.

Collected only when `TEST_DATABASE_URL` is set (see `conftest.py`). The schema is rebuilt
from `scripts/create_db.sql` once per module, so the target database must be disposable.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
import pytest

from src import db
from src.models import ScannedProduct
from src.store_products import store_product

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCHEMA_FILE = Path(__file__).parents[1] / "scripts" / "create_db.sql"


@pytest.fixture(scope="module", autouse=True)
def fresh_schema() -> None:
    conn = psycopg2.connect(os.environ["TEST_DATABASE_URL"])
    try:
        with conn, conn.cursor() as cur:
            cur.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
    finally:
        conn.close()


def _load_fixture(name: str) -> list[dict]:
    with open(FIXTURES_DIR / name, encoding="utf-8") as json_file:
        items: list[dict] = json.load(json_file)
    return items


def test_count_elements_in_table_on_fresh_schema():
    assert db.count_elements_in_table("product") == 0
    assert db.count_elements_in_table("scanned_products") == 0


def test_insert_scanned_product_is_idempotent():
    scanned_products = [ScannedProduct(**item) for item in _load_fixture("scanned_products.json")]
    unique_ids = {product.product_id for product in scanned_products}

    for scanned_product in scanned_products:
        db.insert_scanned_product(scanned_product)
    # A second pass must not create duplicates.
    for scanned_product in scanned_products:
        db.insert_scanned_product(scanned_product)

    assert db.count_elements_in_table("scanned_products") == len(unique_ids)
    assert set(db.get_all_scanned_product_ids()) == unique_ids


def test_store_product_full_is_idempotent():
    items = _load_fixture("products_full.json")
    expected_ids = {float(item["id"]) for item in items}

    for item in items:
        store_product(item)
    # A second pass must not create duplicate products.
    for item in items:
        store_product(item)

    assert db.count_elements_in_table("product") == len(expected_ids)
    assert db.count_elements_in_table("nutrition_information") == len(expected_ids)
    assert db.count_elements_in_table("photo") == sum(len(item["photos"]) for item in items)

    with db.cursor() as cur:
        cur.execute("SELECT id FROM product")
        assert {float(row[0]) for row in cur.fetchall()} == expected_ids


def test_availability_bookkeeping_drives_the_store_candidates():
    scanned = [ScannedProduct(**item) for item in _load_fixture("scanned_products.json")]
    for scanned_product in scanned:
        db.insert_scanned_product(scanned_product)
    all_ids = {product.product_id for product in scanned}
    live_id, gone_id = sorted(all_ids)[:2]
    now = datetime(2026, 10, 15, 12, 0, 0)

    # Nothing checked yet: every scanned product is a candidate, in id order.
    candidates = db.get_product_ids_to_store(recheck_unavailable_after_days=7)
    assert set(candidates) == all_ids
    assert candidates == sorted(candidates)

    # A 404 today removes the product from the candidates; a success keeps it.
    db.record_store_outcome([live_id], [gone_id], checked_at=datetime.now())
    assert gone_id not in db.get_product_ids_to_store(7)
    assert live_id in db.get_product_ids_to_store(7)

    # An unavailable product whose last check is old enough is re-probed.
    db.record_store_outcome([], [gone_id], checked_at=datetime.now() - timedelta(days=8))
    assert gone_id in db.get_product_ids_to_store(7)
    assert gone_id not in db.get_product_ids_to_store(30)

    # unavailable_since keeps the first 404 date across re-checks.
    with db.cursor() as cur:
        cur.execute(
            "SELECT unavailable_since FROM scanned_products WHERE product_id = %s", (gone_id,)
        )
        first_seen_gone = cur.fetchone()[0]
    db.record_store_outcome([], [gone_id], checked_at=now)
    with db.cursor() as cur:
        cur.execute(
            "SELECT unavailable_since FROM scanned_products WHERE product_id = %s", (gone_id,)
        )
        assert cur.fetchone()[0] == first_seen_gone

    # The scan seeing the product again clears the flag.
    assert db.clear_unavailable([gone_id, live_id]) == 1
    assert gone_id in db.get_product_ids_to_store(7)
    assert db.clear_unavailable([]) == 0
