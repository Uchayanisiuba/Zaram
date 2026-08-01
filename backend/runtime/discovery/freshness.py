# backend/runtime/discovery/freshness.py
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .contracts import FreshnessLevel


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d %b %Y",
        "%b %d, %Y",
    ):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def estimate_freshness(metadata: Any, retrieved_at: float) -> FreshnessLevel:
    now = datetime.now(tz=UTC)

    published_str = getattr(metadata, "published", None)
    modified_str = getattr(metadata, "last_modified", None)

    published_dt = _parse_date(published_str)
    modified_dt = _parse_date(modified_str)

    candidate_dt = modified_dt or published_dt
    if candidate_dt is None:
        return FreshnessLevel.UNKNOWN

    delta = (now - candidate_dt).total_seconds()
    if delta < 60:
        return FreshnessLevel.LIVE
    if delta < 86400:
        return FreshnessLevel.RECENT
    return FreshnessLevel.STATIC
