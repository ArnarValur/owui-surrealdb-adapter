"""Tests for production hardening: input validation, reconnection, thread safety.

These tests verify the security and resilience fixes added in the hardening phase.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from owui_surrealdb_adapter.client import (
    SurrealDBClient,
    _validate_name,
    _validate_limit,
    _validate_filter_keys,
    _is_not_found,
    _is_transport_error,
    _INSERT_BATCH_SIZE,
)
from owui_surrealdb_adapter.config import SurrealDBConfig, _positive_int


# ---------------------------------------------------------------------------
# Input Validation Tests — SQL Injection Prevention
# ---------------------------------------------------------------------------


class TestValidateName:
    """Tests for _validate_name — the core injection prevention."""

    def test_valid_simple_name(self):
        _validate_name("docs")  # should not raise

    def test_valid_name_with_hyphens(self):
        _validate_name("file-550e8400-e29b-41d4-a716-446655440000")

    def test_valid_name_with_underscores(self):
        _validate_name("my_collection_v2")

    def test_valid_name_with_dots(self):
        _validate_name("my.collection")

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_name("")

    def test_rejects_backticks(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_name("docs`; DROP TABLE x; --")

    def test_rejects_semicolons(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_name("docs; REMOVE DATABASE vectors; --")

    def test_rejects_spaces(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_name("my collection")

    def test_rejects_sql_injection_attempt(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_name("x`; REMOVE DATABASE vectors; --`")

    def test_rejects_unicode_control_chars(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_name("docs\x00evil")


class TestValidateLimit:
    """Tests for _validate_limit — bounds checking."""

    def test_valid_int(self):
        assert _validate_limit(10) == 10

    def test_valid_string_int(self):
        assert _validate_limit("10") == 10

    def test_clamps_to_minimum(self):
        assert _validate_limit(0) == 1
        assert _validate_limit(-5) == 1

    def test_clamps_to_maximum(self):
        assert _validate_limit(99999) == 10000

    def test_rejects_non_numeric(self):
        with pytest.raises(ValueError, match="Invalid limit"):
            _validate_limit("abc")

    def test_rejects_none(self):
        with pytest.raises(ValueError, match="Invalid limit"):
            _validate_limit(None)


class TestValidateFilterKeys:
    """Tests for _validate_filter_keys — metadata key injection prevention."""

    def test_valid_keys(self):
        _validate_filter_keys({"file_id": "x", "status": "active"})  # should not raise

    def test_rejects_key_with_semicolon(self):
        with pytest.raises(ValueError, match="Invalid filter key"):
            _validate_filter_keys({"id; REMOVE TABLE x": "value"})

    def test_rejects_key_with_dot(self):
        with pytest.raises(ValueError, match="Invalid filter key"):
            _validate_filter_keys({"metadata.nested": "value"})

    def test_rejects_key_starting_with_number(self):
        with pytest.raises(ValueError, match="Invalid filter key"):
            _validate_filter_keys({"0bad": "value"})

    def test_allows_underscored_key(self):
        _validate_filter_keys({"_private_key": "value"})  # should not raise


# ---------------------------------------------------------------------------
# Transport Error Detection
# ---------------------------------------------------------------------------


class TestIsTransportError:
    """Tests for _is_transport_error — dead connection detection."""

    def test_detects_connection_closed(self):
        assert _is_transport_error(Exception("WebSocket connection closed"))

    def test_detects_connection_refused(self):
        assert _is_transport_error(Exception("connection refused"))

    def test_detects_broken_pipe(self):
        assert _is_transport_error(Exception("broken pipe"))

    def test_not_found_is_not_transport(self):
        assert _is_transport_error(Exception("table does not exist")) is False

    def test_generic_error_is_not_transport(self):
        assert _is_transport_error(Exception("invalid query syntax")) is False


class TestIsNotFound:
    """Tests for _is_not_found — table not found detection."""

    def test_detects_does_not_exist(self):
        assert _is_not_found(Exception("The table 'foo' does not exist"))

    def test_detects_table_not_found(self):
        assert _is_not_found(Exception("table not found"))

    def test_not_found_error_class(self):
        class NotFoundError(Exception):
            pass
        assert _is_not_found(NotFoundError("something"))

    def test_generic_error_is_not_not_found(self):
        assert _is_not_found(Exception("connection refused")) is False


# ---------------------------------------------------------------------------
# Config Validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    """Tests for config field validation."""

    def test_positive_int_valid(self):
        assert _positive_int("NONEXISTENT_VAR_12345", "42") == 42

    def test_positive_int_rejects_negative(self):
        with pytest.raises(ValueError, match="positive integer"):
            _positive_int("NONEXISTENT_VAR_12345", "-1")

    def test_positive_int_rejects_zero(self):
        with pytest.raises(ValueError, match="positive integer"):
            _positive_int("NONEXISTENT_VAR_12345", "0")

    def test_positive_int_rejects_non_numeric(self):
        with pytest.raises(ValueError, match="positive integer"):
            _positive_int("NONEXISTENT_VAR_12345", "abc")

    def test_config_has_connect_timeout(self):
        config = SurrealDBConfig()
        assert config.connect_timeout == 10

    def test_config_has_max_retries(self):
        config = SurrealDBConfig()
        assert config.max_retries == 3

    def test_config_has_retry_backoff(self):
        config = SurrealDBConfig()
        assert config.retry_backoff == 1.0


# ---------------------------------------------------------------------------
# Context Manager & Close
# ---------------------------------------------------------------------------


class TestContextManager:
    """Tests for close() and context manager support."""

    def test_close_clears_connection(self):
        config = SurrealDBConfig()
        c = SurrealDBClient(config=config)
        c.client = MagicMock()
        c._surreal_ctx = MagicMock()

        c.close()

        assert c.client is None
        assert c._surreal_ctx is None

    def test_close_calls_exit_on_context(self):
        config = SurrealDBConfig()
        c = SurrealDBClient(config=config)
        mock_ctx = MagicMock()
        c._surreal_ctx = mock_ctx
        c.client = MagicMock()

        c.close()

        mock_ctx.__exit__.assert_called_once_with(None, None, None)

    def test_close_idempotent(self):
        config = SurrealDBConfig()
        c = SurrealDBClient(config=config)
        # Close without any connection — should not raise
        c.close()
        c.close()

    def test_context_manager_exit_calls_close(self):
        config = SurrealDBConfig()
        c = SurrealDBClient(config=config)
        c.client = MagicMock()
        c._surreal_ctx = MagicMock()

        with patch.object(c, '_ensure_connected'):
            with c:
                pass  # __enter__ + __exit__

        assert c.client is None


# ---------------------------------------------------------------------------
# Reconnection Logic
# ---------------------------------------------------------------------------


class TestReconnection:
    """Tests for _execute_with_retry and _force_reconnect."""

    def _make_client(self):
        config = SurrealDBConfig(max_retries=2, retry_backoff=0.01)
        c = SurrealDBClient(config=config)
        c.client = MagicMock()
        c._surreal_ctx = MagicMock()
        return c

    def test_successful_query_no_retry(self):
        c = self._make_client()
        c.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": [1, 2, 3]}]
        }

        result = c._execute_with_retry("SELECT 1;")
        assert result == [[1, 2, 3]]
        assert c.client.query_raw.call_count == 1

    def test_retries_on_transport_error(self):
        c = self._make_client()

        # First call: transport error, second call: success
        call_count = 0
        def mock_query_raw(q, p=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("WebSocket connection closed")
            return {"result": [{"status": "OK", "result": "ok"}]}

        c.client.query_raw.side_effect = mock_query_raw

        with patch.object(c, '_force_reconnect'):
            with patch.object(c, '_ensure_connected'):
                result = c._execute_with_retry("SELECT 1;")

        assert result == ["ok"]

    def test_raises_after_max_retries(self):
        c = self._make_client()
        c.client.query_raw.side_effect = Exception("connection refused")

        with patch.object(c, '_force_reconnect'):
            with patch.object(c, '_ensure_connected'):
                with pytest.raises(ConnectionError, match="Failed to execute"):
                    c._execute_with_retry("SELECT 1;")

    def test_non_transport_errors_propagate_immediately(self):
        c = self._make_client()
        c.client.query_raw.side_effect = ValueError("invalid query")

        with pytest.raises(ValueError, match="invalid query"):
            # Should NOT be caught as transport, should raise immediately
            c._execute_with_retry("BAD QUERY;")


# ---------------------------------------------------------------------------
# Extract Record Key — Extended ID Formats
# ---------------------------------------------------------------------------


class TestExtractRecordKey:
    """Tests for _extract_record_key with all SurrealDB ID formats."""

    def test_simple_table_key(self):
        assert SurrealDBClient._extract_record_key("table:key") == "key"

    def test_bracket_wrapped_uuid(self):
        assert SurrealDBClient._extract_record_key(
            "table:⟨550e8400-e29b-41d4-a716-446655440000⟩"
        ) == "550e8400-e29b-41d4-a716-446655440000"

    def test_object_based_id(self):
        assert SurrealDBClient._extract_record_key(
            "table:{nested_id}"
        ) == "nested_id"

    def test_array_based_id(self):
        assert SurrealDBClient._extract_record_key(
            "table:[1,2,3]"
        ) == "1,2,3"

    def test_plain_key(self):
        assert SurrealDBClient._extract_record_key("simple_key") == "simple_key"

    def test_uuid_format_key(self):
        """Real OWUI ID pattern — UUID with hyphens."""
        assert SurrealDBClient._extract_record_key(
            "owui_file-abc123:⟨chunk-550e8400-e29b⟩"
        ) == "chunk-550e8400-e29b"


# ---------------------------------------------------------------------------
# Batch Insert Chunking
# ---------------------------------------------------------------------------


class TestBatchChunking:
    """Tests for large insert batching."""

    def test_small_batch_single_query(self):
        config = SurrealDBConfig()
        c = SurrealDBClient(config=config)
        c.client = MagicMock()
        c.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}]
        }

        with patch.object(c, 'has_collection', return_value=True):
            c.upsert("docs", [
                {"id": f"item{i}", "text": f"text{i}", "vector": [0.1], "metadata": {}}
                for i in range(5)
            ])

        # 5 items < _INSERT_BATCH_SIZE → single query
        assert c.client.query_raw.call_count == 1

    def test_large_batch_multiple_queries(self):
        config = SurrealDBConfig()
        c = SurrealDBClient(config=config)
        c.client = MagicMock()
        c.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}]
        }

        num_items = _INSERT_BATCH_SIZE + 50  # 150 items → 2 batches

        with patch.object(c, 'has_collection', return_value=True):
            c.upsert("docs", [
                {"id": f"item{i}", "text": f"text{i}", "vector": [0.1], "metadata": {}}
                for i in range(num_items)
            ])

        # Should be 2 queries: 100 + 50
        assert c.client.query_raw.call_count == 2

        # Verify batch sizes via params
        batch1_data = c.client.query_raw.call_args_list[0][1].get("data") if c.client.query_raw.call_args_list[0][1] else c.client.query_raw.call_args_list[0][0][1]["data"]
        assert len(batch1_data) == _INSERT_BATCH_SIZE


# ---------------------------------------------------------------------------
# Delete with Parameterized Queries
# ---------------------------------------------------------------------------


class TestDeleteParameterized:
    """Tests that delete uses parameterized queries (no SQL injection)."""

    def _make_client(self):
        config = SurrealDBConfig(table_prefix="test_")
        c = SurrealDBClient(config=config)
        c.client = MagicMock()
        c.client.query_raw.return_value = {
            "result": [{"status": "OK", "result": None}]
        }
        return c

    def test_delete_uses_validated_interpolation(self):
        """Delete by ID uses validated interpolation — IDs are checked by _validate_name first."""
        c = self._make_client()
        c.delete("docs", ids=["chunk1"])

        query = c.client.query_raw.call_args[0][0]
        assert "DELETE `test_docs`:`chunk1`" in query

    def test_delete_rejects_injection_in_id(self):
        """Crafted ID with injection attempt is rejected by validation."""
        c = self._make_client()
        with pytest.raises(ValueError, match="Invalid record_id"):
            c.delete("docs", ids=["`; REMOVE DATABASE vectors; --"])

    def test_delete_rejects_injection_in_collection(self):
        """Crafted collection name is rejected by validation."""
        c = self._make_client()
        with pytest.raises(ValueError, match="Invalid collection_name"):
            c.delete("docs`; DROP TABLE", ids=["chunk1"])

    def test_delete_by_filter_still_parameterized(self):
        """Filter-based delete uses parameterized WHERE clause."""
        c = self._make_client()
        c.delete("docs", filter={"file_id": "f1"})

        query = c.client.query_raw.call_args[0][0]
        params = c.client.query_raw.call_args[0][1]
        assert "WHERE" in query
        assert "metadata.file_id" in query
        assert params["fv0"] == "f1"
