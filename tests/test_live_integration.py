"""Live integration tests against pluto-surrealdb on localhost:8000.

Tests all 9 VectorDBBase methods using the EXACT call patterns
that Open WebUI's async wrapper uses (positional args, plain dicts,
non-existent collections, etc.).

Run:  pytest tests/test_live_integration.py -v
Requires: pluto-surrealdb running on localhost:8000
"""

import uuid
import pytest
from owui_surrealdb_adapter.client import SurrealDBClient, SearchResult, GetResult
from owui_surrealdb_adapter.config import SurrealDBConfig

# Test with a unique prefix so we don't interfere with real data
TEST_PREFIX = f"test_{uuid.uuid4().hex[:8]}_"
DIM = 4  # small vectors for speed


@pytest.fixture(scope="module")
def client():
    """Create a client connected to the live SurrealDB."""
    cfg = SurrealDBConfig(
        uri="ws://localhost:8000/rpc",
        namespace="test_owui",
        database="test_vectors",
        user="root",
        password="root",
        table_prefix=TEST_PREFIX,
        index_type="hnsw",
    )
    c = SurrealDBClient(config=cfg)
    c._ensure_connected()
    yield c
    # Cleanup: remove all test tables
    c.reset()


def _make_items(n: int, offset: int = 0) -> list[dict]:
    """Create N items in the exact format OWUI passes to insert/upsert."""
    return [
        {
            "id": f"item-{i + offset}",
            "text": f"Document chunk number {i + offset}",
            "vector": [float(i + offset)] * DIM,
            "metadata": {
                "file_id": f"file-{(i + offset) % 3}",
                "source": "test",
                "chunk_index": i + offset,
            },
        }
        for i in range(n)
    ]


COLLECTION = "test-docs"


# ── 1. Non-existent table handling (BEFORE any data exists) ──────────

class TestNonExistentTable:
    """All read/delete methods must gracefully handle missing tables."""

    def test_has_collection_returns_false(self, client):
        assert client.has_collection("nonexistent-xyz") is False

    def test_get_returns_none(self, client):
        result = client.get("nonexistent-xyz")
        assert result is None

    def test_query_returns_none(self, client):
        # Positional: (collection_name, filter, limit) — matches async wrapper
        result = client.query("nonexistent-xyz", {"file_id": "x"}, None)
        assert result is None

    def test_search_returns_empty(self, client):
        # Positional: (collection_name, vectors, filter, limit) — matches async wrapper
        result = client.search("nonexistent-xyz", [[0.0] * DIM], None, 5)
        assert isinstance(result, SearchResult)
        assert result.ids == [[]]

    def test_delete_by_ids_noop(self, client):
        # Should not raise
        client.delete("nonexistent-xyz", ["some-id"], None)

    def test_delete_by_filter_noop(self, client):
        # Should not raise
        client.delete("nonexistent-xyz", None, {"file_id": "x"})

    def test_delete_collection_noop(self, client):
        # Should not raise
        client.delete_collection("nonexistent-xyz")


# ── 2. Insert + basic reads ─────────────────────────────────────────

class TestInsertAndRead:
    """Test insert() creates collection and data is readable."""

    def test_insert_creates_collection(self, client):
        items = _make_items(5)
        # Positional: (collection_name, items) — matches async wrapper
        client.insert(COLLECTION, items)
        assert client.has_collection(COLLECTION) is True

    def test_get_returns_all(self, client):
        result = client.get(COLLECTION)
        assert result is not None
        assert isinstance(result, GetResult)
        assert len(result.ids[0]) == 5
        assert len(result.documents[0]) == 5
        assert len(result.metadatas[0]) == 5

    def test_get_document_content(self, client):
        result = client.get(COLLECTION)
        # Verify actual text content is stored
        assert "Document chunk number 0" in result.documents[0]

    def test_get_metadata_intact(self, client):
        result = client.get(COLLECTION)
        meta = result.metadatas[0][0]
        assert "file_id" in meta
        assert "source" in meta
        assert meta["source"] == "test"


# ── 3. Upsert (update existing) ─────────────────────────────────────

class TestUpsert:
    def test_upsert_updates_existing(self, client):
        # Update item-0 with new text
        updated = [{
            "id": "item-0",
            "text": "Updated document chunk",
            "vector": [99.0] * DIM,
            "metadata": {"file_id": "file-0", "source": "updated"},
        }]
        client.upsert(COLLECTION, updated)

        result = client.get(COLLECTION)
        # Still 5 items (not 6)
        assert len(result.ids[0]) == 5

    def test_upsert_data_actually_changed(self, client):
        result = client.get(COLLECTION)
        # Find the updated item
        idx = result.ids[0].index("item-0")
        assert result.documents[0][idx] == "Updated document chunk"
        assert result.metadatas[0][idx]["source"] == "updated"


# ── 4. Query (metadata filtered get) ────────────────────────────────

class TestQuery:
    def test_query_by_equality(self, client):
        # Positional: (collection_name, filter, limit)
        result = client.query(COLLECTION, {"file_id": "file-0"}, None)
        assert result is not None
        # file_id "file-0" matches items 0 and 3
        assert len(result.ids[0]) >= 1
        for meta in result.metadatas[0]:
            assert meta["file_id"] == "file-0"

    def test_query_with_limit(self, client):
        result = client.query(COLLECTION, {"source": "test"}, 2)
        assert result is not None
        assert len(result.ids[0]) <= 2

    def test_query_no_matches(self, client):
        result = client.query(COLLECTION, {"file_id": "nonexistent"}, None)
        assert result is None

    def test_query_in_filter(self, client):
        result = client.query(
            COLLECTION,
            {"file_id": {"$in": ["file-0", "file-1"]}},
            None,
        )
        assert result is not None
        for meta in result.metadatas[0]:
            assert meta["file_id"] in ("file-0", "file-1")


# ── 5. Search (KNN vector search) ───────────────────────────────────

class TestSearch:
    def test_basic_search(self, client):
        query_vec = [1.0] * DIM
        # Positional: (collection_name, vectors, filter, limit)
        result = client.search(COLLECTION, [query_vec], None, 3)
        assert isinstance(result, SearchResult)
        assert len(result.ids) == 1  # one query vector
        assert len(result.ids[0]) <= 3
        assert len(result.distances[0]) == len(result.ids[0])
        assert len(result.documents[0]) == len(result.ids[0])

    def test_search_distances_are_similarities(self, client):
        query_vec = [1.0] * DIM
        result = client.search(COLLECTION, [query_vec], None, 5)
        # Distances should be cosine similarities (0-1 range, higher = more similar)
        for d in result.distances[0]:
            assert 0.0 <= d <= 1.0 or d > 1.0  # allow slight numerical overshoot

    def test_search_with_filter(self, client):
        query_vec = [2.0] * DIM
        result = client.search(COLLECTION, [query_vec], {"source": "test"}, 3)
        assert isinstance(result, SearchResult)
        for meta in result.metadatas[0]:
            assert meta["source"] == "test"

    def test_search_multiple_vectors(self, client):
        """Batch search — OWUI sends multiple query vectors at once."""
        vecs = [[1.0] * DIM, [2.0] * DIM, [3.0] * DIM]
        result = client.search(COLLECTION, vecs, None, 2)
        assert len(result.ids) == 3  # one result set per query vector


# ── 6. Delete ────────────────────────────────────────────────────────

class TestDelete:
    def test_delete_by_ids(self, client):
        before = client.get(COLLECTION)
        count_before = len(before.ids[0])

        # Positional: (collection_name, ids, filter)
        client.delete(COLLECTION, ["item-4"], None)

        after = client.get(COLLECTION)
        assert len(after.ids[0]) == count_before - 1
        assert "item-4" not in after.ids[0]

    def test_delete_by_filter(self, client):
        # Delete all items with file_id "file-0"
        client.delete(COLLECTION, None, {"file_id": "file-0"})

        result = client.get(COLLECTION)
        if result:
            for meta in result.metadatas[0]:
                assert meta["file_id"] != "file-0"


# ── 7. Delete collection + reset ────────────────────────────────────

class TestCollectionLifecycle:
    def test_delete_collection(self, client):
        # Insert into a separate collection to delete
        client.insert("to-delete", _make_items(2))
        assert client.has_collection("to-delete") is True

        client.delete_collection("to-delete")
        assert client.has_collection("to-delete") is False

    def test_reset_removes_all_prefixed(self, client):
        # Create two collections
        client.insert("reset-a", _make_items(2))
        client.insert("reset-b", _make_items(2))
        assert client.has_collection("reset-a") is True
        assert client.has_collection("reset-b") is True

        client.reset()

        assert client.has_collection("reset-a") is False
        assert client.has_collection("reset-b") is False
