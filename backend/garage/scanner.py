"""Discovery scanner for the AI Garage (v0.6.0).

:class:`GarageScanner` is the *engine* that performs discovery. It reads the
sources configured in :class:`~garage.registry.GarageRegistry` and runs
each one in isolation: a single failing provider (e.g. Ollama offline)
never breaks the rest of the scan. The scanner holds no persistent state —
it returns fresh results that the manager stores.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .contracts import HardwareProfile, ModelInfo, RuntimeInfo, VoiceInfo
from .discoverers.voices import VoiceRegistryAdapter

logger = logging.getLogger(__name__)


class GarageScanner:
    """Runs discovery against every configured source."""

    def __init__(self, registry: Any) -> None:
        self._registry = registry

    # --- model providers ---
    async def scan_models(self, *, timeout: float = 2.0) -> List[ModelInfo]:
        models: List[ModelInfo] = []
        for provider in self._registry.list_model_providers():
            try:
                found = await provider.discover_models(timeout=timeout)
                models.extend(found or [])
            except Exception as exc:
                logger.warning(
                    "Model scan failed for provider '%s': %s",
                    getattr(provider, "provider_id", "?"),
                    exc,
                )
        return models

    # --- voices ---
    async def scan_voices(self) -> List[VoiceInfo]:
        source = self._registry.get_voice_source()
        if source is None:
            return []
        try:
            adapter = VoiceRegistryAdapter(source)
            raw = await adapter.list_voices()
            return adapter.to_voice_infos(raw)
        except Exception as exc:
            logger.warning("Voice scan failed: %s", exc)
            return []

    # --- runtimes ---
    def scan_runtimes(self) -> List[RuntimeInfo]:
        source = self._registry.get_runtime_source()
        if source is None:
            return []
        try:
            return source.snapshot_runtimes()
        except Exception as exc:
            logger.warning("Runtime scan failed: %s", exc)
            return []

    # --- personalities ---
    def scan_personalities(self) -> List[Dict[str, Any]]:
        source = self._registry.get_personality_source()
        if source is None:
            return []
        try:
            return source.list_personalities()
        except Exception as exc:
            logger.warning("Personality scan failed: %s", exc)
            return []

    # --- hardware ---
    def profile_hardware(self) -> HardwareProfile:
        profiler = self._registry.get_hardware_profiler()
        if profiler is None:
            # Safe fallback: a profile reporting nothing discovered.
            return HardwareProfile()
        try:
            return profiler.profile()
        except Exception as exc:
            logger.warning("Hardware profiling failed: %s", exc)
            return HardwareProfile()

    # --- health ---
    async def health(self) -> Dict[str, Any]:
        per_provider: Dict[str, Any] = {}
        for provider in self._registry.list_model_providers():
            pid = getattr(provider, "provider_id", "?")
            try:
                per_provider[pid] = await provider.health()
            except Exception as exc:  # pragma: no cover - defensive
                per_provider[pid] = {"available": False, "error": str(exc)}
        return {"providers": per_provider}
