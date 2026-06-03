"""Shared test fixtures for owui-surrealdb-adapter integration tests."""

from __future__ import annotations

import os
import pytest

from owui_surrealdb_adapter.config import SurrealDBConfig
from owui_surrealdb_adapter.client import SurrealDBClient


# ---------------------------------------------------------------------------
# Test configuration — uses env vars or falls back to PlutoII defaults
# ---------------------------------------------------------------------------

TEST_SURREALDB_URI = os.getenv("TEST_SURREALDB_URI", "ws://localhost:8000/rpc")
TEST_SURREALDB_NS = os.getenv("TEST_SURREALDB_NS", "owui_test")
TEST_SURREALDB_DB = os.getenv("TEST_SURREALDB_DB", "vectors_test")
TEST_SURREALDB_USER = os.getenv("TEST_SURREALDB_USER", "root")
TEST_SURREALDB_PASS = os.getenv("TEST_SURREALDB_PASS", "root")
TEST_TABLE_PREFIX = "test_"


@pytest.fixture
def test_config() -> SurrealDBConfig:
    """Config pointing at the test SurrealDB instance."""
    return SurrealDBConfig(
        uri=TEST_SURREALDB_URI,
        namespace=TEST_SURREALDB_NS,
        database=TEST_SURREALDB_DB,
        user=TEST_SURREALDB_USER,
        password=TEST_SURREALDB_PASS,
        table_prefix=TEST_TABLE_PREFIX,
        index_type="hnsw",
        ef_search=40,
    )


@pytest.fixture
def client(test_config: SurrealDBConfig) -> SurrealDBClient:
    """A SurrealDBClient instance with test config (not connected)."""
    return SurrealDBClient(config=test_config)
