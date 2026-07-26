from __future__ import annotations

import asyncio
import time
from typing import Any

from .contracts import (
    MemoryRecord,
    MemoryQuery,
    MemoryResult,
    MemoryRuntime,
    MemoryStatus,
    MemoryType,
    RetrievalStrategy,
    RuntimeMetadata,
    Capability,
    CapabilityLocality,
)
from .store import InMemoryMemoryStore, create_memory_store, MemoryStore
from .index import HybridMemoryIndex, create_memory_index, MemoryIndex
from .retrieval import HybridMemoryRetriever, MemoryRetriever
from .ranking import MemoryRankerImpl, MemoryRanker
from .history import ConversationHistory
from .episodic import EpisodicMemory
from .semantic import SemanticMemory
from .embeddings import EmbeddingService, create_embedding_service
from .graph import MemoryGraph, EdgeType, create_memory_graph
from .decay import MemoryDecayEngine, DecayConfig, DecayResult, create_decay_engine


class MemoryRuntimeImpl(MemoryRuntime):
    """Main Memory Runtime - single source of truth for all memory operations."""

    def __init__(
        self,
        store_type: str = "memory",
        index_type: str = "hybrid",
        persist_path: str | None = None,
        embedding_dim: int = 384,
        embedding_backend: str = "hash",
    ):
        self._runtime_id = "memory"
        self._state = MemoryStatus.INITIALIZING
        self._start_time = time.time()
        self._initialized = False

        self._store: MemoryStore = create_memory_store(
            store_type, persist_path=persist_path
        )
        self._index: MemoryIndex = create_memory_index(
            index_type, embedding_dim=embedding_dim
        )
        self._retriever: MemoryRetriever = HybridMemoryRetriever(self._store, self._index)
        self._ranker: MemoryRanker = MemoryRankerImpl()
        self._history: ConversationHistory = ConversationHistory(self)
        self._episodic: EpisodicMemory = EpisodicMemory(self)
        self._semantic: SemanticMemory = SemanticMemory(self)
        self._embedder: EmbeddingService = create_embedding_service(
            backend=embedding_backend, dim=embedding_dim
        )
        self._graph: MemoryGraph = create_memory_graph()
        self._decay_engine: MemoryDecayEngine = create_decay_engine()

        self._stats = {
            "stores": 0,
            "retrievals": 0,
            "errors": 0,
            "total_latency_ms": 0.0,
        }

    async def initialize(self) -> None:
        self._state = MemoryStatus.INITIALIZING
        await self._store.health_check()
        await self._index.health_check()
        embed_health = self._embedder.health_check()
        if embed_health.get("status") != "healthy":
            print(f"[MemoryRuntime] Embedding service degraded: {embed_health}")
        self._state = MemoryStatus.READY
        self._initialized = True
        print(f"[MemoryRuntime] Initialized with store={type(self._store).__name__}, index={type(self._index).__name__}, embedder={self._embedder._backend}")

    async def shutdown(self) -> None:
        self._state = MemoryStatus.STOPPING
        self._state = MemoryStatus.STOPPED

    def get_runtime_id(self) -> str:
        return self._runtime_id

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id=self._runtime_id,
            version="1.0.0",
            priority="high",
            capabilities=[
                Capability(id="memory.store", runtime_id=self._runtime_id, category="memory"),
                Capability(id="memory.retrieve", runtime_id=self._runtime_id, category="memory"),
                Capability(id="memory.remember", runtime_id=self._runtime_id, category="memory"),
                Capability(id="memory.reinforce", runtime_id=self._runtime_id, category="memory"),
                Capability(id="memory.forget", runtime_id=self._runtime_id, category="memory"),
                Capability(id="memory.consolidate", runtime_id=self._runtime_id, category="memory"),
                Capability(id="memory.decay", runtime_id=self._runtime_id, category="memory"),
                Capability(id="memory.conversation.history", runtime_id=self._runtime_id, category="memory"),
                Capability(id="memory.episodic", runtime_id=self._runtime_id, category="memory"),
                Capability(id="memory.semantic", runtime_id=self._runtime_id, category="memory"),
                Capability(id="memory.graph", runtime_id=self._runtime_id, category="memory"),
                Capability(id="memory.importance", runtime_id=self._runtime_id, category="memory"),
            ],
        )

    def get_state(self) -> MemoryStatus:
        return self._state

    def health_check(self) -> dict[str, Any]:
        store_health = asyncio.run(self._store.health_check()) if hasattr(self._store, 'health_check') else {"status": "unknown"}
        index_health = asyncio.run(self._index.health_check()) if hasattr(self._index, 'health_check') else {"status": "unknown"}
        retriever_health = asyncio.run(self._retriever.health_check()) if hasattr(self._retriever, 'health_check') else {"status": "unknown"}
        ranker_health = asyncio.run(self._ranker.health_check()) if hasattr(self._ranker, 'health_check') else {"status": "unknown"}
        embedder_health = self._embedder.health_check()
        graph_health = self._graph.health_check()

        return {
            "runtime_id": self._runtime_id,
            "state": self._state.value,
            "uptime_seconds": time.time() - self._start_time,
            "store": store_health,
            "index": index_health,
            "retriever": retriever_health,
            "ranker": ranker_health,
            "embedder": embedder_health,
            "graph": graph_health,
            "stats": self._stats,
        }

    async def store(
        self,
        content: str,
        memory_type: MemoryType,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        importance: float = 0.5,
    ) -> str:
        start = time.time()
        try:
            embedding = self._embedder.embed(content) if content else None
            record = MemoryRecord(
                content=content,
                memory_type=memory_type,
                metadata=metadata or {},
                embedding=embedding,
                session_id=session_id,
                user_id=user_id,
                tags=tags or [],
                importance=importance,
            )
            record_id = await self._store.put(record)
            await self._index.add(record)
            self._stats["stores"] += 1
            return record_id
        except Exception as e:
            self._stats["errors"] += 1
            print(f"[MemoryRuntime] Store failed: {e}")
            raise
        finally:
            self._stats["total_latency_ms"] += (time.time() - start) * 1000

    async def retrieve(
        self,
        query: str,
        memory_types: list[MemoryType] | None = None,
        max_results: int = 10,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
        session_id: str | None = None,
        user_id: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[MemoryResult]:
        start = time.time()
        try:
            query_embedding = self._embedder.embed(query) if query else None
            query_metadata = {}
            if query_embedding:
                query_metadata["query_embedding"] = query_embedding

            memory_query = MemoryQuery(
                query=query,
                memory_types=memory_types or [MemoryType.CONVERSATION, MemoryType.EPISODIC, MemoryType.SEMANTIC],
                max_results=max_results,
                strategy=strategy,
                filters=filters or {},
                session_id=session_id,
                user_id=user_id,
                metadata=query_metadata,
            )
            results = await self._retriever.retrieve(memory_query)
            results = await self._ranker.rank(results, memory_query)
            self._stats["retrievals"] += 1
            return results
        except Exception as e:
            self._stats["errors"] += 1
            print(f"[MemoryRuntime] Retrieve failed: {e}")
            raise
        finally:
            self._stats["total_latency_ms"] += (time.time() - start) * 1000

    async def get_conversation_history(self, session_id: str, limit: int = 50) -> list[MemoryRecord]:
        return await self._history.get_full_history(session_id, limit)

    async def get_episodic_memories(self, user_id: str, limit: int = 20) -> list[MemoryRecord]:
        results = await self._episodic.get_recent_events(user_id, limit)
        return [r.record for r in results]

    async def get_semantic_memories(self, query: str, limit: int = 10) -> list[MemoryResult]:
        return await self._semantic.query_knowledge(query, limit=limit)

    async def update_importance(self, record_id: str, importance: float) -> bool:
        record = await self._store.get(record_id)
        if not record:
            return False
        updated = MemoryRecord(
            id=record.id,
            content=record.content,
            memory_type=record.memory_type,
            metadata=record.metadata,
            embedding=record.embedding,
            created_at=record.created_at,
            updated_at=time.time(),
            access_count=record.access_count,
            last_accessed=record.last_accessed,
            tags=record.tags,
            session_id=record.session_id,
            user_id=record.user_id,
            importance=importance,
            source=record.source,
        )
        await self._store.put(updated)
        await self._index.add(updated)
        return True

    async def forget(self, record_id: str) -> bool:
        await self._index.remove(record_id)
        return await self._store.delete(record_id)

    async def consolidate(self) -> dict[str, Any]:
        """Consolidate memories by grouping similar episodic memories into semantic memories.

        - Groups episodic memories by similarity (embedding cosine similarity)
        - Creates semantic memory summaries for groups with 3+ similar memories
        - Links consolidated memories in the graph
        """
        stats = await self._store.stats()
        episodic_records = [
            r for r in self._store._records.values()
            if r.memory_type == MemoryType.EPISODIC and r.embedding
        ]

        consolidated = 0
        groups_created = 0
        now = time.time()

        used: set[str] = set()
        for i, record_a in enumerate(episodic_records):
            if record_a.id in used:
                continue
            group = [record_a]
            used.add(record_a.id)

            for record_b in episodic_records[i + 1:]:
                if record_b.id in used:
                    continue
                if not record_b.embedding:
                    continue
                similarity = self._cosine_similarity(record_a.embedding, record_b.embedding)
                if similarity > 0.75:
                    group.append(record_b)
                    used.add(record_b.id)

            if len(group) >= 3:
                summary_content = "; ".join(r.content for r in group[:5])
                summary_record = MemoryRecord(
                    content=f"Consolidated memory: {summary_content}",
                    memory_type=MemoryType.SEMANTIC,
                    metadata={
                        "consolidated": True,
                        "source_count": len(group),
                        "source_ids": [r.id for r in group],
                    },
                    tags=["consolidated", "semantic"],
                    importance=0.7,
                    source="consolidation",
                )
                summary_id = await self.store_record(summary_record)

                for r in group:
                    self._graph.add_edge(
                        r.id,
                        summary_id,
                        EdgeType.ASSOCIATIVE,
                        weight=0.8,
                        metadata={"relation": "consolidated_into"},
                    )
                groups_created += 1
                consolidated += len(group)

        return {
            "stats": stats.__dict__,
            "consolidated_memories": consolidated,
            "groups_created": groups_created,
            "episodic_reviewed": len(episodic_records),
            "message": "Consolidation complete",
        }

    async def get_record(self, record_id: str) -> MemoryRecord | None:
        return await self._store.get(record_id)

    async def store_record(self, record: MemoryRecord) -> str:
        embedding = record.embedding
        if embedding is None and record.content:
            embedding = self._embedder.embed(record.content)
        stored_record = MemoryRecord(
            id=record.id,
            content=record.content,
            memory_type=record.memory_type,
            metadata=record.metadata,
            embedding=embedding,
            created_at=record.created_at,
            updated_at=record.updated_at,
            access_count=record.access_count,
            last_accessed=record.last_accessed,
            tags=record.tags,
            session_id=record.session_id,
            user_id=record.user_id,
            importance=record.importance,
            source=record.source,
        )
        record_id = await self._store.put(stored_record)
        await self._index.add(stored_record)
        self._stats["stores"] += 1
        return record_id

    async def remember(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        importance: float = 0.5,
    ) -> str:
        """Store a memory with automatic importance scoring."""
        auto_importance = self._calculate_importance(content, memory_type, tags or [])
        return await self.store(
            content=content,
            memory_type=memory_type,
            metadata=metadata,
            session_id=session_id,
            user_id=user_id,
            tags=tags,
            importance=max(importance, auto_importance),
        )

    async def reinforce(self, record_id: str, delta: float = 0.1) -> bool:
        """Increase the importance of a memory by delta."""
        record = await self._store.get(record_id)
        if not record:
            return False
        new_importance = min(record.importance + delta, 1.0)
        return await self.update_importance(record_id, new_importance)

    async def apply_decay(self, decay_threshold: float = 0.1) -> dict[str, Any]:
        """Apply decay rules to memories.

        Memories with importance below the threshold are forgotten.
        Memories with importance above the threshold but below 0.3 are decayed
        (importance reduced based on age).
        Recently accessed memories get a boost.
        """
        config = DecayConfig(forget_threshold=decay_threshold)
        result = await self._decay_engine.apply_decay(
            self._store, graph=self._graph, config=config
        )
        self._stats["decayed"] = result.decayed
        self._stats["forgotten"] = result.forgotten
        return result.to_dict()

    def _calculate_importance(
        self,
        content: str,
        memory_type: MemoryType,
        tags: list[str],
    ) -> float:
        """Calculate automatic importance score based on content characteristics."""
        score = 0.5

        if memory_type == MemoryType.EPISODIC:
            score += 0.1
        elif memory_type == MemoryType.SEMANTIC:
            score += 0.05
        elif memory_type == MemoryType.WORKING:
            score -= 0.1

        if len(content) > 200:
            score += 0.05
        if len(content) > 500:
            score += 0.05

        if "important" in content.lower() or "remember" in content.lower():
            score += 0.1

        if len(tags) > 0:
            score += min(len(tags) * 0.02, 0.1)

        return min(max(score, 0.0), 1.0)

    @property
    def history(self) -> ConversationHistory:
        return self._history

    @property
    def episodic(self) -> EpisodicMemory:
        return self._episodic

    @property
    def semantic(self) -> SemanticMemory:
        return self._semantic

    @property
    def graph(self) -> MemoryGraph:
        return self._graph

    async def link_memories(
        self,
        source_id: str,
        target_id: str,
        edge_type: EdgeType = EdgeType.ASSOCIATIVE,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Create a relationship between two memories."""
        source = await self._store.get(source_id)
        target = await self._store.get(target_id)
        if not source or not target:
            return False
        self._graph.add_edge(source_id, target_id, edge_type, weight, metadata)
        return True

    async def get_related_memories(
        self,
        record_id: str,
        edge_types: list[EdgeType] | None = None,
        max_results: int = 10,
    ) -> list[MemoryResult]:
        """Get memories related to a given memory via the graph."""
        related = self._graph.get_related(record_id, edge_types, max_weight=0.0, max_results=max_results)
        results = []
        for rid, weight, edge_type in related:
            record = await self._store.get(rid)
            if record:
                results.append(MemoryResult(
                    record=record,
                    score=weight,
                    match_reason=f"graph:{edge_type.value}",
                    rank=0,
                ))
        return results

    async def find_memory_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> list[str] | None:
        """Find a path between two memories in the graph."""
        return self._graph.find_path(source_id, target_id, max_depth)

    async def get_graph_stats(self) -> dict[str, Any]:
        """Get memory graph statistics."""
        return self._graph.get_stats()

    async def auto_link_memories(self, record_id: str, max_links: int = 5) -> int:
        """Automatically link a memory to similar memories based on embeddings."""
        record = await self._store.get(record_id)
        if not record or not record.embedding:
            return 0

        linked = 0
        for other_id, other_record in self._store._records.items():
            if other_id == record_id or not other_record.embedding:
                continue
            similarity = self._cosine_similarity(record.embedding, other_record.embedding)
            if similarity > 0.7:
                self._graph.add_edge(
                    record_id,
                    other_id,
                    EdgeType.SIMILARITY,
                    weight=similarity,
                )
                linked += 1
                if linked >= max_links:
                    break
        return linked

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        import math
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


def create_memory_runtime(**kwargs) -> MemoryRuntimeImpl:
    return MemoryRuntimeImpl(**kwargs)