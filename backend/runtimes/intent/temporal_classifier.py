from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .query_envelope import TemporalSensitivity


@dataclass(frozen=True)
class ClassificationResult:
    """Result of classifying a query's temporal sensitivity."""

    sensitivity: TemporalSensitivity
    confidence: float
    matched_patterns: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sensitivity": self.sensitivity.value,
            "confidence": self.confidence,
            "matched_patterns": list(self.matched_patterns),
            "reasons": list(self.reasons),
        }


class TemporalClassifier:
    """Classifies queries as time-sensitive, timeless, or mixed.

    A time-sensitive query requires current/recent information (e.g. "current
    weather", "latest stock price"). A timeless query asks for stable
    knowledge (e.g. "explain recursion"). Mixed queries contain both signals.
    """

    _TIME_SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("current", re.compile(r"\b(current|now|today|right now|at the moment)\b", re.IGNORECASE)),
        ("latest", re.compile(r"\b(latest|newest|most recent|recent|recently)\b", re.IGNORECASE)),
        ("breaking", re.compile(r"\b(breaking|just happened|just now|today's)\b", re.IGNORECASE)),
        ("time_query", re.compile(r"\b(what time|when|how long|how old)\b", re.IGNORECASE)),
        ("realtime_data", re.compile(
            r"\b(weather|temperature|forecast|stock|price|market|bitcoin|crypto|"
            r"nasdaq|dow|news|headlines|traffic|score|election|president|ceo|founder|"
            r"released|launch|update|version)\b",
            re.IGNORECASE,
        )),
        ("year_reference", re.compile(r"\b20(2[5-9]|3[0-9])\b")),
        ("live", re.compile(r"\b(live|real-time|realtime|ongoing)\b", re.IGNORECASE)),
    ]

    _TIMELESS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("explain", re.compile(r"\b(explain|how does|how do|how did|why|because)\b", re.IGNORECASE)),
        ("concept", re.compile(r"\b(concept|theory|principle|definition|meaning|what is|what are)\b", re.IGNORECASE)),
        ("tutorial", re.compile(r"\b(tutorial|guide|how to|steps|learn|understand)\b", re.IGNORECASE)),
        ("compare", re.compile(r"\b(compare|difference|versus|vs|between)\b", re.IGNORECASE)),
        ("historical", re.compile(r"\b(history|historically|origin|evolution|developed)\b", re.IGNORECASE)),
    ]

    def classify(self, query: str) -> ClassificationResult:
        """Classify a query's temporal sensitivity.

        Returns a ClassificationResult with the sensitivity level and
        confidence score (0.0–1.0).
        """
        if not query or len(query.strip()) < 3:
            return ClassificationResult(
                sensitivity=TemporalSensitivity.MIXED,
                confidence=0.0,
                reasons=["query too short or empty"],
            )

        matched_sensitive: list[str] = []
        matched_timeless: list[str] = []

        for name, pattern in self._TIME_SENSITIVE_PATTERNS:
            if pattern.search(query):
                matched_sensitive.append(name)

        for name, pattern in self._TIMELESS_PATTERNS:
            if pattern.search(query):
                matched_timeless.append(name)

        sensitive_count = len(matched_sensitive)
        timeless_count = len(matched_timeless)

        if sensitive_count > 0 and timeless_count > 0:
            return ClassificationResult(
                sensitivity=TemporalSensitivity.MIXED,
                confidence=min(0.95, 0.5 + 0.1 * (sensitive_count + timeless_count)),
                matched_patterns=matched_sensitive + matched_timeless,
                reasons=[
                    f"matched {sensitive_count} time-sensitive pattern(s)",
                    f"matched {timeless_count} timeless pattern(s)",
                ],
            )

        if sensitive_count > 0:
            confidence = min(0.95, 0.6 + 0.1 * sensitive_count)
            return ClassificationResult(
                sensitivity=TemporalSensitivity.TIME_SENSITIVE,
                confidence=confidence,
                matched_patterns=matched_sensitive,
                reasons=[f"matched {sensitive_count} time-sensitive pattern(s): {', '.join(matched_sensitive)}"],
            )

        if timeless_count > 0:
            confidence = min(0.95, 0.6 + 0.1 * timeless_count)
            return ClassificationResult(
                sensitivity=TemporalSensitivity.TIMELESS,
                confidence=confidence,
                matched_patterns=matched_timeless,
                reasons=[f"matched {timeless_count} timeless pattern(s): {', '.join(matched_timeless)}"],
            )

        return ClassificationResult(
            sensitivity=TemporalSensitivity.MIXED,
            confidence=0.3,
            reasons=["no strong temporal signal detected"],
        )

    def is_time_sensitive(self, query: str) -> bool:
        """Quick boolean check: is this query time-sensitive?"""
        result = self.classify(query)
        return result.sensitivity == TemporalSensitivity.TIME_SENSITIVE
