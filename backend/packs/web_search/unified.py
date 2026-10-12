"""Unified web search interface combining all providers."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod

from core.egress import get_gate, DataClass, EgressGate
from backend.network.session import create_governed_session, ZaramGovernedSession


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    snippet: str
    provider: str
    score: float = 0.0
    published: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SearchProvider(ABC):
    """Abstract base class for search providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass
    
    @property
    @abstractmethod
    def rate_limit_rpm(self) -> int:
        """Requests per minute limit."""
        pass
    
    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Execute a search query."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check provider health."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close the provider."""
        pass


class WebSearchManager:
    """Manages multiple search providers with rate limiting and egress logging."""
    
    def __init__(self, egress_gate: EgressGate = None):
        self.providers: Dict[str, SearchProvider] = {}
        self.rate_limiters: Dict[str, Any] = {}
        self.api_keys: Dict[str, str] = {}
        self._egress_gate = egress_gate or get_gate()
        self._governed_sessions: Dict[str, ZaramGovernedSession] = {}
    
    def register_provider(self, provider: SearchProvider, api_key: str = None) -> None:
        """Register a search provider."""
        self.providers[provider.name] = provider
        if api_key:
            self.api_keys[provider.name] = api_key
    
    def set_egress_gate(self, gate: EgressGate) -> None:
        """Set the egress gate for logging."""
        self._egress_gate = gate
    
    def _get_governed_session(self, provider_name: str) -> ZaramGovernedSession:
        """Get or create a governed session for a provider."""
        if provider_name not in self._governed_sessions:
            self._governed_sessions[provider_name] = create_governed_session(
                self._egress_gate,
                source=provider_name,
            )
        return self._governed_sessions[provider_name]
    
    async def search(
        self,
        query: str,
        max_results: int = 10,
        providers: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """Search across all or specified providers."""
        if providers is None:
            providers = list(self.providers.keys())
        
        # Run searches in parallel
        tasks = []
        for provider_name in providers:
            if provider_name in self.providers:
                provider = self.providers[provider_name]
                tasks.append(self._search_with_rate_limit(provider, query, max_results))
        
        if not tasks:
            return []
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Merge and deduplicate results
        all_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                continue
            if isinstance(result, list):
                all_results.extend(result)
        
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)
        
        # Sort by score
        unique_results.sort(key=lambda r: r.score, reverse=True)
        return unique_results[:max_results]
    
    async def _search_with_rate_limit(
        self,
        provider: SearchProvider,
        query: str,
        max_results: int,
    ) -> List[SearchResult]:
        """Search with rate limiting."""
        # Check rate limit
        limiter = self.rate_limiters.get(provider.name)
        if limiter:
            await limiter.acquire()
        
        start = time.time()
        try:
            results = await provider.search(query, max_results)
            
            # Log to egress (the governed session already logs via gate, but we add search metadata)
            if self._egress_gate:
                latency_ms = (time.time() - start) * 1000
                self._log_egress(provider.name, query, results, latency_ms)
            
            return results
        except Exception as e:
            if self._egress_gate:
                self._log_egress_error(provider.name, query, str(e))
            raise
    
    def _log_egress(self, provider: str, query: str, results: List[SearchResult], latency_ms: float) -> None:
        """Log search request to egress with search metadata."""
        try:
            import json
            self._egress_gate.log.append(
                host=provider,
                method="POST",
                url=f"https://{provider}.com/search",
                body=json.dumps({"query": query}),
                decision="allowed",
                reason=f"web search via {provider}",
                source="web_search",
                kind=DataClass.PROMPT,
                byte_count=len(query) + sum(len(r.snippet) for r in results),
                meta={
                    "provider": provider,
                    "query": query[:100],
                    "result_count": len(results),
                    "latency_ms": latency_ms,
                },
            )
        except Exception:
            pass
    
    def _log_egress_error(self, provider: str, query: str, error: str) -> None:
        """Log search error to egress."""
        try:
            self._egress_gate.log.append(
                host=provider,
                method="POST",
                url=f"https://{provider}.com/search",
                body=query,
                decision="denied",
                reason=f"search error: {error}",
                source="web_search",
                kind=DataClass.PROMPT,
                byte_count=len(query),
                meta={"provider": provider, "error": error},
            )
        except Exception:
            pass
    
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all registered providers."""
        results = {}
        for name, provider in self.providers.items():
            results[name] = await provider.health_check()
        return results
    
    async def close_all(self) -> None:
        """Close all governed sessions."""
        for session in self._governed_sessions.values():
            await session.close()
        self._governed_sessions.clear()


async def create_web_search_manager(
    tavily_key: str = None,
    brave_key: str = None,
    searxng_url: str = None,
    egress_gate: EgressGate = None,
) -> WebSearchManager:
    """Create and configure the web search manager with governed sessions."""
    from .providers.tavily import TavilyProvider
    from .providers.brave import BraveProvider
    from .providers.searxng import SearXNGProvider
    from .rate_limiter import TokenBucketRateLimiter
    
    manager = WebSearchManager(egress_gate)
    
    # Tavily
    if tavily_key:
        tavily_session = manager._get_governed_session("tavily")
        tavily = TavilyProvider(tavily_key, tavily_session)
        manager.register_provider(tavily, tavily_key)
        manager.rate_limiters["tavily"] = TokenBucketRateLimiter(tavily.rate_limit_rpm)
    
    # Brave
    if brave_key:
        brave_session = manager._get_governed_session("brave")
        brave = BraveProvider(brave_key, brave_session)
        manager.register_provider(brave, brave_key)
        manager.rate_limiters["brave"] = TokenBucketRateLimiter(brave.rate_limit_rpm)
    
    # SearXNG
    if searxng_url:
        searxng_session = manager._get_governed_session("searxng")
        searxng = SearXNGProvider(searxng_url, searxng_session)
        manager.register_provider(searxng)
        manager.rate_limiters["searxng"] = TokenBucketRateLimiter(searxng.rate_limit_rpm)
    
    return manager