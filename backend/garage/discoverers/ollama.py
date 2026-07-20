"""Ollama discovery adapter for the AI Garage (v0.6.0).

This is the *only* module in the Garage that knows about Ollama. It queries
the Ollama REST API and translates responses into provider-independent
:class:`~garage.contracts.ModelInfo` records. No model name is hardcoded;
everything is learned from ``/api/tags`` and ``/api/show``.

All network access is failure-safe and timeout-bounded so the Garage never
blocks or crashes when Ollama is not installed.
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

DEFAULT_BASE_URL = "http://127.0.0.1:11434"


class OllamaAdapter:
    """Discovers models served by a local Ollama instance."""

    provider_id = "ollama"
    kind = ProviderKind.LOCAL_LLM

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    # --- ModelProviderAdapter surface ---
    async def discover_models(self, *, timeout: float = 2.0) -> List[ModelInfo]:
        try:
            tags = self._get("/api/tags", timeout=timeout) or {}
        except Exception as exc:
            logger.warning(
                "Ollama discovery failed (provider unavailable): %s", exc,
                extra={"provider": self.provider_id},
            )
            return []

        models: List[ModelInfo] = []
        for entry in tags.get("models", []) or []:
            name = entry.get("name") or entry.get("model")
            if not name:
                continue
            models.append(self._to_model(name, entry, timeout=timeout))
        return models

    async def health(self) -> Dict[str, Any]:
        try:
            self._get("/api/tags", timeout=2.0)
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
        response = requests.get(f"{self.base_url}{path}", timeout=timeout)
        response.raise_for_status()
        return response.json()

    def _to_model(
        self, name: str, tag: Dict[str, Any], *, timeout: float
    ) -> ModelInfo:
        details = tag.get("details", {}) or {}
        capabilities: set[str] = set()
        context_length: Optional[int] = None
        size = tag.get("size")

        # Enrich with /api/show when reachable (best-effort).
        try:
            show = self._post("/api/show", {"model": name}, timeout=timeout) or {}
            caps = show.get("capabilities") or []
            capabilities.update(str(c).lower() for c in caps)
            model_info = show.get("model_info", {}) or {}
            ctx = model_info.get("context_length")
            if isinstance(ctx, int):
                context_length = ctx
            q = (
                show.get("details", {}).get("quantization_level")
                or model_info.get("quantization_level")
            )
            if q:
                details = {**details, "quantization_level": q}
        except Exception as exc:
            logger.debug(
                "Ollama /api/show failed for %s: %s", name, exc,
                extra={"provider": self.provider_id},
            )

        is_embedding = "embedding" in capabilities
        category = ModelCategory.EMBEDDING if is_embedding else ModelCategory.LLM

        quantization = details.get("quantization_level")
        parameter_size = details.get("parameter_size")

        return ModelInfo(
            id=f"{self.provider_id}:{name}",
            display_name=name,
            provider=self.provider_id,
            provider_kind=self.kind,
            category=category,
            size_bytes=size if isinstance(size, int) else None,
            context_length=context_length,
            quantization=quantization if isinstance(quantization, str) else None,
            capabilities=capabilities,
            supports_vision="vision" in capabilities,
            supports_embedding="embedding" in capabilities,
            supports_tools="tools" in capabilities,
            recommended_use=(
                "semantic search / vector embeddings"
                if is_embedding
                else                 "local chat, reasoning and tool use"
            ),
            memory_requirement_bytes=size if isinstance(size, int) else None,
            locality=CapabilityLocality.LOCAL,
            available=True,
            health_status=HealthStatus.HEALTHY,
            endpoint=self.base_url,
            metadata={
                "parameter_size": parameter_size,
                "family": details.get("family"),
                "format": details.get("format"),
            },
        )

    def _post(
        self, path: str, payload: Dict[str, Any], *, timeout: float
    ) -> Optional[Dict[str, Any]]:
        response = requests.post(f"{self.base_url}{path}", json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
