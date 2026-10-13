# Plan: Adapter Hardening v0.2.0

> Strict TDD workflow — Red → Green → Refactor on every task

---

## Phase 1: First-KB Bug Fix [checkpoint: 4c662e9]

- [x] Task: Handle metadata-only (zero-dimension) collections in `upsert()` `4c662e9`
    - [x] Write test: upsert items with empty vector `[]` → table created, data persisted
    - [x] Write test: `has_collection()` returns True for metadata-only table
    - [x] Write test: second upsert to same metadata table works (idempotent)
    - [x] Implement: create SCHEMAFULL table without vector index when `dimension == 0`
    - [x] Implement: `has_collection()` recognizes tables without `idx_vector`

- [x] Task: Verify first-KB flow matches OWUI's `knowledge-bases` pattern `4c662e9`
    - [x] Write test: simulate OWUI KB registration flow (upsert with no vectors → query back)
    - [x] Write test: `get("knowledge-bases")` returns data after upsert
    - [x] Verify existing vector-collection tests still pass (173 passed)

---

## Phase 2: Version Alignment [checkpoint: 7b7b509]

- [x] Task: Fix pyproject.toml version `7b7b509`
    - [x] Change `version = "2.0.0"` → `version = "0.2.0"`
    - [x] Verify `pip install -e .` still works

---

## Phase 3: Code Quality Audit [checkpoint: ca4ec98]

- [x] Task: Audit error detection helpers `ca4ec98`
    - [x] Review `_is_db_missing()`, `_is_not_found()`, `_is_transport_error()` for gaps
    - [x] Fix: `_is_transport_error()` — added explicit parentheses for and/or precedence

- [x] Task: Audit `has_collection()` resilience `ca4ec98`
    - [x] Fix: switched from raw `query_raw()` to `_execute_with_retry()` for transport resilience

- [x] Task: Audit `delete()` for large ID lists `ca4ec98`
    - [x] Fix: added batch chunking using `_INSERT_BATCH_SIZE` (was building one mega-query)

- [x] Task: Audit connection lifecycle and thread safety `ca4ec98`
    - [x] Reviewed `_ensure_connected()` / `_force_reconnect()` / `close()` — double-check locking pattern is correct
    - [x] Improved comment on double-check locking rationale

- [x] Task: Removed `created_at` field from schema `4c662e9`
    - [x] SurrealDB's INSERT doesn't trigger DEFAULT values — field blocked SCHEMAFULL inserts
    - [x] Field was unused by OWUI — clean removal, no test references

---

## Phase 4: Tag & Verify [checkpoint: ca4ec98]

- [x] Task: Run full test suite with coverage
    - [x] `pytest --cov=owui_surrealdb_adapter --cov-report=term-missing`
    - [x] 88% coverage (>80% gate ✅)
    - [x] 173 tests all green ✅

- [x] Task: Git tag v0.2.0
    - [x] All changes committed (4 commits since v0.1.0)
    - [x] `git tag v0.2.0` ✅
