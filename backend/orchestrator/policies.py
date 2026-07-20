"""Policy engine for the AI Orchestrator (v0.6.1).

Policies are *configuration*, not code. Each :class:`PolicySpec` is a bundle of
capability weights plus an optional hard locality constraint. New policies are
added by registering a spec — never by editing the scoring/router logic.

Built-in policies cover the milestone's required set (Speed, Highest Quality,
Lowest VRAM, Offline Only, Cloud Preferred, Coding Optimized, Creative Writing,
Long Context, Reasoning, Vision, Speech, Tool Calling, Balanced).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .contracts import RoutingMode, merge_weights


class PolicyId(str, Enum):
    SPEED = "speed"
    HIGHEST_QUALITY = "highest_quality"
    LOWEST_VRAM = "lowest_vram"
    OFFLINE_ONLY = "offline_only"
    CLOUD_PREFERRED = "cloud_preferred"
    CODING_OPTIMIZED = "coding_optimized"
    CREATIVE_WRITING = "creative_writing"
    LONG_CONTEXT = "long_context"
    REASONING = "reasoning"
    VISION = "vision"
    SPEECH = "speech"
    TOOL_CALLING = "tool_calling"
    BALANCED = "balanced"


@dataclass
class PolicySpec:
    """A named, configurable routing policy."""

    id: str
    name: str
    description: str
    weights: Dict[str, float] = field(default_factory=dict)
    locality: Optional[str] = None
    mode_hint: Optional[RoutingMode] = None
    hard: bool = False


BUILTIN_POLICIES: Dict[str, PolicySpec] = {
    PolicyId.SPEED.value: PolicySpec(
        id=PolicyId.SPEED.value,
        name="Speed",
        description="Prefer the fastest, lightest models.",
        weights={"fast_response": 2.0, "low_memory": 1.5, "long_context": 0.7},
        mode_hint=RoutingMode.LOCAL_ONLY,
    ),
    PolicyId.HIGHEST_QUALITY.value: PolicySpec(
        id=PolicyId.HIGHEST_QUALITY.value,
        name="Highest Quality",
        description="Prefer the most capable models for hard tasks.",
        weights={"reasoning": 1.8, "coding": 1.6, "long_context": 1.5, "creative": 1.3},
    ),
    PolicyId.LOWEST_VRAM.value: PolicySpec(
        id=PolicyId.LOWEST_VRAM.value,
        name="Lowest VRAM",
        description="Minimize GPU memory footprint.",
        weights={"low_memory": 2.5, "fast_response": 1.3, "long_context": 0.6},
    ),
    PolicyId.OFFLINE_ONLY.value: PolicySpec(
        id=PolicyId.OFFLINE_ONLY.value,
        name="Offline Only",
        description="Only local models that work without network.",
        locality="local",
        hard=True,
    ),
    PolicyId.CLOUD_PREFERRED.value: PolicySpec(
        id=PolicyId.CLOUD_PREFERRED.value,
        name="Cloud Preferred",
        description="Prefer cloud models when available.",
        weights={"cloud": 2.0, "local": 0.5},
        mode_hint=RoutingMode.CLOUD_ONLY,
    ),
    PolicyId.CODING_OPTIMIZED.value: PolicySpec(
        id=PolicyId.CODING_OPTIMIZED.value,
        name="Coding Optimized",
        description="Bias toward strong coding models.",
        weights={"coding": 2.2, "reasoning": 1.4, "tool_calling": 1.3},
    ),
    PolicyId.CREATIVE_WRITING.value: PolicySpec(
        id=PolicyId.CREATIVE_WRITING.value,
        name="Creative Writing",
        description="Bias toward expressive, creative models.",
        weights={"creative": 2.2, "summarization": 1.3},
    ),
    PolicyId.LONG_CONTEXT.value: PolicySpec(
        id=PolicyId.LONG_CONTEXT.value,
        name="Long Context",
        description="Require/prefer large context windows.",
        weights={"long_context": 2.5, "summarization": 1.2},
    ),
    PolicyId.REASONING.value: PolicySpec(
        id=PolicyId.REASONING.value,
        name="Reasoning",
        description="Bias toward strong reasoning models.",
        weights={"reasoning": 2.2, "coding": 1.3},
    ),
    PolicyId.VISION.value: PolicySpec(
        id=PolicyId.VISION.value,
        name="Vision",
        description="Require multimodal/vision capable models.",
        weights={"vision": 2.5, "multimodal": 2.0},
    ),
    PolicyId.SPEECH.value: PolicySpec(
        id=PolicyId.SPEECH.value,
        name="Speech",
        description="Bias toward speech-capable models.",
        weights={"speech": 2.5},
    ),
    PolicyId.TOOL_CALLING.value: PolicySpec(
        id=PolicyId.TOOL_CALLING.value,
        name="Tool Calling",
        description="Require tool-capable models.",
        weights={"tool_calling": 2.5},
    ),
    PolicyId.BALANCED.value: PolicySpec(
        id=PolicyId.BALANCED.value,
        name="Balanced",
        description="No bias; consider every capability equally.",
        weights={},
    ),
}


class PolicyEngine:
    """Tracks which policies are active and derives weights/filters from them."""

    def __init__(self, specs: Optional[Dict[str, PolicySpec]] = None) -> None:
        self._specs: Dict[str, PolicySpec] = dict(specs or BUILTIN_POLICIES)
        self._active: Set[str] = set()

    # --- registry ---
    def register(self, spec: PolicySpec) -> None:
        self._specs[spec.id] = spec

    def get_spec(self, policy_id: str) -> Optional[PolicySpec]:
        return self._specs.get(policy_id)

    def available(self) -> List[PolicySpec]:
        return list(self._specs.values())

    # --- activation ---
    def activate(self, policy_id: str) -> None:
        if policy_id in self._specs:
            self._active.add(policy_id)

    def deactivate(self, policy_id: str) -> None:
        self._active.discard(policy_id)

    def set_active(self, policy_ids: List[str]) -> None:
        self._active = {pid for pid in policy_ids if pid in self._specs}

    def active_ids(self) -> List[str]:
        return [pid for pid in self._active if pid in self._specs]

    def active_specs(self) -> List[PolicySpec]:
        return [self._specs[pid] for pid in self._active if pid in self._specs]

    # --- derived selection signals ---
    def weights(self) -> Dict[str, float]:
        return merge_weights([s.weights for s in self.active_specs()])

    def mode_hint(self) -> Optional[RoutingMode]:
        for spec in self.active_specs():
            if spec.mode_hint is not None:
                return spec.mode_hint
        return None

    def filter_candidates(self, candidates: List[Any]) -> List[Any]:
        """Apply hard locality constraints from active policies."""
        for spec in self.active_specs():
            if spec.hard and spec.locality:
                wanted = spec.locality
                candidates = [
                    c for c in candidates if c.profile.model.locality.value == wanted
                ]
        return candidates
