"""Shared contracts for the Zaram AI Orchestrator (v0.6.1).

The Orchestrator is the *decision* layer of Zaram. It never executes models and
never contains provider-specific logic. Every type here is provider-agnostic:
no model name, no Ollama/OpenAI/LM Studio/Cloud concept appears anywhere.

The Orchestrator consumes discovered models exclusively from the AI Garage
(via the :class:`ModelSource` protocol, satisfied by ``GarageManager``). The
data shape for a model is :class:`garage.contracts.ModelInfo`; this module adds
the orchestration-specific request/plan/decision shapes on top of it.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from garage.contracts import (
    CapabilityLocality,
    HealthStatus,
    ModelCategory,
    ModelInfo,
    ProviderKind,
)


class RoutingMode(Enum):
    """How an execution plan should be carried out by the Models Runtime.

    The Orchestrator only *plans* these modes; it never executes them.
    """

    LOCAL_ONLY = "local_only"
    CLOUD_ONLY = "cloud_only"
    HYBRID = "hybrid"
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    FALLBACK = "fallback"
    # Future collaboration strategies (planned, not yet executed).
    BROADCAST = "broadcast"
    VOTING = "voting"

    @classmethod
    def from_value(cls, value: Optional[str]) -> "RoutingMode":
        if not value:
            return cls.LOCAL_ONLY
        try:
            return cls(str(value).lower())
        except ValueError:
            return cls.LOCAL_ONLY


class TaskType(Enum):
    """The high-level kind of work a request represents."""

    GENERAL = "general"
    REASONING = "reasoning"
    CODING = "coding"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    VISION = "vision"
    TOOL_CALLING = "tool_calling"
    SPEECH = "speech"
    CREATIVE_WRITING = "creative_writing"
    QUESTION_ANSWERING = "question_answering"

    @classmethod
    def from_value(cls, value: Optional[str]) -> "TaskType":
        if not value:
            return cls.GENERAL
        try:
            return cls(str(value).lower())
        except ValueError:
            return cls.GENERAL


# Stable identifiers for the canonical capability dimensions the Orchestrator
# scores every model against. These are *skills*, never model names.
class Capability:
    REASONING = "reasoning"
    CODING = "coding"
    CREATIVE = "creative"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    VISION = "vision"
    SPEECH = "speech"
    EMBEDDING = "embedding"
    TOOL_CALLING = "tool_calling"
    LONG_CONTEXT = "long_context"
    MULTIMODAL = "multimodal"
    FAST_RESPONSE = "fast_response"
    LOW_MEMORY = "low_memory"
    OFFLINE = "offline"
    CLOUD = "cloud"
    LOCAL = "local"


ALL_CAPABILITIES: List[str] = [
    Capability.REASONING,
    Capability.CODING,
    Capability.CREATIVE,
    Capability.TRANSLATION,
    Capability.SUMMARIZATION,
    Capability.VISION,
    Capability.SPEECH,
    Capability.EMBEDDING,
    Capability.TOOL_CALLING,
    Capability.LONG_CONTEXT,
    Capability.MULTIMODAL,
    Capability.FAST_RESPONSE,
    Capability.LOW_MEMORY,
    Capability.OFFLINE,
    Capability.CLOUD,
    Capability.LOCAL,
]


@dataclass
class CapabilityScore:
    """Normalized (0..1) capability scores for a single model."""

    model_id: str
    scores: Dict[str, float] = field(default_factory=dict)
    overall: float = 0.0

    def get(self, capability: str, default: float = 0.0) -> float:
        return float(self.scores.get(capability, default))


@dataclass
class ModelProfile:
    """A model enriched with derived capability scores and resource estimates.

    Built from a :class:`garage.contracts.ModelInfo`; never references a name.
    """

    model: ModelInfo
    scores: Dict[str, float] = field(default_factory=dict)
    latency_estimate_ms: float = 0.0
    vram_requirement_bytes: int = 0
    ram_requirement_bytes: int = 0
    reliability: float = 1.0

    @property
    def model_id(self) -> str:
        return self.model.id

    def capability(self, name: str, default: float = 0.0) -> float:
        return float(self.scores.get(name, default))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model.id,
            "display_name": self.model.display_name,
            "locality": self.model.locality.value,
            "provider": self.model.provider,
            "available": self.model.available,
            "scores": dict(self.scores),
            "latency_estimate_ms": self.latency_estimate_ms,
            "vram_requirement_bytes": self.vram_requirement_bytes,
            "ram_requirement_bytes": self.ram_requirement_bytes,
            "reliability": self.reliability,
        }


@dataclass
class TaskIntent:
    """A normalized understanding of what a request needs."""

    task_type: TaskType = TaskType.GENERAL
    required_capabilities: Set[str] = field(default_factory=set)
    optional_capabilities: Set[str] = field(default_factory=set)
    is_latency_sensitive: bool = False
    requires_privacy: bool = False
    requires_offline: bool = False
    estimated_tokens: int = 0
    raw_prompt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type.value,
            "required_capabilities": sorted(self.required_capabilities),
            "optional_capabilities": sorted(self.optional_capabilities),
            "is_latency_sensitive": self.is_latency_sensitive,
            "requires_privacy": self.requires_privacy,
            "requires_offline": self.requires_offline,
            "estimated_tokens": self.estimated_tokens,
        }


@dataclass
class OrchestrationRequest:
    """The public input to the Orchestrator. Pure data, no execution."""

    request_id: str = field(default_factory=lambda: f"req_{uuid.uuid4().hex[:12]}")
    prompt: str = ""
    task_type: Optional[TaskType] = None
    required_capabilities: Set[str] = field(default_factory=set)
    preferences: List[str] = field(default_factory=list)
    profile: Optional[str] = None
    priority: str = "normal"
    correlation_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "task_type": self.task_type.value if self.task_type else None,
            "required_capabilities": sorted(self.required_capabilities),
            "preferences": list(self.preferences),
            "profile": self.profile,
            "priority": self.priority,
            "correlation_id": self.correlation_id,
        }


@dataclass
class ModelCandidate:
    """A model considered for a request, with its ranking evidence."""

    model_id: str
    profile: ModelProfile
    capability_match: float = 0.0
    score: float = 0.0
    mode: RoutingMode = RoutingMode.LOCAL_ONLY
    rationale: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "display_name": self.profile.model.display_name,
            "capability_match": round(self.capability_match, 4),
            "score": round(self.score, 4),
            "mode": self.mode.value,
            "rationale": list(self.rationale),
            "warnings": list(self.warnings),
        }


@dataclass
class RoutingPlan:
    """The Orchestrator's internal plan: ranked candidates + selection context."""

    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:12]}")
    request_id: str = ""
    intent: TaskIntent = field(default_factory=TaskIntent)
    candidates: List[ModelCandidate] = field(default_factory=list)
    selected: Optional[ModelCandidate] = None
    mode: RoutingMode = RoutingMode.LOCAL_ONLY
    fallback_chain: List[str] = field(default_factory=list)
    stages: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "request_id": self.request_id,
            "intent": self.intent.to_dict(),
            "candidates": [c.to_dict() for c in self.candidates],
            "selected": self.selected.to_dict() if self.selected else None,
            "mode": self.mode.value,
            "fallback_chain": list(self.fallback_chain),
            "stages": list(self.stages),
            "latency_ms": round(self.latency_ms, 3),
        }


