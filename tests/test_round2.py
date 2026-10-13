"""Tests for Round 2 fixes:
- VectorDBBase inheritance & hybrid_search fallback (#1)
- Cold-start has_collection (#1 from Round 1)
- Reconnect generation counter & race safety (#2)
- Field projections in search, query, and get (#3)
- Narrowed _is_not_found (#4)
- O(K) cascade delete & idx_file_id DDL (#5)
- connect_timeout wiring in _connect (#6)
- Backtick stripping in _extract_record_key (#7)
"""

from __future__ import annotations

import socket
import threading
from unittest.mock import MagicMock, patch

import pytest

from owui_surrealdb_adapter.client import (
    SurrealDBClient,
    VectorDBBase,
    _is_db_missing,
    _is_not_found,
)
from owui_surrealdb_adapter.config import SurrealDBConfig


class TestVectorDBBaseInheritance:
    """Change #1: SurrealDBClient inherits VectorDBBase and its default hybrid_search."""

    def test_inherits_vectordb_base_and_hybrid_search_is_default(self):
        c = SurrealDBClient(config=SurrealDBConfig())
        assert isinstance(c, VectorDBBase)
        assert type(c).hybrid_search is VectorDBBase.hybrid_search
        assert c.hybrid_search("col", "query", [[0.1, 0.2]]) is None

    def test_has_collection_connects_on_cold_start(self):
        c = SurrealDBClient(config=SurrealDBConfig(table_prefix="owui_"))
        assert c.client is None

        with patch.object(c, "_ensure_connected") as mock_ensure, patch.object(
            c,
            "_execute_with_retry",
            return_value=[{"indexes": {"idx_vector": "DEFINE INDEX ..."}, "fields": {}}],
        ) as mock_exec:
            assert c.has_collection("file-123") is True
            mock_ensure.assert_called_once()
            mock_exec.assert_called_once_with("INFO FOR TABLE `owui_file-123`;")


class TestReconnectRaceAndGeneration:
    """Change #2: Two threads hit one dead socket -> one reconnect, zero AttributeErrors."""

    def test_concurrent_threads_single_reconnect_no_attribute_error(self):
        config = SurrealDBConfig(max_retries=2, retry_backoff=0.001)
        c = SurrealDBClient(config=config)

        dead_conn = MagicMock(name="dead_conn")
        live_conn = MagicMock(name="live_conn")

        # Initial state: connected on generation 1 with dead_conn
        c.client = dead_conn
        c._surreal_ctx = MagicMock()
        c._conn_generation = 1

        barrier = threading.Barrier(2)

        def dead_query_raw(query, params=None):
            # Both worker threads enter query_raw on the dead socket at the same time
            barrier.wait(timeout=2.0)
            raise ConnectionError("WebSocket connection closed")

        dead_conn.query_raw.side_effect = dead_query_raw
        live_conn.query_raw.return_value = {
            "result": [{"status": "OK", "result": [{"id": "t:1"}]}]
        }

        connect_calls = 0

        def fake_connect():
            nonlocal connect_calls
            connect_calls += 1
            c.client = live_conn
            c._surreal_ctx = MagicMock()
            c._conn_generation += 1

        results: list[ list] = []
        errors: list[BaseException] = []

        def worker():
            try:
                res = c._execute_with_retry("SELECT id FROM `owui_test`;")
                results.append(res)
            except BaseException as exc:
                errors.append(exc)

        with patch.object(c, "_connect", side_effect=fake_connect):
            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)
            t1.start()
            t2.start()
            t1.join(timeout=5.0)
            t2.join(timeout=5.0)

        assert errors == [], f"Unexpected thread errors: {errors}"
        assert len(results) == 2
        assert connect_calls == 1, f"Expected exactly 1 reconnect, got {connect_calls}"


