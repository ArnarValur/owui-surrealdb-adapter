# Product Requirements — owui-surrealdb-adapter

## Overview

A standalone Python package that bridges Open WebUI's vector database interface (`VectorDBBase`) to SurrealDB. Maintained as Merkurial-studio's private adapter — public repo for community reference, but not dependent on upstream OWUI acceptance. Deploys as a Docker overlay that patches OWUI's factory at build time.

## In Scope

- Full VectorDBBase implementation (9 methods) targeting SurrealDB 3.1+
- HNSW and DiskANN vector index support
- Docker overlay integration (no OWUI fork required)
- Cascade delete for orphaned file tables
- Metadata-only (non-vector) collection support
- Connection resilience (auto-reconnect, retry with backoff)
- SQL injection prevention (validated identifiers, parameterized queries)
- Public GitHub repo (`ArnarValur/owui-surrealdb-adapter`)

## Out of Scope

- Upstream OWUI PR (community is slow — maintain independently)
- xterm.js / Vite build fixes (ZeroGravity concern, tracked in ZG conductor)
- GPU-specific Docker configuration (generic adapter, GPU is deployment-level)
- Multi-tenant / multi-user authentication (single shared SDB namespace)
- OWUI version tracking beyond current pin (0.9.6)

## Open Questions

- Future ZeroGravity integration — ZG may consume the same SDB vector data. Cross-project schema alignment TBD.
- Potential for Antigravity SDK integration with SurrealDB ecosystem (exploratory, not committed).
