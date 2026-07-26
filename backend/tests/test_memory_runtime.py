# backend/tests/test_memory_runtime.py
"""Tests for the Memory Runtime, Embedding Service, and Knowledge Runtime integration."""
from __future__ import annotations

import asyncio
import time

import pytest

from runtimes.memory import (
    MemoryRuntimeImpl,
    create_memory_runtime,
    EmbeddingService,
    create_embedding_service,
    MemoryRecord,
    MemoryType,
    RetrievalStrategy,
    MemoryStatus,
    MemoryGraph,
    EdgeType,
    create_memory_graph,
    MemoryDecayEngine,
    DecayConfig,
    create_decay_engine,
)
from runtimes.memory.contracts import MemoryQuery
from knowledge.cache import KnowledgeCache
from knowledge.runtime import KnowledgeRuntime
from knowledge.providers import MemoryProvider
from knowledge.protocol import ResultType


# ---------------------------------------------------------------------------
# Embedding Service Tests
# ---------------------------------------------------------------------------

class TestEmbeddingService:
    def test_hash_embedding_deterministic(self):
        service = EmbeddingService(backend="hash", dim=128)
        emb1 = service.embed("hello world")
        emb2 = service.embed("hello world")
        assert emb1 == emb2
        assert len(emb1) == 128

    def test_hash_embedding_different_texts(self):
        service = EmbeddingService(backend="hash", dim=128)
        emb1 = service.embed("hello world")
        emb2 = service.embed("goodbye universe")
        assert emb1 != emb2

    def test_hash_embedding_normalized(self):
        import math
        service = EmbeddingService(backend="hash", dim=64)
        emb = service.embed("test content")
        norm = math.sqrt(sum(x * x for x in emb))
        assert abs(norm - 1.0) < 0.01

    def test_empty_text(self):
        service = EmbeddingService(backend="hash", dim=64)
        emb = service.embed("")
        assert len(emb) == 64
        assert all(x == 0.0 for x in emb)

    def test_batch_embedding(self):
        service = EmbeddingService(backend="hash", dim=64)
        results = service.embed_batch(["a", "b", "c"])
        assert len(results) == 3
        assert all(len(r) == 64 for r in results)

    def test_cache(self):
        service = EmbeddingService(backend="hash", dim=64)
        emb1 = service.embed("cached text")
        service._cache.clear()
        emb2 = service.embed("cached text")
        assert emb1 == emb2

    def test_health_check(self):
        service = EmbeddingService(backend="hash", dim=64)
        health = service.health_check()
        assert health["status"] == "healthy"
        assert health["backend"] == "hash"
        assert health["dim"] == 64

    def test_create_factory(self):
        service = create_embedding_service(backend="hash", dim=128)
        assert isinstance(service, EmbeddingService)
        assert service.get_dim() == 128


# ---------------------------------------------------------------------------
# Memory Runtime Tests
# ---------------------------------------------------------------------------

