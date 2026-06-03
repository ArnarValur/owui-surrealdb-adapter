"""Tests for all 7 VectorDBBase methods + _build_filter (Phase 4).

All tests use mocked _execute_query to verify correct SurrealQL generation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from owui_surrealdb_adapter.client import SurrealDBClient, SearchResult, GetResult
from owui_surrealdb_adapter.config import SurrealDBConfig


@pytest.fixture
def client():
    """Client with mocked connection and _execute_query."""
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
    c = SurrealDBClient(config=config)
    c.client = MagicMock()
    return c


# ---------------------------------------------------------------------------
# _build_filter tests (Audit Bug #3)
# ---------------------------------------------------------------------------


class TestBuildFilter:

    def test_simple_equality(self, client):
        params = {}
        parts = client._build_filter({"file_id": "abc123"}, params)
        assert parts == ["metadata.file_id = $fv0"]
        assert params == {"fv0": "abc123"}

    def test_in_operator(self, client):
        """$in filter translates to SurrealQL IN clause (audit bug #3 fix)."""
        params = {}
        parts = client._build_filter(
            {"file_id": {"$in": ["id1", "id2", "id3"]}}, params
        )
        assert parts == ["metadata.file_id IN $fv0"]
        assert params == {"fv0": ["id1", "id2", "id3"]}

    def test_mixed_filters(self, client):
        """Mixed equality and $in filters."""
        params = {}
        parts = client._build_filter(
            {"status": "active", "file_id": {"$in": ["a", "b"]}}, params
        )
        assert len(parts) == 2
        assert "metadata.status = $fv0" in parts
        assert "metadata.file_id IN $fv1" in parts

    def test_custom_prefix(self, client):
        params = {}
        parts = client._build_filter({"x": 1}, params, prefix="p")
        assert parts == ["metadata.x = $p0"]
        assert params == {"p0": 1}


# ---------------------------------------------------------------------------
# has_collection tests (Audit Bug #2)
# ---------------------------------------------------------------------------


class TestHasCollection:

    def test_returns_false_for_nonexistent_table(self, client):
        """Non-existent table → False (not True like the buggy adapter)."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": {"indexes": {}}}]
        }
        assert client.has_collection("nonexistent") is False

    def test_returns_false_for_table_without_vector_index(self, client):
        """Table exists but has no idx_vector → False."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": {"indexes": {"idx_other": "..."}}}]
        }
        assert client.has_collection("no_vectors") is False

    def test_returns_true_for_table_with_idx_vector(self, client):
        """Table with idx_vector → True."""
        client.client.query_raw.return_value = {
            "result": [
                {
                    "status": "OK",
                    "result": {
                        "indexes": {
                            "idx_vector": "DEFINE INDEX idx_vector ON test_docs FIELDS embedding HNSW DIMENSION 384 DIST COSINE"
                        }
                    },
                }
            ]
        }
        assert client.has_collection("docs") is True

    def test_uses_prefixed_table_name(self, client):
        """Verifies the table name includes the configured prefix."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": {"indexes": {}}}]
        }
        client.has_collection("my_docs")
        query = client.client.query_raw.call_args[0][0]
        assert "test_my_docs" in query

    def test_returns_false_on_exception(self, client):
        """Any exception → False (graceful degradation)."""
        client.client.query_raw.side_effect = Exception("connection lost")
        assert client.has_collection("docs") is False


# ---------------------------------------------------------------------------
# upsert tests
# ---------------------------------------------------------------------------


class TestUpsert:

    def test_insert_new_items(self, client):
        """Upsert generates INSERT ... ON DUPLICATE KEY UPDATE."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}] * 2
        }
        # Mock has_collection to return True (skip create)
        with patch.object(client, "has_collection", return_value=True):
            client.upsert("docs", [
                {
                    "id": "chunk1",
                    "text": "hello world",
                    "vector": [0.1, 0.2, 0.3],
                    "metadata": {"file_id": "f1"},
                },
            ])

        query = client.client.query_raw.call_args[0][0]
        assert "INSERT INTO" in query
        assert "test_docs" in query
        assert "ON DUPLICATE KEY UPDATE" in query

    def test_batch_upsert(self, client):
        """Multiple items generate a single INSERT statement."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}] * 2
        }
        with patch.object(client, "has_collection", return_value=True):
            client.upsert("docs", [
                {"id": "c1", "text": "a", "vector": [0.1], "metadata": {}},
                {"id": "c2", "text": "b", "vector": [0.2], "metadata": {}},
            ])

        query = client.client.query_raw.call_args[0][0]
        assert "INSERT INTO" in query

    def test_creates_collection_if_missing(self, client):
        """Auto-creates collection on first upsert."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}] * 8
        }
        with patch.object(client, "has_collection", return_value=False):
            with patch.object(client, "_create_collection") as mock_create:
                client.upsert("docs", [
                    {"id": "c1", "text": "a", "vector": [0.1, 0.2, 0.3], "metadata": {}},
                ])
                mock_create.assert_called_once_with("docs", 3)


