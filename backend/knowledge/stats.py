# backend/knowledge/stats.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeStatistics:
    """Knowledge runtime statistics exposed to the kernel."""

    runtime: Any = None

    def snapshot(self) -> dict[str, Any]:
        graph = getattr(self.runtime, "_graph", None)
        vector_store = getattr(self.runtime, "_vector_store", None)
        cache = getattr(self.runtime, "_cache", None)
        providers = getattr(self.runtime, "_providers", [])
        objects = getattr(self.runtime, "_objects", [])
        telemetry = getattr(self.runtime, "_telemetry", None)
        graph_stats = graph.stats() if graph else {}
        chunks = [c for obj in objects for c in getattr(obj, "chunks", [])]
        confidences = [c.confidence.confidence for c in chunks if c.confidence] + [obj.confidence.confidence for obj in objects if obj.confidence]
        freshness_scores = [c.freshness.compute_score() for c in chunks if c.freshness] if chunks else []
        if not freshness_scores and objects:
            freshness_scores = [obj.freshness.compute_score() for obj in objects if obj.freshness]
        duplicate_ratio = self._compute_duplicate_ratio(objects)
        authority_dist = self._compute_authority_distribution(objects)
        return {
            "graph": graph_stats,
            "entity_count": graph_stats.get("entity_count", 0),
            "relationship_count": graph_stats.get("relationship_count", 0),
            "knowledge_objects": len(objects),
            "chunk_count": len(chunks),
            "embedding_count": sum(1 for c in chunks if c.embedding),
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
            "avg_freshness": sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0.0,
            "duplicate_ratio": duplicate_ratio,
            "authority_distribution": authority_dist,
            "provider_count": len(providers),
            "cache_size": cache.size if cache else 0,
            "cache_hit_rate": cache.hit_rate if cache else 0.0,
            "index_size": vector_store.size() if vector_store else 0,
            "telemetry": telemetry.snapshot() if telemetry else {},
        }

    def _compute_duplicate_ratio(self, objects: list[Any]) -> float:
        seen_titles: set[str] = set()
        duplicate_titles: set[str] = set()
        for obj in objects:
            title = getattr(obj, "content", "")[:80].strip().lower()
            if title in seen_titles:
                duplicate_titles.add(title)
            seen_titles.add(title)
        total = len(seen_titles) + len(duplicate_titles)
        return len(duplicate_titles) / total if total > 0 else 0.0

    def _compute_authority_distribution(self, objects: list[Any]) -> dict[str, int]:
        buckets = {"high": 0, "medium": 0, "low": 0}
        for obj in objects:
            score = getattr(obj, "authority_score", 0.5)
            if score >= 0.8:
                buckets["high"] += 1
            elif score >= 0.5:
                buckets["medium"] += 1
            else:
                buckets["low"] += 1
        return buckets
