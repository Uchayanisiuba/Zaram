# backend/knowledge/fusion.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from .protocol import KnowledgeResult, KnowledgeFusion, KnowledgeProvider


@dataclass
class KnowledgeFusionEngine:
    """Merges multiple providers, duplicate articles, multiple documents, and conflicting information."""

    def fuse(self, results: list[KnowledgeResult]) -> list[KnowledgeFusion]:
        groups: dict[str, KnowledgeFusion] = {}
        for result in results:
            key = (result.title or result.url or "").strip().lower()
            if not key:
                continue
            if key not in groups:
                groups[key] = KnowledgeFusion(
                    primary=result,
                    sources=[result.provider],
                )
            else:
                fusion = groups[key]
                fusion.duplicates.append(result)
                if result.provider not in fusion.sources:
                    fusion.sources.append(result.provider)
                fusion.agreement_score = self._agreement(fusion.primary, result)
        return list(groups.values())

    def _agreement(self, a: KnowledgeResult, b: KnowledgeResult) -> float:
        score = 0.0
        if a.title and b.title and a.title.lower() == b.title.lower():
            score += 0.5
        if a.url and b.url and a.url.lower() == b.url.lower():
            score += 0.5
        return min(1.0, score)

    def detect_conflicts(self, fusion: KnowledgeFusion) -> list[dict[str, Any]]:
        conflicts: list[dict[str, Any]] = []
        seen: dict[str, list[KnowledgeResult]] = {}
        for r in [fusion.primary] + fusion.duplicates:
            key = "confidence"
            val = r.confidence
            if key not in seen:
                seen[key] = []
            seen[key].append(r)
        for key, vals in seen.items():
            unique_vals = list({getattr(v, key) for v in vals})
            if len(unique_vals) > 1:
                conflicts.append({
                    "field": key,
                    "values": unique_vals,
                    "sources": [v.provider for v in vals],
                })
        return conflicts
