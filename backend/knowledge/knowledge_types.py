# backend/knowledge/knowledge_types.py
from __future__ import annotations

import re
from typing import Any
from .protocol import KnowledgeChunk, KnowledgeObject, KnowledgeType


_TYPE_INDICATORS: dict[KnowledgeType, list[str]] = {
    KnowledgeType.FACT: [
        " is ", " are ", " was ", " were ", " has ", " have ", " does ", " do ",
        "states that", "according to", "confirmed", "verified", "measured", "observed",
    ],
    KnowledgeType.CONCEPT: [
        "concept", "theory", "idea", "principle", "paradigm", "framework",
        "model", "approach", "methodology", "abstract", "general",
    ],
    KnowledgeType.PROCEDURE: [
        "step", "steps", "procedure", "how to", "instructions", "process",
        "first", "then", "next", "finally", "configure", "install", "setup",
    ],
    KnowledgeType.OPINION: [
        "believe", "think", "opinion", "view", "perspective", "argue",
        "should", "recommend", "suggest", "personally", "in my view",
        "i believe", "i think", "i strongly",
    ],
    KnowledgeType.OBSERVATION: [
        "observed", "noticed", "appears", "seems", "looks like", "apparent",
        "seems to be", "data suggests", "trend indicates",
    ],
    KnowledgeType.PERSONAL: [
        " i ", " my ", " me ", " we ", " our ", " us ", "i'm", "i've", "i'll",
        "personally", "in my experience", "for me",
    ],
    KnowledgeType.EXTERNAL: [
        "according to", "study shows", "research indicates", "source:",
        "reported by", "cited in", "published",
    ],
    KnowledgeType.GENERATED: [
        "generated", "synthesized", "inferred", "deduced", "concluded",
        "derived from", "based on analysis",
    ],
}


class KnowledgeTypeClassifier:
    """Classify knowledge objects and chunks by type."""

    def classify_chunk(self, chunk: KnowledgeChunk) -> KnowledgeType:
        return self._classify_text(chunk.text)

    def classify_object(self, obj: KnowledgeObject) -> KnowledgeType:
        if obj.chunks:
            counts: dict[KnowledgeType, int] = {}
            for chunk in obj.chunks:
                ktype = self.classify_chunk(chunk)
                counts[ktype] = counts.get(ktype, 0) + 1
            if counts:
                return max(counts, key=counts.get)
        return self._classify_text(obj.content)

    def _classify_text(self, text: str) -> KnowledgeType:
        text_lower = " " + text.lower() + " "
        scores: dict[KnowledgeType, float] = {}
        for ktype, indicators in _TYPE_INDICATORS.items():
            score = 0.0
            for indicator in indicators:
                count = text_lower.count(indicator)
                score += count * (1.0 + len(indicator.split()) * 0.1)
            scores[ktype] = score
        if not scores or max(scores.values()) == 0:
            return KnowledgeType.EXTERNAL
        return max(scores, key=scores.get)
