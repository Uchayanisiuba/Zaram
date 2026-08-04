"""Orchestration manager for the provider layer (v0.6.0).

:class:`ProviderManager` is the single control point the API and runtime talk
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
from .health import ProviderHealth, ProviderHealthAggregator
from .model_catalog import ModelCatalog
from .registry import ProviderRegistry
from .scanner import ProviderScanner

logger = logging.getLogger(__name__)


class ProviderManager:
    """Discovers and serves Zaram's AI resources."""

    def __init__(
        self,
        registry: Optional[ProviderRegistry] = None,
        scanner: Optional[ProviderScanner] = None,
        *,
        event_bus: Optional[EventBus] = None,
        aggregator: Optional[ProviderHealthAggregator] = None,
    ) -> None:
        self.registry = registry or ProviderRegistry()
        self.scanner = scanner or ProviderScanner(self.registry)
        self._event_bus = event_bus
        self._aggregator = aggregator or ProviderHealthAggregator()

        self.catalog = ModelCatalog()
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
            "Provider scan complete: %d models, %d voices, %d runtimes, %d personalities",
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

    def select_default_model(
        self, *, category: ModelCategory = ModelCategory.LLM
    ) -> Optional[ModelInfo]:
        """The model Zaram may route to without the user having chosen one.

        Returns ``None`` rather than a fallback when nothing qualifies. A
        caller with no model is a caller that says so; a caller handed a model
        the user never consented to is a Rule 5 violation that looks like a
        working feature.

        Eligibility is ``ModelInfo.selectable_by_default`` and nothing else, so
        the rule lives with the field it depends on: a model whose data policy
        is unknown or ``LOGGED_AND_TRAINED_ON`` is not offered here, however
        capable or convenient it is.
        """
        candidates = [
            m
            for m in self.list_models(category=category, available_only=True)
            if m.selectable_by_default
        ]
        if not candidates:
            return None

        # Local first — Rule 1 means we never route to paid inference on our own
        # initiative — then largest, as a stand-in for most capable. Ties break
        # on id so boot is deterministic rather than dict-ordered.
        def rank(model: ModelInfo) -> tuple:
            return (
                0 if model.locality is CapabilityLocality.LOCAL else 1,
                -(model.size_bytes or 0),
                model.id,
            )

        return sorted(candidates, key=rank)[0]

    def rejected_default_candidates(
        self, *, category: ModelCategory = ModelCategory.LLM
    ) -> List[ModelInfo]:
        """Available models excluded from auto-selection, for explaining why.

        "Show routing decisions in plain language" needs the models that were
        *not* picked as much as the one that was — a user with three cloud
        models installed and no default deserves to be told it was the data
        policy, not a bug.
        """
        return [
            m
            for m in self.list_models(category=category, available_only=True)
            if not m.selectable_by_default
        ]

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
                    source_runtime="providers",
                    event_type="providers.scanned",
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
