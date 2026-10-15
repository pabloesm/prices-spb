"""Pytest configuration.

The tests in `db_test.py` insert real rows and recreate the schema, so they must never run
against the application database. They are collected only when `TEST_DATABASE_URL` points
at a disposable Postgres database; otherwise `uv run pytest` runs the unit tests alone and
needs no environment at all.

To run the DB tests locally:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/prices_spb_test uv run pytest
"""

import os

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

if not TEST_DATABASE_URL:
    collect_ignore = ["db_test.py"]
    # Unit tests import modules that build `Settings` at import time. Give the required
    # fields harmless values so the suite needs no environment. The DB pool is created
    # lazily, so this URL is never dialled.
    os.environ.setdefault("DATABASE_NEON_URL", "postgresql://unused:unused@127.0.0.1:1/unused")
    os.environ.setdefault("API_URL_TEMPLATE", "http://api.test/products/{id}/")
    os.environ.setdefault("CF_URL", "http://worker.test/")
    os.environ.setdefault("URL_SEED", "http://seed.test/categories/1")
else:
    if TEST_DATABASE_URL == os.environ.get("DATABASE_NEON_URL"):
        raise pytest.UsageError(
            "TEST_DATABASE_URL must point at a disposable database, not the one in "
            "DATABASE_NEON_URL: the DB tests drop and recreate every table."
        )
    # Point the application's DB layer at the test database. Process environment takes
    # precedence over `.env` in pydantic-settings, so this wins even if a `.env` exists.
    os.environ["DATABASE_NEON_URL"] = TEST_DATABASE_URL
    # Required by `Settings` but irrelevant to the DB tests.
    os.environ.setdefault("API_URL_TEMPLATE", "http://api.test/products/{id}/")
    os.environ.setdefault("CF_URL", "http://worker.test/")
    os.environ.setdefault("URL_SEED", "http://seed.test/categories/1")
