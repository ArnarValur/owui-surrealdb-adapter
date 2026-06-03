# owui-surrealdb-adapter

SurrealDB vector database adapter for [Open WebUI](https://github.com/open-webui/open-webui).

Replaces the default vector store (Chroma/Qdrant/etc.) with SurrealDB — your docs, embeddings, and RAG all in one database.

## Quick Start

```bash
pip install -e .
```

Set `VECTOR_DB=surrealdb` in your Open WebUI config, then configure:

| Variable | Default | What it does |
|----------|---------|-------------|
| `SURREALDB_URI` | `ws://localhost:8000/rpc` | Connection URI |
| `SURREALDB_NS` | `owui` | Namespace |
| `SURREALDB_DB` | `vectors` | Database |
| `SURREALDB_USER` | `root` | Auth user |
| `SURREALDB_PASS` | `root` | Auth password |
| `SURREALDB_TABLE_PREFIX` | `owui_` | Table name prefix |
| `SURREALDB_INDEX_TYPE` | `hnsw` | `hnsw` or `diskann` |
| `SURREALDB_EF_SEARCH` | `40` | KNN search effort |

## Docker (coming soon)

Docker overlay image that extends Open WebUI — no fork needed. See Phase 6 in the plan.

## Dev

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Status

- ✅ All 7 VectorDBBase methods implemented
- ✅ 5 audit bugs fixed (silent failures, false positives, missing `$in`, wrong delete key, batch vectors)
- ✅ 53 tests, 96.5% coverage
- 🔜 Docker overlay + E2E testing

## License

MIT
