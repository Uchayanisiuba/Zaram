# backend/runtime/discovery/selector.py
from __future__ import annotations

from .contracts import DiscoveryIntent, DiscoveryProvider, DiscoveryRequest, RetrievalMode
from .registry import ProviderRegistry

_INTENT_PROVIDER_TYPES: dict[DiscoveryIntent, list[str]] = {
    DiscoveryIntent.ENCYCLOPEDIA: ["encyclopedia"],
    DiscoveryIntent.PROGRAMMING: ["programming"],
    DiscoveryIntent.NEWS: ["news"],
    DiscoveryIntent.GENERAL: ["news", "encyclopedia"],
    DiscoveryIntent.RSS: ["rss"],
    DiscoveryIntent.DYNAMIC: ["dynamic"],
    DiscoveryIntent.ACADEMIC: ["encyclopedia", "news"],
    DiscoveryIntent.SOCIAL: ["news"],
}


def select_providers(
    registry: ProviderRegistry, request: DiscoveryRequest
) -> list[DiscoveryProvider]:
    if request.providers:
        selected = []
        for pid in request.providers:
            provider = registry.get(pid)
            if provider and provider.is_available():
                selected.append(provider)
        return selected

    intent = request.intent or DiscoveryIntent.GENERAL
    provider_types = _INTENT_PROVIDER_TYPES.get(intent, ["duckduckgo"])

    selected: list[DiscoveryProvider] = []
    for ptype in provider_types:
        for provider in registry.get_by_type(ptype):
            if provider.is_available():
                selected.append(provider)
    return selected


def resolve_mode(request: DiscoveryRequest) -> RetrievalMode:
    return request.mode
