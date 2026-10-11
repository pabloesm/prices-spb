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
    for name in ("API_URL_TEMPLATE", "CF_URL", "URL_SEED"):
        os.environ.setdefault(name, "unused-in-tests")
