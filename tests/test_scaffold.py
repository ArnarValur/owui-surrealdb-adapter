"""Smoke tests for package scaffolding — verifies import and config work."""

from __future__ import annotations

import os

from owui_surrealdb_adapter import __version__, SurrealDBClient
from owui_surrealdb_adapter.config import SurrealDBConfig


def test_version():
    assert __version__ == "2.0.0"


def test_config_defaults():
    config = SurrealDBConfig()
    assert config.uri == os.getenv("SURREALDB_URI", "ws://localhost:8000/rpc")
    assert config.namespace == os.getenv("SURREALDB_NS", "owui")
    assert config.table_prefix == os.getenv("SURREALDB_TABLE_PREFIX", "owui_")
    assert config.index_type == os.getenv("SURREALDB_INDEX_TYPE", "hnsw")
    assert config.ef_search == int(os.getenv("SURREALDB_EF_SEARCH", "40"))


def test_config_is_websocket():
    ws = SurrealDBConfig(uri="ws://localhost:8000/rpc")
    assert ws.is_websocket is True

    http = SurrealDBConfig(uri="http://localhost:8000")
    assert http.is_websocket is False


def test_client_init(test_config):
    client = SurrealDBClient(config=test_config)
    assert client.config is test_config
    assert client.client is None


def test_client_prefixed(client):
    assert client._prefixed("my_docs") == "test_my_docs"