class TestMemoryRuntime:
    @pytest.fixture
    def runtime(self):
        rt = create_memory_runtime(
            store_type="memory",
            index_type="hybrid",
            embedding_dim=128,
            embedding_backend="hash",
        )
        asyncio.run(rt.initialize())
        return rt

    def test_initialize(self, runtime):
        assert runtime.get_state() == MemoryStatus.READY
        assert runtime.get_runtime_id() == "memory"

    def test_store_and_retrieve(self, runtime):
        record_id = asyncio.run(runtime.store(
            content="The capital of France is Paris",
            memory_type=MemoryType.SEMANTIC,
            tags=["geography", "facts"],
        ))
        assert record_id is not None

        results = asyncio.run(runtime.retrieve(
            query="capital of France",
            memory_types=[MemoryType.SEMANTIC],
            max_results=5,
        ))
        assert len(results) > 0
        assert any("Paris" in r.record.content for r in results)

    def test_store_generates_embedding(self, runtime):
        record_id = asyncio.run(runtime.store(
            content="Test embedding content",
            memory_type=MemoryType.CONVERSATION,
        ))
        record = asyncio.run(runtime.get_record(record_id))
        assert record is not None
        assert record.embedding is not None
        assert len(record.embedding) == 128

    def test_retrieve_with_vector_search(self, runtime):
        asyncio.run(runtime.store(
            content="Python is a programming language",
            memory_type=MemoryType.SEMANTIC,
            tags=["programming"],
        ))
        asyncio.run(runtime.store(
            content="The Eiffel Tower is in Paris",
            memory_type=MemoryType.SEMANTIC,
            tags=["travel"],
        ))

        results = asyncio.run(runtime.retrieve(
            query="programming language",
            memory_types=[MemoryType.SEMANTIC],
            max_results=5,
            strategy=RetrievalStrategy.VECTOR_SIMILARITY,
        ))
        assert len(results) > 0
        assert any("Python" in r.record.content for r in results)

    def test_retrieve_with_keyword_search(self, runtime):
        asyncio.run(runtime.store(
            content="Machine learning algorithms",
            memory_type=MemoryType.SEMANTIC,
        ))

        results = asyncio.run(runtime.retrieve(
            query="machine learning",
            memory_types=[MemoryType.SEMANTIC],
            max_results=5,
            strategy=RetrievalStrategy.KEYWORD_MATCH,
        ))
        assert len(results) > 0

    def test_retrieve_hybrid_strategy(self, runtime):
        asyncio.run(runtime.store(
            content="Quantum computing uses qubits",
            memory_type=MemoryType.SEMANTIC,
        ))

        results = asyncio.run(runtime.retrieve(
            query="quantum computing",
            memory_types=[MemoryType.SEMANTIC],
            max_results=5,
            strategy=RetrievalStrategy.HYBRID,
        ))
        assert len(results) > 0

    def test_get_record(self, runtime):
        record_id = asyncio.run(runtime.store(
            content="Test record",
            memory_type=MemoryType.CONVERSATION,
        ))
        record = asyncio.run(runtime.get_record(record_id))
        assert record is not None
        assert record.content == "Test record"

    def test_get_record_not_found(self, runtime):
        record = asyncio.run(runtime.get_record("nonexistent-id"))
        assert record is None

    def test_update_importance(self, runtime):
        record_id = asyncio.run(runtime.store(
            content="Important fact",
            memory_type=MemoryType.SEMANTIC,
            importance=0.3,
        ))
        result = asyncio.run(runtime.update_importance(record_id, 0.9))
        assert result is True

        record = asyncio.run(runtime.get_record(record_id))
        assert record is not None
        assert record.importance == 0.9

    def test_update_importance_not_found(self, runtime):
        result = asyncio.run(runtime.update_importance("nonexistent", 0.9))
        assert result is False

    def test_forget(self, runtime):
        record_id = asyncio.run(runtime.store(
            content="To be forgotten",
            memory_type=MemoryType.CONVERSATION,
        ))
        result = asyncio.run(runtime.forget(record_id))
        assert result is True

        record = asyncio.run(runtime.get_record(record_id))
        assert record is None

    def test_forget_not_found(self, runtime):
        result = asyncio.run(runtime.forget("nonexistent"))
        assert result is False

    def test_consolidate(self, runtime):
        asyncio.run(runtime.store(
            content="Fact 1",
            memory_type=MemoryType.SEMANTIC,
        ))
        result = asyncio.run(runtime.consolidate())
        assert "stats" in result
        assert result["stats"]["total_records"] >= 1

    def test_health_check(self, runtime):
        health = runtime.health_check()
        assert health["runtime_id"] == "memory"
        assert health["state"] == "ready"
        assert "store" in health
        assert "index" in health
        assert "embedder" in health
        assert health["embedder"]["status"] == "healthy"

    def test_get_metadata(self, runtime):
        metadata = runtime.get_metadata()
        assert metadata.runtime_id == "memory"
        assert metadata.version == "1.0.0"
        cap_ids = [c.id for c in metadata.capabilities]
        assert "memory.store" in cap_ids
        assert "memory.retrieve" in cap_ids

    def test_store_record_with_embedding_preserved(self, runtime):
        record = MemoryRecord(
            content="Pre-embedded content",
            memory_type=MemoryType.SEMANTIC,
            embedding=[0.1] * 128,
        )
        record_id = asyncio.run(runtime.store_record(record))
        stored = asyncio.run(runtime.get_record(record_id))
        assert stored is not None
        assert stored.embedding is not None
        assert len(stored.embedding) == 128

    def test_store_record_generates_embedding(self, runtime):
        record = MemoryRecord(
            content="Content without embedding",
            memory_type=MemoryType.SEMANTIC,
        )
        record_id = asyncio.run(runtime.store_record(record))
        stored = asyncio.run(runtime.get_record(record_id))
        assert stored is not None
        assert stored.embedding is not None
        assert len(stored.embedding) == 128

    def test_retrieve_empty_query(self, runtime):
        results = asyncio.run(runtime.retrieve(
            query="",
            memory_types=[MemoryType.SEMANTIC],
            max_results=5,
        ))
        assert isinstance(results, list)

    def test_retrieve_filters_by_session(self, runtime):
        asyncio.run(runtime.store(
            content="Session A message",
            memory_type=MemoryType.CONVERSATION,
            session_id="session-a",
        ))
        asyncio.run(runtime.store(
            content="Session B message",
            memory_type=MemoryType.CONVERSATION,
            session_id="session-b",
        ))

        results = asyncio.run(runtime.retrieve(
            query="",
            memory_types=[MemoryType.CONVERSATION],
            max_results=10,
            session_id="session-a",
        ))
        assert len(results) == 1
        assert "Session A" in results[0].record.content

    def test_retrieve_filters_by_user(self, runtime):
        asyncio.run(runtime.store(
            content="User 1 data",
            memory_type=MemoryType.CONVERSATION,
            user_id="user-1",
        ))
        asyncio.run(runtime.store(
            content="User 2 data",
            memory_type=MemoryType.CONVERSATION,
            user_id="user-2",
        ))

        results = asyncio.run(runtime.retrieve(
            query="",
            memory_types=[MemoryType.CONVERSATION],
            max_results=10,
            user_id="user-1",
        ))
        assert len(results) == 1
        assert "User 1" in results[0].record.content


