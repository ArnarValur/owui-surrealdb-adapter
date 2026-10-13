# Spec: owui-surrealdb-adapter v2

> Standalone Open WebUI vector DB adapter backed by SurrealDB 3.1

---

## Overview

Replace the buggy original `surrealdb_adapter.py` with a clean, tested, pip-installable package that integrates into Open WebUI via Docker overlay — no fork required.

**Problem:** The current adapter has 5 known bugs (2 critical) that break RAG functionality — HNSW indexes never created, `$in` filters ignored, deletes miss records, SDK errors silently swallowed.

**Solution:** Ground-up rewrite implementing `VectorDBBase` correctly, with real integration tests against SurrealDB 3.1.

---

## Functional Requirements

### VectorDBBase Implementation (7 methods)

| Method | Behavior |
|--------|----------|
| `has_collection` | `INFO FOR TABLE ... STRUCTURE` → check `idx_vector` exists |
| `search` | KNN via `<\|K, EF\|>` operator, translate `$in` filters, return `SearchResult` |
| `upsert` | `INSERT ... ON DUPLICATE KEY UPDATE` with vectors + metadata + text |
| `get` | `SELECT * FROM table` → return `GetResult` with double-nested lists |
| `delete` | `DELETE table:record_id` (primary key, not metadata.id) |
| `delete_collection` | `REMOVE TABLE table` |
| `reset` | Drop all prefixed tables |

### Safe Query Execution

- Use `query_raw()` + per-statement status inspection
- Raise on ANY statement failure (fix audit bug #1)

### Filter Translation

- Simple equality: `metadata.key = $param`
- `$in` operator: `metadata.key IN $param` (fix audit bug #3)
- Extensible for future operators (`$ne`, `$gt`, etc.)

### Schema Management

- `DEFINE TABLE OVERWRITE ... SCHEMAFULL`
- `DEFINE FIELD OVERWRITE` for content, embedding, metadata, created_at
- `DEFINE INDEX OVERWRITE` for HNSW (default) or DiskANN (opt-in via env var)

### Connection

- WebSocket (recommended) or HTTP — auto-detected from `SURREALDB_URI` scheme
- Single shared connection (avoids RocksDB lock contention)
- Auth via `SURREALDB_USER` / `SURREALDB_PASS`
- Namespace/database via `SURREALDB_NS` / `SURREALDB_DB`

---

## Non-Functional Requirements

- **Python 3.11+**
- **Zero OWUI fork** — standalone pip package + Docker overlay
- **SurrealDB 3.1 compatible** (also works on 3.0.x)
- **Table prefix** configurable via `SURREALDB_TABLE_PREFIX` (default: `owui_`)
- **Idempotent schema** — safe to re-run `_create_collection` via `DEFINE ... OVERWRITE`

---

## Acceptance Criteria

1. All 7 `VectorDBBase` methods implemented and passing tests
2. All 5 audit bugs verified fixed with dedicated test cases
3. Integration tests pass against real SurrealDB 3.1 on PlutoII
4. Docker overlay builds and runs OWUI with `VECTOR_DB=surrealdb`
5. End-to-end: upload a PDF in OWUI → ask a question → get RAG-augmented answer using SurrealDB vectors

---

## Configuration (env vars)

| Variable | Default | Description |
|----------|---------|-------------|
| `VECTOR_DB` | — | Set to `surrealdb` to activate |
| `SURREALDB_URI` | `ws://localhost:8000` | Connection URI |
| `SURREALDB_NS` | `owui` | Namespace |
| `SURREALDB_DB` | `vectors` | Database |
| `SURREALDB_USER` | `root` | Auth user |
| `SURREALDB_PASS` | `root` | Auth password |
| `SURREALDB_TABLE_PREFIX` | `owui_` | Table name prefix |
| `SURREALDB_INDEX_TYPE` | `hnsw` | `hnsw` or `diskann` |
| `SURREALDB_EF_SEARCH` | `40` | KNN search effort |

---

## Edge Cases & Constraints

- RocksDB ghost records after DELETE — monitor query performance
- `INFO FOR TABLE` may trigger write-transaction errors on RocksDB — needs testing
- DiskANN may keep graph in memory in some builds — verify before recommending
- SDK `query()` tuple behavior — defensive coding with `query_raw()` regardless

---

## Dependencies

- `surrealdb` PyPI package (2.0.0)
- Open WebUI (latest, via Docker base image)
- SurrealDB 3.1 server (dockerized on PlutoII for dev, Saturn for prod)

---

## Out of Scope

- Open WebUI app database (SQLite/PostgreSQL) — stays native
- Embedding model changes — OWUI handles embeddings, adapter only stores vectors
- Upstream PR to Open WebUI (future, after battle-testing)
- Hybrid search / BM25 (future track)
- OWUI Connections/Pipes/Functions integration — adapter uses standard VectorDBBase
