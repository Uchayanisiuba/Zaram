# backend/knowledge/confidence.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConfidenceEngine:
    """Computes confidence scores for knowledge results."""

    def compute(self, result: Any, sources: int = 1, agreement: float = 1.0, freshness: float = 1.0, ranking: float = 0.0) -> Any:
        from .protocol import ConfidenceScore
        return ConfidenceScore(
            confidence=result.confidence,
            sourceCount=sources,
            agreementScore=agreement,
            freshnessScore=freshness,
            rankingScore=ranking,
        )

    def from_chunks(self, chunks: list[Any], now: float | None = None) -> Any:
        import time
        now = now or time.time()
        count = len(chunks)
        if count == 0:
            from .protocol import ConfidenceScore
            return ConfidenceScore()
        avg_conf = sum(c.confidence.confidence for c in chunks if c.confidence) / count
        avg_fresh = sum(c.freshness.compute_score(now) if c.freshness else 0.5 for c in chunks) / count
        return self.compute(
            result=__import__("types").SimpleNamespace(confidence=avg_conf),
            sources=count,
            agreement=1.0,
            freshness=avg_fresh,
            ranking=sum(c.confidence.rankingScore if c.confidence else 0 for c in chunks) / count,
        )
