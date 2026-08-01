# backend/tests/discovery/test_cache.py
from __future__ import annotations

import time

from runtime.discovery.cache import DiscoveryCache


class TestDiscoveryCache:
    def test_set_and_get(self):
        cache = DiscoveryCache()
        cache.set("key", {"data": "value"})
        assert cache.get("key") == {"data": "value"}

    def test_expired(self):
        cache = DiscoveryCache()
        cache.set("key", "value")
        assert cache.get("key", ttl=0) is None

    def test_missing_key(self):
        cache = DiscoveryCache()
        assert cache.get("missing") is None

    def test_clear(self):
        cache = DiscoveryCache()
        cache.set("key", "value")
        cache.clear()
        assert cache.get("key") is None

    def test_lru_eviction(self):
        cache = DiscoveryCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_invalidate_prefix(self):
        cache = DiscoveryCache()
        cache.set("discovery:1", "a")
        cache.set("discovery:2", "b")
        cache.set("other:1", "c")
        removed = cache.invalidate_prefix("discovery:")
        assert removed == 2
        assert cache.get("other:1") == "c"
        assert cache.get("discovery:1") is None

    def test_invalidate_pattern(self):
        cache = DiscoveryCache()
        cache.set("discovery:x:1", "a")
        cache.set("discovery:x:2", "b")
        cache.set("discovery:y:1", "c")
        removed = cache.invalidate_pattern(r"discovery:x:\d+")
        assert removed == 2
        assert cache.get("discovery:y:1") == "c"

    def test_cleanup_expired(self):
        cache = DiscoveryCache()
        cache.set("key", "value")
        time.sleep(0.01)
        removed = cache.cleanup_expired(ttl=0)
        assert removed == 1
        assert cache.get("key") is None

    def test_size(self):
        cache = DiscoveryCache()
        assert cache.size == 0
        cache.set("a", 1)
        assert cache.size == 1
