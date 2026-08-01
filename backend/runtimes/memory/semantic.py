from __future__ import annotations

from typing import Any
import time

from .contracts import MemoryRecord, MemoryResult, MemoryType, RetrievalStrategy


class SemanticMemory:
    """Manages semantic memories - facts, concepts, and general knowledge."""

    def __init__(self, memory_runtime: "MemoryRuntime"):
        self._runtime = memory_runtime

    async def learn_fact(
        self,
        fact: str,
        category: str,
        confidence: float = 0.8,
        source: str = "user",
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        record = MemoryRecord(
            content=fact,
            memory_type=MemoryType.SEMANTIC,
            metadata={
                "category": category,
                "confidence": confidence,
                "source": source,
                **(metadata or {}),
            },
            user_id=user_id,
            tags=["semantic", category],
            importance=confidence,
            source=source,
        )
        return await self._runtime.store_record(record)

    async def query_knowledge(
        self,
        query: str,
        user_id: str | None = None,
        category: str | None = None,
        min_confidence: float = 0.5,
        limit: int = 10,
    ) -> list[MemoryResult]:
        filters = {"category": category} if category else {}
        results = await self._runtime.retrieve(
            query=query,
            memory_types=[MemoryType.SEMANTIC],
            max_results=limit * 2,
            user_id=user_id,
            filters=filters,
            strategy=RetrievalStrategy.SEMANTIC,
        )
        filtered = [r for r in results if r.record.metadata.get("confidence", 0) >= min_confidence]
        return filtered[:limit]

    async def get_facts_by_category(
        self,
        category: str,
        user_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryResult]:
        results = await self._runtime.retrieve(
            query="",
            memory_types=[MemoryType.SEMANTIC],
            max_results=limit,
            user_id=user_id,
            filters={"category": category},
        )
        return sorted(results, key=lambda r: r.record.metadata.get("confidence", 0), reverse=True)

    async def update_confidence(self, fact_id: str, new_confidence: float) -> bool:
        record = await self._runtime.get_record(fact_id)
        if not record or record.memory_type != MemoryType.SEMANTIC:
            return False
        record.metadata["confidence"] = new_confidence
        record.importance = new_confidence
        # This would need an update method in the runtime
        return True

    async def extract_facts_from_text(
        self,
        text: str,
        user_id: str | None = None,
        source: str = "extraction",
    ) -> list[str]:
        facts = []
        sentences = text.split(". ")
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20 and len(sent) < 500:
                fact_id = await self.learn_fact(
                    fact=sent,
                    category="extracted",
                    confidence=0.6,
                    source=source,
                    user_id=user_id,
                )
                facts.append(fact_id)
        return facts

    async def health_check(self) -> dict[str, Any]:
        return {"status": "healthy", "runtime_id": self._runtime.get_runtime_id()}