class TestFieldProjections:
    """Change #3: search, query, and get omit embedding from SELECT projection."""

    def _make_client(self) -> SurrealDBClient:
        c = SurrealDBClient(config=SurrealDBConfig(table_prefix="owui_"))
        c.client = MagicMock()
        c._surreal_ctx = MagicMock()
        return c

    def test_search_projection_excludes_embedding(self):
        c = self._make_client()
        with patch.object(c, "_execute_with_retry", return_value=[[]]) as mock_exec:
            c.search("my_col", [[0.1, 0.2]], limit=5)
            sql = mock_exec.call_args[0][0]
            assert sql.startswith(
                "SELECT id, content, metadata, vector::distance::knn() AS dist FROM `owui_my_col`"
            )
            assert "SELECT *" not in sql

    def test_query_projection_excludes_embedding(self):
        c = self._make_client()
        with patch.object(
            c,
            "_execute_with_retry",
            return_value=[[{"id": "owui_my_col:1", "content": "hi", "metadata": {}}]],
        ) as mock_exec:
            c.query("my_col", {"source": "doc"})
            sql = mock_exec.call_args[0][0]
            assert sql.startswith("SELECT id, content, metadata FROM `owui_my_col`")
            assert "SELECT *" not in sql

    def test_get_projection_excludes_embedding(self):
        c = self._make_client()
        with patch.object(
            c,
            "_execute_with_retry",
            return_value=[[{"id": "owui_my_col:1", "content": "hi", "metadata": {}}]],
        ) as mock_exec:
            c.get("my_col")
            sql = mock_exec.call_args[0][0]
            assert sql == "SELECT id, content, metadata FROM `owui_my_col`;"


class TestNarrowedIsNotFound:
    """Change #4: _is_not_found matches only table-level errors, not generic 'does not exist'."""

    def test_table_not_found_matches(self):
        assert _is_not_found(Exception("The table 'owui_abc' does not exist")) is True
        assert _is_not_found(Exception("Table not found: owui_abc")) is True

    def test_non_table_does_not_exist_is_not_swallowed(self):
        assert _is_not_found(Exception("Index 'idx_vector' does not exist")) is False
        assert _is_not_found(Exception("Function 'vector::bad' does not exist")) is False
        assert _is_not_found(Exception("Parameter $foo does not exist")) is False

    def test_db_or_namespace_missing_still_excluded(self):
        db_exc = Exception("Database 'vectors' does not exist")
        ns_exc = Exception("Namespace 'owui' does not exist")
        assert _is_db_missing(db_exc) is True
        assert _is_not_found(db_exc) is False
        assert _is_not_found(ns_exc) is False


class TestCascadeDeleteSinglePass:
    """Change #5: O(K) cascade delete queries and idx_file_id index definition."""

    def test_cascade_delete_queries_once_per_other_kb(self):
        c = SurrealDBClient(config=SurrealDBConfig(table_prefix="owui_"))
        c.client = MagicMock()

        kb_del = "11111111-1111-1111-1111-111111111111"
        kb_other1 = "22222222-2222-2222-2222-222222222222"
        kb_other2 = "33333333-3333-3333-3333-333333333333"

        # Deleted KB has 3 files: f1 (shared with kb_other1), f2 (orphan), f3 (orphan)
        def side_effect(query: str, params=None):
            if f"`owui_{kb_del}`" in query and "SELECT array::distinct" in query:
                return [[{"file_ids": ["f1", "f2", "f3"]}]]
            if query == "INFO FOR DB;":
                return [
                    {
                        "tables": {
                            f"owui_{kb_del}": {},
                            f"owui_{kb_other1}": {},
                            f"owui_{kb_other2}": {},
                            "owui_file-f1": {},
                            "owui_file-f2": {},
                            "owui_file-f3": {},
                        }
                    }
                ]
            if f"`owui_{kb_other1}`" in query:
                return [[{"file_ids": ["f1"]}]]
            if f"`owui_{kb_other2}`" in query:
                return [[{"file_ids": ["f99"]}]]
            if query.startswith("REMOVE TABLE IF EXISTS"):
                return [None]
            raise AssertionError(f"Unexpected query: {query}")

        with patch.object(c, "_execute_with_retry", side_effect=side_effect) as mock_exec:
            dropped = c._cascade_delete_file_tables(kb_del)

        assert dropped == ["owui_file-f2", "owui_file-f3"]
        # 1 (target KB) + 1 (INFO FOR DB) + 2 (other KBs) + 2 (REMOVE TABLE) = 6 queries
        # (vs. 1 + 1 + 3*2 + 2 = 10 under the old O(F*K) loop)
        assert mock_exec.call_count == 6



class TestExtractRecordKeyBackticks:
    """Change #7: _extract_record_key strips backticks."""

    def test_strips_backticks_and_preserves_existing_formats(self):
        extract = SurrealDBClient._extract_record_key
        assert extract("owui_col:`abc-123`") == "abc-123"
        assert extract("`abc-123`") == "abc-123"
        assert extract("owui_col:⟨abc-123⟩") == "abc-123"
        assert extract("owui_col:plain_id") == "plain_id"