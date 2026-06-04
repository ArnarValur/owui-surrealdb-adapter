"""Configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _positive_int(env_var: str, default: str) -> int:
    """Parse an env var as a positive integer, raising on invalid input."""
    raw = os.getenv(env_var, default)
    try:
        val = int(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{env_var} must be a positive integer, got: {raw!r}"
        ) from exc
    if val <= 0:
        raise ValueError(
            f"{env_var} must be a positive integer, got: {val}"
        )
    return val


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
    ef_search: int = field(default_factory=lambda: _positive_int("SURREALDB_EF_SEARCH", "40"))
    connect_timeout: int = field(default_factory=lambda: _positive_int("SURREALDB_CONNECT_TIMEOUT", "10"))
    max_retries: int = field(default_factory=lambda: _positive_int("SURREALDB_MAX_RETRIES", "3"))
    retry_backoff: float = field(default_factory=lambda: float(os.getenv("SURREALDB_RETRY_BACKOFF", "1.0")))

    @classmethod
    def from_env(cls) -> SurrealDBConfig:
        """Create config from current environment variables."""
        return cls()

    @property
    def is_websocket(self) -> bool:
        """True if the URI uses WebSocket protocol."""
        return self.uri.startswith(("ws://", "wss://"))
