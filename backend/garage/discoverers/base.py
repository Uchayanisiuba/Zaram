"""Discovery adapter protocols for the AI Garage (v0.6.0).

Each source of AI resources is abstracted behind a Protocol. Concrete
adapters (Ollama, LM Studio, file-based personalities, Kernel registry,
...) implement these interfaces. The Garage never references a concrete
engine outside its own adapter, so new providers plug in without touching
:class:`~garage.manager.GarageManager` or the runtime.
"""

from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable

from ..contracts import (
    HardwareProfile,
    ModelInfo,
    ProviderKind,
    RuntimeInfo,
    VoiceInfo,
)


@runtime_checkable
class ModelProviderAdapter(Protocol):
    """A source of local or cloud models (Ollama, LM Studio, OpenAI-compatible)."""

    provider_id: str
    kind: ProviderKind

    async def discover_models(self, *, timeout: float = 2.0) -> List[ModelInfo]:
        """Return the models this provider currently exposes (may be empty)."""
        ...

    async def health(self) -> Dict[str, Any]:
        """Return a structured health report (must include ``available``)."""
        ...

    def to_dict(self) -> Dict[str, Any]:
        """Serializable description of the provider for the registry."""
        ...


@runtime_checkable
class VoiceSourceAdapter(Protocol):
    """A source of installed voices (e.g. a VoiceManager / provider registry)."""

    async def list_voices(self) -> Dict[str, Any]:
        """Return a mapping of voice id -> metadata."""
        ...


@runtime_checkable
class RuntimeSourceAdapter(Protocol):
    """A source of installed Zaram runtimes (e.g. the Kernel RuntimeRegistry)."""

    def snapshot_runtimes(self) -> List[RuntimeInfo]:
        """Return the currently registered runtimes."""
        ...


@runtime_checkable
class PersonalitySourceAdapter(Protocol):
    """A source of installed personalities (e.g. a JSON profile file)."""

    def list_personalities(self) -> List[Dict[str, Any]]:
        """Return the installed personalities as a list of dicts."""
        ...


@runtime_checkable
class HardwareProfiler(Protocol):
    """Produces a point-in-time :class:`HardwareProfile` of the host."""

    def profile(self) -> HardwareProfile:
        """Gather CPU/RAM/GPU/VRAM/OS/storage + acceleration availability."""
        ...
