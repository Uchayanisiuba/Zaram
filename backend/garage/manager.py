"""Orchestration manager for the AI Garage (v0.6.0).

:class:`GarageManager` is the single control point the API and runtime talk
to. It owns the model catalog and the caches of voices / runtimes /
personalities / hardware, drives discovery through the scanner, and exposes
pure, offline, read-only accessors. It never imports a concrete engine.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.event_bus import EventBus

from .contracts import (
    CapabilityLocality,
    HardwareProfile,
    ModelCategory,
    ModelInfo,
    ProviderKind,
    RuntimeInfo,
    VoiceInfo,
)
from .health import GarageHealth, GarageHealthAggregator
from .model_catalog import GarageModelCatalog
from .registry import GarageRegistry
from .scanner import GarageScanner

logger = logging.getLogger(__name__)


class GarageManager:
    """Discovers and serves Zaram's AI resources."""

    def __init__(
        self,
        registry: Optional[GarageRegistry] = None,
        scanner: Optional[GarageScanner] = None,
        *,
        event_bus: Optional[EventBus] = None,
        aggregator: Optional[GarageHealthAggregator] = None,
    ) -> None:
        self.registry = registry or GarageRegistry()
        self.scanner = scanner or GarageScanner(self.registry)
        self._event_bus = event_bus
        self._aggregator = aggregator or GarageHealthAggregator()

        self.catalog = GarageModelCatalog()
        self._voices: List[VoiceInfo] = []
        self._runtimes: List[RuntimeInfo] = []
        self._personalities: List[Dict[str, Any]] = []
        self._hardware: HardwareProfile = HardwareProfile()
        self._scanned = False

    # --- discovery lifecycle ---
    async def refresh(self, *, timeout: float = 2.0) -> None:
        """Re-run discovery across every configured source and cache the results."""
        models = await self.scanner.scan_models(timeout=timeout)
        self.catalog.clear()
        self.catalog.upsert_all(models)

        self._voices = await self.scanner.scan_voices()
        self._runtimes = self.scanner.scan_runtimes()
        self._personalities = self.scanner.scan_personalities()
        self._hardware = self.scanner.profile_hardware()

        self._scanned = True
        self._publish_scanned()
        logger.info(
            "Garage scan complete: %d models, %d voices, %d runtimes, %d personalities",
            self.catalog.count(),
            len(self._voices),
            len(self._runtimes),
            len(self._personalities),
        )

    async def ensure_scanned(self) -> None:
        """Lazily perform one scan if none has happened yet."""
        if not self._scanned:
            await self.refresh()

    # --- model read API ---
    def list_models(
        self,
        *,
        category: Optional[ModelCategory] = None,
        capability: Optional[str] = None,
        locality: Optional[CapabilityLocality] = None,
        available_only: bool = False,
        provider: Optional[str] = None,
    ) -> List[ModelInfo]:
        return self.catalog.filter(
            category=category,
            capability=capability,
            locality=locality,
            available_only=available_only,
            provider=provider,
        )

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        return self.catalog.get(model_id)

    # --- provider read API ---
    def list_providers(self) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []
        for provider in self.registry.list_model_providers():
            pid = getattr(provider, "provider_id", "?")
            models = self.catalog.filter(provider=pid)
            available = any(m.available for m in models)
            try:
                base = provider.to_dict()
            except Exception:
                base = {
                    "id": pid,
                    "kind": getattr(provider, "kind", ProviderKind.LOCAL_LLM).value,
                }
            base["model_count"] = len(models)
            base["available"] = available
            base["health_status"] = "healthy" if available else "unavailable"
            specs.append(base)
        return specs

    # --- voices / runtimes / personalities / hardware ---
    def list_voices(self) -> List[VoiceInfo]:
        return list(self._voices)

    def list_runtimes(self) -> List[RuntimeInfo]:
        return list(self._runtimes)

    def list_personalities(self) -> List[Dict[str, Any]]:
        return list(self._personalities)

    def hardware_profile(self) -> HardwareProfile:
        return self._hardware

    # --- comprehensive health report ---
    def health_report(self) -> Dict[str, Any]:
        provider_specs = self.list_providers()
        health = self._aggregator.aggregate(
            runtime_status="ready" if self._scanned else "uninitialized",
            provider_specs=provider_specs,
            scanner_health={"providers": {}},
            model_count=self.catalog.count(),
            available_models=self.catalog.available_count(),
            voice_count=len(self._voices),
            runtime_count=len(self._runtimes),
            personality_count=len(self._personalities),
            categories=list(self.catalog.by_category().keys()),
            hardware=self._hardware.to_dict(),
        )
        return health.to_dict()

    # --- events ---
    def _publish_scanned(self) -> None:
        if self._event_bus is None:
            return
        try:
            from core.event_bus import ZaramEvent

            self._event_bus.publish(
                ZaramEvent(
                    source_runtime="garage",
                    event_type="garage.scanned",
                    data={
                        "models": self.catalog.count(),
                        "voices": len(self._voices),
                        "runtimes": len(self._runtimes),
                        "personalities": len(self._personalities),
                    },
                )
            )
        except Exception:  # pragma: no cover - defensive
            return
