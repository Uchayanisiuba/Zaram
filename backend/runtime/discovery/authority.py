# backend/runtime/discovery/authority.py
from __future__ import annotations

from .contracts import AuthorityLevel, DiscoveryProvider, ProviderCapability


class AuthorityRegistry:
    """Registry for provider authority levels and authority-aware selection."""

    def __init__(self) -> None:
        self._provider_authority: dict[str, AuthorityLevel] = {}
        self._authority_scores: dict[str, float] = {}

    def register_provider(self, provider: DiscoveryProvider) -> None:
        level = provider.get_authority_level()
        self._provider_authority[provider.get_provider_id()] = level
        self._authority_scores[provider.get_provider_id()] = self._authority_to_score(level)

    def unregister_provider(self, provider_id: str) -> None:
        self._provider_authority.pop(provider_id, None)
        self._authority_scores.pop(provider_id, None)

    def get_authority(self, provider_id: str) -> AuthorityLevel:
        return self._provider_authority.get(provider_id, AuthorityLevel.UNKNOWN)

    def get_authority_score(self, provider_id: str) -> float:
        return self._authority_scores.get(provider_id, 0.0)

    def rank_providers(
        self,
        provider_candidates: list[ProviderCapability],
        required_authority: AuthorityLevel,
    ) -> list[ProviderCapability]:
        if required_authority == AuthorityLevel.UNKNOWN:
            return sorted(provider_candidates, key=lambda pc: -self._authority_to_score(pc.authority))
        filtered = [pc for pc in provider_candidates if self._authority_to_score(pc.authority) >= self._authority_to_score(required_authority)]
        return sorted(filtered, key=lambda pc: -self._authority_to_score(pc.authority))

    def _authority_to_score(self, level: AuthorityLevel) -> float:
        scores = {
            AuthorityLevel.GOVERNMENT: 1.0,
            AuthorityLevel.ACADEMIC: 0.9,
            AuthorityLevel.OFFICIAL_DOCS: 0.85,
            AuthorityLevel.WIKIPEDIA: 0.7,
            AuthorityLevel.GITHUB: 0.6,
            AuthorityLevel.COMMUNITY: 0.4,
            AuthorityLevel.BLOG: 0.3,
            AuthorityLevel.UNKNOWN: 0.1,
        }
        return scores.get(level, 0.1)
