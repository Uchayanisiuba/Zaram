"""Provider/discoverer registry for the AI Garage (v0.6.0).

The :class:`GarageRegistry` is the *configuration* of what the Garage scans.
It holds the registered model providers and the injected voice / runtime /
personality / hardware sources. Adding a new provider never touches the
manager or the scanner — callers just ``register_model_provider``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .contracts import ProviderKind, ProviderSummary

logger = logging.getLogger(__name__)


class GarageRegistry:
    """In-memory registry of Garage discovery sources."""

    def __init__(self) -> None:
        # provider_id -> ModelProviderAdapter
        self._model_providers: Dict[str, Any] = {}
        self._voice_source: Optional[Any] = None
        self._runtime_source: Optional[Any] = None
        self._personality_source: Optional[Any] = None
        self._hardware_profiler: Optional[Any] = None

    # --- model providers ---
    def register_model_provider(self, provider: Any) -> None:
        provider_id = getattr(provider, "provider_id", None)
        if not provider_id:
            raise ValueError("Model provider must define 'provider_id'")
        if provider_id in self._model_providers:
            raise ValueError(f"Model provider '{provider_id}' is already registered")
        self._model_providers[provider_id] = provider
        logger.info("Registered Garage model provider '%s'", provider_id)

    def remove_model_provider(self, provider_id: str) -> bool:
        removed = self._model_providers.pop(provider_id, None) is not None
        if removed:
            logger.info("Removed Garage model provider '%s'", provider_id)
        return removed

    def get_model_provider(self, provider_id: str) -> Any:
        if provider_id not in self._model_providers:
            raise KeyError(f"Model provider '{provider_id}' is not registered")
        return self._model_providers[provider_id]

    def list_model_providers(self) -> List[Any]:
        return list(self._model_providers.values())

    def count_model_providers(self) -> int:
        return len(self._model_providers)

    def is_registered(self, provider_id: str) -> bool:
        return provider_id in self._model_providers

    # --- injected sources ---
    def set_voice_source(self, source: Any) -> None:
        self._voice_source = source

    def get_voice_source(self) -> Optional[Any]:
        return self._voice_source

    def set_runtime_source(self, source: Any) -> None:
        self._runtime_source = source

    def get_runtime_source(self) -> Optional[Any]:
        return self._runtime_source

    def set_personality_source(self, source: Any) -> None:
        self._personality_source = source

    def get_personality_source(self) -> Optional[Any]:
        return self._personality_source

    def set_hardware_profiler(self, profiler: Any) -> None:
        self._hardware_profiler = profiler

    def get_hardware_profiler(self) -> Optional[Any]:
        return self._hardware_profiler

    # --- discovery metadata ---
    def provider_specs(self) -> List[ProviderSummary]:
        specs: List[ProviderSummary] = []
        for provider in self._model_providers.values():
            try:
                specs.append(ProviderSummary.from_dict(provider.to_dict()))
            except Exception as exc:
                logger.warning("Provider spec failed: %s", exc)
        return specs

    def capabilities(self) -> List[str]:
        return [
            "garage.discover_models",
            "garage.discover_voices",
            "garage.discover_runtimes",
            "garage.profile_hardware",
        ]

    def registered_provider_kinds(self) -> Dict[str, str]:
        kinds: Dict[str, str] = {}
        for provider in self._model_providers.values():
            kind = getattr(provider, "kind", ProviderKind.LOCAL_LLM)
            kinds[getattr(provider, "provider_id", "?")] = kind.value
        return kinds
