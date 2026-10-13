# Pulse — owui-surrealdb-adapter

> **Updated:** 2026-10-14 — conductor moved into the repo (relocation session)
> State only, cap ~60 lines. Rewritten from scratch at every checkpoint —
> if you are appending to this file, you are doing it wrong.

## 📍 Now — what runs where

- Canonical repo: `~/Projects/owui-surrealdb-adapter` (moved from `~/SurrealDB/` 2026-10-14). Tags `v0.1.0`, `v0.2.0`.
- Saturn still runs `owui-surrealdb:v0.4.x-cuda`, built from the old copy `~/Saturn/owui-surrealdb-adapter/` (marked DEPRECATED, kept until Saturn is on v0.5.0).
- PlutoII test bench: `~/Saturn/docker/owui-pluto/docker-compose.yml` → container `owui-pluto` (port 3000) + `pluto-surrealdb` (SurrealDB 3.1.2, host port 8000, root/root).
- Old pulse (June state) archived: `pulse-archive/pulse-2026-06-11.md`.

## 🚀 Active tracks

- None registered. v0.5.0 release work runs from the task brief (see Next queue).

## ⚠️ Blockers

- None.

## 📋 Next queue

1. **Stage 0 — make this repo canonical:** drop stray files, 184 tests green, bring in `Dockerfile` (0.11.3-cuda) + `hotpatches/` from the Saturn copy, `.dockerignore` hardening, version 0.5.0 everywhere, `purge_orphans()` auto-discovery defaults to dry run, README drift fixes. Branch `release/v0.5.0`.
2. **Stage 1 — PlutoII bench:** build `owui-surrealdb:v0.5.0-cuda`, point owui-pluto at it, acceptance checks a–f (real base class, no hybrid flag, hybrid-on RAG, KB delete cascade, cold-start file delete, clean logs). Tag `v0.5.0` only when all pass.
3. **Saturn deploy of v0.5.0** — separate task, not started from the bench work.
4. Retire `~/Saturn/owui-surrealdb-adapter/` once Saturn runs v0.5.0.

## 📌 Parked

- Upstream PR open-webui#22287 — refused (BSL licence); goal is a standalone overlay package. See `docs/brief.md`.
- `SURREALDB_CONNECT_TIMEOUT` is ignored (SDK hardcodes 10 s open timeout).