# ---------------------------------------------------------------------------
# Knowledge Cache Tests
# ---------------------------------------------------------------------------

class TestKnowledgeCacheExtended:
    def test_invalidate_pattern(self):
        cache = KnowledgeCache()
        cache.set("knowledge:python:1", {"data": "a"})
        cache.set("knowledge:python:2", {"data": "b"})
        cache.set("knowledge:java:1", {"data": "c"})
        removed = cache.invalidate_pattern(r"knowledge:python")
        assert removed == 2
        assert cache.get("knowledge:python:1") is None
        assert cache.get("knowledge:python:2") is None
        assert cache.get("knowledge:java:1") is not None

    def test_invalidate_prefix(self):
        cache = KnowledgeCache()
        cache.set("prefix:a", 1)
        cache.set("prefix:b", 2)
        cache.set("other:c", 3)
        removed = cache.invalidate_prefix("prefix:")
        assert removed == 2
        assert cache.get("prefix:a") is None
        assert cache.get("prefix:b") is None
        assert cache.get("other:c") is not None

    def test_cleanup_expired(self):
        cache = KnowledgeCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        removed = cache.cleanup_expired(ttl=0)
        assert removed == 2
        assert cache.size == 0

    def test_cleanup_expired_partial(self):
        cache = KnowledgeCache()
        cache.set("key1", "value1")
        removed = cache.cleanup_expired(ttl=9999)
        assert removed == 0
        assert cache.size == 1


# ---------------------------------------------------------------------------
# Memory Provider Tests
# ---------------------------------------------------------------------------

