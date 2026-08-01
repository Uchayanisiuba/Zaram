from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence
import time


@dataclass(frozen=True)
class SourceQuality:
    """Quality metrics for a knowledge source."""

    source_id: str
    reliability: float = 0.5
    recency_weight: float = 0.5
    authority_score: float = 0.5
    last_success: float = 0.0
    failure_count: int = 0
    success_count: int = 0

    @property
    def availability(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5
        return self.success_count / total

    @property
    def health_score(self) -> float:
        recency_factor = min(1.0, (time.time() - self.last_success) / 3600.0) if self.last_success else 1.0
        return (
            0.4 * self.reliability
            + 0.3 * self.authority_score
            + 0.2 * self.availability
            + 0.1 * (1.0 - recency_factor)
        )


@dataclass(frozen=True)
class ConfidenceResult:
    """Aggregated confidence evaluation for a set of results."""

    overall: float
    source_confidence: float
    recency_confidence: float
    coverage_confidence: float
    signal_strength: float
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": round(self.overall, 4),
            "source_confidence": round(self.source_confidence, 4),
            "recency_confidence": round(self.recency_confidence, 4),
            "coverage_confidence": round(self.coverage_confidence, 4),
            "signal_strength": round(self.signal_strength, 4),
            "details": dict(self.details),
        }


class ConfidenceEngine:
    """Evaluates confidence in knowledge discovery results.

    Confidence is computed from three signals:
    1. **Source confidence** — weighted average of source health scores.
    2. **Recency confidence** — how recent the results are (time-sensitive queries).
    3. **Coverage confidence** — whether enough results were returned.
    """

    def __init__(self, default_ttl: float = 900.0):
        self._sources: dict[str, SourceQuality] = {}
        self._default_ttl = default_ttl

    def register_source(self, source_id: str, quality: SourceQuality) -> None:
        """Register or update a source's quality metrics."""
        self._sources[source_id] = quality

    def update_source_success(self, source_id: str, latency_ms: float = 0.0) -> None:
        """Record a successful response from a source."""
        existing = self._sources.get(source_id)
        if existing:
            self._sources[source_id] = SourceQuality(
                source_id=source_id,
                reliability=existing.reliability,
                recency_weight=existing.recency_weight,
                authority_score=existing.authority_score,
                last_success=time.time(),
                failure_count=existing.failure_count,
                success_count=existing.success_count + 1,
            )
        else:
            self._sources[source_id] = SourceQuality(
                source_id=source_id,
                last_success=time.time(),
                success_count=1,
            )

    def update_source_failure(self, source_id: str) -> None:
        """Record a failed response from a source."""
        existing = self._sources.get(source_id)
        if existing:
            self._sources[source_id] = SourceQuality(
                source_id=source_id,
                reliability=existing.reliability,
                recency_weight=existing.recency_weight,
                authority_score=existing.authority_score,
                last_success=existing.last_success,
                failure_count=existing.failure_count + 1,
                success_count=existing.success_count,
            )

    def evaluate(
        self,
        results: Sequence[Any],
        sources_consulted: Sequence[str] | None = None,
        max_results: int = 10,
        query_age_seconds: float = 0.0,
    ) -> ConfidenceResult:
        """Evaluate confidence for a set of discovery results.

        Args:
            results: The results returned by discovery.
            sources_consulted: IDs of sources that were queried.
            max_results: The maximum number of results expected.
            query_age_seconds: How old the query is (for staleness).

        Returns:
            A ConfidenceResult with overall and per-dimension scores.
        """
        result_count = len(results)
        sources = list(sources_consulted or [])

        # --- Source confidence ---
        if not sources:
            source_confidence = 0.0
        else:
            scores = []
            for sid in sources:
                quality = self._sources.get(sid)
                if quality:
                    scores.append(quality.health_score)
                else:
                    scores.append(0.5)
            source_confidence = sum(scores) / len(scores) if scores else 0.0

        # --- Recency confidence ---
        if query_age_seconds > 0:
            staleness = min(1.0, query_age_seconds / self._default_ttl)
            recency_confidence = 1.0 - staleness
        else:
            recency_confidence = 1.0

        # --- Coverage confidence ---
        if max_results <= 0:
            coverage_confidence = 0.0
        else:
            coverage_confidence = min(1.0, result_count / max_results)

        # --- Signal strength ---
        signal_strength = min(1.0, result_count / max(max_results, 1))

        # --- Overall confidence ---
        overall = (
            0.4 * source_confidence
            + 0.3 * recency_confidence
            + 0.3 * coverage_confidence
        )
        overall = min(1.0, overall)

        return ConfidenceResult(
            overall=overall,
            source_confidence=source_confidence,
            recency_confidence=recency_confidence,
            coverage_confidence=coverage_confidence,
            signal_strength=signal_strength,
            details={
                "result_count": result_count,
                "sources_consulted": sources,
                "max_results": max_results,
                "query_age_seconds": query_age_seconds,
            },
        )

    def get_source_quality(self, source_id: str) -> SourceQuality | None:
        return self._sources.get(source_id)

    def list_sources(self) -> dict[str, SourceQuality]:
        return dict(self._sources)
