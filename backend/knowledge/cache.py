# backend/knowledge/cache.py
from __future__ import annotations

import gzip
import json
import os
import re
import threading
import time
from collections import OrderedDict
from typing import Any


class KnowledgeCache:
    """Thread-safe TTL cache with persistence, dedup, compression, and incremental updates."""

    def __init__(self, max_size: int = 2048, persist_path: str = ""):
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
        self._persist_path = persist_path
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._insertions = 0
        self._default_ttl = 900.0
        self._per_key_ttl: dict[str, float] = {}
        if persist_path and os.path.exists(persist_path):
            self._load()

    def get(self, key: str, ttl: float = 900) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                self._misses += 1
                return None
            value, ts = entry
            effective_ttl = self._per_key_ttl.get(key, ttl)
            if time.time() - ts >= effective_ttl:
                del self._store[key]
                self._per_key_ttl.pop(key, None)
                self._misses += 1
                return None
            self._store.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, time.time())
            if ttl is not None:
                self._per_key_ttl[key] = ttl
            self._insertions += 1
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)
                self._evictions += 1
            self._persist_if_enabled()

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
            self._per_key_ttl.pop(key, None)

    def invalidate_pattern(self, pattern: str) -> int:
        regex = re.compile(pattern)
        removed = 0
        with self._lock:
            keys_to_remove = [k for k in self._store if regex.search(k)]
            for k in keys_to_remove:
                del self._store[k]
                removed += 1
            if removed:
                self._persist_if_enabled()
        return removed

    def invalidate_prefix(self, prefix: str) -> int:
        removed = 0
        with self._lock:
            keys_to_remove = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._store[k]
                removed += 1
            if removed:
                self._persist_if_enabled()
        return removed

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._per_key_ttl.clear()
            self._persist_if_enabled()

    def cleanup_expired(self, ttl: float = 900) -> int:
        now = time.time()
        removed = 0
        with self._lock:
            keys_to_remove = [k for k, (_, ts) in self._store.items() if now - ts >= ttl]
            for k in keys_to_remove:
                del self._store[k]
                removed += 1
            if removed:
                self._persist_if_enabled()
        return removed

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def deduplicate(self) -> int:
        with self._lock:
            seen: dict[str, str] = {}
            duplicates: list[str] = []
            for key, (value, ts) in list(self._store.items()):
                try:
                    normalized = json.dumps(value, sort_keys=True, default=str)
                except Exception:
                    continue
                if normalized in seen:
                    duplicates.append(key)
                else:
                    seen[normalized] = key
            for key in duplicates:
                del self._store[key]
            if duplicates:
                self._persist_if_enabled()
            return len(duplicates)

    def incremental_update(self, updates: dict[str, Any]) -> int:
        count = 0
        with self._lock:
            for key, delta in updates.items():
                if key in self._store:
                    value, ts = self._store[key]
                    if isinstance(value, dict) and isinstance(delta, dict):
                        merged = {**value, **delta}
                        self._store[key] = (merged, ts)
                        count += 1
            if count:
                self._persist_if_enabled()
        return count

    def _persist_if_enabled(self) -> None:
        if not self._persist_path:
            return
        try:
            data = {k: v for k, v in self._store.items()}
            payload = json.dumps(data, default=str).encode("utf-8")
            tmp = self._persist_path + ".tmp"
            with gzip.open(tmp, "wb") as f:
                f.write(payload)
            os.replace(tmp, self._persist_path)
        except Exception:
            pass

    def _load(self) -> None:
        if not self._persist_path or not os.path.exists(self._persist_path):
            return
        try:
            with gzip.open(self._persist_path, "rb") as f:
                data = json.loads(f.read().decode("utf-8"))
            with self._lock:
                for key, (value, ts) in data.items():
                    self._store[key] = (value, ts)
        except Exception:
            pass

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "hit_rate": self.hit_rate,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "insertions": self._insertions,
                "utilization": len(self._store) / self._max_size if self._max_size > 0 else 0.0,
            }