class TestMemoryProvider:
    def test_provider_with_memory_runtime(self):
        runtime = create_memory_runtime(
            store_type="memory",
            embedding_dim=64,
            embedding_backend="hash",
        )
        asyncio.run(runtime.initialize())

        asyncio.run(runtime.store(
            content="The sky is blue",
            memory_type=MemoryType.SEMANTIC,
            tags=["weather"],
        ))

        provider = MemoryProvider(memory_runtime=runtime)
        assert provider.is_available() is True
        assert provider.id == "memory"

        results = provider.search("sky is blue", max_results=5)
        assert len(results) > 0
        assert results[0].provider == "memory"
        assert results[0].type == ResultType.MEMORY

    def test_provider_without_memory_runtime(self):
        provider = MemoryProvider(memory_runtime=None)
        assert provider.is_available() is False
        assert provider.search("test") == []

    def test_provider_health(self):
        runtime = create_memory_runtime(
            store_type="memory",
            embedding_dim=64,
            embedding_backend="hash",
        )
        asyncio.run(runtime.initialize())
        provider = MemoryProvider(memory_runtime=runtime)
        health = provider.health()
        assert health["status"] == "healthy"


# ---------------------------------------------------------------------------
# Knowledge Runtime + Memory Integration Tests
# ---------------------------------------------------------------------------

class TestKnowledgeRuntimeMemoryIntegration:
    def test_search_includes_memory_results(self):
        memory_runtime = create_memory_runtime(
            store_type="memory",
            embedding_dim=64,
            embedding_backend="hash",
        )
        asyncio.run(memory_runtime.initialize())

        asyncio.run(memory_runtime.store(
            content="Zaram is a local-first AI operating system",
            memory_type=MemoryType.SEMANTIC,
            tags=["project"],
        ))

        kr = KnowledgeRuntime(memory_runtime=memory_runtime)

        response = kr.search("Zaram AI operating system", max_results=5)
        assert response.query == "Zaram AI operating system"
        assert "memory" in response.providers_consulted
        assert len(response.results) > 0
        memory_results = [r for r in response.results if r.provider == "memory"]
        assert len(memory_results) > 0

    def test_search_caches_memory_results(self):
        memory_runtime = create_memory_runtime(
            store_type="memory",
            embedding_dim=64,
            embedding_backend="hash",
        )
        asyncio.run(memory_runtime.initialize())

        asyncio.run(memory_runtime.store(
            content="Cached fact about AI",
            memory_type=MemoryType.SEMANTIC,
        ))

        kr = KnowledgeRuntime(memory_runtime=memory_runtime)

        response1 = kr.search("AI fact", max_results=5)
        response2 = kr.search("AI fact", max_results=5)
        assert response2.cached is True

    def test_search_invalidate_cache_pattern(self):
        memory_runtime = create_memory_runtime(
            store_type="memory",
            embedding_dim=64,
            embedding_backend="hash",
        )
        asyncio.run(memory_runtime.initialize())

        asyncio.run(memory_runtime.store(
            content="Test fact",
            memory_type=MemoryType.SEMANTIC,
        ))

        kr = KnowledgeRuntime(memory_runtime=memory_runtime)

        kr.search("Test fact", max_results=5)
        assert kr.get_cache_stats()["size"] > 0

        kr.invalidate_cache_pattern("knowledge:")
        assert kr.get_cache_stats()["size"] == 0

    def test_search_no_memory_runtime(self):
        kr = KnowledgeRuntime(memory_runtime=None)

        response = kr.search("test query", max_results=5)
        assert response.status.value in ("healthy", "degraded")
        assert "memory" not in response.providers_consulted


# ---------------------------------------------------------------------------
# Memory Graph Tests
# ---------------------------------------------------------------------------

