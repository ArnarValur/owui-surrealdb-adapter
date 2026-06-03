"""Configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SurrealDBConfig:
    """Adapter configuration parsed from environment variables.

    All values have sensible defaults matching the spec.
    """

    uri: str = field(default_factory=lambda: os.getenv("SURREALDB_URI", "ws://localhost:8000/rpc"))
    namespace: str = field(default_factory=lambda: os.getenv("SURREALDB_NS", "owui"))
    database: str = field(default_factory=lambda: os.getenv("SURREALDB_DB", "vectors"))
    user: str = field(default_factory=lambda: os.getenv("SURREALDB_USER", "root"))
    password: str = field(default_factory=lambda: os.getenv("SURREALDB_PASS", "root"))
    table_prefix: str = field(default_factory=lambda: os.getenv("SURREALDB_TABLE_PREFIX", "owui_"))
    index_type: str = field(default_factory=lambda: os.getenv("SURREALDB_INDEX_TYPE", "hnsw"))
    ef_search: int = field(default_factory=lambda: int(os.getenv("SURREALDB_EF_SEARCH", "40")))

    @classmethod
    def from_env(cls) -> SurrealDBConfig:
        """Create config from current environment variables."""
        return cls()

    @property
    def is_websocket(self) -> bool:
        """True if the URI uses WebSocket protocol."""
        return self.uri.startswith(("ws://", "wss://"))