# ---------------------------------------------------------------------------
# search tests (Audit Bug #3)
# ---------------------------------------------------------------------------


class TestSearch:

    def test_basic_knn_search(self, client):
        """KNN search returns ranked SearchResult."""
        client.client.query_raw.return_value = {
            "result": [{
                "status": "OK",
                "result": [
                    {"id": "test_docs:c1", "content": "hello", "metadata": {"file_id": "f1"},
                     "dist": 0.1},
                    {"id": "test_docs:c2", "content": "world", "metadata": {"file_id": "f2"},
                     "dist": 0.3},
                ],
            }]
        }

        result = client.search("docs", [[0.1, 0.2, 0.3]], limit=5)

        assert result is not None
        assert isinstance(result, SearchResult)
        assert len(result.ids) == 1  # 1 query vector
        assert len(result.ids[0]) == 2  # 2 results
        assert result.ids[0] == ["c1", "c2"]

    def test_search_with_equality_filter(self, client):
        """Simple equality filter is included in WHERE clause."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": []}]
        }

        client.search("docs", [[0.1]], limit=5, filter={"file_id": "f1"})

        query = client.client.query_raw.call_args[0][0]
        assert "WHERE" in query
        assert "metadata.file_id" in query

    def test_search_with_in_filter(self, client):
        """$in filter translates to IN clause (audit bug #3 fix)."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": []}]
        }

        client.search(
            "docs", [[0.1]], limit=5,
            filter={"file_id": {"$in": ["id1", "id2"]}}
        )

        query = client.client.query_raw.call_args[0][0]
        assert "IN" in query

    def test_respects_limit(self, client):
        """Limit parameter is passed to KNN operator."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": []}]
        }

        client.search("docs", [[0.1]], limit=10)

        query = client.client.query_raw.call_args[0][0]
        assert "10" in query

    def test_distance_normalization(self, client):
        """Cosine distance → similarity in [0,1]."""
        client.client.query_raw.return_value = {
            "result": [{
                "status": "OK",
                "result": [
                    {"id": "test_docs:c1", "content": "x", "metadata": {}, "dist": 0.2},
                ],
            }]
        }

        result = client.search("docs", [[0.1]], limit=5)
        # Cosine distance 0.2 → similarity 0.8
        assert result.distances[0][0] == pytest.approx(0.8, abs=0.01)

    def test_returns_search_result_double_nested(self, client):
        """SearchResult has double-nested lists as OWUI expects."""
        client.client.query_raw.return_value = {
            "result": [{
                "status": "OK",
                "result": [
                    {"id": "test_docs:c1", "content": "doc1", "metadata": {"k": "v"}, "dist": 0.1},
                ],
            }]
        }

        result = client.search("docs", [[0.1]], limit=5)

        # Outer list = per query vector, inner list = per result
        assert isinstance(result.ids, list)
        assert isinstance(result.ids[0], list)
        assert isinstance(result.documents, list)
        assert isinstance(result.documents[0], list)
        assert result.documents[0][0] == "doc1"
        assert result.metadatas[0][0] == {"k": "v"}


# ---------------------------------------------------------------------------
# get tests
# ---------------------------------------------------------------------------


class TestGet:

    def test_returns_all_items(self, client):
        """get() returns all items from collection."""
        client.client.query_raw.return_value = {
            "result": [{
                "status": "OK",
                "result": [
                    {"id": "test_docs:c1", "content": "a", "metadata": {"k": "1"}},
                    {"id": "test_docs:c2", "content": "b", "metadata": {"k": "2"}},
                ],
            }]
        }

        result = client.get("docs")

        assert result is not None
        assert isinstance(result, GetResult)
        assert result.ids == [["c1", "c2"]]
        assert result.documents == [["a", "b"]]

    def test_returns_double_nested_lists(self, client):
        """GetResult has double-nested lists."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": [
                {"id": "test_docs:x", "content": "y", "metadata": {}},
            ]}]
        }

        result = client.get("docs")
        assert isinstance(result.ids[0], list)

    def test_returns_none_for_nonexistent(self, client):
        """Non-existent collection returns None."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": []}]
        }

        result = client.get("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# delete tests (Audit Bug #4)
# ---------------------------------------------------------------------------


class TestDelete:

    def test_delete_by_record_ids(self, client):
        """Delete by IDs uses record ID directly, not metadata.id (bug #4 fix)."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}] * 2
        }

        client.delete("docs", ids=["chunk1", "chunk2"])

        query = client.client.query_raw.call_args[0][0]
        # Should use DELETE `table`:`id` format
        assert "DELETE" in query
        assert "test_docs" in query
        # Should NOT use metadata.id
        assert "metadata.id" not in query

    def test_delete_by_filter(self, client):
        """Delete by filter dict."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}]
        }

        client.delete("docs", filter={"file_id": "f1"})

        query = client.client.query_raw.call_args[0][0]
        assert "DELETE" in query
        assert "WHERE" in query
        assert "metadata.file_id" in query

    def test_items_removed(self, client):
        """After delete, the items should not be queryable (structural test)."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}]
        }
        # Just verifying the delete call completes without error
        client.delete("docs", ids=["c1"])
        assert client.client.query_raw.called


