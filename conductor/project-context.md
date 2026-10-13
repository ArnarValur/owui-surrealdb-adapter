# Project Context — SurrealDB Merkurial Solutions

> Operational context for this project. Customize per conductor branch.
> Persona and communication style are handled separately — this file is purely operational.

---

## Product Definition

- **Name:** owui-surrealdb-adapter
- **Tagline:** SurrealDB vector backend for Open WebUI, shipped as a Docker overlay
- **Description:** Python package implementing Open WebUI's `VectorDBBase` on SurrealDB 3.x. Installed into the official OWUI image by a Dockerfile that patches two OWUI files (`factory.py`, `type.py`). Full brief: [docs/brief.md](./docs/brief.md).
- **Target Audience:** Merkurial-studio's own OWUI instances (Saturn, PlutoII bench); public repo for reference
- **Key Differentiators:** No OWUI fork; cascade delete of orphaned file tables; metadata-only collections; auto-reconnect

## Product Guidelines

- **Brand Voice:** Technical and precise — documentation-driven, clear API surfaces
- **UX Principles:** Reliability-first — robust error handling, graceful degradation
- **Accessibility:** Standard code accessibility (clear naming, typed interfaces)

## Tech Stack

- **Languages:** Python, SurrealQL
- **Frameworks:** SurrealDB SDK (surrealdb crate / JS SDK)
- **Databases:** SurrealDB (primary)
- **Deployment Targets:** Self-hosted (Docker / bare metal)
- **Hosting:** Self-hosted on Saturn (ASUS Ascent GX10)

---

## Caution Levels

| Domain              | Level       | Notes                                   |
|---------------------|-------------|-----------------------------------------|
| Extensions / Adaptors | 🔴 Critical | Core functionality — verify thoroughly |
| SurrealQL Scripts   | 🟡 Careful  | Data impact — test against staging     |
| Config / Build      | 🔴 Critical | Can break everything — verify before    |
| SDK Wrappers        | 🟡 Careful  | API surface changes affect consumers   |
| Documentation       | 🟢 Normal   | Low risk                                |
| conductor/ files    | 🟡 Careful  | Source of truth — don't corrupt         |

---

## Domain Expertise

| Area                | Confidence  | Notes                                   |
|---------------------|-------------|-----------------------------------------|
| SurrealDB           | High        | Core target database                    |
| SurrealQL           | High        | Query language for all operations       |
| Python SDK          | Medium      | surrealdb Python package                |
| Docker              | High        | Primary deployment mechanism            |

---

## Preferred Workflows

1. **Session Start Protocol:**
   - Read `conductor/relay.md` first (pending messages, blockers)
   - Then read `conductor/pulse.md` (current state, recent progress)
   - Review `conductor/tracks.md` for next task

2. **Checkpoint Frequency:**
   - Checkpoint after every completed phase
   - Consider mid-phase checkpoints for long phases (>5 tasks)

3. **Decision Logging:**
   - Log non-obvious decisions in git notes
   - Update `pulse.md` after every major step
   - Verify actual state on disk before proposing changes

4. **Debugging Protocol:**
   - Check legacy interference before blaming new code
   - If a fix fails twice, stop and escalate
   - Audit actual state vs documented state

---

## Project-Specific Constraints

- All SurrealDB instances run on Saturn (ARM64, NVIDIA GB10 GPU)
- Python 3.11+ required
- No user data in logs
- Pin all major dependency versions
- SurrealDB connection via WebSocket preferred over HTTP

---

## Environment Notes

- **Repo:** `~/Projects/owui-surrealdb-adapter` (PlutoII). Python 3.12 venv in `.venv`.
- **Test bench:** PlutoII — `~/Saturn/docker/owui-pluto/` (owui-pluto + pluto-surrealdb on `pluto-net`)
- **Production:** Saturn (`ssh saturn-claude`) — deploys are separate tasks
- **Secrets:** `.env` (git-ignored, read by compose)
