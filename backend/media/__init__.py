"""Zaram Media Runtime foundation (v0.5.5).

A provider-independent, dependency-injected, event-driven runtime that owns
*all* media subsystems. It holds no implementations — it orchestrates providers
(Voice, Vision, Avatar, Camera, Screen, Video, ...) through a single uniform
abstraction.

This milestone establishes the foundation only. The Voice Runtime remains the
first registered media capability; it is discovered at startup and never moved
or rewritten.

Public API
----------
- :class:`MediaAsset` — generic, modality-agnostic media handle.
- :class:`MediaSession` / :class:`MediaSessionStore` — active media tracking.
- :class:`MediaProvider` — base contract for every future media backend.
- :class:`MediaRegistry` — provider + capability discovery + health.
- :class:`MediaManager` — session/stream lifecycle, routing, orchestration.
- :class:`MediaRuntime` — Kernel-facing runtime + Voice Runtime integration.
- :mod:`media.events` / :mod:`media.health` — events and health reporting.
"""

from __future__ import annotations

from .assets import MediaAsset
from .contracts import (
    HealthStatus,
    MediaCapability,
    MediaLocality,
    MediaProviderSpec,
    MediaState,
    MediaType,
)
from .events import (
    ALL_MEDIA_EVENTS,
    MEDIA_CHUNK,
    MEDIA_COMPLETED,
    MEDIA_ERROR,
    MEDIA_HEALTH_CHANGED,
    MEDIA_REGISTERED,
    MEDIA_STARTED,
    MEDIA_STOPPED,
    create_media_event,
)
from .health import MediaHealth, MediaHealthAggregator
from .manager import MediaManager
from .providers import MediaProvider
from .registry import MediaRegistry
from .runtime import RUNTIME_ID, RUNTIME_VERSION, MediaRuntime
from .session import MediaSession, MediaSessionStore

__all__ = [
    # runtime
    "MediaRuntime",
    "RUNTIME_ID",
    "RUNTIME_VERSION",
    # manager / registry
    "MediaManager",
    "MediaRegistry",
    # models
    "MediaAsset",
    "MediaSession",
    "MediaSessionStore",
    "MediaProvider",
    # contracts
    "MediaType",
    "MediaState",
    "MediaLocality",
    "HealthStatus",
    "MediaCapability",
    "MediaProviderSpec",
    # events
    "create_media_event",
    "ALL_MEDIA_EVENTS",
    "MEDIA_STARTED",
    "MEDIA_STOPPED",
    "MEDIA_CHUNK",
    "MEDIA_COMPLETED",
    "MEDIA_ERROR",
    "MEDIA_REGISTERED",
    "MEDIA_HEALTH_CHANGED",
    # health
    "MediaHealth",
    "MediaHealthAggregator",
]
