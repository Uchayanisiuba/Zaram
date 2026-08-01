# backend/tests/discovery/test_freshness.py
from __future__ import annotations

import time

from runtime.discovery.contracts import DiscoveryMetadata, FreshnessLevel
from runtime.discovery.freshness import estimate_freshness


class TestFreshnessDetection:
    def test_unknown_when_no_dates(self):
        meta = DiscoveryMetadata(provider="x", url="u", title="t")
        level = estimate_freshness(meta, time.time())
        assert level == FreshnessLevel.UNKNOWN

    def test_recent_when_published_recently(self):
        now = time.time()
        published = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now - 300))
        meta = DiscoveryMetadata(provider="x", url="u", title="t", published=published)
        level = estimate_freshness(meta, now)
        assert level == FreshnessLevel.RECENT

    def test_static_when_published_old(self):
        now = time.time()
        published = time.strftime("%Y-%m-%d", time.gmtime(now - 86400 * 400))
        meta = DiscoveryMetadata(provider="x", url="u", title="t", published=published)
        level = estimate_freshness(meta, now)
        assert level == FreshnessLevel.STATIC

    def test_live_when_published_very_recent(self):
        now = time.time()
        published = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now - 30))
        meta = DiscoveryMetadata(provider="x", url="u", title="t", published=published)
        level = estimate_freshness(meta, now)
        assert level == FreshnessLevel.LIVE

    def test_prefers_last_modified(self):
        now = time.time()
        published = time.strftime("%Y-%m-%d", time.gmtime(now - 86400 * 400))
        modified = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now - 300))
        meta = DiscoveryMetadata(provider="x", url="u", title="t", published=published, last_modified=modified)
        level = estimate_freshness(meta, now)
        assert level == FreshnessLevel.RECENT
