"""Tests for connection lifecycle and schema management (Phase 3).

Connection tests mock the Surreal SDK.
Schema tests verify correct SurrealQL generation via _execute_query mocking.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from owui_surrealdb_adapter.client import SurrealDBClient
from owui_surrealdb_adapter.config import SurrealDBConfig


# ---------------------------------------------------------------------------
# Connection lifecycle tests
# ---------------------------------------------------------------------------


@pytest.fixture
def ws_config():
    return SurrealDBConfig(
        uri="ws://localhost:8000/rpc",
        namespace="test_ns",
        database="test_db",
        user="root",
        password="root",
        table_prefix="test_",
    )


@pytest.fixture
def http_config():
    return SurrealDBConfig(
        uri="http://localhost:8000",
        namespace="test_ns",
        database="test_db",
        user="root",
        password="root",
        table_prefix="test_",
    )


class TestConnectionLifecycle:

    def test_connect_websocket(self, ws_config):
        """WebSocket URI creates a Surreal context manager connection."""
        client = SurrealDBClient(config=ws_config)
        assert client.client is None

        with patch("surrealdb.Surreal") as MockSurreal:
            mock_conn = MagicMock()
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            MockSurreal.return_value = mock_ctx

            client._connect()

            MockSurreal.assert_called_once_with("ws://localhost:8000/rpc")
            mock_conn.signin.assert_called_once_with(
                {"username": "root", "password": "root"}
            )
            mock_conn.use.assert_called_once_with("test_ns", "test_db")
            assert client.client is mock_conn

    def test_connect_http(self, http_config):
        """HTTP URI creates a Surreal context manager connection."""
        client = SurrealDBClient(config=http_config)

        with patch("surrealdb.Surreal") as MockSurreal:
            mock_conn = MagicMock()
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            MockSurreal.return_value = mock_ctx

            client._connect()

            MockSurreal.assert_called_once_with("http://localhost:8000")

    def test_ensure_connected_creates_connection_once(self, ws_config):
        """_ensure_connected only connects if client is None."""
        client = SurrealDBClient(config=ws_config)

        with patch.object(client, "_connect") as mock_connect:
            # First call — should connect
            client._ensure_connected()
            assert mock_connect.call_count == 1

            # Simulate that _connect set client
            client.client = MagicMock()

            # Second call — already connected, no-op
            client._ensure_connected()
            assert mock_connect.call_count == 1

    def test_auth_with_namespace_database(self, ws_config):
        """signin + use are called with config values."""
        client = SurrealDBClient(config=ws_config)

        with patch("surrealdb.Surreal") as MockSurreal:
            mock_conn = MagicMock()
            mock_ctx = MagicMock()
            mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
            mock_ctx.__exit__ = MagicMock(return_value=False)
            MockSurreal.return_value = mock_ctx

            client._connect()

            mock_conn.signin.assert_called_once_with(
                {"username": "root", "password": "root"}
            )
            mock_conn.use.assert_called_once_with("test_ns", "test_db")


# ---------------------------------------------------------------------------
# Schema / _create_collection tests
# ---------------------------------------------------------------------------


@pytest.fixture
def connected_client():
    """Client with mocked connection, ready for schema tests."""
    config = SurrealDBConfig(
        uri="ws://localhost:8000/rpc",
        namespace="test",
        database="test",
        user="root",
        password="root",
        table_prefix="test_",
        index_type="hnsw",
        ef_search=40,
    )
    client = SurrealDBClient(config=config)
    client.client = MagicMock()
    return client


class TestCreateCollection:

    def test_creates_schemafull_table_with_fields(self, connected_client):
        """_create_collection generates DEFINE TABLE + FIELD statements."""
        connected_client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}] * 6
        }

        connected_client._create_collection("my_docs", dimension=384)

        query_str = connected_client.client.query_raw.call_args[0][0]

        assert "DEFINE TABLE OVERWRITE" in query_str
        assert "test_my_docs" in query_str
        assert "SCHEMAFULL" in query_str
        assert "DEFINE FIELD OVERWRITE content" in query_str
        assert "DEFINE FIELD OVERWRITE embedding" in query_str
        assert "DEFINE FIELD OVERWRITE metadata" in query_str

    def test_creates_hnsw_index(self, connected_client):
        """Default config creates HNSW index with correct dimension."""
        connected_client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}] * 6
        }

        connected_client._create_collection("my_docs", dimension=384)

        query_str = connected_client.client.query_raw.call_args[0][0]

        assert "DEFINE INDEX OVERWRITE idx_vector" in query_str
        assert "HNSW DIMENSION 384" in query_str
        assert "DIST COSINE" in query_str

    def test_creates_diskann_index_when_configured(self):
        """DiskANN index type uses DISKANN instead of HNSW."""
        config = SurrealDBConfig(
            uri="ws://localhost:8000/rpc",
            namespace="test",
            database="test",
            user="root",
            password="root",
            table_prefix="test_",
            index_type="diskann",
        )
        client = SurrealDBClient(config=config)
        client.client = MagicMock()
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}] * 6
        }

        client._create_collection("my_docs", dimension=768)

        query_str = client.client.query_raw.call_args[0][0]
        assert "DISKANN DIMENSION 768" in query_str
        assert "HNSW" not in query_str

    def test_idempotent_define_overwrite(self, connected_client):
        """Running _create_collection twice doesn't error (DEFINE OVERWRITE)."""
        connected_client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}] * 6
        }

        # Run twice — should not raise
        connected_client._create_collection("my_docs", dimension=384)
        connected_client._create_collection("my_docs", dimension=384)

        assert connected_client.client.query_raw.call_count == 2
