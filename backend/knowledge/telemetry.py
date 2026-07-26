# backend/knowledge/telemetry.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeTelemetry:
    """Telemetry for the knowledge pipeline."""

    embedding_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    ranking_latency_ms: float = 0.0
    cache_hits: int = 0
    index_size: int = 0
    duplicate_ratio: float = 0.0
    avg_confidence: float = 0.0
    pipeline_stage: str = "idle"
    _samples_confidence: list[float] = field(default_factory=list, repr=False)

    def record_embedding(self, latency_ms: float) -> None:
        self.embedding_latency_ms = latency_ms

    def record_retrieval(self, latency_ms: float) -> None:
        self.retrieval_latency_ms = latency_ms

    def record_ranking(self, latency_ms: float) -> None:
        self.ranking_latency_ms = latency_ms

    def record_cache_hit(self) -> None:
        self.cache_hits += 1

    def record_confidence(self, confidence: float) -> None:
        self._samples_confidence.append(confidence)
        if len(self._samples_confidence) > 1000:
            self._samples_confidence = self._samples_confidence[-1000:]
        self.avg_confidence = sum(self._samples_confidence) / len(self._samples_confidence)

    def snapshot(self) -> dict[str, Any]:
        return {
            "embedding_latency_ms": self.embedding_latency_ms,
            "retrieval_latency_ms": self.retrieval_latency_ms,
            "ranking_latency_ms": self.ranking_latency_ms,
            "cache_hits": self.cache_hits,
            "index_size": self.index_size,
            "duplicate_ratio": self.duplicate_ratio,
            "avg_confidence": self.avg_confidence,
            "pipeline_stage": self.pipeline_stage,
        }
