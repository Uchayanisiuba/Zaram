# backend/knowledge/runtime.py
from __future__ import annotations

import asyncio
import time
import threading
from dataclasses import dataclass, field
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.event_bus import ZaramEvent
from .cache import KnowledgeCache
from .protocol import (
    KnowledgeChunk, KnowledgeContext, KnowledgeFusion, KnowledgeObject,
    KnowledgeProvider, KnowledgeRequest, KnowledgeResult,
    RankedResult, SearchResponse, TelemetrySnapshot, VectorStore,
)
from .chunking import SemanticChunker, ChunkingConfig
from .embedding import EmbeddingRuntime, HashEmbeddingProvider
from .vector_store import LocalVectorStore
from .retrieval import SemanticRetrieval
from .ranking import RankingEngine
from .freshness import FreshnessEngine
from .citations import CitationEngine
from .confidence import ConfidenceEngine
from .fusion import KnowledgeFusionEngine
from .telemetry import KnowledgeTelemetry
from .graph import KnowledgeGraph
from .entity_extraction import EntityExtractor
from .relationships import RelationshipBuilder
from .temporal import TemporalEngine
from .knowledge_types import KnowledgeTypeClassifier
from .authority import AuthorityRegistry
from .incremental_embedding import IncrementalEmbeddingEngine
from .reindexing import BackgroundReindexer
from .continuous_learning import ContinuousLearningPipeline
from .garbage_collection import KnowledgeGarbageCollector
from .cross_document import CrossDocumentLinker
from .conflict_resolution import ConflictResolution
from .stats import KnowledgeStatistics


@dataclass
class ConnectorHealth:
    connector_id: str
    connector_type: str
    status: str
    latency_ms: float = 0.0
    last_sync: float = field(default_factory=time.time)
    requests: int = 0
    failures: int = 0
    cache_hits: int = 0


