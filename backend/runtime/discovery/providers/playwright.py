# backend/runtime/discovery/providers/playwright.py
from __future__ import annotations

from typing import Any

from ..contracts import (
    AuthorityLevel,
    Capability,
    DiscoveryMetadata,
    DiscoveryResult,
    FreshnessLevel,
)
from .base import BaseDiscoveryProvider


class PlaywrightProvider(BaseDiscoveryProvider):
    """Browser-based fallback provider for dynamic sites.

    Used ONLY when API providers fail or dynamic websites are required.
    Never used as the first choice.
    """

    def __init__(self) -> None:
        super().__init__(
            "playwright",
            "dynamic",
            cache_ttl=300,
            capabilities=[Capability.WEB, Capability.DOCUMENTATION],
            authority=AuthorityLevel.BLOG,
            cost=0.0,
            avg_latency_ms=2000.0,
        )
        self._available = False
        self._last_error = "Playwright not installed"

    async def discover(
        self, request: Any, context: Any
    ) -> list[DiscoveryResult]:
        if not self._available:
            return []

        try:
            from playwright.async_api import async_playwright  # type: ignore

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(f"https://duckduckgo.com/?q={request.query}", timeout=15000)
                text = await page.content()
                await browser.close()

            metadata = DiscoveryMetadata(
                provider="playwright",
                url=f"https://duckduckgo.com/?q={request.query}",
                title=request.query,
                language="en",
                confidence=0.5,
                freshness=FreshnessLevel.LIVE,
                raw_metadata={"content_length": len(text)},
            )
            return [DiscoveryResult(
                content=text[:1000],
                summary=text[:280],
                metadata=metadata,
                confidence=0.5,
                freshness=FreshnessLevel.LIVE,
                provider="playwright",
                retrieval_time=0.0,
            )]
        except Exception as exc:
            self._record_failure(str(exc))
            return []

    def is_available(self) -> bool:
        return self._available
