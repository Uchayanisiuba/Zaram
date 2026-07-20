"""User preference engine for the AI Orchestrator (v0.6.1).

Preferences are user-facing routing biases (Prefer Local, Prefer Cloud,
Balanced, Offline Required, Fast Responses, Highest Quality, ...). They are
runtime-configurable: the future Settings Runtime / UI will call
:meth:`PreferencesManager.set_preferences`, which emits a change event without
any code change. Internally a preference is just a bundle of capability weights
plus an optional hard locality constraint — identical machinery to policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .contracts import RoutingMode, merge_weights


class PreferenceId(str, Enum):
    PREFER_LOCAL = "prefer_local"
    PREFER_CLOUD = "prefer_cloud"
    BALANCED = "balanced"
    OFFLINE_ONLY = "offline_only"
    LOWEST_VRAM = "lowest_vram"
    FASTEST_RESPONSE = "fastest_response"
    HIGHEST_QUALITY = "highest_quality"
    CODING_OPTIMIZED = "coding_optimized"
    CREATIVE_WRITING = "creative_writing"
    REASONING_FIRST = "reasoning_first"
    ENERGY_SAVING = "energy_saving"
    PERFORMANCE_MODE = "performance_mode"


@dataclass
class PreferenceSpec:
    """A named, user-configurable routing preference."""

    id: str
    name: str
    description: str
    weights: Dict[str, float] = field(default_factory=dict)
    locality: Optional[str] = None
    mode_hint: Optional[RoutingMode] = None
    hard: bool = False


BUILTIN_PREFERENCES: Dict[str, PreferenceSpec] = {
    PreferenceId.PREFER_LOCAL.value: PreferenceSpec(
        id=PreferenceId.PREFER_LOCAL.value,
        name="Prefer Local",
        description="Favor local models to keep data on device.",
        weights={"local": 2.0, "cloud": 0.5, "offline": 1.5},
        mode_hint=RoutingMode.LOCAL_ONLY,
    ),
    PreferenceId.PREFER_CLOUD.value: PreferenceSpec(
        id=PreferenceId.PREFER_CLOUD.value,
        name="Prefer Cloud",
        description="Favor cloud models for maximum capability.",
        weights={"cloud": 2.0, "local": 0.5},
        mode_hint=RoutingMode.CLOUD_ONLY,
    ),
    PreferenceId.BALANCED.value: PreferenceSpec(
        id=PreferenceId.BALANCED.value,
        name="Balanced",
        description="No bias.",
        weights={},
    ),
    PreferenceId.OFFLINE_ONLY.value: PreferenceSpec(
        id=PreferenceId.OFFLINE_ONLY.value,
        name="Offline Required",
        description="Only models that work without network.",
        locality="local",
        hard=True,
    ),
    PreferenceId.LOWEST_VRAM.value: PreferenceSpec(
        id=PreferenceId.LOWEST_VRAM.value,
        name="Lowest VRAM",
        description="Minimize GPU memory usage.",
        weights={"low_memory": 2.5, "fast_response": 1.3},
    ),
    PreferenceId.FASTEST_RESPONSE.value: PreferenceSpec(
        id=PreferenceId.FASTEST_RESPONSE.value,
        name="Fastest Response",
        description="Minimize latency above all.",
        weights={"fast_response": 2.5, "low_memory": 1.3, "long_context": 0.7},
        mode_hint=RoutingMode.LOCAL_ONLY,
    ),
    PreferenceId.HIGHEST_QUALITY.value: PreferenceSpec(
        id=PreferenceId.HIGHEST_QUALITY.value,
        name="Highest Quality",
        description="Maximize output quality.",
        weights={"reasoning": 1.8, "coding": 1.6, "long_context": 1.5, "creative": 1.3},
    ),
    PreferenceId.CODING_OPTIMIZED.value: PreferenceSpec(
        id=PreferenceId.CODING_OPTIMIZED.value,
        name="Prefer Coding Models",
        description="Bias toward coding-capable models.",
        weights={"coding": 2.2, "reasoning": 1.4, "tool_calling": 1.3},
    ),
    PreferenceId.CREATIVE_WRITING.value: PreferenceSpec(
        id=PreferenceId.CREATIVE_WRITING.value,
        name="Prefer Creative Models",
        description="Bias toward creative writing models.",
        weights={"creative": 2.2, "summarization": 1.3},
    ),
    PreferenceId.REASONING_FIRST.value: PreferenceSpec(
        id=PreferenceId.REASONING_FIRST.value,
        name="Reasoning First",
        description="Prioritize reasoning strength.",
        weights={"reasoning": 2.4, "coding": 1.2},
    ),
    PreferenceId.ENERGY_SAVING.value: PreferenceSpec(
        id=PreferenceId.ENERGY_SAVING.value,
        name="Energy Saving",
        description="Prefer efficient, small models.",
        weights={"low_memory": 2.0, "fast_response": 1.8, "long_context": 0.6},
    ),
    PreferenceId.PERFORMANCE_MODE.value: PreferenceSpec(
        id=PreferenceId.PERFORMANCE_MODE.value,
        name="Performance Mode",
        description="Maximize throughput and capability.",
        weights={"reasoning": 1.6, "coding": 1.6, "long_context": 1.4, "fast_response": 1.2},
    ),
}


class PreferencesManager:
    """The preference engine: stores active preferences and emits change events."""

    def __init__(
        self,
        specs: Optional[Dict[str, PreferenceSpec]] = None,
        *,
        on_change: Optional[Callable[[List[str]], None]] = None,
    ) -> None:
        self._specs: Dict[str, PreferenceSpec] = dict(specs or BUILTIN_PREFERENCES)
        self._active: Set[str] = set()
        self._on_change = on_change

    # --- registry ---
    def register(self, spec: PreferenceSpec) -> None:
        self._specs[spec.id] = spec

    def get_spec(self, preference_id: str) -> Optional[PreferenceSpec]:
        return self._specs.get(preference_id)

    def available(self) -> List[PreferenceSpec]:
        return list(self._specs.values())

    # --- activation (runtime configurable) ---
    def set_preferences(self, preference_ids: List[str]) -> List[str]:
        """Replace the active preference set. Returns the validated active ids."""
        resolved = [pid for pid in preference_ids if pid in self._specs]
        if set(resolved) != self._active:
            self._active = set(resolved)
            if self._on_change is not None:
                self._on_change(self.active_ids())
        return self.active_ids()

    def activate(self, preference_id: str) -> None:
        if preference_id in self._specs and preference_id not in self._active:
            self._active.add(preference_id)
            if self._on_change is not None:
                self._on_change(self.active_ids())

    def deactivate(self, preference_id: str) -> None:
        if self._active.discard(preference_id) and self._on_change is not None:
            self._on_change(self.active_ids())

    def active_ids(self) -> List[str]:
        return [pid for pid in self._active if pid in self._specs]

    def active_specs(self) -> List[PreferenceSpec]:
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
        for spec in self.active_specs():
            if spec.hard and spec.locality:
                wanted = spec.locality
                candidates = [
                    c for c in candidates if c.profile.model.locality.value == wanted
                ]
        return candidates