class KnowledgeRuntime:
    """Central knowledge runtime that orchestrates connectors, providers, and knowledge subsystems."""

    def __init__(
        self,
        cache_ttl: int = 900,
        max_workers: int = 8,
        internet_runtime: Any | None = None,
        memory_runtime: Any | None = None,
        event_bus: Any | None = None,
    ):
        self._connectors: list[Any] = []
        self._providers: list[Any] = []
        self._internet_runtime = internet_runtime
        self._memory_runtime = memory_runtime
        self._event_bus = event_bus
        self._state = "ready"
        self._start_time = time.time()
        self._cache = KnowledgeCache()
        self._default_cache_ttl = cache_ttl
        self._max_workers = max_workers
        self._lock = threading.Lock()
        self._health: dict[str, ConnectorHealth] = {}

        self._chunker = SemanticChunker()
        self._embedding = EmbeddingRuntime()
        self._embedding.register(HashEmbeddingProvider())
        self._vector_store = LocalVectorStore()
        self._retrieval = SemanticRetrieval(self._vector_store, self._embedding)
        self._ranking = RankingEngine()
        self._freshness = FreshnessEngine()
        self._citation = CitationEngine()
        self._confidence = ConfidenceEngine()
        self._fusion = KnowledgeFusionEngine()
        self._telemetry = KnowledgeTelemetry()

        self._graph = KnowledgeGraph()
        self._entity_extractor = EntityExtractor()
        self._relationship_builder = RelationshipBuilder()
        self._temporal = TemporalEngine()
        self._knowledge_types = KnowledgeTypeClassifier()
        self._authority = AuthorityRegistry()
        self._incremental_embedding = IncrementalEmbeddingEngine()
        self._incremental_embedding.embedding = self._embedding
        self._reindexer = BackgroundReindexer(self)
        self._continuous_learning = ContinuousLearningPipeline(runtime=self)
        self._gc = KnowledgeGarbageCollector(self)
        self._cross_document = CrossDocumentLinker()
        self._conflict_resolution = ConflictResolution()
        self._stats_provider = KnowledgeStatistics(runtime=self)
        self._objects: list[KnowledgeObject] = []

        self._stats = {
            "total_searches": 0,
            "cache_hits": 0,
            "internet_searches": 0,
            "memory_searches": 0,
            "total_latency_ms": 0.0,
        }

    # -------------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------------

    def register_connector(self, connector: Any) -> None:
        with self._lock:
            if any(c.get_connector_id() == connector.get_connector_id() for c in self._connectors):
                raise ValueError(f"Connector {connector.get_connector_id()} is already registered")
            self._connectors.append(connector)
            self._health[connector.get_connector_id()] = ConnectorHealth(
                connector_id=connector.get_connector_id(),
                connector_type=connector.get_connector_type().value,
                status="healthy" if connector.is_available() else "unavailable",
            )

    def register_provider(self, provider: Any) -> None:
        with self._lock:
            provider_id = provider.id
            if any(p.id == provider_id for p in self._providers):
                raise ValueError(f"Provider {provider_id} is already registered")
            self._providers.append(provider)
            self._health[provider_id] = ConnectorHealth(
                connector_id=provider_id,
                connector_type=getattr(provider, "result_type", None).value if hasattr(getattr(provider, "result_type", None), "value") else "provider",
                status="healthy" if provider.is_available() else "unavailable",
            )

    def register(self, provider: Any) -> None:
        self.register_provider(provider)

    def unregister_connector(self, connector_id: str) -> None:
        with self._lock:
            self._connectors = [c for c in self._connectors if c.get_connector_id() != connector_id]
            self._health.pop(connector_id, None)

    def unregister_provider(self, provider_id: str) -> None:
        with self._lock:
            self._providers = [p for p in self._providers if p.id != provider_id]
            self._health.pop(provider_id, None)

    def get_connector(self, connector_id: str) -> Any | None:
        with self._lock:
            for c in self._connectors:
                if c.get_connector_id() == connector_id:
                    return c
        return None

    def get_provider(self, provider_id: str) -> Any | None:
        with self._lock:
            for p in self._providers:
                if p.id == provider_id:
                    return p
        return None

    def list_connectors(self) -> list[dict[str, Any]]:
        with self._lock:
            result = []
            for c in self._connectors:
                h = self._health.get(c.get_connector_id())
                meta = c.metadata() if hasattr(c, "metadata") else {}
                health = c.health() if hasattr(c, "health") else {}
                if h:
                    health.update({
                        "latency_ms": h.latency_ms,
                        "last_sync": h.last_sync,
                        "requests": h.requests,
                        "failures": h.failures,
                        "cache_hits": h.cache_hits,
                    })
                result.append({**meta, **health})
            for p in self._providers:
                h = self._health.get(p.id)
                meta = p.metadata() if hasattr(p, "metadata") else {}
                health = p.health() if hasattr(p, "health") else {}
                if h:
                    health.update({
                        "latency_ms": h.latency_ms,
                        "last_sync": h.last_sync,
                        "requests": h.requests,
                        "failures": h.failures,
                        "cache_hits": h.cache_hits,
                    })
                result.append({**meta, **health})
            return result

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    def search(self, query: str, max_results: int = 6, connectors: list[str] | None = None,
               include_memory: bool = True, session_id: str | None = None, user_id: str | None = None) -> SearchResponse:
        query_key = query.strip().lower()
        cache_key = f"knowledge:{hash(query_key)}:{include_memory}:{session_id or 'none'}"

        cached = self._cache.get(cache_key, ttl=self._default_cache_ttl)
        if cached is not None:
            cached["cached"] = True
            self._stats["cache_hits"] += 1
            self._telemetry.record_cache_hit()
            return SearchResponse(**cached)

        self._stats["total_searches"] += 1
        start = time.time()
        self._telemetry.pipeline_stage = "searching"

        all_results: list[KnowledgeResult] = []
        consulted: list[str] = []
        connector_status: dict[str, str] = {}
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            internet_results = []
            memory_results = []

            if self._internet_runtime:
                try:
                    from runtimes.internet import InternetRuntime, SearchQuery, InternetConnectorType
                    internet_query = SearchQuery(
                        query=query,
                        max_results=max_results * 2,
                        connector_types=[InternetConnectorType(c) for c in connectors] if connectors else None,
                    )
                    internet_results = loop.run_until_complete(self._internet_runtime.search(internet_query))
                    self._stats["internet_searches"] += 1
                    for r in internet_results:
                        consulted.append(r.connector)
                        connector_status[r.connector] = "ok"
                except Exception as e:
                    connector_status["internet"] = "error"

            for r in internet_results:
                result = KnowledgeResult(
                    title=r.title, url=r.url, snippet=r.snippet, provider=r.connector,
                    confidence=r.score, type=__import__("knowledge.protocol", fromlist=["ResultType"]).ResultType.WEB,
                    metadata=r.metadata, retrieved_at=r.retrieved_at,
                )
                result = self._authority.apply_to_result(result)
                all_results.append(result)

            if include_memory and self._memory_runtime:
                try:
                    from runtimes.memory import MemoryRuntime, MemoryType, RetrievalStrategy
                    memory_results = loop.run_until_complete(self._memory_runtime.retrieve(
                        query=query,
                        memory_types=[MemoryType.CONVERSATION, MemoryType.EPISODIC, MemoryType.SEMANTIC],
                        max_results=max_results,
                        strategy=RetrievalStrategy.HYBRID,
                        session_id=session_id,
                        user_id=user_id,
                    ))
                    self._stats["memory_searches"] += 1
                    for r in memory_results:
                        consulted.append("memory")
                        connector_status["memory"] = "ok"
                except Exception as e:
                    connector_status["memory"] = "error"

            for r in memory_results:
                result = KnowledgeResult(
                    title=r.record.content[:80],
                    url=f"memory:{r.record.id}",
                    snippet=r.record.content[:300],
                    provider="memory",
                    confidence=r.score,
                    type=__import__("knowledge.protocol", fromlist=["ResultType"]).ResultType.MEMORY,
                    metadata={"memory_type": r.record.memory_type.value, "match_reason": r.match_reason},
                    retrieved_at=r.record.created_at,
                )
                result = self._authority.apply_to_result(result)
                all_results.append(result)
        finally:
            loop.close()

        graph_results = self._graph_search(query, max_results)
        all_results.extend(graph_results)
        for result in graph_results:
            consulted.append("graph")
            connector_status["graph"] = "ok"

        fusions = self._fusion.fuse(all_results)
        merged = self._merge_fusions(fusions)
        ranked = self._rank_merged(merged, max_results)

        latency_ms = (time.time() - start) * 1000
        self._telemetry.record_ranking(latency_ms)
        self._telemetry.pipeline_stage = "idle"

        for c in [r.result for r in ranked]:
            self._telemetry.record_confidence(c.confidence)

        with self._lock:
            for c in self._connectors + self._providers:
                cid = getattr(c, "get_connector_id", lambda: c.id)()
                h = self._health.get(cid)
                if h and cid in consulted:
                    h.latency_ms = latency_ms
                    h.last_sync = time.time()
                    h.requests += 1
                elif h:
                    h.requests += 1

        response = SearchResponse(
            query=query,
            results=[r.result for r in ranked],
            providers_consulted=list(set(consulted)),
            provider_status=connector_status,
            latency_ms=latency_ms,
            status=__import__("knowledge.protocol", fromlist=["ProviderStatus"]).ProviderStatus.HEALTHY if ranked else __import__("knowledge.protocol", fromlist=["ProviderStatus"]).ProviderStatus.DEGRADED,
        )

        cache_payload = {
            "query": response.query,
            "results": response.results,
            "providers_consulted": response.providers_consulted,
            "provider_status": response.provider_status,
            "latency_ms": response.latency_ms,
            "cached": False,
            "status": response.status.value,
        }
        self._cache.set(cache_key, cache_payload)
        self._stats["total_latency_ms"] += latency_ms
        return response

    def _graph_search(self, query: str, max_results: int) -> list[KnowledgeResult]:
        results: list[KnowledgeResult] = []
        entities = self._graph.neighborhood_search(query, max_results=max_results)
        for entity in entities:
            entity_type = entity.entity_type.value if hasattr(entity.entity_type, "value") else str(entity.entity_type)
            results.append(KnowledgeResult(
                title=entity.name,
                snippet=f"Entity ({entity_type}): {entity.name}. Aliases: {', '.join(entity.aliases)}",
                provider="graph",
                confidence=0.8,
                type=__import__("knowledge.protocol", fromlist=["ResultType"]).ResultType.VECTOR,
                knowledge_type=__import__("knowledge.protocol", fromlist=["KnowledgeType"]).KnowledgeType.CONCEPT,
                authority_score=0.6,
                metadata={"entity_id": entity.id, "entity_type": entity_type, "source": "graph"},
            ))
        return results

    def _merge_fusions(self, fusions: list[Any]) -> list[Any]:
        merged: list[Any] = []
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        for fusion in fusions:
            url_key = (fusion.primary.url or "").strip().lower()
            title_key = (fusion.primary.title or "").strip().lower()
            if url_key and url_key in seen_urls:
                continue
            if title_key and title_key in seen_titles:
                continue
            if url_key:
                seen_urls.add(url_key)
            if title_key:
                seen_titles.add(title_key)
            merged.append(fusion)
        return merged

    def _rank_merged(self, fusions: list[Any], max_results: int) -> list[RankedResult]:
        results = [f.primary for f in fusions]
        scores = [f.fused_confidence for f in fusions]
        return self._ranking.rank(results, scores)[:max_results]

    # -------------------------------------------------------------------------
    # Knowledge API
    # -------------------------------------------------------------------------

    def retrieve(self, request: KnowledgeRequest) -> KnowledgeContext:
        """Retrieve knowledge chunks for a request."""
        self._telemetry.pipeline_stage = "retrieving"
        start = time.time()
        result = self._retrieval.retrieve(request)
        latency = (time.time() - start) * 1000
        self._telemetry.record_retrieval(latency)
        ctx = self._retrieval.optimize_context_window(result.chunks)
        self._telemetry.pipeline_stage = "idle"
        return ctx

    def store(self, obj: KnowledgeObject) -> str:
        """Store a knowledge object: chunk, embed, index, extract entities, build relationships."""
        chunks = self._chunker.chunk(obj.content, citation=obj.citation, metadata=obj.metadata)
        for chunk in chunks:
            chunk.metadata["object_id"] = obj.id
            chunk.knowledge_type = self._knowledge_types.classify_chunk(chunk)
            extraction = self._entity_extractor.extract_from_chunk(chunk)
            chunk.entities = extraction.entities
        texts = [c.text for c in chunks]
        embeddings = self._embedding.embed(texts)
        for chunk, vec in zip(chunks, embeddings):
            chunk.embedding = vec
        self._vector_store.add(chunks)
        for chunk in chunks:
            if chunk.freshness:
                chunk.freshness.indexed = time.time()
        obj.chunks = chunks
        for chunk in chunks:
            rels = self._relationship_builder.build_from_chunk(chunk)
            chunk.relationships.extend(rels)
            for rel in rels:
                self._graph.add_relationship(rel)
        for chunk in chunks:
            for entity in chunk.entities:
                self._graph.add_entity(entity)
        extraction = self._entity_extractor.extract_from_object(obj)
        obj.entities = extraction.entities
        obj.relationships = [rel for chunk in chunks for rel in chunk.relationships]
        self._temporal.apply_to_object(obj)
        obj.knowledge_type = self._knowledge_types.classify_object(obj)
        obj.authority_score = self._authority.get_score(obj.citation.provider if obj.citation else "unknown")
        self._objects.append(obj)
        self._cross_document_links(obj)
        return obj.id

    def update(self, obj_id: str, content: str | None = None, metadata: dict[str, Any] | None = None) -> KnowledgeObject | None:
        """Update a stored knowledge object."""
        for chunk_id, chunk in list(self._vector_store._chunks.items()):
            if chunk.metadata.get("object_id") == obj_id:
                self._vector_store.delete(chunk_id)
        if content:
            obj = KnowledgeObject(id=obj_id, content=content, metadata=metadata or {})
            return self.store(obj)
        return None

    def invalidate(self, obj_id: str) -> None:
        """Invalidate all chunks associated with an object."""
        for chunk_id, chunk in list(self._vector_store._chunks.items()):
            if chunk.metadata.get("object_id") == obj_id:
                self._vector_store.delete(chunk_id)

    def embed(self, texts: list[str], provider_id: str | None = None) -> list[list[float]]:
        """Embed texts using the embedding runtime."""
        self._telemetry.pipeline_stage = "embedding"
        start = time.time()
        result = self._embedding.embed(texts, provider_id)
        latency = (time.time() - start) * 1000
        self._telemetry.record_embedding(latency)
        self._telemetry.pipeline_stage = "idle"
        return result

    def rank(self, results: list[KnowledgeResult], scores: list[float] | None = None) -> list[RankedResult]:
        """Rank knowledge results."""
        self._telemetry.pipeline_stage = "ranking"
        start = time.time()
        ranked = self._ranking.rank(results, scores)
        latency = (time.time() - start) * 1000
        self._telemetry.record_ranking(latency)
        self._telemetry.pipeline_stage = "idle"
        return ranked

    def search_semantic(self, query: str, max_results: int = 6) -> list[RankedResult]:
        """Semantic search using vector store."""
        request = KnowledgeRequest(query=query, max_results=max_results, strategy="top_k")
        ctx = self.retrieve(request)
        scored = [(c, 1.0) for c in ctx.chunks]
        ranked = sorted(scored, key=lambda x: x[1], reverse=True)[:max_results]
        results = [
            RankedResult(
                result=KnowledgeResult(title=c.text, snippet=c.text, provider="vector"),
                rank_score=score,
                similarity=score,
            )
            for c, score in ranked
        ]
        return results

    def search_graph(self, query: str, max_results: int = 6) -> list[KnowledgeResult]:
        """Search the knowledge graph by entity name."""
        entities = self._graph.neighborhood_search(query, max_results=max_results)
        results = []
        for entity in entities:
            results.append(KnowledgeResult(
                title=entity.name,
                snippet=f"Entity ({entity.entity_type.value}): {entity.name}",
                provider="graph",
                confidence=0.8,
                type=__import__("knowledge.protocol", fromlist=["ResultType"]).ResultType.VECTOR,
                metadata={"entity_id": entity.id, "entity_type": entity.entity_type.value},
            ))
        return results

    def traverse_graph(self, entity_id: str, relationship_type: Any = None, max_depth: int = 3) -> list[dict[str, Any]]:
        """Traverse the knowledge graph from an entity."""
        entities = self._graph.traverse(entity_id, relationship_type, max_depth)
        return [{"id": e.id, "name": e.name, "type": e.entity_type.value} for e in entities]

    def get_entity(self, name: str) -> dict[str, Any] | None:
        """Find an entity by name."""
        entity = self._graph.find_entity_by_name(name)
        if not entity:
            return None
        return {
            "id": entity.id,
            "name": entity.name,
            "type": entity.entity_type.value,
            "aliases": entity.aliases,
            "canonical": entity.canonical,
        }

    def build_graph(self) -> dict[str, Any]:
        """Rebuild the knowledge graph from all stored objects."""
        for obj in self._objects:
            extraction = self._entity_extractor.extract_from_object(obj)
            for entity in extraction.entities:
                self._graph.add_entity(entity)
            relationships = self._relationship_builder.build_from_object(obj)
            for rel in relationships:
                self._graph.add_relationship(rel)
        return self._graph.stats()

    def detect_conflicts(self, results: list[KnowledgeResult]) -> list[dict[str, Any]]:
        """Detect conflicts between knowledge results."""
        fusions = self._fusion.fuse(results)
        conflicts: list[dict[str, Any]] = []
        for fusion in fusions:
            if fusion.duplicates:
                detected = self._conflict_resolution.detect_conflicts(fusion)
                conflicts.extend(detected)
        return conflicts

    def resolve_conflicts(self, results: list[KnowledgeResult], strategy: str = "keep_both") -> list[KnowledgeResult]:
        """Resolve conflicts between knowledge results."""
        fusions = self._fusion.fuse(results)
        resolved: list[KnowledgeResult] = []
        for fusion in fusions:
            if fusion.duplicates:
                resolved_fusion = self._conflict_resolution.resolve(fusion, strategy=strategy)
                resolved.append(resolved_fusion.primary)
                resolved.extend(resolved_fusion.duplicates)
            else:
                resolved.append(fusion.primary)
        return resolved

    def run_garbage_collection(self) -> dict[str, Any]:
        """Run knowledge garbage collection."""
        result = self._gc.collect()
        return {
            "removed_count": result.removed_count,
            "expired_entries": result.expired_entries,
            "broken_citations": result.broken_citations,
            "orphaned_entities": result.orphaned_entities,
            "duplicate_chunks": result.duplicate_chunks,
            "unused_graph_nodes": result.unused_graph_nodes,
        }

    def start_background_worker(self) -> None:
        """Start background reindexing and continuous learning."""
        self._reindexer.start()
        self._continuous_learning.start()

    def stop_background_worker(self) -> None:
        """Stop background reindexing and continuous learning."""
        self._reindexer.stop()
        self._continuous_learning.stop()

    def enqueue_reindex(self, task_type: str, items: list[Any]) -> dict[str, Any]:
        """Enqueue a background reindex task."""
        task = self._reindexer.enqueue(task_type, items)
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "total": task.total,
            "status": task.status,
        }

    def get_knowledge_statistics(self) -> dict[str, Any]:
        """Expose knowledge runtime statistics."""
        return self._stats_provider.snapshot()

    def _cross_document_links(self, obj: KnowledgeObject) -> None:
        if len(self._objects) < 2:
            return
        candidates = self._objects[-10:]
        relationships = self._cross_document.link_objects(candidates + [obj])
        for rel in relationships:
            self._graph.add_relationship(rel)

    # -------------------------------------------------------------------------
    # Runtime Protocol (Event Bus integration)
    # -------------------------------------------------------------------------

    def get_runtime_id(self) -> str:
        return "knowledge"

    def get_version(self) -> str:
        return "1.0.0"

    def get_metadata(self) -> dict[str, Any]:
        return {
            "runtime_id": self.get_runtime_id(),
            "version": "1.0.0",
            "priority": "critical",
            "capabilities": [
                "knowledge.search",
                "knowledge.cache",
                "knowledge.index",
                "knowledge.telemetry",
            ],
            "dependencies": ["event_bus"],
        }

    def get_state(self) -> str:
        return self._state

    def health_check(self) -> dict[str, Any]:
        return {
            "runtime_id": self.get_runtime_id(),
            "state": self._state,
            "uptime_seconds": time.time() - self._start_time,
            "connectors": self.list_connectors(),
            "cache": self.get_cache_stats(),
            "stats": self.get_stats(),
        }

    async def initialize(self) -> None:
        self._state = "ready"
        if self._event_bus:
            self._event_bus.subscribe("knowledge.search", self._handle_search_event)
            self._event_bus.publish(ZaramEvent(
                source_runtime="knowledge",
                event_type="runtime.ready",
                data={"runtime_id": self.get_runtime_id()},
            ))
        print("[KnowledgeRuntime] Initialized")

    async def shutdown(self) -> None:
        self._state = "stopped"
        await self.close()

    def _handle_search_event(self, event: Any) -> None:
        data = event.data if hasattr(event, "data") else event
        query = data.get("query", "")
        if query:
            self.search(query, max_results=data.get("max_results", 6))

    # -------------------------------------------------------------------------
    # Health & Diagnostics
    # -------------------------------------------------------------------------

    def get_health(self) -> list[dict[str, Any]]:
        return self.list_connectors()

    def get_cache_stats(self) -> dict[str, Any]:
        return {
            "size": self._cache.size,
            "max_size": self._cache._max_size,
            "cache_hit_rate": self._cache.hit_rate,
        }

    def invalidate_cache(self, key: str) -> None:
        self._cache.invalidate(key)

    def invalidate_cache_pattern(self, pattern: str) -> int:
        return self._cache.invalidate_pattern(pattern)

    def invalidate_cache_prefix(self, prefix: str) -> int:
        return self._cache.invalidate_prefix(prefix)

    def clear_cache(self) -> None:
        self._cache.clear()

    def get_stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "avg_latency_ms": self._stats["total_latency_ms"] / max(self._stats["total_searches"], 1),
        }

    def get_telemetry(self) -> dict[str, Any]:
        snap = self._telemetry.snapshot()
        snap.update({
            "index_size": self._vector_store.size(),
            "provider_count": len(self._providers),
        })
        return snap

    async def close(self) -> None:
        self.stop_background_worker()
        if self._internet_runtime:
            await self._internet_runtime.shutdown()
        if self._memory_runtime:
            await self._memory_runtime.shutdown()
