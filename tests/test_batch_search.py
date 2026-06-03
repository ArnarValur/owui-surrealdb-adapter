"""Tests for batch vector search (Phase 5 — Audit Bug #5)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from owui_surrealdb_adapter.client import SurrealDBClient
from owui_surrealdb_adapter.config import SurrealDBConfig


@pytest.fixture
def client():
    config = SurrealDBConfig(
        uri="ws://localhost:8000/rpc",
        namespace="test",
        database="test",
        user="root",
        password="root",
        table_prefix="test_",
    )
    c = SurrealDBClient(config=config)
    c.client = MagicMock()
    return c


class TestBatchVectorSearch:

    def test_single_vector_single_result_set(self, client):
        """Search with 1 vector → 1 result set."""
        client.client.query_raw.return_value = {
            "result": [{
                "status": "OK",
                "result": [
                    {"id": "test_docs:c1", "content": "a", "metadata": {}, "dist": 0.1},
                ],
            }]
        }

        result = client.search("docs", [[0.1, 0.2]], limit=5)

        assert len(result.ids) == 1
        assert result.ids[0] == ["c1"]

    def test_three_vectors_three_result_sets(self, client):
        """Search with 3 vectors → 3 result sets (audit bug #5 fix)."""
        # Each query_raw call returns different results
        client.client.query_raw.side_effect = [
            {"result": [{"status": "OK", "result": [
                {"id": "test_docs:a1", "content": "x", "metadata": {}, "dist": 0.1},
            ]}]},
            {"result": [{"status": "OK", "result": [
                {"id": "test_docs:b1", "content": "y", "metadata": {}, "dist": 0.2},
            ]}]},
            {"result": [{"status": "OK", "result": [
                {"id": "test_docs:c1", "content": "z", "metadata": {}, "dist": 0.3},
            ]}]},
        ]

        vectors = [[0.1], [0.2], [0.3]]
        result = client.search("docs", vectors, limit=5)

        assert len(result.ids) == 3
        assert result.ids[0] == ["a1"]
        assert result.ids[1] == ["b1"]
        assert result.ids[2] == ["c1"]

        # Verify 3 separate queries were made
        assert client.client.query_raw.call_count == 3

    def test_empty_vectors_returns_empty(self, client):
        """Search with 0 vectors → empty result."""
        result = client.search("docs", [], limit=5)

        assert len(result.ids) == 0
        assert client.client.query_raw.call_count == 0