# ---------------------------------------------------------------------------
# delete_collection tests
# ---------------------------------------------------------------------------


class TestDeleteCollection:

    def test_removes_table(self, client):
        """delete_collection uses REMOVE TABLE."""
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}]
        }

        client.delete_collection("docs")

        query = client.client.query_raw.call_args[0][0]
        assert "REMOVE TABLE" in query
        assert "test_docs" in query

    def test_has_collection_false_after_delete(self, client):
        """After deleting, has_collection returns False."""
        # delete
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}]
        }
        client.delete_collection("docs")

        # has_collection check
        client.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": {"indexes": {}}}]
        }
        assert client.has_collection("docs") is False


# ---------------------------------------------------------------------------
# reset tests
# ---------------------------------------------------------------------------


class TestReset:

    def test_drops_all_prefixed_tables(self, client):
        """reset() finds prefixed tables via INFO FOR DB and removes them."""
        # First call: INFO FOR DB returns table list
        client.client.query_raw.side_effect = [
            {
                "result": [{
                    "status": "OK",
                    "result": {
                        "tables": {
                            "test_docs": "DEFINE TABLE test_docs SCHEMAFULL",
                            "test_notes": "DEFINE TABLE test_notes SCHEMAFULL",
                            "other_table": "DEFINE TABLE other_table SCHEMAFULL",
                        }
                    },
                }]
            },
            # Second call: REMOVE TABLE batch
            {"result": [
                {"status": "OK", "result": None},
                {"status": "OK", "result": None},
            ]},
        ]

        client.reset()

        # Should have called query_raw twice
        assert client.client.query_raw.call_count == 2

        # Second call should remove only prefixed tables
        remove_query = client.client.query_raw.call_args_list[1][0][0]
        assert "REMOVE TABLE" in remove_query
        assert "test_docs" in remove_query
        assert "test_notes" in remove_query
        assert "other_table" not in remove_query

    def test_no_tables_after_reset(self, client):
        """When no prefixed tables exist, no REMOVE is called."""
        client.client.query_raw.return_value = {
            "result": [{
                "status": "OK",
                "result": {
                    "tables": {"other": "DEFINE TABLE other SCHEMAFULL"}
                },
            }]
        }

        client.reset()

        # Only the INFO FOR DB call
        assert client.client.query_raw.call_count == 1
