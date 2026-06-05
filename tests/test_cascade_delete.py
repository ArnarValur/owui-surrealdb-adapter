"""Tests for cascade delete and purge_orphans functionality.

Requires a running SurrealDB instance (uses test namespace/database).
"""

from __future__ import annotations

import uuid

import pytest

from owui_surrealdb_adapter.client import SurrealDBClient, _UUID_RE
from owui_surrealdb_adapter.config import SurrealDBConfig
from tests.conftest import (
    TEST_SURREALDB_URI,
    TEST_SURREALDB_NS,
    TEST_SURREALDB_DB,
    TEST_SURREALDB_USER,
    TEST_SURREALDB_PASS,
    TEST_TABLE_PREFIX,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(cascade: bool = True) -> SurrealDBConfig:
    return SurrealDBConfig(
        uri=TEST_SURREALDB_URI,
        namespace=TEST_SURREALDB_NS,
        database=TEST_SURREALDB_DB,
        user=TEST_SURREALDB_USER,
        password=TEST_SURREALDB_PASS,
        table_prefix=TEST_TABLE_PREFIX,
        index_type="hnsw",
        ef_search=40,
        cascade_delete=cascade,
    )


def _fake_vector(dim: int = 4) -> list[float]:
    """Generate a simple deterministic vector."""
    return [0.1 * (i + 1) for i in range(dim)]


def _insert_file_items(
    client: SurrealDBClient, file_id: str, count: int = 3, dim: int = 4
) -> None:
    """Insert mock vector chunks into a file-{file_id} collection."""
    items = [
        {
            "id": f"chunk-{i}",
            "text": f"Content for chunk {i} of file {file_id}",
            "vector": _fake_vector(dim),
            "metadata": {"file_id": file_id, "source": "test"},
        }
        for i in range(count)
    ]
    client.upsert(f"file-{file_id}", items)


def _insert_kb_items(
    client: SurrealDBClient, kb_id: str, file_ids: list[str], dim: int = 4
) -> None:
    """Insert mock vector chunks into a KB collection, mimicking OWUI behavior."""
    items = []
    for file_id in file_ids:
        for i in range(2):  # 2 chunks per file in KB
            items.append({
                "id": f"{file_id}-chunk-{i}",
                "text": f"KB content from file {file_id} chunk {i}",
                "vector": _fake_vector(dim),
                "metadata": {"file_id": file_id, "source": "test"},
            })
    client.upsert(kb_id, items)


# ---------------------------------------------------------------------------
# UUID detection
# ---------------------------------------------------------------------------

class TestIsKbCollection:
    """Test _is_kb_collection() UUID detection."""

    def test_uuid_detected(self, client: SurrealDBClient):
        assert client._is_kb_collection("dc56fa18-d3ef-4b1f-ad18-a566e8a2fe6e")

    def test_file_prefix_not_detected(self, client: SurrealDBClient):
        assert not client._is_kb_collection("file-dc56fa18-d3ef-4b1f-ad18-a566e8a2fe6e")

    def test_knowledge_bases_not_detected(self, client: SurrealDBClient):
        assert not client._is_kb_collection("knowledge-bases")

    def test_user_memory_not_detected(self, client: SurrealDBClient):
        assert not client._is_kb_collection("user-memory-abc123")

    def test_random_string_not_detected(self, client: SurrealDBClient):
        assert not client._is_kb_collection("some-random-name")


# ---------------------------------------------------------------------------
# Cascade delete — live integration tests
# ---------------------------------------------------------------------------

@pytest.fixture
def cascade_client():
    """Client with cascade_delete=True, connected and cleaned up after test."""
    client = SurrealDBClient(config=_make_config(cascade=True))
    client._ensure_connected()
    yield client
    # Cleanup: remove all test-prefixed tables
    client.reset()
    client.close()


@pytest.fixture
def no_cascade_client():
    """Client with cascade_delete=False."""
    client = SurrealDBClient(config=_make_config(cascade=False))
    client._ensure_connected()
    yield client
    client.reset()
    client.close()


class TestCascadeDelete:
    """Live integration tests for cascade delete behavior."""

    def test_cascade_deletes_orphaned_file_tables(self, cascade_client: SurrealDBClient):
        """Delete KB → file tables only in that KB should be dropped."""
        kb_id = str(uuid.uuid4())
        file_ids = [str(uuid.uuid4()) for _ in range(3)]

        # Create file tables
        for fid in file_ids:
            _insert_file_items(cascade_client, fid)

        # Create KB collection referencing all 3 files
        _insert_kb_items(cascade_client, kb_id, file_ids)

        # Verify all tables exist
        assert cascade_client.has_collection(kb_id)
        for fid in file_ids:
            assert cascade_client.has_collection(f"file-{fid}")

        # Delete the KB
        cascade_client.delete_collection(kb_id)

        # KB table should be gone
        assert not cascade_client.has_collection(kb_id)

        # All 3 file tables should also be gone (orphaned)
        for fid in file_ids:
            assert not cascade_client.has_collection(f"file-{fid}"), \
                f"File table for {fid} should have been cascade-deleted"

    def test_cascade_preserves_shared_file_tables(self, cascade_client: SurrealDBClient):
        """File in 2 KBs → deleting 1 KB preserves the file table."""
        kb1_id = str(uuid.uuid4())
        kb2_id = str(uuid.uuid4())
        shared_file = str(uuid.uuid4())
        kb1_only_file = str(uuid.uuid4())

        # Create file tables
        _insert_file_items(cascade_client, shared_file)
        _insert_file_items(cascade_client, kb1_only_file)

        # KB1 has both files, KB2 has only shared_file
        _insert_kb_items(cascade_client, kb1_id, [shared_file, kb1_only_file])
        _insert_kb_items(cascade_client, kb2_id, [shared_file])

        # Delete KB1
        cascade_client.delete_collection(kb1_id)

        # KB1 gone
        assert not cascade_client.has_collection(kb1_id)
        # KB2 still exists
        assert cascade_client.has_collection(kb2_id)
        # Shared file should SURVIVE (still in KB2)
        assert cascade_client.has_collection(f"file-{shared_file}"), \
            "Shared file table should survive — still referenced by KB2"
        # KB1-only file should be DROPPED
        assert not cascade_client.has_collection(f"file-{kb1_only_file}"), \
            "KB1-only file table should have been cascade-deleted"

    def test_cascade_disabled(self, no_cascade_client: SurrealDBClient):
        """cascade_delete=False → file tables survive KB deletion."""
        kb_id = str(uuid.uuid4())
        file_id = str(uuid.uuid4())

        _insert_file_items(no_cascade_client, file_id)
        _insert_kb_items(no_cascade_client, kb_id, [file_id])

        no_cascade_client.delete_collection(kb_id)

        assert not no_cascade_client.has_collection(kb_id)
        # File table should SURVIVE (cascade disabled)
        assert no_cascade_client.has_collection(f"file-{file_id}"), \
            "File table should survive when cascade_delete is disabled"

    def test_cascade_skips_file_collections(self, cascade_client: SurrealDBClient):
        """Deleting a file-* collection should NOT trigger cascade."""
        file_id = str(uuid.uuid4())
        other_file_id = str(uuid.uuid4())

        _insert_file_items(cascade_client, file_id)
        _insert_file_items(cascade_client, other_file_id)

        # Delete a file collection directly
        cascade_client.delete_collection(f"file-{file_id}")

        # The deleted file table is gone
        assert not cascade_client.has_collection(f"file-{file_id}")
        # The other file table should be untouched
        assert cascade_client.has_collection(f"file-{other_file_id}"), \
            "Other file tables should not be affected by file-collection delete"

    def test_cascade_skips_knowledge_bases_collection(self, cascade_client: SurrealDBClient):
        """Deleting 'knowledge-bases' should NOT trigger cascade."""
        # Create a knowledge-bases collection with a test record
        cascade_client.upsert("knowledge-bases", [{
            "id": "test-kb",
            "text": "Test KB description",
            "vector": _fake_vector(4),
            "metadata": {},
        }])

        file_id = str(uuid.uuid4())
        _insert_file_items(cascade_client, file_id)

        cascade_client.delete_collection("knowledge-bases")

        assert not cascade_client.has_collection("knowledge-bases")
        assert cascade_client.has_collection(f"file-{file_id}"), \
            "File tables should survive knowledge-bases deletion"

    def test_cascade_handles_empty_kb(self, cascade_client: SurrealDBClient):
        """Deleting an empty KB collection should not error."""
        kb_id = str(uuid.uuid4())

        # Create empty KB table
        cascade_client._ensure_connected()
        cascade_client._create_collection(kb_id, 4)

        # Should not raise
        cascade_client.delete_collection(kb_id)
        assert not cascade_client.has_collection(kb_id)

    def test_cascade_handles_nonexistent_kb(self, cascade_client: SurrealDBClient):
        """Deleting a non-existent KB collection should not error."""
        kb_id = str(uuid.uuid4())
        # Should not raise
        cascade_client.delete_collection(kb_id)


# ---------------------------------------------------------------------------
# purge_orphans — live integration tests
# ---------------------------------------------------------------------------

class TestPurgeOrphans:
    """Live integration tests for purge_orphans()."""

    def test_purge_auto_discovery(self, cascade_client: SurrealDBClient):
        """Auto-discover mode: finds and drops orphaned file tables."""
        kb_id = str(uuid.uuid4())
        active_file = str(uuid.uuid4())
        orphan_file = str(uuid.uuid4())

        # Create both file tables
        _insert_file_items(cascade_client, active_file)
        _insert_file_items(cascade_client, orphan_file)

        # Only active_file is in a KB
        _insert_kb_items(cascade_client, kb_id, [active_file])

        # Purge orphans (auto-discovery)
        dropped = cascade_client.purge_orphans()

        # orphan_file should be dropped
        prefix = cascade_client.config.table_prefix
        assert f"{prefix}file-{orphan_file}" in dropped
        assert not cascade_client.has_collection(f"file-{orphan_file}")
        # active_file should survive
        assert cascade_client.has_collection(f"file-{active_file}")

    def test_purge_with_active_ids(self, cascade_client: SurrealDBClient):
        """Explicit active_file_ids set: only unlisted file tables are dropped."""
        file1 = str(uuid.uuid4())
        file2 = str(uuid.uuid4())
        file3 = str(uuid.uuid4())

        for fid in [file1, file2, file3]:
            _insert_file_items(cascade_client, fid)

        # Only file1 is "active"
        dropped = cascade_client.purge_orphans(active_file_ids={file1})

        prefix = cascade_client.config.table_prefix
        assert f"{prefix}file-{file2}" in dropped
        assert f"{prefix}file-{file3}" in dropped
        assert f"{prefix}file-{file1}" not in dropped

        assert cascade_client.has_collection(f"file-{file1}")
        assert not cascade_client.has_collection(f"file-{file2}")
        assert not cascade_client.has_collection(f"file-{file3}")

    def test_purge_dry_run(self, cascade_client: SurrealDBClient):
        """Dry run reports orphans without dropping them."""
        orphan = str(uuid.uuid4())
        _insert_file_items(cascade_client, orphan)

        # No KBs exist, so the file is orphaned
        dropped = cascade_client.purge_orphans(dry_run=True)

        prefix = cascade_client.config.table_prefix
        assert f"{prefix}file-{orphan}" in dropped
        # Table should still exist (dry run)
        assert cascade_client.has_collection(f"file-{orphan}")

    def test_purge_no_orphans(self, cascade_client: SurrealDBClient):
        """No orphans → returns empty list."""
        kb_id = str(uuid.uuid4())
        file_id = str(uuid.uuid4())

        _insert_file_items(cascade_client, file_id)
        _insert_kb_items(cascade_client, kb_id, [file_id])

        dropped = cascade_client.purge_orphans()
        assert dropped == []

    def test_purge_empty_db(self, cascade_client: SurrealDBClient):
        """Empty database → returns empty list."""
        dropped = cascade_client.purge_orphans()
        assert dropped == []
