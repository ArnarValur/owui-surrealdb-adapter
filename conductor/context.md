# Domain Glossary

> Ubiquitous language for this project. All commands, specs, and discussions use these terms verbatim.
> Last refined: 2026-06-11T11:21+02:00

## Entities

| Term | Definition | Also Known As |
|------|-----------|---------------|
| Adapter | The `owui-surrealdb-adapter` Python package — bridges Open WebUI's VectorDBBase interface to SurrealDB | SDB adapter |
| KB collection | A UUID-named SurrealDB table storing a knowledge base's aggregated vectors (one per KB) | KB table |
| File collection | A `file-{uuid}` prefixed table storing per-file vector chunks | File table |
| Metadata collection | A non-vector collection (e.g. `knowledge-bases`) used by OWUI for indexing — has no embeddings | Index table |
| Cascade delete | Self-cleaning logic that drops orphaned file tables when a KB collection is deleted | — |
| Docker overlay | The Dockerfile that extends OWUI's base image and patches in the SurrealDB backend via `patch.py` | — |
| Table prefix | The `owui_` prefix applied to all SurrealDB tables to avoid collisions in shared instances | — |

## Relationships

- **KB collection** 1:N **File collection** — each KB references multiple file tables via `metadata.file_id`
- **Metadata collection** lists all **KB collections** — the `knowledge-bases` table is OWUI's KB index
- **Cascade delete** operates on the KB → File relationship to clean orphans
- **Docker overlay** installs the **Adapter** into OWUI's base image via `patch.py`

## Terminology Boundaries

- "Collection" = OWUI term. Mapped to SurrealDB "table" with the configured table prefix.
- "Vector" vs "Metadata" collection — metadata collections have no embeddings (dimension 0). The adapter must handle both.
- "Adapter" refers to this package, NOT a generic database adapter pattern.
