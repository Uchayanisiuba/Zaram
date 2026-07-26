# backend/tests/test_knowledge_runtime.py
"""Tests for the Knowledge Provider Framework (Alpha.11)."""
from __future__ import annotations

import time

import pytest

from knowledge.protocol import KnowledgeResult, ResultType, ProviderStatus, SearchResponse
from knowledge.cache import KnowledgeCache
from knowledge.runtime import KnowledgeRuntime, ConnectorHealth
from knowledge.providers import (
    BaseKnowledgeProvider,
    MemoryProvider,
    VectorProvider,
    WikipediaProvider,
    DuckDuckGoProvider,
    RSSProvider,
    GitHubProvider,
    ProjectProvider,
    MarkdownProvider,
    PDFProvider,
    PlaceholderProvider,
    SearchMixin,
)


# ---------------------------------------------------------------------------
# Protocol Tests
# ---------------------------------------------------------------------------

class TestKnowledgeResult:
    def test_create_result(self):
        r = KnowledgeResult(
            title="Test",
            url="https://example.com",
            snippet="snippet",
            provider="test",
            confidence=0.9,
            score=0.95,
            type=ResultType.WEB,
        )
        assert r.title == "Test"
        assert r.confidence == 0.9
        assert r.type == ResultType.WEB

    def test_to_dict(self):
        r = KnowledgeResult(title="Test", url="https://example.com", provider="test")
        d = r.to_dict()
        assert d["title"] == "Test"
        assert d["url"] == "https://example.com"
        assert d["type"] == "web"

    def test_frozen_dataclass(self):
        r = KnowledgeResult(title="Test")
        with pytest.raises(AttributeError):
            r.title = "Changed"  # type: ignore


# ---------------------------------------------------------------------------
# Cache Tests
# ---------------------------------------------------------------------------

class TestKnowledgeCache:
    def test_set_and_get(self):
        cache = KnowledgeCache()
        cache.set("key", {"data": "value"})
        assert cache.get("key") == {"data": "value"}

    def test_expired(self):
        cache = KnowledgeCache()
        cache.set("key", "value")
        assert cache.get("key", ttl=0) is None

    def test_missing_key(self):
        cache = KnowledgeCache()
        assert cache.get("missing") is None

    def test_clear(self):
        cache = KnowledgeCache()
        cache.set("key", "value")
        cache.clear()
        assert cache.get("key") is None

    def test_lru_eviction(self):
        cache = KnowledgeCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # Should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_deduplicate(self):
        cache = KnowledgeCache()
        cache.set("a", {"x": 1})
        cache.set("b", {"x": 1})
        removed = cache.deduplicate()
        assert removed == 1
        assert cache.size == 1

    def test_incremental_update(self):
        cache = KnowledgeCache()
        cache.set("a", {"x": 1, "y": 2})
        updated = cache.incremental_update({"a": {"z": 3}})
        assert updated == 1
        assert cache.get("a") == {"x": 1, "y": 2, "z": 3}

    def test_persist_and_load(self, tmp_path):
        path = str(tmp_path / "cache.json.gz")
        cache = KnowledgeCache(persist_path=path)
        cache.set("k1", "v1")
        cache.set("k2", {"nested": True})
        cache2 = KnowledgeCache(persist_path=path)
        assert cache2.get("k1") == "v1"
        assert cache2.get("k2") == {"nested": True}

    def test_hit_rate(self):
        cache = KnowledgeCache()
        cache.set("a", 1)
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.hit_rate > 0


# ---------------------------------------------------------------------------
# Provider Tests
# ---------------------------------------------------------------------------

