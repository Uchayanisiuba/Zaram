# backend/runtime/discovery/cache.py
from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from typing import Any


class DiscoveryCache:
    """Thread-safe TTL cache for discovery results."""

    def __init__(self, max_size: int = 2048):
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, key: str, ttl: float = 900) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            value, ts = entry
            if time.time() - ts >= ttl:
                del self._store[key]
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, time.time())
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_pattern(self, pattern: str) -> int:
        regex = re.compile(pattern)
        removed = 0
        with self._lock:
            keys_to_remove = [k for k in self._store if regex.search(k)]
            for k in keys_to_remove:
                del self._store[k]
                removed += 1
        return removed

    def invalidate_prefix(self, prefix: str) -> int:
        removed = 0
        with self._lock:
            keys_to_remove = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._store[k]
                removed += 1
        return removed

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def cleanup_expired(self, ttl: float = 900) -> int:
        now = time.time()
        removed = 0
        with self._lock:
            keys_to_remove = [
                k for k, (_, ts) in self._store.items() if now - ts >= ttl
            ]
            for k in keys_to_remove:
                del self._store[k]
                removed += 1
        return removed

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)
