"""Discovers Claude models from Anthropic's ``/v1/models``.

The other half of `runtimes/models/engines/anthropic_engine.py`: the engine
answers, this says what can. Same posture as `OpenAICompatibleAdapter` —
every request goes through the egress gate (discovery against a cloud
provider *is* egress, carrying a key), the call is synchronous and run in a
thread so a host whose policy is *ask* cannot freeze the event loop, and a
provider that will not answer yields no models rather than an exception.

**Every current Claude model accepts images**, so `supports_vision` is set
on each; that is a fact about the family, not a guess about an entry. The
context window comes from `max_input_tokens` when the listing carries it,
and stays unknown otherwise — never a default, for the reason
`core/context_budget.py` gives.

**No data policy is inferred.** Same rule as the OpenAI-compatible adapter:
the terms a remote provider handles prompts under are not derivable from
its hostname, and a wrong guess is a privacy claim the user acts on.
Unknown terms keep the model out of automatic routing
(`selectable_by_default`) while leaving it available to choose by name,
exactly as OpenRouter's models are today.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from ..contracts import (
    CapabilityLocality,
    DataPolicy,
    HealthStatus,
    ModelCategory,
    ModelInfo,
    ProviderKind,
    ProviderSummary,
    specialisation_from_name,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicAdapter:
    """Lists what an Anthropic key can reach."""

    def __init__(
        self,
        provider_id: str = "anthropic",
        *,
        base_url: str = DEFAULT_BASE_URL,
        api_key: Optional[str] = None,
        data_policy: Optional[DataPolicy] = None,
    ) -> None:
        self.provider_id = provider_id
        self.kind = ProviderKind.CLOUD_API
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._data_policy = data_policy

    async def discover_models(self, *, timeout: float = 2.0) -> List[ModelInfo]:
        try:
            payload = await asyncio.to_thread(self._get, "/v1/models?limit=100", timeout=timeout) or {}
        except Exception as exc:  # noqa: BLE001 - discovery must not fail the scan
            logger.warning(
                "%s discovery failed (provider unavailable): %s",
                self.provider_id, exc, extra={"provider": self.provider_id},
            )
            return []
        models: List[ModelInfo] = []
        for entry in payload.get("data", []) or []:
            model_id = entry.get("id") if isinstance(entry, dict) else None
            if not model_id:
                continue
            models.append(self._to_model(str(model_id), entry))
        return models

    async def health(self) -> Dict[str, Any]:
        try:
            await asyncio.to_thread(self._get, "/v1/models?limit=1", timeout=2.0)
            return {"available": True, "provider": self.provider_id, "endpoint": self.base_url}
        except Exception as exc:  # noqa: BLE001
            return {"available": False, "provider": self.provider_id, "error": str(exc)}

    def resident_models(self, *, timeout: float = 1.0) -> Optional[Dict[str, Optional[int]]]:
        """Nothing is resident anywhere near this machine. An empty map, which
        is a fact, rather than ``None``, which would mean "could not tell"."""
        return {}

    def to_dict(self) -> Dict[str, Any]:
        return ProviderSummary(
            id=self.provider_id,
            kind=self.kind,
            endpoint=self.base_url,
            health_status=HealthStatus.UNKNOWN,
        ).to_dict()

    # --- internals ---
    def _get(self, path: str, *, timeout: float) -> Optional[Dict[str, Any]]:
        """Through the gate, synchronously, from a thread — see the
        OpenAI-compatible adapter's `_get` for why each of those three."""
        from core.egress import get_gate

        headers = {"anthropic-version": ANTHROPIC_VERSION}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return json.loads(
            get_gate().request(
                f"{self.base_url}{path}",
                timeout=timeout,
                headers=headers,
                source="providers.anthropic",
            )
        )

    def _to_model(self, model_id: str, entry: Dict[str, Any]) -> ModelInfo:
        window = entry.get("max_input_tokens")
        return ModelInfo(
            id=f"{self.provider_id}:{model_id}",
            display_name=str(entry.get("display_name") or model_id),
            provider=self.provider_id,
            provider_kind=self.kind,
            category=ModelCategory.LLM,
            context_length=window if isinstance(window, int) and window > 0 else None,
            capabilities={"completion", "vision", "tools"},
            supports_vision=True,
            supports_tools=True,
            locality=CapabilityLocality.CLOUD,
            available=True,
            health_status=HealthStatus.HEALTHY,
            endpoint=self.base_url,
            data_policy=self._data_policy,
            specialisation=specialisation_from_name(model_id),
            metadata={"raw_id": model_id, "created_at": entry.get("created_at")},
        )
