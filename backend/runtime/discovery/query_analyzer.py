# backend/runtime/discovery/query_analyzer.py
from __future__ import annotations

import re

from .contracts import (
    AuthorityLevel,
    Capability,
    DiscoveryIntent,
    DiscoveryRequest,
    FreshnessLevel,
    QueryAnalysis,
    SearchDifficulty,
)


class QueryAnalyzer:
    """Analyzes discovery queries to extract structured parameters."""

    _FRESHNESS_KEYWORDS = {
        "latest": FreshnessLevel.LIVE,
        "current": FreshnessLevel.LIVE,
        "breaking": FreshnessLevel.LIVE,
        "today": FreshnessLevel.LIVE,
        "recent": FreshnessLevel.RECENT,
        "new": FreshnessLevel.RECENT,
        "update": FreshnessLevel.RECENT,
        "history": FreshnessLevel.STATIC,
        "old": FreshnessLevel.STATIC,
        "archive": FreshnessLevel.STATIC,
    }

    _AUTHORITY_KEYWORDS = {
        "government": AuthorityLevel.GOVERNMENT,
        "official": AuthorityLevel.OFFICIAL_DOCS,
        "documentation": AuthorityLevel.OFFICIAL_DOCS,
        "research": AuthorityLevel.ACADEMIC,
        "paper": AuthorityLevel.ACADEMIC,
        "study": AuthorityLevel.ACADEMIC,
        "wikipedia": AuthorityLevel.WIKIPEDIA,
        "repo": AuthorityLevel.GITHUB,
        "github": AuthorityLevel.GITHUB,
        "forum": AuthorityLevel.COMMUNITY,
        "community": AuthorityLevel.COMMUNITY,
        "blog": AuthorityLevel.BLOG,
        "tutorial": AuthorityLevel.BLOG,
    }

    _DIFFICULTY_SIGNALS = {
        "easy": ("compare", "list", "what is", "who is", "when was"),
        "medium": ("how to", "why", "analyze", "difference between"),
        "hard": ("architecture", "design", "implement", "optimize", "evaluate"),
    }

    def analyze(self, request: DiscoveryRequest) -> QueryAnalysis:
        query = request.query.strip()
        lower = query.lower()
        words = set(lower.split())

        intent = request.intent or self._detect_intent(lower, words)
        topic = self._extract_topic(query)
        domain = self._detect_domain(lower, words)
        freshness = request.freshness_requirement if request.freshness_requirement != FreshnessLevel.UNKNOWN else self._detect_freshness(lower, words)
        authority = request.authority_requirement if request.authority_requirement != AuthorityLevel.UNKNOWN else self._detect_authority(lower, words)
        latency_budget = request.latency_budget_ms if request.latency_budget_ms > 0 else self._estimate_latency_budget(lower)
        difficulty = self._detect_difficulty(lower)
        capabilities = self._expected_capabilities(intent, domain, lower)

        confidence = 0.8
        if request.intent is not None:
            confidence += 0.1
        if freshness != FreshnessLevel.UNKNOWN:
            confidence += 0.05
        if authority != AuthorityLevel.UNKNOWN:
            confidence += 0.05
        confidence = min(confidence, 0.95)

        return QueryAnalysis(
            intent=intent,
            topic=topic,
            domain=domain,
            freshness_requirement=freshness,
            authority_requirement=authority,
            latency_budget_ms=latency_budget,
            search_difficulty=difficulty,
            expected_capabilities=capabilities,
            raw_query=query,
            confidence=confidence,
        )

    def _detect_intent(self, lower: str, words: set[str]) -> DiscoveryIntent:
        if any(w in lower for w in ["code", "programming", "github", "repo", "library", "api"]):
            return DiscoveryIntent.PROGRAMMING
        if any(w in lower for w in ["news", "breaking", "headline", "today"]):
            return DiscoveryIntent.NEWS
        if any(w in lower for w in ["rss", "feed", "subscribe"]):
            return DiscoveryIntent.RSS
        if any(w in lower for w in ["dynamic", "scrape", "browser"]):
            return DiscoveryIntent.DYNAMIC
        if any(w in lower for w in ["research", "paper", "study", "academic"]):
            return DiscoveryIntent.ACADEMIC
        if any(w in lower for w in ["social", "reddit", "twitter", "forum"]):
            return DiscoveryIntent.SOCIAL
        if any(w in lower for w in ["what is", "who is", "when was", "where is", "definition", "history"]):
            return DiscoveryIntent.ENCYCLOPEDIA
        return DiscoveryIntent.GENERAL

    def _extract_topic(self, query: str) -> str:
        cleaned = re.sub(r"[^\w\s]", " ", query)
        words = cleaned.split()
        stop = {"what", "who", "where", "when", "why", "how", "is", "are", "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "latest", "current"}
        topic_words = [w for w in words if w.lower() not in stop]
        return " ".join(topic_words[:5]) if topic_words else query

    def _detect_domain(self, lower: str, words: set[str]) -> str:
        if any(w in lower for w in ["python", "javascript", "rust", "go", "java", "c++", "code"]):
            return "programming"
        if any(w in lower for w in ["science", "physics", "biology", "chemistry"]):
            return "science"
        if any(w in lower for w in ["history", "war", "century", "ancient"]):
            return "history"
        if any(w in lower for w in ["finance", "stock", "market", "crypto"]):
            return "finance"
        if any(w in lower for w in ["health", "medical", "disease", "drug"]):
            return "health"
        return "general"

    def _detect_freshness(self, lower: str, words: set[str]) -> FreshnessLevel:
        for keyword, level in self._FRESHNESS_KEYWORDS.items():
            if keyword in lower:
                return level
        return FreshnessLevel.UNKNOWN

    def _detect_authority(self, lower: str, words: set[str]) -> AuthorityLevel:
        for keyword, level in self._AUTHORITY_KEYWORDS.items():
            if keyword in lower:
                return level
        return AuthorityLevel.UNKNOWN

    def _detect_difficulty(self, lower: str) -> SearchDifficulty:
        for difficulty, signals in self._DIFFICULTY_SIGNALS.items():
            if any(signal in lower for signal in signals):
                return SearchDifficulty(difficulty)
        return SearchDifficulty.MEDIUM

    def _estimate_latency_budget(self, lower: str) -> float:
        if any(w in lower for w in ["fast", "quick", "now", "instant"]):
            return 500.0
        if any(w in lower for w in ["thorough", "deep", "comprehensive", "detailed"]):
            return 5000.0
        return 2000.0

    def _expected_capabilities(self, intent: DiscoveryIntent, domain: str, lower: str) -> list[Capability]:
        caps: list[Capability] = [Capability.WEB]
        if intent == DiscoveryIntent.ENCYCLOPEDIA:
            caps.extend([Capability.REFERENCE, Capability.ACADEMIC])
        elif intent == DiscoveryIntent.PROGRAMMING:
            caps.extend([Capability.CODE, Capability.REPOSITORIES, Capability.DOCUMENTATION])
        elif intent == DiscoveryIntent.NEWS:
            caps.append(Capability.NEWS)
        elif intent == DiscoveryIntent.ACADEMIC:
            caps.extend([Capability.ACADEMIC, Capability.RESEARCH])
        elif intent == DiscoveryIntent.RSS:
            caps.append(Capability.NEWS)
        elif intent == DiscoveryIntent.GENERAL:
            caps.extend([Capability.RESEARCH, Capability.REFERENCE])
        if domain == "programming":
            caps.extend([Capability.CODE, Capability.REPOSITORIES])
        return list(set(caps))