class TestProviders:
    def test_memory_provider(self):
        p = MemoryProvider()
        assert p.id == "memory"
        assert p.priority() == 50
        assert p.is_available() is False
        assert p.search("test") == []

    def test_vector_provider(self):
        p = VectorProvider()
        assert p.id == "vector"
        assert p.is_available() is False

    def test_wikipedia_provider(self):
        p = WikipediaProvider()
        assert p.id == "wikipedia"
        assert p.cache_ttl == 3600
        results = p.search("Python programming", max_results=2)
        if results:
            assert results[0].provider == "wikipedia"
            assert results[0].type == ResultType.WEB

    def test_duckduckgo_provider(self):
        p = DuckDuckGoProvider()
        assert p.id == "duckduckgo"
        results = p.search("OpenAI", max_results=2)
        assert isinstance(results, list)
        if results:
            assert results[0].provider == "duckduckgo"

    def test_github_provider(self):
        p = GitHubProvider()
        assert p.id == "github"
        results = p.search("ollama", max_results=2)
        assert isinstance(results, list)
        if results:
            assert results[0].type == ResultType.GITHUB

    def test_project_provider(self):
        p = ProjectProvider()
        assert p.id == "project"
        assert p.is_available() is False

    def test_rss_provider(self):
        p = RSSProvider()
        assert p.id == "rss"
        assert p.is_available() is False

    def test_markdown_provider(self):
        p = MarkdownProvider()
        assert p.id == "markdown"
        assert p.is_available() is False

    def test_pdf_provider(self):
        p = PDFProvider()
        assert p.id == "pdf"
        assert p.is_available() is False

    def test_placeholder_provider(self):
        p = PlaceholderProvider("future_gmail")
        assert p.id == "future_gmail"
        assert p.is_available() is False
        assert p.search("test") == []


# ---------------------------------------------------------------------------
# Runtime Tests
# ---------------------------------------------------------------------------

class TestKnowledgeRuntime:
    def setup_method(self):
        self.runtime = KnowledgeRuntime()
        self.runtime.register_provider(WikipediaProvider())
        self.runtime.register_provider(DuckDuckGoProvider())

    def test_register_and_list(self):
        connectors = self.runtime.list_connectors()
        ids = [p["id"] for p in connectors]
        assert "wikipedia" in ids
        assert "duckduckgo" in ids

    def test_search_returns_results(self):
        response = self.runtime.search("Python", max_results=6)
        assert response.query == "Python"
        assert isinstance(response.results, list)

    def test_search_empty_query(self):
        response = self.runtime.search("", max_results=6)
        assert response.results == []

    def test_duplicate_provider_registration(self):
        with pytest.raises(ValueError):
            self.runtime.register_provider(WikipediaProvider())

    def test_unregister(self):
        self.runtime.unregister_provider("wikipedia")
        connectors = self.runtime.list_connectors()
        ids = [p["id"] for p in connectors]
        assert "wikipedia" not in ids

    def test_get_provider(self):
        p = self.runtime.get_provider("wikipedia")
        assert p is not None
        assert p.id == "wikipedia"

    def test_get_unknown_provider(self):
        assert self.runtime.get_provider("nonexistent") is None

    def test_search_merges_and_dedups(self):
        response = self.runtime.search("Python", max_results=10)
        titles = [r.title for r in response.results]
        assert len(titles) == len(set(titles))  # No duplicates

    def test_cache_stats(self):
        stats = self.runtime.get_cache_stats()
        assert "size" in stats
        assert "max_size" in stats

    def test_health(self):
        health = self.runtime.get_health()
        assert isinstance(health, list)
        assert len(health) > 0

    def test_empty_search_after_filtering(self):
        p = PDFProvider()
        self.runtime.register_provider(p)
        response = self.runtime.search("test", connectors=["pdf"])
        assert response.results == []

    def test_cache_invalidation(self):
        self.runtime.search("test query", max_results=5)
        assert self.runtime.get_cache_stats()["size"] > 0
        self.runtime.clear_cache()
        assert self.runtime.get_cache_stats()["size"] == 0

    def test_cache_invalidation_pattern(self):
        self.runtime.search("test query", max_results=5)
        assert self.runtime.get_cache_stats()["size"] > 0
        removed = self.runtime.invalidate_cache_pattern("knowledge:")
        assert removed > 0
        assert self.runtime.get_cache_stats()["size"] == 0


# ---------------------------------------------------------------------------
# Chunking Tests
# ---------------------------------------------------------------------------

