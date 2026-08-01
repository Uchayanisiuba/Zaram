# backend/runtime/discovery/extractor.py
from __future__ import annotations

from typing import Any

from .contracts import DiscoveryMetadata, DiscoveryResult, FreshnessLevel


def normalize_result(raw: dict[str, Any], provider_id: str) -> DiscoveryResult:
    metadata = DiscoveryMetadata(
        provider=provider_id,
        url=raw.get("url", ""),
        title=raw.get("title", ""),
        author=raw.get("author"),
        published=raw.get("published"),
        language=raw.get("language", "en"),
        confidence=float(raw.get("confidence", 0.8)),
        freshness=raw.get("freshness", FreshnessLevel.UNKNOWN),
        license=raw.get("license"),
        last_modified=raw.get("last_modified"),
        raw_metadata={k: v for k, v in raw.items() if k not in {"url", "title", "author", "published", "language", "confidence", "freshness", "license", "last_modified", "content", "summary", "sources"}},
    )
    return DiscoveryResult(
        content=raw.get("content", ""),
        summary=raw.get("summary", ""),
        metadata=metadata,
        sources=[],
        confidence=metadata.confidence,
        freshness=metadata.freshness,
        provider=provider_id,
        retrieval_time=raw.get("retrieval_time", 0.0),
    )


def merge_results(results: list[DiscoveryResult]) -> list[DiscoveryResult]:
    seen: set[str] = set()
    merged: list[DiscoveryResult] = []
    for r in results:
        key = (r.metadata.url or r.metadata.title or "").strip().lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(r)
    return merged
