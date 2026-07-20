"""OpenAI-compatible discovery adapter for the AI Garage (v0.6.0).

Many local AI servers (LM Studio, Ollama's OpenAI mode, LocalAI, ...) and
cloud endpoints expose the OpenAI ``/v1/models`` contract. This single
adapter covers all of them; the only difference is the base URL. LM Studio
is therefore just this adapter pointed at its default local port.

Like every Garage discoverer, this module is the *only* place that knows the
OpenAI wire format, and it never hardcodes a model name.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

from ..contracts import (
    CapabilityLocality,
    HealthStatus,
    ModelCategory,
    ModelInfo,
    ProviderKind,
    ProviderSummary,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:1234"
LM_STUDIO_BASE_URL = "http://127.0.0.1:1234"
OPENAI_BASE_URL = "https://api.openai.com"


class OpenAICompatibleAdapter:
    """Discovers models from any OpenAI-compatible ``/v1/models`` endpoint."""

    def __init__(
        self,
        provider_id: str = "openai_compatible",
        *,
        base_url: str = DEFAULT_BASE_URL,
        kind: ProviderKind = ProviderKind.LOCAL_AI_SERVER,
        api_key: Optional[str] = None,
    ) -> None:
        self.provider_id = provider_id
        self.kind = kind
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key

    # --- ModelProviderAdapter surface ---
    async def discover_models(self, *, timeout: float = 2.0) -> List[ModelInfo]:
        try:
            payload = self._get("/v1/models", timeout=timeout) or {}
        except Exception as exc:
            logger.warning(
                "%s discovery failed (provider unavailable): %s",
                self.provider_id,
                exc,
                extra={"provider": self.provider_id},
            )
            return []

        models: List[ModelInfo] = []
        for entry in payload.get("data", []) or []:
            model_id = entry.get("id")
            if not model_id:
                continue
            models.append(self._to_model(model_id, entry))
        return models

    async def health(self) -> Dict[str, Any]:
        try:
            self._get("/v1/models", timeout=2.0)
            return {"available": True, "provider": self.provider_id, "endpoint": self.base_url}
        except Exception as exc:
            return {"available": False, "provider": self.provider_id, "error": str(exc)}

    def to_dict(self) -> Dict[str, Any]:
        return ProviderSummary(
            id=self.provider_id,
            kind=self.kind,
            endpoint=self.base_url,
            health_status=HealthStatus.UNKNOWN,
        ).to_dict()

    # --- internals ---
    def _get(self, path: str, *, timeout: float) -> Optional[Dict[str, Any]]:
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        response = requests.get(
            f"{self.base_url}{path}", timeout=timeout, headers=headers
        )
        response.raise_for_status()
        return response.json()

    def _to_model(self, model_id: str, entry: Dict[str, Any]) -> ModelInfo:
        # OpenAI's /v1/models exposes only an id + ownership; deeper metadata
        # (size, context, quantization, capabilities) is not part of the spec,
        # so we record what we know and leave the rest unknown.
        owned_by = entry.get("owned_by", "unknown")
        name = model_id.split("/")[-1]
        return ModelInfo(
            id=f"{self.provider_id}:{model_id}",
            display_name=name,
            provider=self.provider_id,
            provider_kind=self.kind,
            category=ModelCategory.LLM,
            version=entry.get("version", ""),
            supports_tools=True,  # OpenAI-compatible servers generally support tools
            locality=(
                CapabilityLocality.CLOUD
                if self.kind is ProviderKind.CLOUD_API
                else CapabilityLocality.LOCAL
            ),
            available=True,
            health_status=HealthStatus.HEALTHY,
            endpoint=self.base_url,
            metadata={"owned_by": owned_by, "raw_id": model_id},
        )


class LMStudioAdapter(OpenAICompatibleAdapter):
    """LM Studio's local OpenAI-compatible server (auto-detected by the runtime)."""

    def __init__(self, base_url: str = LM_STUDIO_BASE_URL) -> None:
        super().__init__(
            provider_id="lm_studio",
            base_url=base_url,
            kind=ProviderKind.LOCAL_AI_SERVER,
        )
