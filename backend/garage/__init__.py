"""Zaram AI Garage foundation (v0.6.0).

Zaram's control center for AI resources. The Garage discovers and catalogs
every AI capability available to the system — local LLMs, local AI servers,
installed voices, installed personalities, active runtimes, and (future)
skills and plugins — without manual configuration.

It owns no engines. Every concrete source lives behind an adapter in
:mod:`garage.discoverers`; the Garage itself is provider-agnostic,
dependency-injected, event-driven, and fully offline-testable.

Public API
----------
- :class:`GarageRuntime` — Kernel-facing runtime + default provider wiring.
- :class:`GarageManager` — discovery orchestration + read-only accessors.
- :class:`GarageRegistry` — discovery source configuration.
- :class:`GarageScanner` — executes discovery against each source.
- :class:`GarageModelCatalog` — generic model store.
- :class:`GarageHealth` / :class:`GarageHealthAggregator` — health reports.
- :mod:`garage.contracts` — generic, modality-agnostic data shapes.
- :mod:`garage.discoverers` — Ollama / LM Studio / OpenAI / voice /
  runtime / personality / hardware adapters.
- :mod:`garage.api` — read-only FastAPI router.
"""

from __future__ import annotations

from .api import router as api_router
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
from .health import GarageHealth, GarageHealthAggregator
from .manager import GarageManager
from .model_catalog import GarageModelCatalog
from .registry import GarageRegistry
from .runtime import RUNTIME_ID, RUNTIME_VERSION, GarageRuntime
from .scanner import GarageScanner

__all__ = [
    "GarageRuntime",
    "RUNTIME_ID",
    "RUNTIME_VERSION",
    "GarageManager",
    "GarageRegistry",
    "GarageScanner",
    "GarageModelCatalog",
    "GarageHealth",
    "GarageHealthAggregator",
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
