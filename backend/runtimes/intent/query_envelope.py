from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time
import uuid


class IntentType(str, Enum):
    REASONING = "reasoning"
    SEARCH = "search"
    DISCOVERY = "discovery"
    CREATIVE = "creative"
    CONVERSATION = "conversation"
    TASK = "task"
    AGENT = "agent"
    UNKNOWN = "unknown"


class TemporalSensitivity(str, Enum):
    TIME_SENSITIVE = "time_sensitive"
    TIMELESS = "timeless"
    MIXED = "mixed"


@dataclass(frozen=True)
class QueryEnvelope:
    """Immutable envelope wrapping a user query with routing metadata.

    The envelope travels through the Event Bus alongside the query,
    carrying everything downstream runtimes need to make routing and
    confidence decisions without re-parsing the raw text.
    """

    query: str
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    intent_type: IntentType = IntentType.UNKNOWN
    temporal_sensitivity: TemporalSensitivity = TemporalSensitivity.MIXED
    confidence_threshold: float = 0.7
    preferred_sources: list[str] = field(default_factory=list)
    max_results: int = 10
    session_id: str | None = None
    user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "intent_type": self.intent_type.value,
            "temporal_sensitivity": self.temporal_sensitivity.value,
            "confidence_threshold": self.confidence_threshold,
            "preferred_sources": list(self.preferred_sources),
            "max_results": self.max_results,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_query(
        cls,
        query: str,
        intent_type: IntentType = IntentType.UNKNOWN,
        **kwargs: Any,
    ) -> "QueryEnvelope":
        """Build an envelope from a raw query string."""
        return cls(query=query, intent_type=intent_type, **kwargs)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp
