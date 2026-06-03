"""Tests for _execute_query() — safe multi-statement executor (Audit Bug #1).

These tests mock the SDK's query_raw() to verify our wrapper catches errors
that the SDK's query() silently swallows.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from owui_surrealdb_adapter.client import SurrealDBClient
from owui_surrealdb_adapter.config import SurrealDBConfig


@pytest.fixture
def mock_client():
    """Client with a mocked surrealdb.Surreal connection."""
    config = SurrealDBConfig(
        uri="ws://localhost:8000/rpc",
        namespace="test",
        database="test",
        user="root",
        password="root",
        table_prefix="test_",
    )
    client = SurrealDBClient(config=config)
    client.client = MagicMock()
    return client


class TestExecuteQuerySuccess:
    """Single and multi-statement success paths."""

    def test_single_statement_success_returns_result(self, mock_client):
        """A single successful statement returns its result."""
        mock_client.client.query_raw.return_value = {
            "result": [
                {"status": "OK", "result": [{"id": "test:1", "name": "doc"}]}
            ]
        }
        results = mock_client._execute_query("SELECT * FROM test;")
        assert results == [[{"id": "test:1", "name": "doc"}]]

    def test_multi_statement_success_returns_all_results(self, mock_client):
        """Multiple successful statements return all results in order."""
        mock_client.client.query_raw.return_value = {
            "result": [
                {"status": "OK", "result": None},  # DEFINE TABLE
                {"status": "OK", "result": None},  # DEFINE FIELD
                {"status": "OK", "result": None},  # DEFINE INDEX
            ]
        }
        results = mock_client._execute_query(
            "DEFINE TABLE t; DEFINE FIELD f ON t; DEFINE INDEX i ON t;"
        )
        assert len(results) == 3
        assert results == [None, None, None]

    def test_passes_params_to_query_raw(self, mock_client):
        """Parameters are forwarded to query_raw."""
        mock_client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": []}]
        }
        mock_client._execute_query("SELECT * FROM t WHERE x = $x;", {"x": 42})
        mock_client.client.query_raw.assert_called_once_with(
            "SELECT * FROM t WHERE x = $x;", {"x": 42}
        )

    def test_empty_result_list(self, mock_client):
        """An empty result list returns empty list."""
        mock_client.client.query_raw.return_value = {"result": []}
        results = mock_client._execute_query("-- comment only")
        assert results == []


class TestExecuteQueryStatementFailure:
    """Tests for per-statement error detection (audit bug #1 core fix)."""

    def test_single_statement_failure_raises(self, mock_client):
        """A single failing statement raises an exception."""
        mock_client.client.query_raw.return_value = {
            "result": [
                {
                    "status": "ERR",
                    "result": "There was a problem with the database: field 'x' not found",
                }
            ]
        }
        with pytest.raises(Exception):
            mock_client._execute_query("INSERT INTO t {x: 1};")

    def test_second_statement_failure_raises(self, mock_client):
        """When stmt 1 succeeds but stmt 2 fails, must still raise.

        This is the exact scenario the SDK's query() silently swallows.
        """
        mock_client.client.query_raw.return_value = {
            "result": [
                {"status": "OK", "result": None},  # DEFINE TABLE succeeds
                {
                    "status": "ERR",
                    "result": "There was a problem with the database: index error",
                },  # DEFINE INDEX fails
            ]
        }
        with pytest.raises(Exception):
            mock_client._execute_query(
                "DEFINE TABLE t SCHEMAFULL; DEFINE INDEX idx ON t FIELDS embedding HNSW;"
            )

    def test_third_statement_failure_raises(self, mock_client):
        """Failure in any position (not just [0] or [1]) is caught."""
        mock_client.client.query_raw.return_value = {
            "result": [
                {"status": "OK", "result": None},
                {"status": "OK", "result": None},
                {
                    "status": "ERR",
                    "result": "Some error on third statement",
                },
            ]
        }
        with pytest.raises(Exception):
            mock_client._execute_query("S1; S2; S3;")


class TestExecuteQueryRpcError:
    """Tests for top-level RPC/transport errors."""

    def test_rpc_error_raises(self, mock_client):
        """A top-level error field (transport/auth error) raises."""
        mock_client.client.query_raw.return_value = {
            "error": {"code": -32000, "message": "Not authenticated"}
        }
        with pytest.raises(Exception):
            mock_client._execute_query("SELECT * FROM t;")

    def test_rpc_error_takes_priority_over_results(self, mock_client):
        """If both error and result exist, error takes priority."""
        mock_client.client.query_raw.return_value = {
            "error": {"code": -32000, "message": "Auth failed"},
            "result": [{"status": "OK", "result": []}],
        }
        with pytest.raises(Exception):
            mock_client._execute_query("SELECT * FROM t;")