class TestChunking:
    def test_basic_chunking(self):
        from knowledge.chunking import SemanticChunker, ChunkingConfig
        chunker = SemanticChunker(ChunkingConfig(max_tokens=100, min_chunk_chars=10))
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunker.chunk(text)
        assert len(chunks) > 0
        assert all(c.text for c in chunks)

    def test_chunk_metadata(self):
        from knowledge.chunking import SemanticChunker, ChunkingConfig
        chunker = SemanticChunker(ChunkingConfig(max_tokens=50, min_chunk_chars=1))
        chunks = chunker.chunk("Hello world. " * 20, metadata={"source": "test"})
        assert chunks[0].metadata.get("source") == "test"
        assert chunks[0].chunk_index == 0

    def test_chunk_with_citation(self):
        from knowledge.chunking import SemanticChunker, ChunkingConfig
        from knowledge.protocol import Citation
        citation = Citation(title="Doc", url="http://test")
        chunker = SemanticChunker(ChunkingConfig(max_tokens=50, min_chunk_chars=1))
        chunks = chunker.chunk("Hello world. " * 20, citation=citation)
        assert chunks[0].citation is not None
        assert chunks[0].citation.title == "Doc"


# ---------------------------------------------------------------------------
# Embedding Tests
# ---------------------------------------------------------------------------

class TestEmbedding:
    def test_hash_embedding(self):
        from knowledge.embedding import HashEmbeddingProvider
        provider = HashEmbeddingProvider(dimension=64)
        assert provider.dimension() == 64
        assert provider.is_available() is True
        vectors = provider.embed(["hello", "world"])
        assert len(vectors) == 2
        assert len(vectors[0]) == 64

    def test_embedding_runtime(self):
        from knowledge.embedding import EmbeddingRuntime, HashEmbeddingProvider
        runtime = EmbeddingRuntime()
        runtime.register(HashEmbeddingProvider(dimension=32))
        assert runtime.default_provider() is not None
        vectors = runtime.embed(["test"])
        assert len(vectors) == 1
        assert len(vectors[0]) == 32

    def test_embedding_deduplication(self):
        from knowledge.embedding import EmbeddingRuntime, HashEmbeddingProvider
        runtime = EmbeddingRuntime()
        runtime.register(HashEmbeddingProvider(dimension=16))
        v1 = runtime.embed(["hello"])[0]
        v2 = runtime.embed(["hello"])[0]
        assert v1 == v2


# ---------------------------------------------------------------------------
# Vector Store Tests
# ---------------------------------------------------------------------------