class TestMemoryGraph:
    def test_add_and_get_neighbors(self):
        from runtimes.memory import MemoryGraph, EdgeType

        graph = MemoryGraph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_edge("a", "b", EdgeType.ASSOCIATIVE, weight=0.8)

        neighbors = graph.get_neighbors("a")
        assert len(neighbors) == 1
        assert neighbors[0][0] == "b"
        assert neighbors[0][1] == 0.8
        assert neighbors[0][2] == EdgeType.ASSOCIATIVE

    def test_remove_node(self):
        from runtimes.memory import MemoryGraph, EdgeType

        graph = MemoryGraph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_edge("a", "b", EdgeType.CAUSAL)

        assert graph.remove_node("a") is True
        assert graph.remove_node("nonexistent") is False
        assert len(graph._nodes) == 1

    def test_remove_edge(self):
        from runtimes.memory import MemoryGraph, EdgeType

        graph = MemoryGraph()
        graph.add_edge("a", "b", EdgeType.ASSOCIATIVE)
        graph.add_edge("a", "c", EdgeType.CAUSAL)

        assert graph.remove_edge("a", "b") is True
        assert graph.remove_edge("a", "b") is False
        assert len(graph._edges["a"]) == 1

    def test_find_path(self):
        from runtimes.memory import MemoryGraph, EdgeType

        graph = MemoryGraph()
        graph.add_edge("a", "b", EdgeType.ASSOCIATIVE)
        graph.add_edge("b", "c", EdgeType.ASSOCIATIVE)
        graph.add_edge("c", "d", EdgeType.ASSOCIATIVE)

        path = graph.find_path("a", "d")
        assert path is not None
        assert path == ["a", "b", "c", "d"]

    def test_find_path_no_path(self):
        from runtimes.memory import MemoryGraph, EdgeType

        graph = MemoryGraph()
        graph.add_edge("a", "b", EdgeType.ASSOCIATIVE)
        graph.add_edge("c", "d", EdgeType.ASSOCIATIVE)

        path = graph.find_path("a", "d")
        assert path is None

    def test_get_related(self):
        from runtimes.memory import MemoryGraph, EdgeType

        graph = MemoryGraph()
        graph.add_edge("a", "b", EdgeType.ASSOCIATIVE, weight=0.9)
        graph.add_edge("a", "c", EdgeType.SIMILARITY, weight=0.3)
        graph.add_edge("a", "d", EdgeType.CAUSAL, weight=0.5)

        related = graph.get_related("a", min_weight=0.4)
        assert len(related) == 2
        assert related[0][0] in ("b", "d")

    def test_strongly_connected_components(self):
        from runtimes.memory import MemoryGraph, EdgeType

        graph = MemoryGraph()
        graph.add_edge("a", "b", EdgeType.ASSOCIATIVE)
        graph.add_edge("b", "a", EdgeType.ASSOCIATIVE)
        graph.add_edge("c", "d", EdgeType.ASSOCIATIVE)

        components = graph.get_strongly_connected_components()
        assert len(components) >= 2

    def test_central_nodes(self):
        from runtimes.memory import MemoryGraph, EdgeType

        graph = MemoryGraph()
        graph.add_edge("a", "b", EdgeType.ASSOCIATIVE, weight=1.0)
        graph.add_edge("a", "c", EdgeType.ASSOCIATIVE, weight=1.0)
        graph.add_edge("b", "c", EdgeType.ASSOCIATIVE, weight=0.5)

        central = graph.get_central_nodes(top_n=2)
        assert len(central) == 2
        assert central[0][0] in ("a", "b", "c")

    def test_stats(self):
        from runtimes.memory import MemoryGraph, EdgeType

        graph = MemoryGraph()
        graph.add_edge("a", "b", EdgeType.ASSOCIATIVE, weight=0.8)
        graph.add_edge("a", "c", EdgeType.CAUSAL, weight=0.5)

        stats = graph.get_stats()
        assert stats["nodes"] == 3
        assert stats["edges"] == 2
        assert stats["edge_types"]["associative"] == 1
        assert stats["edge_types"]["causal"] == 1

    def test_serialization(self):
        from runtimes.memory import MemoryGraph, EdgeType

        graph = MemoryGraph()
        graph.add_edge("a", "b", EdgeType.ASSOCIATIVE, weight=0.8, metadata={"key": "value"})

        data = graph.to_dict()
        graph2 = MemoryGraph.from_dict(data)

        assert "a" in graph2._nodes
        assert "b" in graph2._nodes
        neighbors = graph2.get_neighbors("a")
        assert len(neighbors) == 1
        assert neighbors[0][1] == 0.8

    def test_clear(self):
        from runtimes.memory import MemoryGraph, EdgeType

        graph = MemoryGraph()
        graph.add_edge("a", "b", EdgeType.ASSOCIATIVE)
        graph.clear()
        assert len(graph._nodes) == 0
        assert len(graph._edges) == 0

    def test_health_check(self):
        from runtimes.memory import MemoryGraph

        graph = MemoryGraph()
        health = graph.health_check()
        assert health["status"] == "healthy"
        assert health["nodes"] == 0


