# backend/knowledge/conflict_resolution.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from .protocol import KnowledgeFusion, KnowledgeResult


@dataclass
class ConflictResolution:
    """Detect and resolve conflicting information."""

    def detect_conflicts(self, fusion: KnowledgeFusion) -> list[dict[str, Any]]:
        conflicts: list[dict[str, Any]] = []
        candidates = [fusion.primary] + fusion.duplicates
        fields = ["confidence", "authority_score", "published", "title"]
        for field_name in fields:
            values = []
            for result in candidates:
                val = getattr(result, field_name, None)
                values.append((result.provider, val))
            unique_vals = list({v for _, v in values if v is not None})
            if len(unique_vals) > 1:
                conflicts.append({
                    "field": field_name,
                    "values": unique_vals,
                    "sources": [p for p, v in values if v in unique_vals],
                })
        return conflicts

    def resolve(self, fusion: KnowledgeFusion, strategy: str = "keep_both") -> KnowledgeFusion:
        if strategy == "keep_both":
            fusion.resolved = True
            fusion.resolution = "kept_both"
        elif strategy == "highest_confidence":
            candidates = [fusion.primary] + fusion.duplicates
            best = max(candidates, key=lambda r: r.confidence)
            fusion.primary = best
            fusion.duplicates = [r for r in candidates if r != best]
            fusion.resolved = True
            fusion.resolution = f"selected_{best.provider}"
        elif strategy == "highest_authority":
            candidates = [fusion.primary] + fusion.duplicates
            best = max(candidates, key=lambda r: r.authority_score)
            fusion.primary = best
            fusion.duplicates = [r for r in candidates if r != best]
            fusion.resolved = True
            fusion.resolution = f"selected_{best.provider}"
        return fusion

    def merge_conflicting(self, fusion: KnowledgeFusion) -> KnowledgeResult:
        all_results = [fusion.primary] + fusion.duplicates
        avg_confidence = sum(r.confidence for r in all_results) / len(all_results)
        avg_authority = sum(r.authority_score for r in all_results) / len(all_results)
        return KnowledgeResult(
            title=fusion.primary.title,
            url=fusion.primary.url,
            snippet=fusion.primary.snippet,
            provider="fusion",
            confidence=avg_confidence,
            score=(avg_confidence + avg_authority) / 2,
            type=fusion.primary.type,
            knowledge_type=fusion.primary.knowledge_type,
            authority_score=avg_authority,
            metadata={
                "fusion": True,
                "conflict": True,
                "sources": [r.provider for r in all_results],
                "resolution": fusion.resolution or "merged",
            },
        )
