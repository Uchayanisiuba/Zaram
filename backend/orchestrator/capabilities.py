"""Capability scoring for the AI Orchestrator (v0.6.1).

Every discovered model is turned into a :class:`~orchestrator.contracts.ModelProfile`
carrying *normalized* (0..1) capability scores. The scores are derived purely
from the provider-agnostic :class:`garage.contracts.ModelInfo` fields — never
from a model name. This is what lets the scoring engine rank models without
ever knowing *who* they are.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from garage.contracts import (
    CapabilityLocality,
    HealthStatus,
    ModelCategory,
    ModelInfo,
)

from .contracts import Capability, ModelProfile

# Neutral baseline capabilities for a generic LLM when a provider has not
# tagged it with explicit skill tokens. Specialized tokens always win (1.0).
_LLM_BASELINE: Dict[str, float] = {
    Capability.REASONING: 0.6,
    Capability.CODING: 0.5,
    Capability.CREATIVE: 0.6,
    Capability.TRANSLATION: 0.6,
    Capability.SUMMARIZATION: 0.6,
    Capability.VISION: 0.0,
    Capability.SPEECH: 0.0,
    Capability.EMBEDDING: 0.0,
    Capability.TOOL_CALLING: 0.0,
}

_CATEGORY_BASELINE: Dict[ModelCategory, Dict[str, float]] = {
    ModelCategory.LLM: dict(_LLM_BASELINE),
    ModelCategory.EMBEDDING: {Capability.EMBEDDING: 1.0},
    ModelCategory.VISION: {Capability.VISION: 1.0, Capability.MULTIMODAL: 1.0},
    ModelCategory.TTS: {Capability.SPEECH: 1.0},
    ModelCategory.STT: {Capability.SPEECH: 1.0},
    ModelCategory.IMAGE: {Capability.VISION: 1.0},
    ModelCategory.VIDEO: {Capability.VISION: 1.0},
    ModelCategory.OTHER: dict(_LLM_BASELINE),
}

# Capability tokens a provider may advertise in ModelInfo.capabilities.
_TOKEN_MAP: Dict[str, str] = {
    "reasoning": Capability.REASONING,
    "coding": Capability.CODING,
    "code": Capability.CODING,
    "creative": Capability.CREATIVE,
    "writing": Capability.CREATIVE,
    "translation": Capability.TRANSLATION,
    "translate": Capability.TRANSLATION,
    "summarization": Capability.SUMMARIZATION,
    "summary": Capability.SUMMARIZATION,
    "vision": Capability.VISION,
    "multimodal": Capability.MULTIMODAL,
    "speech": Capability.SPEECH,
    "tts": Capability.SPEECH,
    "stt": Capability.SPEECH,
    "embedding": Capability.EMBEDDING,
    "tools": Capability.TOOL_CALLING,
    "tool_calling": Capability.TOOL_CALLING,
    "tool_use": Capability.TOOL_CALLING,
    "fast": Capability.FAST_RESPONSE,
    "low_memory": Capability.LOW_MEMORY,
}


def _long_context_score(context_length: Optional[int]) -> float:
    if not context_length or context_length <= 0:
        return 0.5  # unknown context → neutral
    return min(1.0, context_length / 128_000.0)


def _size_based_score(size_bytes: Optional[int], ceiling: float) -> float:
    if not size_bytes or size_bytes <= 0:
        return 0.5
    return max(0.0, min(1.0, 1.0 - (size_bytes / ceiling)))


def compute_capability_scores(model: ModelInfo) -> Dict[str, float]:
    """Return normalized (0..1) capability scores for ``model``."""
    scores: Dict[str, float] = {}
    baseline = _CATEGORY_BASELINE.get(model.category, dict(_LLM_BASELINE))
    for cap, value in baseline.items():
        scores[cap] = float(value)

    # Overlay explicit capability tokens from the provider (always authoritative).
    for token in model.capabilities:
        mapped = _TOKEN_MAP.get(str(token).lower())
        if mapped:
            scores[mapped] = 1.0

    # Structured boolean flags always win over inference.
    if model.supports_vision:
        scores[Capability.VISION] = 1.0
        scores[Capability.MULTIMODAL] = 1.0
    if model.supports_tools:
        scores[Capability.TOOL_CALLING] = 1.0
    if model.supports_embedding:
        scores[Capability.EMBEDDING] = 1.0

    # Locality-derived capabilities.
    if model.locality == CapabilityLocality.LOCAL:
        scores[Capability.LOCAL] = 1.0
        scores[Capability.OFFLINE] = 1.0 if model.available else 0.4
    elif model.locality == CapabilityLocality.CLOUD:
        scores[Capability.CLOUD] = 1.0

    # Derived performance/size capabilities.
    scores[Capability.LONG_CONTEXT] = _long_context_score(model.context_length)
    scores[Capability.LOW_MEMORY] = _size_based_score(model.size_bytes, 16_000_000_000)
    scores[Capability.FAST_RESPONSE] = _size_based_score(model.size_bytes, 30_000_000_000)
    if "fast" in {str(t).lower() for t in model.capabilities}:
        scores[Capability.FAST_RESPONSE] = 1.0

    # Ensure every canonical capability has a value.
    for cap in (
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
    ):
        scores.setdefault(cap, 0.0)
    return scores


def _reliability(model: ModelInfo) -> float:
    if not model.available:
        return 0.2
    if model.health_status == HealthStatus.HEALTHY:
        return 1.0
    if model.health_status == HealthStatus.DEGRADED:
        return 0.7
    return 0.5


def _latency_estimate(model: ModelInfo) -> float:
    base = 150.0
    size = model.size_bytes or 0
    latency = base + (size / 1_000_000_000.0) * 300.0
    if "fast" in {str(t).lower() for t in model.capabilities}:
        latency *= 0.5
    return round(latency, 1)


def build_model_profile(model: ModelInfo) -> ModelProfile:
    """Build a :class:`ModelProfile` (scores + resource estimates) for ``model``."""
    scores = compute_capability_scores(model)
    return ModelProfile(
        model=model,
        scores=scores,
        latency_estimate_ms=_latency_estimate(model),
        vram_requirement_bytes=model.size_bytes or 0,
        ram_requirement_bytes=model.size_bytes or 0,
        reliability=_reliability(model),
    )