# ---------------------------------------------------------------------------
# Memory Decay Engine Tests
# ---------------------------------------------------------------------------

class TestMemoryDecayEngine:
    def test_decay_factor(self):
        from runtimes.memory import MemoryDecayEngine, DecayConfig

        engine = MemoryDecayEngine(DecayConfig(half_life_days=90))
        assert engine.calculate_decay_factor(0) == 1.0
        assert engine.calculate_decay_factor(90) == 0.5
        assert engine.calculate_decay_factor(180) == 0.25

    def test_should_forget(self):
        from runtimes.memory import MemoryDecayEngine, DecayConfig

        engine = MemoryDecayEngine(DecayConfig(forget_threshold=0.1))
        assert engine.should_forget(0.05, 0, 0) is True
        assert engine.should_forget(0.5, 0, 0) is False
        assert engine.should_forget(0.2, 200, 0) is True

    def test_should_decay(self):
        from runtimes.memory import MemoryDecayEngine, DecayConfig

        engine = MemoryDecayEngine(DecayConfig(half_life_days=90, low_importance_threshold=0.3))
        assert engine.should_decay(0.2, 10) is True
        assert engine.should_decay(0.5, 100) is True
        assert engine.should_decay(0.5, 10) is False

    def test_calculate_importance_with_access(self):
        from runtimes.memory import MemoryDecayEngine, DecayConfig

        engine = MemoryDecayEngine(DecayConfig(access_boost=0.05))
        importance = engine.calculate_importance(
            base_importance=0.5,
            age_days=10,
            access_count=5,
            last_accessed=time.time() - 100,
        )
        assert 0.0 <= importance <= 1.0
        assert importance > 0.5

    def test_apply_decay_forgets_low_importance(self):
        import asyncio
        from runtimes.memory import MemoryDecayEngine, DecayConfig, create_memory_runtime, MemoryType

        runtime = create_memory_runtime(embedding_dim=64, embedding_backend="hash")
        asyncio.run(runtime.initialize())

        asyncio.run(runtime.store(
            content="Low importance memory",
            memory_type=MemoryType.CONVERSATION,
            importance=0.05,
        ))

        result = asyncio.run(runtime.apply_decay(decay_threshold=0.1))
        assert result["forgotten"] >= 1

    def test_apply_decay_boosts_recent_access(self):
        import asyncio
        from runtimes.memory import create_memory_runtime, MemoryType

        runtime = create_memory_runtime(embedding_dim=64, embedding_backend="hash")
        asyncio.run(runtime.initialize())

        asyncio.run(runtime.store(
            content="Important memory",
            memory_type=MemoryType.SEMANTIC,
            importance=0.5,
        ))

        result = asyncio.run(runtime.apply_decay(decay_threshold=0.1))
        assert "decayed" in result
        assert "boosted" in result

    def test_health_check(self):
        from runtimes.memory import MemoryDecayEngine

        engine = MemoryDecayEngine()
        health = engine.health_check()
        assert health["status"] == "healthy"
        assert "config" in health


# ---------------------------------------------------------------------------
# Memory API Tests (remember, reinforce)
# ---------------------------------------------------------------------------

