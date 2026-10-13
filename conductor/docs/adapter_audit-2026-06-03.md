# owui-surrealdb-adapter — Consolidated Bug Audit

> **Scope:** All known vulnerabilities in [surrealdb_adapter.py](file:///home/solmundur/Hermes/owui-surrealdb-adapter/surrealdb_adapter.py) discovered across two independent research sessions.
>
> **Tested against:** SurrealDB 3.0.5 on PlutoII, PyPI `surrealdb` SDK 2.0.0
>
> **Upstream references:** Open WebUI `VectorDBBase` + Chroma, Qdrant, pgvector adapters (main branch, June 2026)

---

## Bug Summary

| # | Bug | Lines | Severity | Category |
|---|-----|-------|----------|----------|
| 1 | [Multi-statement silent failures](#1-multi-statement-silent-failures) | All `client.query()` calls | 🔴 Critical | SDK trap |
| 2 | [`has_collection` false positive](#2-has_collection-false-positive) | [L108–L123](file:///home/solmundur/Hermes/owui-surrealdb-adapter/surrealdb_adapter.py#L108-L123) | 🔴 Critical | Logic error |
| 3 | [`$in` filter not supported](#3-in-metadata-filter-not-supported) | [L224–L229](file:///home/solmundur/Hermes/owui-surrealdb-adapter/surrealdb_adapter.py#L224-L229) | 🔴 Critical | Missing feature |
| 4 | [`delete` uses wrong key](#4-delete-uses-metadataid-instead-of-record-id) | [L323–L333](file:///home/solmundur/Hermes/owui-surrealdb-adapter/surrealdb_adapter.py#L323-L333) | 🟡 High | Logic error |
| 5 | [Batch vectors ignored](#5-batch-vector-queries-silently-dropped) | [L221](file:///home/solmundur/Hermes/owui-surrealdb-adapter/surrealdb_adapter.py#L221) | 🟡 Medium | Missing feature |

---

## Detailed Findings

### 1. Multi-Statement Silent Failures

> [!CAUTION]
> The SDK silently swallows errors in batched queries. This affects every write path in the adapter.

**Root cause:** The official PyPI `surrealdb` 2.0.0 SDK's `query()` method ([blocking_http.py:L133–L138](file:///home/solmundur/Hermes/owui-surrealdb-adapter/.venv/lib/python3.12/site-packages/surrealdb/connections/blocking_http.py#L133-L138)) only inspects the **first statement's** result:

```python
# SDK source — blocking_http.py
def query(self, query, vars=None):
    response = self.query_raw(query, vars)
    ...
    self._check_query_result(response["result"][0])   # ← only [0]
    return response["result"][0]["result"]
```

**What breaks:**
- **DDL batches** (`_create_collection`): If `DEFINE TABLE` succeeds but `DEFINE INDEX ... HNSW` fails, the adapter reports success. Table exists but has **no vector index**.
- **Insert/Upsert batches** (`insert`, `upsert`): If record 1 succeeds but record 2 fails (dimension mismatch, schema violation), the error is silently discarded.

**Verified locally:** See [test_multistmt.py](file:///home/solmundur/Hermes/owui-surrealdb-adapter/test_multistmt.py) — standard `query()` swallowed a schema violation; `query_raw()` + manual status check caught it.

**Proposed fix — safe query executor:**
```python
def _execute_query(self, query: str, params: dict | None = None):
    """Execute query and raise on ANY statement failure."""
    response = self.client.query_raw(query, params)
    error = response.get("error")
    if error is not None:
        from surrealdb.errors import parse_rpc_error
        raise parse_rpc_error(error)
    results = response.get("result", [])
    for idx, stmt in enumerate(results):
        if stmt.get("status") == "ERR":
            from surrealdb.errors import parse_query_error
            raise parse_query_error(stmt)
    return [stmt.get("result") for stmt in results]
```

---

### 2. `has_collection` False Positive

> [!CAUTION]
> The adapter thinks every table exists, so HNSW indexes are never created for new collections.

**Current code:**
```python
result = self.client.query(f"SELECT count() AS c FROM `{table}` GROUP ALL;")
return isinstance(result, list)
```

**Root cause:** SurrealDB returns `[]` (empty list) when querying a table that has never been defined. Since `isinstance([], list)` is `True`, this always returns `True`.

**The cascade:**
1. `has_collection("new_docs")` → `True` (wrong)
2. `_create_collection_if_not_exists` → skipped
3. `DEFINE TABLE ... SCHEMAFULL` → never runs
4. `DEFINE INDEX ... HNSW` → never runs
5. Inserts go into a schemaless table with no vector index
6. ANN search either fails or does brute-force full scan

**Proposed fix — check index metadata:**
```python
def has_collection(self, collection_name: str) -> bool:
    if not self.client:
        return False
    try:
        table = self._prefixed(collection_name)
        info = self.client.query(f"INFO FOR TABLE `{table}`;")
        if isinstance(info, dict) and "indexes" in info:
            return "idx_vector" in info["indexes"]
        return False
    except Exception as e:
        err_msg = str(e).lower()
        if "not exist" in err_msg or "not found" in err_msg:
            return False
        log.exception(f"Error checking collection '{collection_name}': {e}")
        return False
```

> [!WARNING]
> `INFO FOR TABLE` may trigger write-transaction errors on RocksDB (the same bug that already affected `INFO FOR DB` in `reset()`). Needs verification on Saturn's RocksDB-backed instance.

---

### 3. `$in` Metadata Filter Not Supported

> [!IMPORTANT]
> Open WebUI uses structured filter dicts with operators like `$in`. The adapter only handles simple equality.

**How Open WebUI calls search:**
```python
# From retrieval/utils.py & upstream adapters (pgvector, qdrant)
VECTOR_DB_CLIENT.search(
    collection_name=name,
    vectors=[embedding],
    limit=k,
    filter={"file_id": {"$in": ["id1", "id2", "id3"]}}
)
```

**Current adapter code:**
```python
for i, (key, value) in enumerate(filter.items()):
    pname = f"fv{i}"
    filter_parts.append(f"metadata.{key} = ${pname}")
    params[pname] = value  # value is {"$in": [...]} — not a string!
```

**What happens:** The adapter passes `{"$in": ["id1", "id2"]}` as a parameter value for an equality check. SurrealDB will never match a dict against a string field. **Zero results returned, RAG context is empty.**

**Cross-reference:** The pgvector adapter ([pgvector.py](https://github.com/open-webui/open-webui/blob/main/backend/open_webui/retrieval/vector/dbs/pgvector.py)) explicitly handles `$in`:
```python
if isinstance(value, dict) and '$in' in value:
    in_values = value['$in']
    where_clauses.append(DocumentChunk.vmetadata[key].astext.in_(...))
```

**Proposed fix:**
```python
def _build_filter(self, filter: dict, params: dict, prefix: str = "fv") -> list[str]:
    parts = []
    for i, (key, value) in enumerate(filter.items()):
        pname = f"{prefix}{i}"
        if isinstance(value, dict) and "$in" in value:
            params[pname] = value["$in"]
            parts.append(f"metadata.{key} IN ${pname}")
        else:
            params[pname] = value
            parts.append(f"metadata.{key} = ${pname}")
    return parts
```

---

### 4. `delete` Uses `metadata.id` Instead of Record ID

**Current code:**
```python
statements.append(f"DELETE FROM `{table}` WHERE metadata.id = ${pname};")
params[pname] = id_value
```

**The problem:** Items are inserted using SurrealDB Record IDs (`CREATE table:item_id CONTENT ...`). The `ids` parameter from Open WebUI contains these Record ID keys. But the delete method searches for them inside `metadata.id` — a metadata field that may not exist or may contain a different value.

**The result:** Delete operations silently match nothing. Files removed from the Open WebUI UI leave orphaned vector chunks in SurrealDB.

**Proposed fix — use primary key directly:**
```python
if ids:
    statements = []
    for id_value in ids:
        statements.append(f"DELETE `{table}`:`{id_value}`;")
    self._execute_query("".join(statements))
```

This is O(1) per record (primary key lookup) instead of a metadata scan.

---

### 5. Batch Vector Queries Silently Dropped

**Current code:**
```python
params: dict = {"qv": vectors[0]}
```

**The problem:** The `search()` method receives `vectors: list[list[float]]` but only uses the first vector. If Open WebUI sends multiple query vectors (batch evaluation, hybrid search), all but the first are silently ignored.

**Cross-reference:**
- **pgvector** handles this with lateral subqueries across all query vectors
- **Chroma** passes the full `query_embeddings=vectors` list
- **Qdrant** also uses `vectors[0]` only (so this is not unique to our adapter)

**Risk assessment:** Medium — Open WebUI's primary retrieval path (`query_doc`) sends a single vector. Batch paths exist but are less common.

**Proposed fix:** Loop over all vectors or document the single-vector constraint with a log warning.

---

## SurrealDB 3.1 Compatibility

> [!NOTE]
> SurrealDB 3.1 (May 2026) introduces no breaking changes to HNSW syntax or on-disk format.

| Feature | 3.0.x | 3.1 | Adapter Status |
|---------|-------|-----|----------------|
| HNSW `DEFINE INDEX` | ✅ | ✅ | Compatible |
| `<\|K,EF\|>` operator | ✅ | ✅ | Compatible |
| `vector::similarity::cosine()` | ✅ | ✅ | Compatible |
| DiskANN index | ❌ | ✅ New | Not used (future option) |
| SurrealKV storage | ✅ | ✅ | Compatible |
| RocksDB storage | ✅ | ✅ | Compatible (with `INFO FOR DB` workaround) |

---

## Cross-Reference: Upstream Adapter Patterns

Patterns from official Open WebUI adapters that our adapter should follow:

| Pattern | Chroma | Qdrant | pgvector | Our Adapter |
|---------|--------|--------|----------|-------------|
| Distance normalization to [0,1] | `(2 - dist) / 2` | `(score + 1) / 2` | `(2 - dist) / 2` | Raw cosine (already [0,1]) ✅ |
| `$in` filter support | Native Chroma `where` | Not shown | Explicit `$in` handling | ❌ Missing |
| Batch vector search | Full list | `vectors[0]` only | Full lateral join | ❌ `vectors[0]` only |
| Delete by primary key | Collection API | Point IDs | SQLAlchemy `.in_()` | ❌ Uses `metadata.id` |
| Error propagation | try/except per call | try/except per call | try/except + rollback | ❌ SDK swallows errors |
