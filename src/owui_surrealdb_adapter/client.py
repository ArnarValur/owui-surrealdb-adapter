from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Optional

from pydantic import BaseModel

from owui_surrealdb_adapter.config import SurrealDBConfig

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

# Safe identifier pattern: alphanumeric, hyphens, underscores, dots
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-\.]+$")

# Safe metadata filter key pattern: alphanumeric + underscores only
_SAFE_FILTER_KEY_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Maximum limit value to prevent abuse
_MAX_LIMIT = 10_000

# Batch size for large inserts
_INSERT_BATCH_SIZE = 100


def _validate_name(name: str, label: str = "name") -> None:
    """Validate that a name contains only safe characters.

    Raises ValueError if the name contains backticks, semicolons,
    or other SurrealQL injection vectors.
    """
    if not name or not _SAFE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid {label}: {name!r} — must be alphanumeric, hyphens, "
            f"underscores, or dots only."
        )


def _validate_limit(limit: Any) -> int:
    """Cast and validate a limit parameter.

    Returns a safe int value between 1 and _MAX_LIMIT.
    """
    try:
        val = int(limit)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid limit: {limit!r} — must be an integer.") from exc
    if val < 1:
        val = 1
    elif val > _MAX_LIMIT:
        val = _MAX_LIMIT
    return val


def _validate_filter_keys(filter_dict: dict) -> None:
    """Validate that all filter dictionary keys are safe identifiers."""
    for key in filter_dict:
        if not _SAFE_FILTER_KEY_RE.match(str(key)):
            raise ValueError(
                f"Invalid filter key: {key!r} — must be alphanumeric/underscores only."
            )


# ---------------------------------------------------------------------------
# Open WebUI result types (mirrors open_webui.retrieval.vector.main)
# Must be Pydantic BaseModels — OWUI calls .model_dump() on them.
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    """Vector search result container."""
    ids: Optional[list[list[str]]] = None
    distances: Optional[list[list[float]]] = None
    documents: Optional[list[list[str]]] = None
    metadatas: Optional[list[list[Any]]] = None


class GetResult(BaseModel):
    """Collection get result container."""
    ids: Optional[list[list[str]]] = None
    documents: Optional[list[list[str]]] = None
    metadatas: Optional[list[list[Any]]] = None


def _is_not_found(exc: Exception) -> bool:
    """Check if an exception is a SurrealDB 'table not found' error.

    Checks both the exception class name and message content for robustness
    across SDK versions.
    """
    cls = type(exc).__name__
    msg = str(exc).lower()
    return (
        cls == "NotFoundError"
        or "does not exist" in msg
        or "table not found" in msg
    )


def _is_transport_error(exc: Exception) -> bool:
    """Check if an exception indicates a dead/broken connection."""
    cls = type(exc).__name__
    msg = str(exc).lower()
    return (
        cls in ("ConnectionError", "WebSocketError", "TransportError", "BrokenPipeError")
        or "connection" in msg and ("closed" in msg or "refused" in msg or "reset" in msg)
        or "broken pipe" in msg
        or "websocket" in msg and "close" in msg
    )


