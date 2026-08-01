# backend/runtime/discovery/rewriter.py
from __future__ import annotations

from .contracts import Capability, QueryRewrite


class QueryRewriter:
    """Generates provider-specific optimized queries."""

    def rewrite(self, query: str, provider_id: str, capabilities: list[Capability]) -> QueryRewrite:
        rewritten = self._apply_rewrite_rules(query, provider_id, capabilities)
        capability = capabilities[0] if capabilities else Capability.WEB
        return QueryRewrite(
            original_query=query,
            rewritten_query=rewritten,
            provider_id=provider_id,
            capability=capability,
        )

    def rewrite_batch(
        self,
        query: str,
        providers: list[tuple[str, list[Capability]]],
    ) -> list[QueryRewrite]:
        return [self.rewrite(query, pid, caps) for pid, caps in providers]

    def _apply_rewrite_rules(self, query: str, provider_id: str, capabilities: list[Capability]) -> str:
        if provider_id == "github":
            return f"{query} repository"
        if provider_id == "wikipedia":
            return query
        if provider_id == "duckduckgo":
            return f"{query} latest"
        if provider_id == "rss":
            return f"{query} feed"
        if provider_id == "playwright":
            return query
        return query
