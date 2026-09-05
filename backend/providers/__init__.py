"""Zaram provider layer (v0.6.0).

Zaram's control center for AI resources. The provider layer discovers and catalogs
every AI capability available to the system — local LLMs, local AI servers,
installed voices, installed personalities, active runtimes, and (future)
skills and plugins — without manual configuration.

It owns no engines. Every concrete source lives behind an adapter in
:mod:`providers.discoverers`; the provider layer itself is provider-agnostic,
dependency-injected, event-driven, and fully offline-testable.

Public API
----------
- :class:`ProvidersRuntime` — Kernel-facing runtime + default provider wiring.
- :class:`ProviderManager` — discovery orchestration + read-only accessors.
- :class:`ProviderRegistry` — discovery source configuration.
- :class:`ProviderScanner` — executes discovery against each source.
- :class:`ModelCatalog` — generic model store.
- :mod:`providers.catalogue` — the dated manifest of pickable providers, with
  the ones Zaram cannot call today graded down rather than hidden. Data only:
  it describes providers, reads no keys, and reaches no network.
- :class:`ProviderHealth` / :class:`ProviderHealthAggregator` — health reports.
- :mod:`providers.contracts` — generic, modality-agnostic data shapes.
- :mod:`providers.discoverers` — Ollama / LM Studio / OpenAI / voice /
  runtime / personality / hardware adapters.
- :mod:`providers.api` — read-only FastAPI router.
"""

from __future__ import annotations

from .api import router as api_router
from .catalogue import PROVIDERS as PROVIDER_CATALOGUE
from .catalogue import ProviderEntry
from .contracts import (
    HardwareProfile,
    HealthStatus,
    ModelCategory,
    ModelInfo,
    ProviderKind,
    ProviderSummary,
    RuntimeInfo,
    VoiceInfo,
)
from .health import ProviderHealth, ProviderHealthAggregator
from .manager import ProviderManager
from .model_catalog import ModelCatalog
from .registry import ProviderRegistry
from .runtime import RUNTIME_ID, RUNTIME_VERSION, ProvidersRuntime
from .scanner import ProviderScanner

__all__ = [
    "ProvidersRuntime",
    "RUNTIME_ID",
    "RUNTIME_VERSION",
    "ProviderManager",
    "ProviderRegistry",
    "ProviderScanner",
    "ModelCatalog",
    "PROVIDER_CATALOGUE",
    "ProviderEntry",
    "ProviderHealth",
    "ProviderHealthAggregator",
    "api_router",
    # contracts
    "ModelInfo",
    "VoiceInfo",
    "RuntimeInfo",
    "HardwareProfile",
    "ProviderSummary",
    "ModelCategory",
    "ProviderKind",
    "HealthStatus",
]
