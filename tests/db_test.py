"""Integration tests for the DB layer.

Collected only when `TEST_DATABASE_URL` is set (see `conftest.py`). The schema is rebuilt
from `scripts/create_db.sql` once per module, so the target database must be disposable.
"""

import json
import os
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