class TestMemoryAPI:
    @pytest.fixture
    def runtime(self):
        rt = create_memory_runtime(
            store_type="memory",
            embedding_dim=64,
            embedding_backend="hash",
        )
        asyncio.run(rt.initialize())
        return rt

    def test_remember_stores_memory(self, runtime):
        record_id = asyncio.run(runtime.remember(
            content="Remember this important fact",
            memory_type=MemoryType.SEMANTIC,
            tags=["important"],
        ))
        assert record_id is not None

        record = asyncio.run(runtime.get_record(record_id))
        assert record is not None
        assert "important fact" in record.content.lower()
        assert record.importance >= 0.5

    def test_remember_auto_importance(self, runtime):
        record_id = asyncio.run(runtime.remember(
            content="This is an important reminder about key concepts",
            memory_type=MemoryType.SEMANTIC,
        ))
        record = asyncio.run(runtime.get_record(record_id))
        assert record is not None
        assert record.importance > 0.5

    def test_reinforce_increases_importance(self, runtime):
        record_id = asyncio.run(runtime.remember(
            content="Reinforce this memory",
            memory_type=MemoryType.SEMANTIC,
            importance=0.3,
        ))

        record_before = asyncio.run(runtime.get_record(record_id))
        original_importance = record_before.importance

        result = asyncio.run(runtime.reinforce(record_id, delta=0.2))
        assert result is True

        record = asyncio.run(runtime.get_record(record_id))
        assert record is not None
        assert record.importance == min(original_importance + 0.2, 1.0)

    def test_reinforce_caps_at_1(self, runtime):
        record_id = asyncio.run(runtime.remember(
            content="Max importance memory",
            memory_type=MemoryType.SEMANTIC,
            importance=0.9,
        ))

        result = asyncio.run(runtime.reinforce(record_id, delta=0.5))
        assert result is True

        record = asyncio.run(runtime.get_record(record_id))
        assert record is not None
        assert record.importance == 1.0

    def test_reinforce_not_found(self, runtime):
        result = asyncio.run(runtime.reinforce("nonexistent", delta=0.1))
        assert result is False

    def test_apply_decay_returns_stats(self, runtime):
        asyncio.run(runtime.store(
            content="Test memory for decay",
            memory_type=MemoryType.SEMANTIC,
            importance=0.5,
        ))

        result = asyncio.run(runtime.apply_decay())
        assert "decayed" in result
        assert "forgotten" in result
        assert "total_records" in result

    def test_graph_property(self, runtime):
        graph = runtime.graph
        assert graph is not None
        assert graph.health_check()["status"] == "healthy"

    def test_link_memories(self, runtime):
        id1 = asyncio.run(runtime.store(
            content="First memory",
            memory_type=MemoryType.SEMANTIC,
        ))
        id2 = asyncio.run(runtime.store(
            content="Second memory",
            memory_type=MemoryType.SEMANTIC,
        ))

        result = asyncio.run(runtime.link_memories(id1, id2, EdgeType.ASSOCIATIVE, 0.8))
        assert result is True

        related = asyncio.run(runtime.get_related_memories(id1))
        assert len(related) > 0

    def test_link_memories_not_found(self, runtime):
        result = asyncio.run(runtime.link_memories("nonexistent", "also_nonexistent"))
        assert result is False

    def test_auto_link_memories(self, runtime):
        from runtimes.memory import MemoryType

        asyncio.run(runtime.store(
            content="Python programming language features",
            memory_type=MemoryType.SEMANTIC,
        ))
        asyncio.run(runtime.store(
            content="Python programming language features",
            memory_type=MemoryType.SEMANTIC,
        ))

        record = list(runtime._store._records.values())[0]
        linked = asyncio.run(runtime.auto_link_memories(record.id))
        assert linked >= 0

    def test_find_memory_path(self, runtime):
        id1 = asyncio.run(runtime.store(
            content="Memory one",
            memory_type=MemoryType.SEMANTIC,
        ))
        id2 = asyncio.run(runtime.store(
            content="Memory two",
            memory_type=MemoryType.SEMANTIC,
        ))

        asyncio.run(runtime.link_memories(id1, id2, EdgeType.ASSOCIATIVE))
        path = asyncio.run(runtime.find_memory_path(id1, id2))
        assert path is not None
        assert id1 in path
        assert id2 in path

    def test_get_graph_stats(self, runtime):
        stats = asyncio.run(runtime.get_graph_stats())
        assert "nodes" in stats
        assert "edges" in stats

    def test_consolidate_groups_similar_memories(self, runtime):
        from runtimes.memory import MemoryType

        content = "Meeting with team about project planning and next steps"
        for i in range(5):
            asyncio.run(runtime.store(
                content=content,
                memory_type=MemoryType.EPISODIC,
                importance=0.5,
            ))

        result = asyncio.run(runtime.consolidate())
        assert "consolidated_memories" in result
        assert "groups_created" in result
        assert result["groups_created"] >= 1
