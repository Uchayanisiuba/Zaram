# backend/runtime/discovery/capability_router.py
from __future__ import annotations

from .contracts import (
    Capability,
    DiscoveryProvider,
    ProviderCapability,
    QueryAnalysis,
)


class CapabilityRouter:
    """Routes discovery requests by capability instead of provider identity."""

    def __init__(self) -> None:
        self._capability_index: dict[Capability, list[ProviderCapability]] = {}

    def register_provider(self, provider: DiscoveryProvider) -> None:
        caps = provider.get_capabilities()
        authority = provider.get_authority_level()
        pc = ProviderCapability(
            provider_id=provider.get_provider_id(),
            capabilities=caps,
            authority=authority,
            cost=provider.estimated_cost(),
            avg_latency_ms=provider.estimated_latency_ms(),
            success_rate=provider.estimated_confidence(),
            availability=1.0 if provider.is_available() else 0.0,
        )
        for cap in caps:
            self._capability_index.setdefault(cap, []).append(pc)

    def unregister_provider(self, provider_id: str) -> None:
        for cap, entries in list(self._capability_index.items()):
            self._capability_index[cap] = [e for e in entries if e.provider_id != provider_id]

    def route(self, analysis: QueryAnalysis) -> list[ProviderCapability]:
        candidates: list[ProviderCapability] = []
        seen: set[str] = set()
        for cap in analysis.expected_capabilities:
            for pc in self._capability_index.get(cap, []):
                if pc.provider_id not in seen and pc.availability > 0:
                    candidates.append(pc)
                    seen.add(pc.provider_id)
        candidates.sort(key=lambda pc: (-pc.authority.value.count(".") if hasattr(pc.authority, "value") else 0, pc.avg_latency_ms))
        return candidates

    def get_capabilities_for_provider(self, provider_id: str) -> list[Capability]:
        for entries in self._capability_index.values():
            for entry in entries:
                if entry.provider_id == provider_id:
                    return entry.capabilities
        return []
