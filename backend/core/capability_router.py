# backend/core/capability_router.py
"""Capability Resolution — resolves capability_ids to Runtime providers.

The CapabilityRouter is the kernel's capability resolution component.
It queries the RuntimeRegistry to find which runtime owns a given
capability, and returns that runtime instance.

No runtime directly calls another runtime.  All resolution goes
through the registry.
"""
from __future__ import annotations

import logging
from typing import Any

from core.contracts import Capability, Runtime
from core.registry import RuntimeRegistry

logger = logging.getLogger(__name__)


class CapabilityResolutionError(KeyError):
    """Raised when a capability cannot be resolved to a runtime."""


class IntentBasedRouter:
    """Routes intents to capability IDs based on intent type.

    Maps high-level intent types (e.g. 'search', 'reasoning') to
    canonical capability IDs that the CapabilityRouter can resolve.
    """

    INTENT_MAP: dict[str, list[str]] = {
        "search": ["knowledge.search", "discovery.search"],
        "reasoning": ["reasoning.generate"],
        "discovery": ["discovery.search"],
        "creative": ["reasoning.generate"],
        "conversation": ["memory.retrieve", "reasoning.generate"],
        "task": ["agent.execute", "reasoning.generate"],
        "agent": ["agent.execute"],
        "vision": ["vision.analyze"],
        "speech": ["speech.tts", "speech.stream"],
    }

    @classmethod
    def get_capability_candidates(cls, intent_type: str) -> list[str]:
        """Return ordered list of capability IDs for an intent type."""
        return list(cls.INTENT_MAP.get(intent_type, ["reasoning.generate"]))

    @classmethod
    def register_intent(cls, intent_type: str, capability_ids: list[str]) -> None:
        """Register or override an intent-to-capability mapping."""
        cls.INTENT_MAP[intent_type] = list(capability_ids)


class CapabilityRouter:
    """Resolves capabilities to Runtime providers via the Registry.

    The router maintains a local cache of capability → runtime_id
    mappings for fast lookup, and delegates to the registry for
    authoritative resolution.
    """

    def __init__(self, registry: RuntimeRegistry) -> None:
        self._registry = registry
        self._cache: dict[str, str] = {}  # capability_id -> runtime_id
        self._cache_valid = False

    def resolve(self, capability_id: str) -> Runtime:
        """Returns the Runtime instance that owns the requested capability.

        Raises
        ------
        CapabilityResolutionError
            If no runtime provides the capability.
        """
        runtime_id = self._cache.get(capability_id)
        if runtime_id is None:
            try:
                runtime = self._registry.get_runtime_for_capability(capability_id)
                runtime_id = runtime.get_runtime_id()
                self._cache[capability_id] = runtime_id
                return runtime
            except KeyError as exc:
                raise CapabilityResolutionError(
                    f"No runtime found for capability '{capability_id}'"
                ) from exc

        try:
            return self._registry.get_runtime(runtime_id)
        except KeyError:
            self._cache.pop(capability_id, None)
            try:
                runtime = self._registry.get_runtime_for_capability(capability_id)
                self._cache[capability_id] = runtime.get_runtime_id()
                return runtime
            except KeyError as exc:
                raise CapabilityResolutionError(
                    f"No runtime found for capability '{capability_id}'"
                ) from exc

    def try_resolve(self, capability_id: str) -> Runtime | None:
        """Attempt to resolve a capability, returning None on failure."""
        try:
            return self.resolve(capability_id)
        except CapabilityResolutionError:
            return None

    def resolve_all(self, capability_ids: list[str]) -> dict[str, Runtime]:
        """Resolve multiple capabilities at once.

        Returns a dict mapping capability_id to Runtime.  Capabilities
        that cannot be resolved are omitted.
        """
        results: dict[str, Runtime] = {}
        for cap_id in capability_ids:
            runtime = self.try_resolve(cap_id)
            if runtime is not None:
                results[cap_id] = runtime
        return results

    def can_resolve(self, capability_id: str) -> bool:
        """Check if a capability can be resolved without raising."""
        return self.try_resolve(capability_id) is not None

    def get_capability_info(self, capability_id: str) -> Capability | None:
        """Get metadata about a capability."""
        for cap in self._registry.list_capabilities():
            if cap.id == capability_id:
                return cap
        return None

    def list_resolvable_capabilities(self) -> list[str]:
        """List all capability IDs that can be resolved."""
        return [cap.id for cap in self._registry.list_capabilities()]

    def invalidate_cache(self) -> None:
        """Clear the capability resolution cache."""
        self._cache.clear()
        self._cache_valid = False

    def resolve_by_intent(self, intent_type: str) -> Runtime:
        """Resolve a runtime by intent type.

        Tries each candidate capability for the intent in order,
        returning the first runtime that can handle it.

        Raises
        ------
        CapabilityResolutionError
            If no runtime can handle any candidate capability.
        """
        candidates = IntentBasedRouter.get_capability_candidates(intent_type)
        last_error: Exception | None = None
        for cap_id in candidates:
            try:
                return self.resolve(cap_id)
            except CapabilityResolutionError as exc:
                last_error = exc
                continue
        raise CapabilityResolutionError(
            f"No runtime found for intent '{intent_type}' "
            f"(tried: {', '.join(candidates)})"
        ) from last_error

    def try_resolve_by_intent(self, intent_type: str) -> Runtime | None:
        """Attempt to resolve by intent, returning None on failure."""
        try:
            return self.resolve_by_intent(intent_type)
        except CapabilityResolutionError:
            return None

    def get_resolution_stats(self) -> dict[str, Any]:
        """Return statistics about capability resolution."""
        all_caps = self._registry.list_capabilities()
        return {
            "total_capabilities": len(all_caps),
            "cached_lookups": len(self._cache),
            "runtimes_registered": len(self._registry.list_runtimes()) if hasattr(self._registry, "list_runtimes") else 0,
        }
