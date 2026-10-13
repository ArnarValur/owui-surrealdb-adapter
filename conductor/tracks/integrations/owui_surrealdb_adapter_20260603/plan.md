# Plan: owui-surrealdb-adapter v2

> Strict TDD workflow — Red → Green → Refactor on every task

---

## Phase 1: Project Scaffolding [checkpoint: dbed9e9]

- [x] Task: Initialize package structure `dbed9e9`
    - [x] Create `owui-surrealdb-adapter/` directory at project root
    - [x] Set up `pyproject.toml` with dependencies (`surrealdb>=2.0.0`)
    - [x] Create `src/owui_surrealdb_adapter/__init__.py`
    - [x] Create `src/owui_surrealdb_adapter/config.py` — env var parsing
    - [x] Create `src/owui_surrealdb_adapter/client.py` — empty `SurrealDBClient(VectorDBBase)` stub
    - [x] Set up `tests/conftest.py` with SurrealDB connection fixture (PlutoII docker)
    - [x] Verify `pip install -e .` works

---

## Phase 2: Core — Safe Query Executor (Audit Bug #1) [checkpoint: a70ddcd]

- [x] Task: Implement `_execute_query()` safe wrapper `a70ddcd`
    - [x] Write tests: multi-statement query where stmt 2 fails → must raise
    - [x] Write tests: single statement success → returns result
    - [x] Write tests: single statement failure → raises
    - [x] Implement `_execute_query()` using `query_raw()` + per-statement status check

---

## Phase 3: Core — Connection & Schema [checkpoint: a947bbb]

- [x] Task: Implement connection lifecycle `a947bbb`
    - [x] Write tests: connect with WebSocket URI
    - [x] Write tests: connect with HTTP URI
    - [x] Write tests: auth with namespace/database selection
    - [x] Implement `_connect()` / `_ensure_connected()` with single shared connection

- [x] Task: Implement `_create_collection()` schema setup `a947bbb`
    - [x] Write tests: creates SCHEMAFULL table with all fields
    - [x] Write tests: creates HNSW index with correct dimension
    - [x] Write tests: creates DiskANN index when configured
    - [x] Write tests: idempotent — running twice doesn't error (DEFINE OVERWRITE)
    - [x] Implement using `DEFINE TABLE/FIELD/INDEX OVERWRITE`

---

## Phase 4: VectorDBBase Methods (7 methods, one task each) [checkpoint: d4261be]

