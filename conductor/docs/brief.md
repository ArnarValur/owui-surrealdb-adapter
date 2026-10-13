# Project brief — owui-surrealdb-adapter

**What it is.** A small Python package that lets Open WebUI (OWUI) store its RAG vectors in SurrealDB. It implements OWUI's `VectorDBBase` interface (9 methods) on top of the `surrealdb` Python SDK, for SurrealDB 3.x with HNSW or DiskANN indexes. Each OWUI collection becomes a SurrealDB table with the `owui_` prefix.

**Two-file overlay design.** No OWUI fork. The `Dockerfile` starts from the official `ghcr.io/open-webui/open-webui:<version>-cuda` image, pip-installs this package, and runs `python -m owui_surrealdb_adapter.patch`, which edits exactly two OWUI files so `VECTOR_DB=surrealdb` works:

- `retrieval/vector/type.py` — adds the `SURREALDB` enum value.
- `retrieval/vector/factory.py` — adds the branch that builds our client.

Backups of both are kept as `*.bak` in the image. Separately, `hotpatches/` holds two Gemini streaming fixes that patch OWUI itself at build time (tool-call index, thought signature); they are not part of the adapter API.

**Why v0.5.0.** Two copies drifted apart: this dev repo (tests, hardening) and `~/Saturn/owui-surrealdb-adapter/` (the one Saturn's images were built from: newer Dockerfile on OWUI 0.11.3 + hotpatches). v0.5.0 is the first release after merging them into this one canonical repo. Versions follow SemVer 0.x (ADR-0001).

**Upstream.** OWUI PR #22287 (SurrealDB as a VectorDB) was refused by the maintainer over SurrealDB's BSL licence. The goal is a standalone overlay package, maintained here.

**Bench SurrealDB.** 2026-10-14: `pluto-surrealdb` moved from v3.1.2 to **v3.2.4** to mirror Saturn (same container name, volume `docker_surrealdb-data`, `pluto-net`; set in `~/Docker/pluto-compose.yml`). Data intact (1332 tables in `owui/vectors`), 186/186 tests green on 3.2.4. Pre-upgrade volume backup: `~/backups/pluto-surrealdb-2026-10-14/`.

**Open steps** live in `pulse.md` → Next queue.
