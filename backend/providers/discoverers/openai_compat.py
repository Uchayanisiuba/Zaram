"""OpenAI-compatible discovery adapter for the provider layer (v0.6.0).

Many local AI servers (LM Studio, Ollama's OpenAI mode, LocalAI, ...) and
cloud endpoints expose the OpenAI ``/v1/models`` contract. This single
adapter covers all of them; the only difference is the base URL. LM Studio
is therefore just this adapter pointed at its default local port.

Like every provider discoverer, this module is the *only* place that knows the
OpenAI wire format, and it never hardcodes a model name.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

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

DEFAULT_BASE_URL = "http://127.0.0.1:1234"
LM_STUDIO_BASE_URL = "http://127.0.0.1:1234"
OPENAI_BASE_URL = "https://api.openai.com"

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]", "0.0.0.0"}


def _policy_for(base_url: str) -> Optional[DataPolicy]:
    """Infer a data policy from the URL, or decline to.

    This adapter is the one that genuinely cuts both ways — the same class is
    LM Studio on loopback and api.openai.com behind a bearer token — so the
    policy is read from the destination rather than from whichever caller
    remembered to pass it. Same reasoning as ``_get`` deferring to the egress
    gate a few lines down.

    Loopback is the only case that can be inferred, and only because it is
    structural: a request to 127.0.0.1 cannot leave. Everything else returns
    ``None``. That is not a gap to fill in later with a sensible guess — the
    terms under which a remote provider handles prompts are not derivable from
    its hostname, and a wrong guess here is a privacy claim the user acts on.
    Whoever registers a cloud provider passes ``data_policy`` explicitly.
    """
    host = urlparse(base_url).hostname
    if host and host.lower() in _LOOPBACK_HOSTS:
        return DataPolicy.NEVER_LEAVES_DEVICE
    return None


def _strip_version(base_url: str) -> str:
    """The API root without a trailing `/v1`, however the user wrote it."""
    trimmed = (base_url or "").strip().rstrip("/")
    return trimmed[: -len("/v1")] if trimmed.endswith("/v1") else trimmed


class OpenAICompatibleAdapter:
    """Discovers models from any OpenAI-compatible ``/v1/models`` endpoint."""

    def __init__(
        self,
        provider_id: str = "openai_compatible",
        *,
        base_url: str = DEFAULT_BASE_URL,
        kind: ProviderKind = ProviderKind.LOCAL_AI_SERVER,
        api_key: Optional[str] = None,
        data_policy: Optional[DataPolicy] = None,
    ) -> None:
        self.provider_id = provider_id
        self.kind = kind
        # `/v1` is stripped here and re-added by each path below, so a base URL
        # given either way reaches the same place. The engine already accepts
        # both — its docstring says so, because both are what providers print
        # in their own dashboards — and the two halves of the cloud path
        # disagreeing about one env var is how `ZARAM_OPENAI_ENDPOINT` ending
        # in `/v1` produced a working chat and a discovery that asked for
        # `/v1/v1/models`. Discovery then returned nothing, no cloud model was
        # known, and routing sent every message local without saying why.
        self.base_url = _strip_version(base_url)
        self._api_key = api_key
        self._data_policy = data_policy if data_policy is not None else _policy_for(base_url)

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
        # Through the gate. This discoverer is the one that genuinely cuts both
        # ways: pointed at LM Studio it is loopback and passes through unlogged,
        # pointed at api.openai.com it is egress carrying a bearer token. The
        # gate decides from the URL, so neither case depends on the caller
        # remembering which it is.
        from core.egress import get_gate

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return json.loads(
            get_gate().request(
                f"{self.base_url}{path}",
                timeout=timeout,
                headers=headers,
                source="providers.openai_compat",
            )
        )

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
            data_policy=self._data_policy,
            specialisation=specialisation_from_name(name),
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
