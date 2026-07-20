"""Configurable scoring engine for the AI Orchestrator (v0.6.1).

Turns a ranked :class:`~orchestrator.contracts.ModelCandidate` into a final
0..1 score by combining:

* capability match against the request's required/optional capabilities,
* the user/policy/profile capability weights,
* context-length fit for the estimated token budget,
* reliability (model health × execution history),
* latency sensitivity,
* execution-history penalties (recent failure, busy models).

Every term is normalized and deterministic. No model name is ever consulted.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .contracts import ALL_CAPABILITIES, Capability, ModelCandidate, TaskIntent


class ScoringEngine:
    """Assigns a 0..1 score to each candidate given intent + effective weights."""

    def __init__(self, history: Any = None) -> None:
        self._history = history

    # --- public API ---
    def score_candidate(
        self,
        candidate: ModelCandidate,
        intent: TaskIntent,
        weights: Optional[Dict[str, float]] = None,
        *,
        estimated_tokens: int = 0,
    ) -> float:
        """Compute and store ``candidate.score``; returns it."""
        w = weights or {cap: 1.0 for cap in ALL_CAPABILITIES}

        def adjusted(cap: str) -> float:
            return candidate.profile.capability(cap) * float(w.get(cap, 1.0))

        required = list(intent.required_capabilities)
        if required:
            cap_match = sum(adjusted(c) for c in required) / len(required)
            missing = [c for c in required if candidate.profile.capability(c) < 0.2]
            if missing:
                candidate.warnings.append(f"missing required capability: {','.join(missing)}")
        else:
            cap_match = 1.0
            missing = []

        optional = list(intent.optional_capabilities)
        opt_match = (sum(adjusted(c) for c in optional) / len(optional)) if optional else 0.0

        # Context-length fit.
        ctx = 1.0
        if estimated_tokens and estimated_tokens > 0:
            cl = candidate.profile.model.context_length or 0
            ctx = 1.0 if cl >= estimated_tokens else max(0.2, cl / estimated_tokens)

        # Reliability = model health × historical success rate.
        success_rate = self._success_rate(candidate.model_id)
        reliability = candidate.profile.reliability * success_rate

        # Latency factor (only meaningful when the request is latency sensitive).
        fast = candidate.profile.capability(Capability.FAST_RESPONSE)
        lat_factor = (0.5 + 0.5 * fast) if intent.is_latency_sensitive else 0.85

        score = 0.50 * cap_match + 0.15 * opt_match + 0.15 * ctx + 0.20 * reliability
        score *= lat_factor

        # Execution-history penalties.
        if self._history is not None:
            if self._safe("is_recently_failed", candidate.model_id):
                score *= 0.6
                candidate.warnings.append("recently failed")
            if self._safe("is_busy", candidate.model_id):
                score *= 0.7
                candidate.warnings.append("model busy")

        score = max(0.0, min(1.0, score))
        candidate.score = score
        candidate.capability_match = cap_match
        if missing:
            candidate.capability_match = 0.0
        return score

    def rank(self, candidates: List[ModelCandidate]) -> List[ModelCandidate]:
        """Return candidates sorted by score descending (stable)."""
        return sorted(candidates, key=lambda c: c.score, reverse=True)

    # --- helpers ---
    def _success_rate(self, model_id: str) -> float:
        if self._history is None:
            return 1.0
        rate = self._safe("failure_rate", model_id)
        if rate is None:
            return 1.0
        return max(0.0, 1.0 - float(rate))

    @staticmethod
    def _safe(method: str, model_id: str) -> Any:
        hist = getattr(ScoringEngine, "_inst", None)  # placeholder; replaced below
        return hist  # pragma: no cover


# The static _safe above is replaced by an instance-aware helper to keep the
# public surface simple. Define the real implementation on the instance.
def _history_call(self: ScoringEngine, method: str, model_id: str) -> Any:
    fn = getattr(self._history, method, None)
    if fn is None:
        return None
    try:
        return fn(model_id)
    except Exception:  # pragma: no cover - defensive
        return None


ScoringEngine._safe = _history_call  # type: ignore[assignment]
