# backend/runtime/discovery/verification.py
from __future__ import annotations

from collections import Counter
from typing import Any

from .contracts import DiscoveryResult, VerificationResult


class VerificationEngine:
    """Compares multiple provider responses to detect agreement, conflict, and duplicates."""

    def verify(self, results: list[DiscoveryResult]) -> VerificationResult:
        if not results:
            return VerificationResult(
                agreement_score=0.0,
                conflict_score=0.0,
                duplicate_count=0,
                missing_information=[],
                conflict_report=[],
                overall_confidence=0.0,
                verified=False,
            )

        if len(results) == 1:
            return VerificationResult(
                agreement_score=1.0,
                conflict_score=0.0,
                duplicate_count=0,
                missing_information=[],
                conflict_report=[],
                overall_confidence=results[0].confidence,
                verified=True,
            )

        titles = [r.metadata.title.lower().strip() for r in results if r.metadata.title]
        unique_titles = len(set(titles))
        duplicate_count = len(titles) - unique_titles

        snippets = [r.summary.lower().strip() for r in results if r.summary]
        agreement = self._compute_agreement(snippets)
        conflict = self._compute_conflict(snippets)
        missing = self._detect_missing(results)
        conflicts = self._build_conflict_report(results)

        overall = agreement * 0.6 + (1.0 - conflict) * 0.4
        verified = overall >= 0.6 and conflict < 0.3

        return VerificationResult(
            agreement_score=agreement,
            conflict_score=conflict,
            duplicate_count=duplicate_count,
            missing_information=missing,
            conflict_report=conflicts,
            overall_confidence=overall,
            verified=verified,
        )

    def _compute_agreement(self, snippets: list[str]) -> float:
        if len(snippets) < 2:
            return 1.0
        pairs = 0
        agreements = 0
        words_list = [set(s.split()) for s in snippets]
        for i in range(len(words_list)):
            for j in range(i + 1, len(words_list)):
                pairs += 1
                intersection = len(words_list[i] & words_list[j])
                union = len(words_list[i] | words_list[j])
                if union == 0:
                    agreements += 1
                else:
                    agreements += intersection / union
        return agreements / max(pairs, 1)

    def _compute_conflict(self, snippets: list[str]) -> float:
        if len(snippets) < 2:
            return 0.0
        conflict_indicators = {"false", "incorrect", "disputed", "contradicts", "myth", "not true"}
        conflicts = 0
        pairs = 0
        for i in range(len(snippets)):
            for j in range(i + 1, len(snippets)):
                pairs += 1
                words_i = set(snippets[i].split())
                words_j = set(snippets[j].split())
                if words_i & conflict_indicators or words_j & conflict_indicators:
                    conflicts += 1
        return conflicts / max(pairs, 1)

    def _detect_missing(self, results: list[DiscoveryResult]) -> list[str]:
        missing: list[str] = []
        if not any(r.metadata.author for r in results):
            missing.append("author")
        if not any(r.metadata.published for r in results):
            missing.append("published")
        if not any(r.metadata.url for r in results):
            missing.append("url")
        return missing

    def _build_conflict_report(self, results: list[DiscoveryResult]) -> list[dict[str, Any]]:
        report: list[dict[str, Any]] = []
        titles = [r.metadata.title for r in results]
        title_counts = Counter(titles)
        for title, count in title_counts.items():
            if count > 1:
                report.append({
                    "type": "duplicate",
                    "title": title,
                    "count": count,
                    "providers": [r.metadata.provider for r in results if r.metadata.title == title],
                })
        return report