- [x] Task: Implement `has_collection()` (Audit Bug #2 fix) `d4261be`
    - [x] Write tests: returns False for non-existent table
    - [x] Write tests: returns False for table without vector index
    - [x] Write tests: returns True for table with `idx_vector`
    - [x] Implement using `INFO FOR TABLE` → check `idx_vector` in indexes

- [x] Task: Implement `upsert()` `d4261be`
    - [x] Write tests: insert new items with vectors + metadata + text
    - [x] Write tests: batch upsert (multiple items)
    - [x] Write tests: auto-creates collection if missing
    - [x] Implement using `INSERT ... ON DUPLICATE KEY UPDATE` via `_execute_query()`

- [x] Task: Implement `search()` (Audit Bug #3 fix) `d4261be`
    - [x] Write tests: basic KNN search returns ranked results
    - [x] Write tests: search with simple equality filter
    - [x] Write tests: search with `$in` filter → translates to `IN` clause
    - [x] Write tests: distance normalization (cosine → [0,1] similarity)
    - [x] Write tests: respects `limit` parameter
    - [x] Write tests: returns `SearchResult` with double-nested lists
    - [x] Implement KNN query + `_build_filter()` helper

- [x] Task: Implement `get()` `d4261be`
    - [x] Write tests: returns all items from collection
    - [x] Write tests: returns `GetResult` with double-nested lists
    - [x] Write tests: returns None for non-existent collection
    - [x] Implement using `SELECT * FROM table`

- [x] Task: Implement `delete()` (Audit Bug #4 fix) `d4261be`
    - [x] Write tests: delete by record IDs (primary key)
    - [x] Write tests: delete by filter dict
    - [x] Write tests: items actually gone after delete
    - [x] Implement using `DELETE table:record_id`

- [x] Task: Implement `delete_collection()` `d4261be`
    - [x] Write tests: removes table entirely
    - [x] Write tests: `has_collection` returns False after delete
    - [x] Implement using `REMOVE TABLE`

- [x] Task: Implement `reset()` `d4261be`
    - [x] Write tests: drops all prefixed tables
    - [x] Write tests: no tables remain after reset
    - [x] Implement using `INFO FOR DB` → iterate prefixed tables → `REMOVE TABLE`

---

## Phase 5: Batch Vector Search (Audit Bug #5) [checkpoint: 109bd1d]

- [x] Task: Handle multiple query vectors `109bd1d`
    - [x] Write tests: search with 1 vector → single result set
    - [x] Write tests: search with 3 vectors → 3 result sets
    - [x] Implement loop over all vectors, aggregate into `SearchResult`

---

## Phase 6: Docker Overlay Integration [checkpoint: 7a39de7]

- [x] Task: Create `patch.py` — factory.py + type.py patcher `1ce814a`
    - [x] Write tests: patch inserts case branch + enum member correctly (13 tests)
    - [x] Write tests: patch is idempotent (running twice doesn't duplicate)
    - [x] Implement patcher targeting match/case in factory.py + StrEnum in type.py

- [x] Task: Create Dockerfile `7a39de7`
    - [x] Write Dockerfile extending OWUI base image
    - [x] Install adapter package + run patcher
    - [x] `VECTOR_DB=surrealdb` activates via patched factory.py

- [x] Task: Create docker-compose.yml `7a39de7`
    - [x] OWUI service (custom image)
    - [x] SurrealDB 3.1 service (RocksDB, healthcheck)
    - [x] Proper env vars, networking, volumes

---

## Phase 7: End-to-End Verification on PlutoII [checkpoint: 7e47a9c]

- [x] Task: Deploy and test full stack locally `7e47a9c`
    - [x] Integrate into existing `pluto-open-webui` + `pluto-surrealdb` containers
    - [x] Upload a markdown file in OWUI → green toast ✅
    - [x] Verify chunks stored in SurrealDB (5 tables, 72 vectors)
    - [x] Ask a question in OWUI → confirmed RAG-augmented answer with citations
    - [x] Delete the file in OWUI → verify chunks removed from SurrealDB
    - [x] Run adapter with multiple knowledge bases → verify collection isolation (E2E §3 ✅)

---

## Phase 7b: Production Hardening

- [x] Task: Security — SQL injection prevention
    - [x] `_validate_name()` regex validation on all names/IDs
    - [x] `_validate_limit()` bounds check (1–10,000)
    - [x] `_validate_filter_keys()` metadata key validation
    - [x] Validated delete — IDs checked before interpolation

- [x] Task: Resilience — connection lifecycle
    - [x] `_execute_with_retry()` with exponential backoff
    - [x] `_force_reconnect()` under `threading.Lock`
    - [x] `close()` + context manager support
    - [x] Config: `connect_timeout`, `max_retries`, `retry_backoff`

- [x] Task: Correctness — error handling + edge cases
    - [x] Narrow `has_collection()` exception handling
    - [x] Extended `_extract_record_key()` for `{}` and `[]` IDs
    - [x] Batch chunking for large inserts (100/batch)

- [x] Task: Docker + DevOps
    - [x] Pin OWUI to 0.9.6, fix backup paths
    - [x] `.env` credentials, `.dockerignore`, healthchecks
    - [x] `pydantic>=2.0` dependency

- [x] Task: Hardening test suite — 57 new tests
- [x] Task: Deploy hardened image to PlutoII + verify
- [x] Task: Create E2E manual testing checklist

- [x] Task: Stress test — "machine gun" for bugs
    - [x] Rapid upload/delete cycles
    - [x] Large document (100+ pages)
    - [x] Multiple concurrent chats with RAG
    - [x] Filter edge cases (`$in` with empty list, single item, 50+ items)
    - [x] Dimension mismatch (wrong embedding model mid-stream)

---

## Phase 8: Documentation & Cleanup

- [x] Task: Write README.md
    - [x] Installation instructions (Docker + pip)
    - [x] Configuration reference (all 11 env vars)
    - [x] Docker overlay setup guide
    - [x] How It Works architecture overview
    - [x] Troubleshooting / known issues
    - [x] Created `.env.example`

- [x] Task: Update conductor artifacts
    - [x] Checkpoint and tag release v0.1.0 (df3f290)
