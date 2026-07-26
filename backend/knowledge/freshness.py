# backend/knowledge/freshness.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FreshnessEngine:
    """Manages freshness scoring for knowledge objects."""

    default_ttl: float = 7 * 24 * 3600

    def create_score(self, created: float | None = None, ttl: float | None = None) -> Any:
        from .protocol import FreshnessScore
        now = created or time.time()
        return FreshnessScore(
            created=now,
            indexed=now,
            lastUpdated=now,
            expires=now + (ttl or self.default_ttl),
        )

    def update(self, score: Any, now: float | None = None) -> Any:
        from .protocol import FreshnessScore
        now = now or time.time()
        return FreshnessScore(
            created=score.created,
            indexed=score.indexed,
            lastUpdated=now,
            expires=score.expires,
        )

    def is_stale(self, score: Any, now: float | None = None) -> bool:
        now = now or time.time()
        return score.expires > 0 and now >= score.expires

    def get_freshness_score(self, score: Any, now: float | None = None) -> float:
        return score.compute_score(now)