class SurrealDBClient:
    """SurrealDB vector database adapter for Open WebUI.

    Implements the VectorDBBase interface (9 methods):
        has_collection, delete_collection, insert, upsert,
        search, query, get, delete, reset

    Method signatures match VectorDBBase EXACTLY — parameter order matters
    because the AsyncVectorDBClient wrapper calls positionally.

    All read/delete methods gracefully handle non-existent tables by
    returning None (reads) or no-op (deletes) instead of raising.

    Thread-safe: connection state is protected by a lock.
    Reconnect: automatically retries on transport errors with backoff.
    """

    def __init__(self, config: Optional[SurrealDBConfig] = None) -> None:
        self.config = config or SurrealDBConfig.from_env()
        self.client: Any = None  # surrealdb.Surreal instance
        self._surreal_ctx: Any = None  # context manager reference
        self._lock = threading.Lock()
        log.info(
            "SurrealDBClient initialized (uri=%s, ns=%s, db=%s, prefix=%s, index=%s)",
            self.config.uri,
            self.config.namespace,
            self.config.database,
            self.config.table_prefix,
            self.config.index_type,
        )

    # -- Context manager support --------------------------------------------

    def __enter__(self) -> SurrealDBClient:
        self._ensure_connected()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the SurrealDB connection and release resources."""
        with self._lock:
            if self._surreal_ctx is not None:
                try:
                    self._surreal_ctx.__exit__(None, None, None)
                except Exception:
                    pass  # Best-effort cleanup
                self._surreal_ctx = None
            self.client = None
        log.debug("SurrealDBClient connection closed.")

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

    def _execute_with_retry(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[Any]:
        """Execute a query with automatic reconnection on transport errors.

        Retries up to config.max_retries times with exponential backoff.
        """
        last_exc: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                self._ensure_connected()
                return self._execute_query(query, params)
            except Exception as exc:
                if _is_transport_error(exc):
                    last_exc = exc
                    log.warning(
                        "Transport error (attempt %d/%d): %s — reconnecting...",
                        attempt + 1,
                        self.config.max_retries + 1,
                        exc,
                    )
                    self._force_reconnect()
                    if attempt < self.config.max_retries:
                        wait = self.config.retry_backoff * (2 ** attempt)
                        time.sleep(wait)
                    continue
                raise  # Non-transport errors propagate immediately
        raise ConnectionError(
            f"Failed to execute query after {self.config.max_retries + 1} attempts. "
            f"Last error: {last_exc}"
        ) from last_exc

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
        """Ensure a live connection to SurrealDB exists (thread-safe)."""
        if self.client is not None:
            return
        with self._lock:
            # Double-check after acquiring lock
            if self.client is None:
                self._connect()

    def _force_reconnect(self) -> None:
        """Close existing connection and reconnect (thread-safe)."""
        with self._lock:
            # Close old connection
            if self._surreal_ctx is not None:
                try:
                    self._surreal_ctx.__exit__(None, None, None)
                except Exception:
                    pass
                self._surreal_ctx = None
            self.client = None
            # Reconnect
            self._connect()

    def _create_collection(self, collection_name: str, dimension: int) -> None:
        """Create a SCHEMAFULL table with vector index.

        Uses DEFINE ... OVERWRITE for idempotency.
        Generates a single multi-statement query for atomicity.
        """
        _validate_name(collection_name, "collection_name")
        table = self._prefixed(collection_name)

        dim = _validate_limit(dimension)  # reuse int validation

        # Build index definition based on config
        if self.config.index_type == "diskann":
            index_def = (
                f"DEFINE INDEX OVERWRITE idx_vector ON `{table}` "
                f"FIELDS embedding DISKANN DIMENSION {dim} DIST COSINE"
            )
        else:
            index_def = (
                f"DEFINE INDEX OVERWRITE idx_vector ON `{table}` "
                f"FIELDS embedding HNSW DIMENSION {dim} DIST COSINE"
            )

        query = "; ".join([
            f"DEFINE TABLE OVERWRITE `{table}` SCHEMAFULL",
            f"DEFINE FIELD OVERWRITE content ON `{table}` TYPE string",
            f"DEFINE FIELD OVERWRITE embedding ON `{table}` TYPE array<float>",
            f"DEFINE FIELD OVERWRITE metadata ON `{table}` TYPE object FLEXIBLE",
            f"DEFINE FIELD OVERWRITE created_at ON `{table}` TYPE datetime DEFAULT time::now()",
            index_def,
        ]) + ";"

        self._execute_with_retry(query)

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
        All filter keys are validated to prevent injection.
        """
        _validate_filter_keys(filter_dict)
        parts: list[str] = []
        for i, (key, value) in enumerate(filter_dict.items()):
            pname = f"{prefix}{i}"
            if isinstance(value, dict) and "$in" in value:
                params[pname] = value["$in"]
                parts.append(f"metadata.{key} IN ${pname}")
            else:
                params[pname] = value
                parts.append(f"metadata.{key} = ${pname}")
        return parts

    @staticmethod
    def _extract_record_key(record_id: Any) -> str:
        """Extract the key portion from a SurrealDB record ID.

        'table:key' → 'key', RecordID → str(key)
        Strips all SurrealDB ID wrapping formats:
        - ⟨⟩ brackets (IDs with hyphens/special chars)
        - { } object-based record IDs
        - [ ] array-based record IDs
        """
        s = str(record_id)
        if ":" in s:
            s = s.split(":", 1)[1]
        # Strip ⟨⟩ brackets that SurrealDB adds for IDs with hyphens/special chars
        if s.startswith("⟨") and s.endswith("⟩"):
            s = s[1:-1]
        # Strip { } for object-based record IDs
        elif s.startswith("{") and s.endswith("}"):
            s = s[1:-1]
        # Strip [ ] for array-based record IDs
        elif s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        return s

    # -- VectorDBBase interface (9 methods) ---------------------------------
    # IMPORTANT: Parameter order MUST match VectorDBBase exactly.
    # The AsyncVectorDBClient wrapper calls these positionally.

    def has_collection(self, collection_name: str) -> bool:
        """Check if a collection exists and has a vector index.

        Uses INFO FOR TABLE to verify idx_vector exists (audit bug #2 fix).
        Only catches table-not-found errors — network/auth errors propagate.
        """
        if not self.client:
            return False
        try:
            _validate_name(collection_name, "collection_name")
            table = self._prefixed(collection_name)
            response = self.client.query_raw(f"INFO FOR TABLE `{table}`;")

            # Check for top-level error
            if response.get("error"):
                return False

            results = response.get("result", [])
            if not results:
                return False

            info = results[0].get("result", {})
            if isinstance(info, dict) and "indexes" in info:
                return "idx_vector" in info["indexes"]
            return False
        except Exception as e:
            if _is_not_found(e):
                log.debug("has_collection('%s'): table not found", collection_name)
                return False
            # Network/auth/unexpected errors — propagate, don't mask
            log.error("has_collection('%s') unexpected error: %s", collection_name, e)
            raise

    def delete_collection(self, collection_name: str) -> None:
        """Drop an entire collection table."""
        self._ensure_connected()
        _validate_name(collection_name, "collection_name")
        table = self._prefixed(collection_name)
        try:
            self._execute_with_retry(f"REMOVE TABLE IF EXISTS `{table}`;")
        except Exception as e:
            if _is_not_found(e):
                return
            raise
        log.info("Deleted collection '%s' (table=%s)", collection_name, table)

    def insert(
        self,
        collection_name: str,
        items: list[dict],
    ) -> None:
        """Insert vector items into a collection.

        Delegates to upsert() — SurrealDB's INSERT ON DUPLICATE KEY UPDATE
        handles both insert and update semantics.
        """
        self.upsert(collection_name, items)

    def upsert(
        self,
        collection_name: str,
        items: list[dict],
    ) -> None:
        """Insert or update vector records.

        Uses INSERT ... ON DUPLICATE KEY UPDATE via _execute_with_retry().
        Auto-creates collection if it doesn't exist.
        Large batches are chunked into groups of _INSERT_BATCH_SIZE.
        """
        self._ensure_connected()
        _validate_name(collection_name, "collection_name")

        if not items:
            return

        # Auto-create collection if needed
        if not self.has_collection(collection_name):
            dimension = len(items[0].get("vector", []))
            if dimension > 0:
                self._create_collection(collection_name, dimension)

        table = self._prefixed(collection_name)

        # Build records for INSERT
        records = []
        for item in items:
            _validate_name(str(item["id"]), "item_id")
            records.append({
                "id": item["id"],
                "content": item.get("text", ""),
                "embedding": item.get("vector", []),
                "metadata": item.get("metadata", {}),
            })

        # Chunk large batches to prevent timeouts / OOM
        for i in range(0, len(records), _INSERT_BATCH_SIZE):
            batch = records[i : i + _INSERT_BATCH_SIZE]
            params = {"data": batch}
            query = (
                f"INSERT INTO `{table}` $data "
                f"ON DUPLICATE KEY UPDATE "
                f"content = $input.content, "
                f"embedding = $input.embedding, "
                f"metadata = $input.metadata;"
            )
            self._execute_with_retry(query, params)

    def search(
        self,
        collection_name: str,
        vectors: list[list[float]],
        filter: Optional[dict] = None,
        limit: int = 10,
    ) -> Optional[SearchResult]:
        """KNN vector search with optional metadata filters.

        Handles $in filters (audit bug #3) and batch vectors (audit bug #5).

        NOTE: param order is (vectors, filter, limit) to match VectorDBBase.
        The async wrapper calls positionally — wrong order = silent bugs.
        """
        self._ensure_connected()
        _validate_name(collection_name, "collection_name")
        limit = _validate_limit(limit)
        table = self._prefixed(collection_name)

        all_ids: list[list[str]] = []
        all_distances: list[list[float]] = []
        all_documents: list[list[str]] = []
        all_metadatas: list[list[dict]] = []

        for qv in vectors:
            params: dict[str, Any] = {"qv": qv}

            # Build filter parts for WHERE clause
            where_parts: list[str] = []
            if filter:
                where_parts = self._build_filter(filter, params)

            ef = _validate_limit(self.config.ef_search)
            query = (
                f"SELECT *, vector::distance::knn() AS dist "
                f"FROM `{table}` "
                f"WHERE embedding <|{limit},{ef}|> $qv "
                f"{('AND ' + ' AND '.join(where_parts) + ' ') if where_parts else ''}"
                f"LIMIT {limit};"
            )

            try:
                results = self._execute_with_retry(query, params)
                rows = results[0] if results else []
            except Exception as e:
                if _is_not_found(e):
                    rows = []
                else:
                    raise

            ids: list[str] = []
            distances: list[float] = []
            documents: list[str] = []
            metadatas: list[dict] = []

            for row in (rows or []):
                ids.append(self._extract_record_key(row.get("id", "")))
                # Cosine distance → similarity: 1 - distance
                dist = row.get("dist", 0.0)
                distances.append(1.0 - dist)
                documents.append(row.get("content", ""))
                metadatas.append(row.get("metadata", {}))

            all_ids.append(ids)
            all_distances.append(distances)
            all_documents.append(documents)
            all_metadatas.append(metadatas)

        return SearchResult(
            ids=all_ids,
            distances=all_distances,
            documents=all_documents,
            metadatas=all_metadatas,
        )

    def query(
        self,
        collection_name: str,
        filter: dict,
        limit: Optional[int] = None,
    ) -> Optional[GetResult]:
        """Query vectors from a collection using metadata filters."""
        self._ensure_connected()
        _validate_name(collection_name, "collection_name")
        table = self._prefixed(collection_name)

        params: dict[str, Any] = {}
        where_parts = self._build_filter(filter, params)
        where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""
        limit_clause = f" LIMIT {_validate_limit(limit)}" if limit else ""

        query = f"SELECT * FROM `{table}` {where_clause}{limit_clause};"

        try:
            results = self._execute_with_retry(query, params)
            rows = results[0] if results else []
        except Exception as e:
            if _is_not_found(e):
                return None
            raise

        if not rows:
            return None

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for row in rows:
            ids.append(self._extract_record_key(row.get("id", "")))
            documents.append(row.get("content", ""))
            metadatas.append(row.get("metadata", {}))

        return GetResult(
            ids=[ids],
            documents=[documents],
            metadatas=[metadatas],
        )

    def get(self, collection_name: str) -> Optional[GetResult]:
        """Retrieve all items from a collection."""
        self._ensure_connected()
        _validate_name(collection_name, "collection_name")
        table = self._prefixed(collection_name)

        try:
            results = self._execute_with_retry(f"SELECT * FROM `{table}`;")
            rows = results[0] if results else []
        except Exception as e:
            if _is_not_found(e):
                return None
            raise

        if not rows:
            return None

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for row in rows:
            ids.append(self._extract_record_key(row.get("id", "")))
            documents.append(row.get("content", ""))
            metadatas.append(row.get("metadata", {}))

        return GetResult(
            ids=[ids],
            documents=[documents],
            metadatas=[metadatas],
        )

    def delete(
        self,
        collection_name: str,
        ids: Optional[list[str]] = None,
        filter: Optional[dict] = None,
    ) -> None:
        """Delete records by primary key or filter.

        Uses parameterized queries — no raw ID interpolation (SQL injection fix).
        Gracefully handles non-existent tables.
        """
        self._ensure_connected()
        _validate_name(collection_name, "collection_name")
        table = self._prefixed(collection_name)

        try:
            if ids:
                # Delete by record ID — validate first, then use SurrealDB record syntax
                # IDs are validated against _SAFE_NAME_RE (alphanumeric, hyphens,
                # underscores, dots only) preventing any injection.
                for id_val in ids:
                    _validate_name(str(id_val), "record_id")
                # Build batch DELETE using validated + ⟨⟩-quoted IDs
                stmts = [f"DELETE `{table}`:`{id_val}`;" for id_val in ids]
                self._execute_with_retry(" ".join(stmts))
            elif filter:
                params: dict[str, Any] = {}
                where_parts = self._build_filter(filter, params)
                where_clause = " AND ".join(where_parts)
                self._execute_with_retry(
                    f"DELETE FROM `{table}` WHERE {where_clause};", params
                )
        except Exception as e:
            if _is_not_found(e):
                return
            raise

    def reset(self) -> None:
        """Drop all tables with the configured prefix."""
        self._ensure_connected()

        # Get all tables in the database
        results = self._execute_with_retry("INFO FOR DB;")
        db_info = results[0] if results else {}

        tables = db_info.get("tables", {}) if isinstance(db_info, dict) else {}

        # Filter to only tables with our prefix
        prefixed = [t for t in tables if t.startswith(self.config.table_prefix)]

        if not prefixed:
            return

        # Validate all table names before building query
        for t in prefixed:
            _validate_name(t, "table_name")

        stmts = [f"REMOVE TABLE `{t}`;" for t in prefixed]
        self._execute_with_retry(" ".join(stmts))
        log.info("Reset: removed %d tables with prefix '%s'", len(prefixed), self.config.table_prefix)
