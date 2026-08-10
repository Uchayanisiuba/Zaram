"""Tests for the enhanced Knowledge Cache."""
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parents[1]
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import time
import pytest

from knowledge.cache import KnowledgeCache


class TestKnowledgeCache:
    def setup_method(self):
        self.cache = KnowledgeCache(max_size=10)

    def test_basic_set_get(self):
        self.cache.set("key1", {"data": "value"})
        result = self.cache.get("key1")
        assert result == {"data": "value"}

    def test_get_missing_key(self):
        result = self.cache.get("nonexistent")
        assert result is None

    def test_ttl_expiration(self):
        self.cache.set("key1", "value")
        result = self.cache.get("key1", ttl=0.01)
        assert result == "value"
        time.sleep(0.02)
        result = self.cache.get("key1", ttl=0.01)
        assert result is None

    def test_per_key_ttl(self):
        self.cache.set("key1", "value", ttl=0.01)
        assert self.cache.get("key1") == "value"
        time.sleep(0.02)
        assert self.cache.get("key1") is None

    def test_max_size_eviction(self):
        for i in range(15):
            self.cache.set(f"key{i}", f"value{i}")
        assert self.cache.size <= 10
        stats = self.cache.get_stats()
        assert stats["evictions"] > 0

    def test_invalidate_by_key(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.invalidate("key1")
        assert self.cache.get("key1") is None
        assert self.cache.get("key2") == "value2"

    def test_invalidate_pattern(self):
        self.cache.set("prefix:a", "value1")
        self.cache.set("prefix:b", "value2")
        self.cache.set("other:c", "value3")
        removed = self.cache.invalidate_pattern(r"^prefix:")
        assert removed == 2
        assert self.cache.get("prefix:a") is None
        assert self.cache.get("prefix:b") is None
        assert self.cache.get("other:c") == "value3"

    def test_invalidate_prefix(self):
        self.cache.set("prefix:a", "value1")
        self.cache.set("prefix:b", "value2")
        self.cache.set("other:c", "value3")
        removed = self.cache.invalidate_prefix("prefix:")
        assert removed == 2
        assert self.cache.get("prefix:a") is None
        assert self.cache.get("other:c") == "value3"

    def test_clear(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.clear()
        assert self.cache.size == 0

    def test_cleanup_expired(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        time.sleep(0.02)
        removed = self.cache.cleanup_expired(ttl=0.01)
        assert removed == 2
        assert self.cache.size == 0

    def test_hit_rate(self):
        self.cache.set("key1", "value1")
        self.cache.get("key1")
        self.cache.get("key1")
        self.cache.get("nonexistent")
        stats = self.cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] > 0

    def test_deduplicate(self):
        self.cache.set("key1", {"data": "same"})
        self.cache.set("key2", {"data": "same"})
        removed = self.cache.deduplicate()
        assert removed == 1

    def test_incremental_update(self):
        self.cache.set("key1", {"a": 1, "b": 2})
        count = self.cache.incremental_update({"key1": {"b": 3, "c": 4}})
        assert count == 1
        result = self.cache.get("key1")
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_stats(self):
        self.cache.set("key1", "value1")
        self.cache.get("key1")
        stats = self.cache.get_stats()
        assert stats["size"] == 1
        assert stats["max_size"] == 10
        assert "evictions" in stats
        assert "insertions" in stats
        assert "utilization" in stats
        assert 0 < stats["utilization"] <= 1.0

    def test_persistence(self, tmp_path):
        persist_path = str(tmp_path / "cache.gz")
        cache1 = KnowledgeCache(max_size=10, persist_path=persist_path)
        cache1.set("key1", "value1")
        cache1.set("key2", "value2")

        cache2 = KnowledgeCache(max_size=10, persist_path=persist_path)
        assert cache2.get("key1") == "value1"
        assert cache2.get("key2") == "value2"

    def test_size_property(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        assert self.cache.size == 2

    def test_insertions_tracked(self):
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        stats = self.cache.get_stats()
        assert stats["insertions"] == 2
