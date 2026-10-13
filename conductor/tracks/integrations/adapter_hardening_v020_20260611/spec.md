# Spec: Adapter Hardening v0.2.0

## Overview

The adapter has a critical bug where the first knowledge base created in a fresh OWUI installation never appears in the `knowledge-bases` index table. Additionally, `pyproject.toml` version is `2.0.0` (leftover from "v2 rewrite" naming) when the actual version should be `0.2.0` per ADR-0001. A code quality audit of `client.py` will surface any additional bugs or edge cases.

## Functional Requirements

1. **First-KB Bug Fix:** The adapter must handle metadata-only collections (zero-dimension / no vectors) — specifically the `knowledge-bases` collection that OWUI uses to index KBs. Currently `upsert()` skips `_create_collection()` when `dimension == 0`, so the table is auto-created as SCHEMALESS by SurrealDB without our SCHEMAFULL definition.

2. **Version Alignment:** `pyproject.toml` version must be `0.2.0` per ADR-0001 (SemVer 0.x until stable).

3. **Code Quality Audit:** Systematic review of all 922 lines in `client.py` for:
   - Silent failure paths
   - Edge cases in `_build_filter()`, `_extract_record_key()`, error detection helpers
   - Thread safety gaps
   - Missing validation
   - Logging blind spots

## Acceptance Criteria

- [ ] Creating first KB in clean OWUI → record appears in `owui_knowledge-bases` table
- [ ] `has_collection("knowledge-bases")` returns `True` after first upsert
- [ ] `pyproject.toml` version reads `0.2.0`
- [ ] All existing 166+ tests still pass
- [ ] New tests for metadata-only collection flow
- [ ] Code audit findings documented and fixed (or deferred with rationale)

## Edge Cases & Constraints

- Metadata collections have no `idx_vector` — `has_collection()` currently requires it → needs a strategy (create table without index, or skip the index check for non-vector collections)
- Must not break existing KB/file collection flows
- Must remain compatible with OWUI 0.9.6's VectorDBBase interface

## Dependencies

- None — all changes in `owui-surrealdb-adapter` repo

## Out of Scope

- OWUI version bump (0.9.6 is latest)
- Docker/deployment changes
- ZeroGravity integration
- xterm.js / GPU configuration