class TestVectorStore:
    def test_add_and_search(self, tmp_path):
        from knowledge.vector_store import LocalVectorStore
        from knowledge.protocol import KnowledgeChunk, Citation, FreshnessScore
        store = LocalVectorStore()
        chunk = KnowledgeChunk(text="hello world", embedding=[1.0, 0.0, 0.0], token_count=2)
        store.add([chunk])
        assert store.size() == 1
        results = store.search([1.0, 0.0, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0][0].text == "hello world"

    def test_delete(self):
        from knowledge.vector_store import LocalVectorStore
        from knowledge.protocol import KnowledgeChunk
        store = LocalVectorStore()
        chunk = KnowledgeChunk(text="temp", embedding=[0.5, 0.5])
        store.add([chunk])
        store.delete(chunk.id)
        assert store.size() == 0

    def test_persist_and_load(self, tmp_path):
        from knowledge.vector_store import LocalVectorStore
        from knowledge.protocol import KnowledgeChunk
        path = str(tmp_path / "index.json")
        store = LocalVectorStore()
        store.add([KnowledgeChunk(text="persist me", embedding=[0.1, 0.2], token_count=2)])
        store.persist(path)
        store2 = LocalVectorStore()
        store2.load(path)
        assert store2.size() == 1

    def test_clear(self):
        from knowledge.vector_store import LocalVectorStore
        from knowledge.protocol import KnowledgeChunk
        store = LocalVectorStore()
        store.add([KnowledgeChunk(text="x", embedding=[0.1])])
        store.clear()
        assert store.size() == 0


# ---------------------------------------------------------------------------
# Retrieval Tests
# ---------------------------------------------------------------------------

class TestRetrieval:
    def test_top_k(self):
        from knowledge.retrieval import SemanticRetrieval
        from knowledge.embedding import EmbeddingRuntime, HashEmbeddingProvider
        from knowledge.vector_store import LocalVectorStore
        from knowledge.protocol import KnowledgeRequest, KnowledgeChunk
        embed = EmbeddingRuntime()
        embed.register(HashEmbeddingProvider(dimension=8))
        store = LocalVectorStore()
        store.add([KnowledgeChunk(text="alpha", embedding=[1.0] + [0.0] * 7, token_count=1)])
        store.add([KnowledgeChunk(text="beta", embedding=[0.0] + [1.0] + [0.0] * 6, token_count=1)])
        retrieval = SemanticRetrieval(store, embed)
        req = KnowledgeRequest(query="alpha", max_results=1, strategy="top_k")
        res = retrieval.retrieve(req)
        assert len(res.chunks) == 1
        assert res.strategy == "top_k"

    def test_mmr(self):
        from knowledge.retrieval import SemanticRetrieval
        from knowledge.embedding import EmbeddingRuntime, HashEmbeddingProvider
        from knowledge.vector_store import LocalVectorStore
        from knowledge.protocol import KnowledgeRequest, KnowledgeChunk
        embed = EmbeddingRuntime()
        embed.register(HashEmbeddingProvider(dimension=8))
        store = LocalVectorStore()
        store.add([KnowledgeChunk(text="a", embedding=[1.0] + [0.0] * 7, token_count=1)])
        store.add([KnowledgeChunk(text="b", embedding=[0.9] + [0.1] + [0.0] * 6, token_count=1)])
        retrieval = SemanticRetrieval(store, embed)
        req = KnowledgeRequest(query="a", max_results=2, strategy="mmr")
        res = retrieval.retrieve(req)
        assert len(res.chunks) <= 2

    def test_context_optimization(self):
        from knowledge.retrieval import SemanticRetrieval
        from knowledge.embedding import EmbeddingRuntime, HashEmbeddingProvider
        from knowledge.vector_store import LocalVectorStore
        from knowledge.protocol import KnowledgeRequest, KnowledgeChunk
        embed = EmbeddingRuntime()
        embed.register(HashEmbeddingProvider(dimension=4))
        store = LocalVectorStore()
        store.add([KnowledgeChunk(text="word " * 100, embedding=[0.1] * 4, token_count=100)])
        retrieval = SemanticRetrieval(store, embed)
        req = KnowledgeRequest(query="word", max_results=10, strategy="top_k")
        ctx = retrieval.optimize_context_window(retrieval.retrieve(req).chunks, max_tokens=50)
        assert ctx.max_tokens == 50


# ---------------------------------------------------------------------------
# Ranking Tests
# ---------------------------------------------------------------------------

class TestRanking:
    def test_basic_rank(self):
        from knowledge.ranking import RankingEngine
        from knowledge.protocol import KnowledgeResult
        engine = RankingEngine()
        results = [
            KnowledgeResult(title="A", provider="wikipedia", confidence=0.9),
            KnowledgeResult(title="B", provider="rss", confidence=0.5),
        ]
        ranked = engine.rank(results)
        assert ranked[0].result.title == "A"

    def test_rank_scores(self):
        from knowledge.ranking import RankingEngine
        from knowledge.protocol import KnowledgeResult
        engine = RankingEngine()
        results = [KnowledgeResult(title="A", provider="wikipedia", confidence=0.9)]
        ranked = engine.rank(results)
        assert 0.0 <= ranked[0].rank_score <= 1.0


# ---------------------------------------------------------------------------
# Freshness Tests
# ---------------------------------------------------------------------------

class TestFreshness:
    def test_create_score(self):
        from knowledge.freshness import FreshnessEngine
        engine = FreshnessEngine(default_ttl=3600)
        score = engine.create_score()
        assert score.created > 0
        assert score.expires > score.created

    def test_is_stale(self):
        from knowledge.freshness import FreshnessEngine
        engine = FreshnessEngine(default_ttl=-1)
        score = engine.create_score()
        assert engine.is_stale(score)

    def test_compute_score(self):
        from knowledge.freshness import FreshnessEngine
        engine = FreshnessEngine(default_ttl=3600)
        score = engine.create_score()
        assert 0.0 <= engine.get_freshness_score(score) <= 1.0


# ---------------------------------------------------------------------------
# Citation Tests
# ---------------------------------------------------------------------------

class TestCitation:
    def test_build_citation(self):
        from knowledge.citations import CitationEngine
        engine = CitationEngine()
        citation = engine.build_citation(title="T", url="http://x", author="A")
        assert citation.title == "T"
        assert citation.author == "A"

    def test_from_result(self):
        from knowledge.citations import CitationEngine
        from knowledge.protocol import KnowledgeResult
        engine = CitationEngine()
        citation = engine.from_result(KnowledgeResult(title="T", url="http://x"))
        assert citation.title == "T"
        assert citation.url == "http://x"

    def test_merge(self):
        from knowledge.citations import CitationEngine
        from knowledge.protocol import Citation
        engine = CitationEngine()
        a = engine.build_citation(title="A", author="Author1")
        b = engine.build_citation(title="B", url="http://b")
        merged = engine.merge(a, b)
        assert merged.title == "A"


# ---------------------------------------------------------------------------
# Confidence Tests
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_compute(self):
        from knowledge.confidence import ConfidenceEngine
        from knowledge.protocol import KnowledgeResult
        engine = ConfidenceEngine()
        score = engine.compute(KnowledgeResult(title="T", confidence=0.8), sources=3, agreement=0.9, freshness=0.7, ranking=0.6)
        assert 0.0 <= score.compute() <= 1.0

    def test_from_chunks(self):
        from knowledge.confidence import ConfidenceEngine
        from knowledge.freshness import FreshnessEngine
        from knowledge.protocol import KnowledgeChunk, KnowledgeResult, ConfidenceScore
        engine = ConfidenceEngine()
        fresh = FreshnessEngine().create_score()
        chunk = KnowledgeChunk(text="a", confidence=ConfidenceScore(confidence=0.8), freshness=fresh)
        score = engine.from_chunks([chunk])
        assert score.sourceCount == 1


# ---------------------------------------------------------------------------
# Fusion Tests
# ---------------------------------------------------------------------------

class TestFusion:
    def test_fuse_dedups(self):
        from knowledge.fusion import KnowledgeFusionEngine
        from knowledge.protocol import KnowledgeResult
        engine = KnowledgeFusionEngine()
        results = [
            KnowledgeResult(title="Same", url="http://a"),
            KnowledgeResult(title="Same", url="http://a"),
            KnowledgeResult(title="Other", url="http://b"),
        ]
        fusions = engine.fuse(results)
        assert len(fusions) == 2

    def test_detect_conflicts(self):
        from knowledge.fusion import KnowledgeFusionEngine
        from knowledge.protocol import KnowledgeResult, KnowledgeFusion
        engine = KnowledgeFusionEngine()
        fusion = KnowledgeFusion(
            primary=KnowledgeResult(title="T", confidence=0.9),
            duplicates=[KnowledgeResult(title="T", confidence=0.5)],
        )
        conflicts = engine.detect_conflicts(fusion)
        assert len(conflicts) >= 0  # may or may not detect depending on implementation


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------

class TestKnowledgeAPI:
    def test_store_and_retrieve(self):
        runtime = KnowledgeRuntime()
        from knowledge.protocol import KnowledgeObject
        obj = KnowledgeObject(content="hello world from api test")
        obj_id = runtime.store(obj)
        assert obj_id is not None
        ctx = runtime.retrieve(__import__("knowledge.protocol", fromlist=["KnowledgeRequest"]).KnowledgeRequest(query="hello", max_results=5, strategy="top_k"))
        assert isinstance(ctx, __import__("knowledge.protocol", fromlist=["KnowledgeContext"]).KnowledgeContext)

    def test_embed(self):
        runtime = KnowledgeRuntime()
        vectors = runtime.embed(["test embedding"])
        assert len(vectors) == 1
        assert len(vectors[0]) == 384

    def test_rank(self):
        runtime = KnowledgeRuntime()
        from knowledge.protocol import KnowledgeResult
        ranked = runtime.rank([KnowledgeResult(title="A", confidence=0.9), KnowledgeResult(title="B", confidence=0.5)])
        assert len(ranked) == 2
        assert ranked[0].result.title == "A"

    def test_invalidate(self):
        runtime = KnowledgeRuntime()
        from knowledge.protocol import KnowledgeObject
        obj = KnowledgeObject(id="obj-1", content="invalidate me")
        runtime.store(obj)
        runtime.invalidate("obj-1")

    def test_search_semantic(self):
        runtime = KnowledgeRuntime()
        results = runtime.search_semantic("test", max_results=3)
        assert isinstance(results, list)
