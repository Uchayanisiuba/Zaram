from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence
import time


class DiscoverySource(str, Enum):
    CACHE = "cache"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    INTERNET = "internet"
    AGENT = "agent"
    NONE = "none"


@dataclass(frozen=True)
class EscalationStep:
    """A single step in the escalation chain."""

    source: DiscoverySource
    timeout_seconds: float
    required: bool
    description: str = ""


@dataclass
class EscalationResult:
    """Result of a discovery escalation attempt."""

    source: DiscoverySource
    results: list[Any] = field(default_factory=list)
    latency_ms: float = 0.0
    success: bool = False
    error: str | None = None
    confidence: float = 0.0


class DiscoveryEscalation:
    """Manages escalation of discovery queries through a source chain.

    When a discovery query is made, the escalation engine tries sources
    in order of preference (cache → memory → knowledge → internet).
    Each source has a timeout and can be marked as required or optional.

    The escalation chain is configurable per query type.
    """

    DEFAULT_CHAIN: list[DiscoverySource] = [
        DiscoverySource.CACHE,
        DiscoverySource.MEMORY,
        DiscoverySource.KNOWLEDGE,
        DiscoverySource.INTERNET,
    ]

    def __init__(self, event_bus: Any | None = None):
        self._event_bus = event_bus
        self._chain_configs: dict[str, list[EscalationStep]] = {}
        self._source_latencies: dict[str, list[float]] = {}
        self._source_success: dict[str, int] = {}
        self._source_failures: dict[str, int] = {}
        self._stats: dict[str, Any] = {
            "escalations": 0,
            "cache_hits": 0,
            "memory_hits": 0,
            "knowledge_hits": 0,
            "internet_hits": 0,
            "escalations_to_next": 0,
            "total_latency_ms": 0.0,
        }
        self._init_default_chains()

    def _init_default_chains(self) -> None:
        self._chain_configs["default"] = [
            EscalationStep(DiscoverySource.CACHE, 0.1, False, "Local cache lookup"),
            EscalationStep(DiscoverySource.MEMORY, 0.5, False, "Memory runtime search"),
            EscalationStep(DiscoverySource.KNOWLEDGE, 5.0, False, "Knowledge runtime search"),
            EscalationStep(DiscoverySource.INTERNET, 10.0, False, "Internet search"),
        ]
        self._chain_configs["time_sensitive"] = [
            EscalationStep(DiscoverySource.CACHE, 0.1, False, "Local cache lookup"),
            EscalationStep(DiscoverySource.KNOWLEDGE, 3.0, True, "Knowledge runtime search"),
            EscalationStep(DiscoverySource.INTERNET, 8.0, False, "Internet search"),
        ]
        self._chain_configs["agent"] = [
            EscalationStep(DiscoverySource.CACHE, 0.1, False, "Local cache lookup"),
            EscalationStep(DiscoverySource.MEMORY, 1.0, False, "Memory runtime search"),
            EscalationStep(DiscoverySource.KNOWLEDGE, 5.0, False, "Knowledge runtime search"),
        ]

    def get_chain(self, query_type: str = "default") -> list[EscalationStep]:
        """Get the escalation chain for a query type."""
        return list(self._chain_configs.get(query_type, self._chain_configs["default"]))

    def register_chain(self, query_type: str, chain: list[EscalationStep]) -> None:
        """Register a custom escalation chain for a query type."""
        self._chain_configs[query_type] = list(chain)

    def get_source_timeout(self, source: DiscoverySource) -> float:
        """Get the timeout for a source type."""
        defaults = {
            DiscoverySource.CACHE: 0.1,
            DiscoverySource.MEMORY: 0.5,
            DiscoverySource.KNOWLEDGE: 5.0,
            DiscoverySource.INTERNET: 10.0,
            DiscoverySource.AGENT: 30.0,
        }
        return defaults.get(source, 5.0)

    def record_success(self, source: DiscoverySource, latency_ms: float) -> None:
        """Record a successful discovery from a source."""
        key = source.value
        self._source_latencies.setdefault(key, []).append(latency_ms)
        self._source_success[key] = self._source_success.get(key, 0) + 1
        if len(self._source_latencies[key]) > 100:
            self._source_latencies[key] = self._source_latencies[key][-50:]

    def record_failure(self, source: DiscoverySource) -> None:
        """Record a failed discovery from a source."""
        key = source.value
        self._source_failures[key] = self._source_failures.get(key, 0) + 1

    def get_source_health(self, source: DiscoverySource) -> dict[str, Any]:
        """Get health metrics for a source."""
        key = source.value
        latencies = self._source_latencies.get(key, [])
        successes = self._source_success.get(key, 0)
        failures = self._source_failures.get(key, 0)
        total = successes + failures
        return {
            "source": key,
            "successes": successes,
            "failures": failures,
            "success_rate": successes / total if total > 0 else 0.0,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
        }

    def should_escalate(
        self,
        results: Sequence[Any],
        current_source: DiscoverySource,
        chain: list[EscalationStep],
        min_results: int = 1,
    ) -> bool:
        """Determine if we should escalate to the next source.

        Escalation happens when:
        - Current source returned no results (or fewer than min_results)
        - There are more sources in the chain
        - The current source is not the last in the chain
        """
        if len(results) >= min_results:
            return False
        current_idx = next(
            (i for i, step in enumerate(chain) if step.source == current_source),
            -1,
        )
        if current_idx == -1:
            return False
        return current_idx < len(chain) - 1

    def get_next_source(
        self,
        current_source: DiscoverySource,
        chain: list[EscalationStep],
    ) -> EscalationStep | None:
        """Get the next escalation step after the current source."""
        current_idx = next(
            (i for i, step in enumerate(chain) if step.source == current_source),
            -1,
        )
        if current_idx == -1 or current_idx >= len(chain) - 1:
            return None
        return chain[current_idx + 1]

    def evaluate_chain(
        self,
        query: str,
        query_type: str = "default",
        min_results: int = 1,
    ) -> list[EscalationStep]:
        """Evaluate the escalation chain for a query.

        Returns the ordered list of escalation steps to try.
        """
        chain = self.get_chain(query_type)
        self._stats["escalations"] += 1
        return chain

    def update_stats(self, source: DiscoverySource, escalated: bool = False) -> None:
        """Update stats after a discovery attempt."""
        if escalated:
            self._stats["escalations_to_next"] += 1
        if source == DiscoverySource.CACHE:
            self._stats["cache_hits"] += 1
        elif source == DiscoverySource.MEMORY:
            self._stats["memory_hits"] += 1
        elif source == DiscoverySource.KNOWLEDGE:
            self._stats["knowledge_hits"] += 1
        elif source == DiscoverySource.INTERNET:
            self._stats["internet_hits"] += 1

    def get_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def reset_stats(self) -> None:
        self._stats = {
            "escalations": 0,
            "cache_hits": 0,
            "memory_hits": 0,
            "knowledge_hits": 0,
            "internet_hits": 0,
            "escalations_to_next": 0,
            "total_latency_ms": 0.0,
        }
