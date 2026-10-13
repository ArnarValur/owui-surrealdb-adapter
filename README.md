# owui-surrealdb-adapter

SurrealDB vector database adapter for [Open WebUI](https://github.com/open-webui/open-webui).

I fell inlove with SurrealDB recently and I use Open WebUI heavily as my home-made AI platform and laboratory (non-enterprise, pure hobby) and I wanted to find a way to build a bridge between OWUI and SDB.

This is an attempt to do just that. But with a small twist. Im hoping maybe I can share this to the OWUI community and get it as an official adapter so there is no need to use the docker overlay method.

## Quick Start

### Docker (recommended)

The adapter ships as a Docker overlay — it extends the official Open WebUI image (`ghcr.io/open-webui/open-webui:0.11.3-cuda`), no fork needed. The image build also applies two Gemini streaming fixes from `hotpatches/` to Open WebUI itself.

```bash
# Clone and start
git clone https://github.com/ArnarValur/owui-surrealdb-adapter.git
cd owui-surrealdb-adapter

# Set credentials (change for production!)
cp .env.example .env

# Launch Open WebUI + SurrealDB
docker compose up -d
```

Open WebUI will be available at **http://localhost:3001** with SurrealDB as the vector backend.

### Standalone (pip)

If you already have Open WebUI installed and want to add SurrealDB support:

```bash
pip install -e .
python -m owui_surrealdb_adapter.patch --owui-root /path/to/open_webui
```

Then set `VECTOR_DB=surrealdb` in your Open WebUI config.

## Configuration

All settings are via environment variables with sensible defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `SURREALDB_URI` | `ws://localhost:8000/rpc` | WebSocket or HTTP connection URI |
| `SURREALDB_NS` | `owui` | SurrealDB namespace |
| `SURREALDB_DB` | `vectors` | SurrealDB database |
| `SURREALDB_USER` | `root` | Auth username |
| `SURREALDB_PASS` | `root` | Auth password |
| `SURREALDB_TABLE_PREFIX` | `owui_` | Prefix for all vector tables |
| `SURREALDB_INDEX_TYPE` | `hnsw` | Vector index type (`hnsw` or `diskann`) |
| `SURREALDB_EF_SEARCH` | `40` | KNN search effort (higher = more accurate, slower) |
| `SURREALDB_CONNECT_TIMEOUT` | `10` | Currently ignored — the SDK hardcodes a 10 s open timeout |
| `SURREALDB_MAX_RETRIES` | `3` | Max reconnection attempts on transport failure |
| `SURREALDB_RETRY_BACKOFF` | `1.0` | Base backoff delay between retries (seconds, doubles each retry) |
| `SURREALDB_CASCADE_DELETE` | `true` | When a knowledge base is deleted, also drop the file tables only it used |

## How It Works

```
Open WebUI  →  VectorDBBase interface  →  SurrealDBClient  →  SurrealDB 3.x
                  (factory.py patch)          (this adapter)      (HNSW index)
```

The adapter patches two files inside Open WebUI at build time:
- **type.py** — adds `SURREALDB` to the `VectorType` enum
- **factory.py** — adds a `case VectorType.SURREALDB:` branch to the factory

At runtime, when `VECTOR_DB=surrealdb`, OWUI routes all vector operations through `SurrealDBClient`, which implements all 9 `VectorDBBase` methods: `has_collection`, `insert`, `upsert`, `search`, `query`, `get`, `delete`, `delete_collection`, and `reset`.

Each knowledge base file gets its own SurrealDB table (`owui_file-{uuid}`) with HNSW-indexed vectors for fast KNN search.

## Dev

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run unit + hardening tests (no SurrealDB needed)
pytest tests/ --ignore=tests/test_live_integration.py \
  --ignore=tests/test_cascade_delete.py --ignore=tests/test_metadata_collections.py

# Run ALL tests including live integration (needs SurrealDB on localhost:8000,
# or set TEST_SURREALDB_URI). test_live_integration.py, test_cascade_delete.py
# and test_metadata_collections.py all need a live SurrealDB.
pytest tests/
```

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `type::thing is not a valid function` | SurrealDB v3.1 renamed it | Already fixed — adapter uses `DELETE table:id` syntax |
| `table does not exist` on first query | Table created lazily on insert | Upload a file first, then query |
| Connection drops after idle | WebSocket timeout | Adapter auto-reconnects with exponential backoff |
| Dimension mismatch after model change | Old vectors have different size | Delete and re-upload affected knowledge bases |

## Status

- ✅ All 9 VectorDBBase methods implemented
- ✅ Production hardened — SQL injection prevention, reconnect logic, thread safety
- ✅ 186 tests passing (unit, hardening and live integration)
- ✅ Docker overlay — extends OWUI 0.11.3-cuda, no fork needed
- ✅ Full RAG pipeline verified: upload → embed → HNSW → KNN search → cited answer
- ❌ Upstream: Open WebUI PR #22287 (SurrealDB as a VectorDB) was refused by the maintainer over SurrealDB's BSL licence. The goal is now a standalone overlay package, maintained here.

## License

MIT
