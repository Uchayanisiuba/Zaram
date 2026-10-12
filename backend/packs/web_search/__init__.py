# backend/packs/web_search/__init__.py
"""Web Search Pack - Trio of search providers with rate limiting and egress logging."""

from .unified import WebSearchManager, SearchResult
from .providers.tavily import TavilyProvider
from .providers.brave import BraveProvider
from .providers.searxng import SearXNGProvider
from .rate_limiter import TokenBucketRateLimiter
from .api_keys import APIKeyManager

__all__ = [
    "WebSearchManager",
    "SearchResult",
    "TavilyProvider",
    "BraveProvider",
    "SearXNGProvider",
    "TokenBucketRateLimiter",
    "APIKeyManager",
]