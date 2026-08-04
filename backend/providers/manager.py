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

#: Fraction of VRAM held back from the residency budget.
#:
#: Weights are not the whole cost — the KV cache grows with context length and
#: concurrency, and the display server wants a slice on a desktop GPU. A model
#: sized to exactly the free VRAM will fit at load and thrash a few thousand
#: tokens into a conversation, which is worse than not choosing it, because the
#: failure arrives later and looks like the product being slow.
#:
#: This number is a judgement, not a measurement, and it is the weakest part of
#: the heuristic. The honest fix is to compute the reserve from the model's own
#: context length; until someone measures it, this stays deliberately generous.
_KV_CACHE_RESERVE_FRACTION = 0.20


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

    def embedding_footprint_bytes(self) -> int:
        """What the embedding model claims, since it is resident continuously.

        Recall runs on every exchange, so the embedder is not an occasional
        tenant of VRAM — it is a permanent one. A chat model chosen as though it
        had the whole card to itself will evict it on the first message and get
        evicted back on the next recall, which is the swap this budget exists to
        prevent.

        Read from the catalog rather than from configuration: whichever
        embedding model discovery actually found is the one that will be
        resident, and the provider layer must not hardcode its name.
        """
        embedders = self.list_models(
            category=ModelCategory.EMBEDDING, available_only=True
        )
        return max((m.size_bytes or 0 for m in embedders), default=0)

    def resident_budget_bytes(self) -> Optional[int]:
        """VRAM a chat model may claim alongside the embedder, or ``None``.

        ``None`` means residency cannot be planned — no accelerator, or one
        whose capacity we cannot read (Metal, DirectML). It is not a budget of
        zero, and callers must not treat it as one: on those machines the fit
        test is skipped rather than failed, because inventing a number here is
        the false-zero bug that ``HardwareProfile.vram_known`` exists to stop.
        """
        hardware = self.hardware_profile()
        if not hardware.vram_known:
            return None

        vram = hardware.vram_bytes or 0
        reserve = int(vram * _KV_CACHE_RESERVE_FRACTION)
        return max(vram - self.embedding_footprint_bytes() - reserve, 0)

    def model_fits_resident(self, model: ModelInfo) -> Optional[bool]:
        """Whether ``model`` can be co-resident with the embedder.

        Three answers, and the third matters: ``True``, ``False``, and ``None``
        for "cannot be determined" — either the budget is unknown or the model
        does not report a size. ``None`` is never promoted to ``True``.
        """
        budget = self.resident_budget_bytes()
        if budget is None or model.size_bytes is None:
            return None
        return model.size_bytes <= budget

    def select_default_model(
        self, *, category: ModelCategory = ModelCategory.LLM
    ) -> Optional[ModelInfo]:
        """The model Zaram may route to without the user having chosen one.

        Returns ``None`` rather than a fallback when nothing qualifies. A
        caller with no model is a caller that says so; a caller handed a model
        the user never consented to is a Rule 5 violation that looks like a
        working feature.

        Three criteria, in this order, because that is the order in which
        getting it wrong hurts:

        1. **Does it fit alongside the embedding model.** A model that forces a
           swap is never the default, even when it is the largest thing
           installed — the cost lands on every single exchange, and it is the
           kind of slowness users attribute to the product rather than to a
           setting. This is a hard gate, not a preference.
        2. **Is it general-purpose.** A coding fine-tune answering general
           questions is a category error that shows up as oddly-shaped answers
           rather than as an obvious failure, so it is harder to diagnose than
           it looks.
        3. **Size**, last, as a rough stand-in for capability. It is the axis
           that matters least and the only one that is easy to measure, which is
           precisely why it used to be the only one considered.

        Size-first selection is what picked a 9 GB coding model on a 12 GB card
        for general chat: largest wins, and both of the criteria that should
        have vetoed it were absent.
        """
        candidates = [
            m
            for m in self.list_models(category=category, available_only=True)
            if m.selectable_by_default
        ]

        # Hard gate. `None` (unknown fit) survives it — an unmeasurable machine
        # must not be left with no default at all — but ranks below a model we
        # positively know fits, so "we could not check" never outranks "it fits".
        candidates = [m for m in candidates if self.model_fits_resident(m) is not False]
        if not candidates:
            return None

        def rank(model: ModelInfo) -> tuple:
            fits = self.model_fits_resident(model)
            return (
                0 if fits is True else 1,
                0 if model.is_general_purpose else 1,
                0 if model.locality is CapabilityLocality.LOCAL else 1,
                -(model.size_bytes or 0),
                model.id,  # deterministic across equal candidates
            )

        return sorted(candidates, key=rank)[0]

    def rejected_default_candidates(
        self, *, category: ModelCategory = ModelCategory.LLM
    ) -> List[tuple[ModelInfo, str]]:
        """Available models excluded from auto-selection, each with the reason.

        "Show routing decisions in plain language" needs the models that were
        *not* picked as much as the one that was, and needs to distinguish the
        reasons: a user told "no default model" deserves to know whether that
        was their data policy or their VRAM, since only one of those is
        something they can act on.
        """
        rejected: List[tuple[ModelInfo, str]] = []
        for model in self.list_models(category=category, available_only=True):
            if not model.selectable_by_default:
                reason = (
                    "data policy is unknown"
                    if not model.data_policy_known
                    else "provider logs and trains on prompts"
                )
                rejected.append((model, reason))
            elif self.model_fits_resident(model) is False:
                rejected.append(
                    (model, "does not fit alongside the embedding model")
                )
        return rejected

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
