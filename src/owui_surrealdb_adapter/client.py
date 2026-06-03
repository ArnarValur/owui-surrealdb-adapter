"""SurrealDB adapter implementing Open WebUI's VectorDBBase interface."""

from __future__ import annotations

import logging
from typing import Any, Optional

from owui_surrealdb_adapter.config import SurrealDBConfig

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Open WebUI result types (mirrors open_webui.retrieval.vector.main)
# ---------------------------------------------------------------------------

class SearchResult:
    """Vector search result container.

    Open WebUI expects:
        ids: list[list[str]]
        distances: list[list[float]]
        documents: list[list[str]]
        metadatas: list[list[dict]]
    All double-nested (outer = per query vector, inner = per result).
    """

    def __init__(
        self,
        ids: list[list[str]],
        distances: list[list[float]],
        documents: list[list[str]],
        metadatas: list[list[dict]],
    ):
        self.ids = ids
        self.distances = distances
        self.documents = documents
        self.metadatas = metadatas


class GetResult:
    """Collection get result container.

    Open WebUI expects:
        ids: list[list[str]]
        documents: list[list[str]]
        metadatas: list[list[dict]]
    All double-nested.
    """

    def __init__(
        self,
        ids: list[list[str]],
        documents: list[list[str]],
        metadatas: list[list[dict]],
    ):
        self.ids = ids
        self.documents = documents
        self.metadatas = metadatas


class SurrealDBClient:
    """SurrealDB vector database adapter for Open WebUI.

    Implements the VectorDBBase interface (7 methods).
    Uses _execute_query() for safe multi-statement execution.
    """

    def __init__(self, config: Optional[SurrealDBConfig] = None) -> None:
        self.config = config or SurrealDBConfig.from_env()
        self.client: Any = None  # surrealdb.Surreal instance
        log.info(
            "SurrealDBClient initialized (uri=%s, ns=%s, db=%s, prefix=%s, index=%s)",
            self.config.uri,
            self.config.namespace,
            self.config.database,
            self.config.table_prefix,
            self.config.index_type,
        )

    # -- Internal helpers ---------------------------------------------------

    def _prefixed(self, collection_name: str) -> str:
        """Return the table name with the configured prefix."""
        return f"{self.config.table_prefix}{collection_name}"

    def _execute_query(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[Any]:
        """Execute a SurrealQL query and raise on ANY statement failure.

        Uses query_raw() + per-statement status inspection to catch errors
        that the SDK's query() silently swallows (audit bug #1).

        Returns:
            List of results, one per statement in the query.

        Raises:
            SurrealError: On RPC/transport errors or any statement failure.
        """
        from surrealdb.errors import parse_query_error, parse_rpc_error

        response = self.client.query_raw(query, params)

        # Check for top-level RPC/transport error first
        error = response.get("error")
        if error is not None:
            raise parse_rpc_error(error)

        # Inspect every statement result — the SDK only checks [0]
        results = response.get("result", [])
        for idx, stmt in enumerate(results):
            if stmt.get("status") == "ERR":
                raise parse_query_error(stmt)

        return [stmt.get("result") for stmt in results]

    def _connect(self) -> None:
        """Create a new connection to SurrealDB, authenticate, and select ns/db."""
        from surrealdb import Surreal

        surreal = Surreal(self.config.uri)
        # Enter context manager — opens WebSocket or HTTP connection
        conn = surreal.__enter__()
        self._surreal_ctx = surreal  # keep reference to avoid GC closing it

        conn.signin({"username": self.config.user, "password": self.config.password})
        conn.use(self.config.namespace, self.config.database)
        self.client = conn

        log.info(
            "Connected to SurrealDB at %s (ns=%s, db=%s)",
            self.config.uri,
            self.config.namespace,
            self.config.database,
        )

    def _ensure_connected(self) -> None:
        """Ensure a live connection to SurrealDB exists."""
        if self.client is None:
            self._connect()

    def _create_collection(self, collection_name: str, dimension: int) -> None:
        """Create a SCHEMAFULL table with vector index.

        Uses DEFINE ... OVERWRITE for idempotency.
        Generates a single multi-statement query for atomicity.
        """
        table = self._prefixed(collection_name)

        # Build index definition based on config
        if self.config.index_type == "diskann":
            index_def = (
                f"DEFINE INDEX OVERWRITE idx_vector ON `{table}` "
                f"FIELDS embedding DISKANN DIMENSION {dimension} DIST COSINE"
            )
        else:
            index_def = (
                f"DEFINE INDEX OVERWRITE idx_vector ON `{table}` "
                f"FIELDS embedding HNSW DIMENSION {dimension} DIST COSINE"
            )

        query = "; ".join([
            f"DEFINE TABLE OVERWRITE `{table}` SCHEMAFULL",
            f"DEFINE FIELD OVERWRITE content ON `{table}` TYPE string",
            f"DEFINE FIELD OVERWRITE embedding ON `{table}` TYPE array<float>",
            f"DEFINE FIELD OVERWRITE metadata ON `{table}` FLEXIBLE TYPE object",
            f"DEFINE FIELD OVERWRITE created_at ON `{table}` TYPE datetime DEFAULT time::now()",
            index_def,
        ]) + ";"

        self._execute_query(query)

        log.info(
            "Created collection '%s' (table=%s, dim=%d, index=%s)",
            collection_name,
            table,
            dimension,
            self.config.index_type,
        )

    def _build_filter(
        self, filter_dict: dict, params: dict, prefix: str = "fv"
    ) -> list[str]:
        """Translate Open WebUI filter dicts to SurrealQL WHERE clauses.

        Handles simple equality and $in operator (audit bug #3).
        """
        raise NotImplementedError("Phase 4: filter translation")

    # -- VectorDBBase interface (7 methods) ---------------------------------

    def has_collection(self, collection_name: str) -> bool:
        """Check if a collection exists and has a vector index.

        Uses INFO FOR TABLE to verify idx_vector exists (audit bug #2 fix).
        """
        raise NotImplementedError("Phase 4: has_collection")

    def search(
        self,
        collection_name: str,
        vectors: list[list[float]],
        limit: int,
        filter: Optional[dict] = None,
    ) -> Optional[SearchResult]:
        """KNN vector search with optional metadata filters.

        Handles $in filters (audit bug #3) and batch vectors (audit bug #5).
        """
        raise NotImplementedError("Phase 4: search")

    def upsert(
        self,
        collection_name: str,
        items: list[dict],
    ) -> None:
        """Insert or update vector records.

        Uses INSERT ... ON DUPLICATE KEY UPDATE via _execute_query().
        """
        raise NotImplementedError("Phase 4: upsert")

    def get(self, collection_name: str) -> Optional[GetResult]:
        """Retrieve all items from a collection."""
        raise NotImplementedError("Phase 4: get")

    def delete(
        self,
        collection_name: str,
        ids: Optional[list[str]] = None,
        filter: Optional[dict] = None,
    ) -> None:
        """Delete records by primary key or filter.

        Uses record IDs directly, not metadata.id (audit bug #4 fix).
        """
        raise NotImplementedError("Phase 4: delete")

    def delete_collection(self, collection_name: str) -> None:
        """Drop an entire collection table."""
        raise NotImplementedError("Phase 4: delete_collection")

    def reset(self) -> None:
        """Drop all tables with the configured prefix."""
        raise NotImplementedError("Phase 4: reset")
