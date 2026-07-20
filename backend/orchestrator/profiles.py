"""Project profile engine for the AI Orchestrator (v0.6.1).

A project profile represents the user's current work (Game Development,
Python Development, Research, ...). The active profile *biases* routing toward
the capabilities that work tends to need — it never hard-codes a model. The
future UI/Settings Runtime will call :meth:`ProfileEngine.set_profile`.

Each :class:`ProfileSpec` is a map of capability biases plus an optional
locality/mode hint. Adding a new profile is a one-line registration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .contracts import RoutingMode, merge_weights


class ProfileId(str, Enum):
    GAME_DEV = "game_development"
    PYTHON_DEV = "python_development"
    WEB_DEV = "web_development"
    RESEARCH = "research"
    WRITING = "writing"
    BUSINESS = "business"
    GENERAL = "general_assistant"
    EDUCATION = "education"
    UNREAL_ENGINE = "unreal_engine"
    BLENDER = "blender"
    CONTENT_CREATION = "content_creation"


@dataclass
class ProfileSpec:
    """A project profile that biases capability weighting."""

    id: str
    name: str
    description: str
    biases: Dict[str, float] = field(default_factory=dict)
    locality: Optional[str] = None
    mode_hint: Optional[RoutingMode] = None


BUILTIN_PROFILES: Dict[str, ProfileSpec] = {
    ProfileId.GAME_DEV.value: ProfileSpec(
        id=ProfileId.GAME_DEV.value,
        name="Game Development",
        description="Bias toward creative, vision, and code-capable models.",
        biases={"creative": 1.6, "vision": 1.5, "coding": 1.4, "multimodal": 1.4},
    ),
    ProfileId.PYTHON_DEV.value: ProfileSpec(
        id=ProfileId.PYTHON_DEV.value,
        name="Python Development",
        description="Bias toward strong coding and reasoning models.",
        biases={"coding": 2.0, "reasoning": 1.6, "tool_calling": 1.4},
    ),
    ProfileId.WEB_DEV.value: ProfileSpec(
        id=ProfileId.WEB_DEV.value,
        name="Web Development",
        description="Bias toward coding and tool-capable models.",
        biases={"coding": 2.0, "tool_calling": 1.5, "creative": 1.2},
    ),
    ProfileId.RESEARCH.value: ProfileSpec(
        id=ProfileId.RESEARCH.value,
        name="Research",
        description="Bias toward reasoning, long context, and summarization.",
        biases={"reasoning": 1.8, "long_context": 2.0, "summarization": 1.6},
    ),
    ProfileId.WRITING.value: ProfileSpec(
        id=ProfileId.WRITING.value,
        name="Writing",
        description="Bias toward creative and summarization models.",
        biases={"creative": 2.0, "summarization": 1.6},
    ),
    ProfileId.BUSINESS.value: ProfileSpec(
        id=ProfileId.BUSINESS.value,
        name="Business",
        description="Balanced, with reasoning and summarization bias.",
        biases={"reasoning": 1.4, "summarization": 1.4, "translation": 1.3},
    ),
    ProfileId.GENERAL.value: ProfileSpec(
        id=ProfileId.GENERAL.value,
        name="General Assistant",
        description="No bias.",
        biases={},
    ),
    ProfileId.EDUCATION.value: ProfileSpec(
        id=ProfileId.EDUCATION.value,
        name="Education",
        description="Bias toward clear reasoning and summarization.",
        biases={"reasoning": 1.5, "summarization": 1.5, "translation": 1.3},
    ),
    ProfileId.UNREAL_ENGINE.value: ProfileSpec(
        id=ProfileId.UNREAL_ENGINE.value,
        name="Unreal Engine",
        description="Bias toward code, vision, and creative models.",
        biases={"coding": 1.8, "vision": 1.6, "creative": 1.5, "multimodal": 1.5},
    ),
    ProfileId.BLENDER.value: ProfileSpec(
        id=ProfileId.BLENDER.value,
        name="Blender",
        description="Bias toward vision and creative models.",
        biases={"vision": 1.8, "creative": 1.7, "multimodal": 1.6},
    ),
    ProfileId.CONTENT_CREATION.value: ProfileSpec(
        id=ProfileId.CONTENT_CREATION.value,
        name="Content Creation",
        description="Bias toward creative, vision, and speech models.",
        biases={"creative": 2.0, "vision": 1.6, "speech": 1.4, "multimodal": 1.5},
    ),
}


class ProfileEngine:
    """Tracks the active project profile and exposes its routing biases."""

    def __init__(
        self,
        specs: Optional[Dict[str, ProfileSpec]] = None,
        *,
        on_change: Optional[Callable[[Optional[str]], None]] = None,
    ) -> None:
        self._specs: Dict[str, ProfileSpec] = dict(specs or BUILTIN_PROFILES)
        self._active: Optional[str] = ProfileId.GENERAL.value
        self._on_change = on_change

    # --- registry ---
    def register(self, spec: ProfileSpec) -> None:
        self._specs[spec.id] = spec

    def get_spec(self, profile_id: str) -> Optional[ProfileSpec]:
        return self._specs.get(profile_id)

    def available(self) -> List[ProfileSpec]:
        return list(self._specs.values())

    # --- activation (runtime configurable) ---
    def set_profile(self, profile_id: Optional[str]) -> Optional[str]:
        if profile_id is not None and profile_id not in self._specs:
            raise ValueError(f"Unknown profile '{profile_id}'")
        if profile_id != self._active:
            self._active = profile_id
            if self._on_change is not None:
                self._on_change(self._active)
        return self._active

    def active_id(self) -> Optional[str]:
        return self._active

    def active_spec(self) -> Optional[ProfileSpec]:
        return self._specs.get(self._active) if self._active else None

    # --- derived selection signals ---
    def biases(self) -> Dict[str, float]:
        spec = self.active_spec()
        return dict(spec.biases) if spec else {}

    def weights(self) -> Dict[str, float]:
        spec = self.active_spec()
        return merge_weights([spec.biases]) if spec and spec.biases else {}

    def mode_hint(self) -> Optional[RoutingMode]:
        spec = self.active_spec()
        return spec.mode_hint if spec else None
