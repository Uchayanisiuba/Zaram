"""Media provider registry (v0.5.5).

Maps provider names to :class:`~media.providers.MediaProvider` instances and
exposes provider lookup, capability discovery, and health reporting. It is
modality-agnostic: it never inspects *what* a provider does, only that it
honors the :class:`MediaProvider` contract.

Future media runtimes (vision, avatar, camera, ...) register here exactly like
voice does, with no changes to the registry itself.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from .contracts import (
    HealthStatus,
    MediaCapability,
    MediaProviderSpec,
    MediaType,
)
from .providers import MediaProvider

logger = logging.getLogger(__name__)


class MediaRegistry:
    """In-memory registry of media providers and their capabilities."""

    def __init__(self) -> None:
        # name -> MediaProvider instance
        self._providers: Dict[str, MediaProvider] = {}

    # --- registration ---
    def register_provider(self, name: str, provider: MediaProvider) -> None:
        """Register a live :class:`MediaProvider` instance under ``name``."""
        if name in self._providers:
            raise ValueError(f"Media provider '{name}' is already registered")
        if not isinstance(provider, MediaProvider):
            raise TypeError(
                f"'{provider!r}' is not a MediaProvider instance"
            )
        self._providers[name] = provider
        logger.info("Registered media provider '%s'", name)

    def remove_provider(self, name: str) -> bool:
        """Remove a provider. Returns True if it was registered."""
        removed = self._providers.pop(name, None) is not None
        if removed:
            logger.info("Removed media provider '%s'", name)
        return removed

    def discover(self, providers: Dict[str, MediaProvider]) -> None:
        """Register a batch of providers (convenience for startup wiring)."""
        for name, provider in providers.items():
            self.register_provider(name, provider)

    # --- retrieval ---
    def is_registered(self, name: str) -> bool:
        return name in self._providers

    def get_provider(self, name: str) -> MediaProvider:
        if name not in self._providers:
            raise KeyError(f"Media provider '{name}' is not registered")
        return self._providers[name]

    def list_providers(self) -> List[str]:
        return list(self._providers)

    def count(self) -> int:
        return len(self._providers)

    # --- capability discovery ---
    def capabilities(self) -> List[MediaCapability]:
        """All capabilities advertised by every registered provider."""
        result: List[MediaCapability] = []
        for name, provider in self._providers.items():
            try:
                for cap in provider.capabilities():
                    result.append(cap)
            except Exception as exc:  # defensive: one bad provider ≠ whole registry
                logger.warning(
                    "Provider '%s' failed capability discovery: %s", name, exc
                )
        return result

    def capabilities_for_type(self, media_type: Union[MediaType, str]) -> List[MediaCapability]:
        """Capabilities that serve a given media type."""
        target = (
            media_type
            if isinstance(media_type, MediaType)
            else MediaType.from_value(media_type)
        )
        return [c for c in self.capabilities() if c.media_type == target]

    def providers_for_type(self, media_type: Union[MediaType, str]) -> List[str]:
        """Names of providers that serve a given media type."""
        target = (
            media_type
            if isinstance(media_type, MediaType)
            else MediaType.from_value(media_type)
        )
        names: List[str] = []
        for name, provider in self._providers.items():
            try:
                if target in provider.media_types():
                    names.append(name)
            except Exception:
                continue
        return names

    def media_types_served(self) -> List[MediaType]:
        """Distinct media types covered by the registry."""
        seen: set[MediaType] = set()
        for cap in self.capabilities():
            seen.add(cap.media_type)
        return sorted(seen, key=lambda m: m.value)

    # --- specs / health ---
    def specs(self) -> List[MediaProviderSpec]:
        """Serializable descriptions of all registered providers."""
        specs: List[MediaProviderSpec] = []
        for name, provider in self._providers.items():
            try:
                specs.append(
                    MediaProviderSpec(
                        name=name,
                        media_types=list(provider.media_types()),
                        runtime_id=getattr(provider, "runtime_id", "media"),
                        locality=provider.locality(),
                        available=True,
                    )
                )
            except Exception as exc:
                logger.warning("Provider '%s' spec failed: %s", name, exc)
        return specs

    async def health(self) -> Dict[str, Any]:
        """Aggregate health across all providers."""
        per_provider: Dict[str, Any] = {}
        available = 0
        for name, provider in self._providers.items():
            try:
                report = await provider.health_check()
            except Exception as exc:  # pragma: no cover - defensive
                report = {"available": False, "error": str(exc)}
            per_provider[name] = report
            if report.get("available"):
                available += 1

        total = len(self._providers)
        status = (
            HealthStatus.HEALTHY
            if total and available == total
            else HealthStatus.DEGRADED
            if available > 0
            else HealthStatus.UNAVAILABLE
            if total
            else HealthStatus.UNKNOWN
        )
        return {
            "provider_count": total,
            "available_count": available,
            "status": status.value,
            "providers": per_provider,
        }
