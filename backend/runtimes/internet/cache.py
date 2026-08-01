from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Protocol

from .contracts import SearchResult, InternetCache


class InMemoryInternetCache(InternetCache):
    """In-memory cache with TTL support."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 900):
        self._cache: dict[str, tuple[list[SearchResult], float]] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> list[SearchResult] | None:
        if key in self._cache:
            results, expiry = self._cache[key]
            if time.time() < expiry:
                self._hits += 1
                return results
            else:
                del self._cache[key]
        self._misses += 1
        return None

    async def set(self, key: str, value: list[SearchResult], ttl: int | None = None) -> None:
        if len(self._cache) >= self._max_size:
            oldest = min(self._cache.items(), key=lambda x: x[1][1])
            del self._cache[oldest[0]]

        expiry = time.time() + (ttl or self._default_ttl)
        self._cache[key] = (value, expiry)

    async def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
        }


class SQLiteInternetCache(InternetCache):
    """SQLite-backed persistent cache."""

    def __init__(self, db_path: str = "internet_cache.db", default_ttl: int = 900):
        self.db_path = db_path
        self._default_ttl = default_ttl
        self._init_db()

    def _init_db(self):
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    expiry REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expiry ON cache(expiry)")

    async def get(self, key: str) -> list[SearchResult] | None:
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM cache WHERE key = ? AND expiry > ?",
                (key, time.time())
            ).fetchone()
            if row:
                return [SearchResult(**r) for r in json.loads(row[0])]
        return None

    async def set(self, key: str, value: list[SearchResult], ttl: int | None = None) -> None:
        import sqlite3
        expiry = time.time() + (ttl or self._default_ttl)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expiry) VALUES (?, ?, ?)",
                (key, json.dumps([r.__dict__ for r in value], default=str), expiry)
            )

    async def clear(self) -> None:
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")

    def stats(self) -> dict[str, Any]:
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            size = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        return {"size": size, "db_path": self.db_path}


def create_internet_cache(cache_type: str = "memory", **kwargs) -> InternetCache:
    if cache_type == "sqlite":
        return SQLiteInternetCache(kwargs.get("db_path", "internet_cache.db"), kwargs.get("default_ttl", 900))
    return InMemoryInternetCache(kwargs.get("max_size", 1000), kwargs.get("default_ttl", 900))