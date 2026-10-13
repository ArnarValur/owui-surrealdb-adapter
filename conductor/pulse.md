# Pulse — owui-surrealdb-adapter

> **Updated:** 2026-10-14 — v0.5.0 passed on the PlutoII bench and was tagged
> State only, cap ~60 lines. Rewritten from scratch at every checkpoint —
> if you are appending to this file, you are doing it wrong.

## 📍 Now — what runs where

- Canonical repo: `~/Projects/owui-surrealdb-adapter`. Branch `release/v0.5.0` (not merged to `main`, not pushed). Tags `v0.1.0`, `v0.2.0`, `v0.5.0`.
- PlutoII bench: `owui-pluto` runs `owui-surrealdb:v0.5.0-cuda` (image `09e282d50d76`, OWUI 0.11.3-cuda + 2 Gemini hotpatches) from `~/Saturn/docker/owui-pluto/docker-compose.yml`, port 3000.
- Bench SurrealDB: `pluto-surrealdb` **3.2.4** (since 2026-10-14, mirrors Saturn), compose `~/Docker/pluto-compose.yml`, volume `docker_surrealdb-data`. Pre-upgrade backup in `~/backups/pluto-surrealdb-2026-10-14/`.
- Saturn still runs `owui-surrealdb:v0.4.x-cuda` from the deprecated copy `~/Saturn/owui-surrealdb-adapter/`.
- Tests: 186 passed on SurrealDB 3.2.4. Bench acceptance a–f all pass (`E2E_CHECKLIST.md`, 2026-10-14).

## 🚀 Active tracks

- None registered.

## ⚠️ Blockers

- None.

## 📋 Next queue

1. Merge `release/v0.5.0` into `main` and push (repo + tag) — Arnar's call.
2. Saturn deploy of v0.5.0 — separate task.
3. Retire `~/Saturn/owui-surrealdb-adapter/` once Saturn runs v0.5.0.
4. OWUI 0.12 upgrade as its own step after Saturn is on v0.5.0 (re-check both hotpatches against 0.12).

## 📌 Parked

- OWUI's file delete (`DELETE /api/v1/files/{id}`) calls `delete(collection_name='file-{id}')` with no ids/filter, which the adapter treats as a no-op, so that path leaves the file table. Known since June (relay 2026-06-05). Deleting from inside a KB uses `delete_collection` and works.
- Upstream PR open-webui#22287 — refused (BSL licence); standalone overlay package instead. See `docs/brief.md`.
- `SURREALDB_CONNECT_TIMEOUT` is ignored (SDK hardcodes 10 s open timeout).