@dataclass
class RoutingDecision:
    """The final selection produced by the router."""

    request_id: str = ""
    model_id: Optional[str] = None
    mode: RoutingMode = RoutingMode.LOCAL_ONLY
    fallback_chain: List[str] = field(default_factory=list)
    rationale: List[str] = field(default_factory=list)
    plan_id: str = ""
    decided_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "model_id": self.model_id,
            "mode": self.mode.value,
            "fallback_chain": list(self.fallback_chain),
            "rationale": list(self.rationale),
            "plan_id": self.plan_id,
        }


@dataclass
class ExecutionRequest:
    """What the Orchestrator hands to the Models Runtime. Planning only."""

    request_id: str = ""
    model_id: Optional[str] = None
    mode: RoutingMode = RoutingMode.LOCAL_ONLY
    fallback_chain: List[str] = field(default_factory=list)
    correlation_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "model_id": self.model_id,
            "mode": self.mode.value,
            "fallback_chain": list(self.fallback_chain),
            "correlation_id": self.correlation_id,
            "payload": dict(self.payload),
        }


def new_id(prefix: str = "orch") -> str:
    """Generate a prefixed unique identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def merge_weights(maps: List[Dict[str, float]], default: float = 1.0) -> Dict[str, float]:
    """Average several capability-weight maps into one.

    A capability absent from a map is treated as ``default`` (so an engine that
    does not mention a capability never suppresses it). Returns an empty dict
    when no maps are supplied; callers should fall back to neutral weights.
    """
    merged: Dict[str, float] = {}
    keys: Set[str] = set()
    for m in maps:
        keys.update(m.keys())
    for key in keys:
        values = [float(m.get(key, default)) for m in maps]
        merged[key] = sum(values) / len(values)
    return merged


def now() -> float:
    """Current epoch timestamp (single source of truth for created_at)."""
    return time.time()
