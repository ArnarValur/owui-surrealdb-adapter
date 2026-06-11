"""Tests for metadata-only (zero-dimension) collection support.

Covers the first-KB registration bug where OWUI's 'knowledge-bases'
collection has no vectors, causing upsert() to skip table creation.
"""

import pytest


class TestMetadataOnlyCollections:
    """Tests for collections without vector embeddings (dimension=0)."""

    def test_upsert_zero_dimension_creates_table(self, client):
        """Upserting items with empty vectors should still create the table."""
        collection = "test-metadata-only"
        items = [
            {
                "id": "item-1",
                "text": "some text",
                "vector": [],
                "metadata": {"key": "value"},
            }
        ]
        client.upsert(collection, items)

        # Table should exist and be queryable
        result = client.get(collection)
        assert result is not None
        assert result.ids == [["item-1"]]
        assert result.documents == [["some text"]]

    def test_has_collection_metadata_only(self, client):
        """has_collection() should return True for metadata-only tables."""
        collection = "test-metadata-has"
        items = [
            {
                "id": "rec-1",
                "text": "hello",
                "vector": [],
                "metadata": {"foo": "bar"},
            }
        ]
        client.upsert(collection, items)

        assert client.has_collection(collection) is True

    def test_upsert_metadata_only_idempotent(self, client):
        """Multiple upserts to metadata-only collection should work."""
        collection = "test-metadata-idem"
        items1 = [
            {"id": "a", "text": "first", "vector": [], "metadata": {"n": 1}},
        ]
        items2 = [
            {"id": "b", "text": "second", "vector": [], "metadata": {"n": 2}},
        ]
        client.upsert(collection, items1)
        client.upsert(collection, items2)

        result = client.get(collection)
        assert result is not None
        assert len(result.ids[0]) == 2

    def test_knowledge_bases_flow(self, client):
        """Simulate OWUI's knowledge-bases registration pattern.

        OWUI upserts KB metadata (no vectors) into 'knowledge-bases',
        then queries it back to list KBs.
        """
        collection = "knowledge-bases"
        # First KB registration
        kb1 = [
            {
                "id": "dc56fa18-d3ef-4a1b-b9c0-aabbccddeeff",
                "text": "",
                "vector": [],
                "metadata": {
                    "name": "My First KB",
                    "description": "Test knowledge base",
                },
            }
        ]
        client.upsert(collection, kb1)

        # Should be retrievable immediately
        result = client.get(collection)
        assert result is not None, "First KB should be retrievable after upsert"
        assert len(result.ids[0]) == 1
        assert result.ids[0][0] == "dc56fa18-d3ef-4a1b-b9c0-aabbccddeeff"

    def test_get_returns_metadata_for_metadata_only(self, client):
        """get() should return full metadata even without vectors."""
        collection = "test-meta-get"
        items = [
            {
                "id": "x1",
                "text": "doc text",
                "vector": [],
                "metadata": {"source": "test", "page": 1},
            }
        ]
        client.upsert(collection, items)

        result = client.get(collection)
        assert result is not None
        assert result.metadatas[0][0]["source"] == "test"
        assert result.metadatas[0][0]["page"] == 1

    def test_delete_metadata_only_collection(self, client):
        """delete_collection() should work on metadata-only tables."""
        collection = "test-meta-del"
        items = [
            {"id": "d1", "text": "bye", "vector": [], "metadata": {}},
        ]
        client.upsert(collection, items)
        assert client.has_collection(collection) is True

        client.delete_collection(collection)
        assert client.has_collection(collection) is False

    def test_query_metadata_only_with_filter(self, client):
        """query() with filter should work on metadata-only collections."""
        collection = "test-meta-query"
        items = [
            {"id": "q1", "text": "a", "vector": [], "metadata": {"type": "alpha"}},
            {"id": "q2", "text": "b", "vector": [], "metadata": {"type": "beta"}},
        ]
        client.upsert(collection, items)

        result = client.query(collection, filter={"type": "beta"})
        assert result is not None
        assert result.ids == [["q2"]]
