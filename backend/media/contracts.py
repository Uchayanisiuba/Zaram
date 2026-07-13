"""Shared contracts for the Zaram Media Runtime (v0.5.5).

This module defines the generic, provider-independent vocabulary used by every
media subsystem (voice, vision, avatar, camera, screen, video, ...). It owns
*no implementations* — only the data shapes and enums that the rest of the
media runtime depends on.

The Media Runtime is intentionally decoupled from the Voice Runtime: nothing
here references Kokoro, audio, or VoiceProvider. Voice simply becomes the
first registered media capability.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MediaType(Enum):
    """Modality of a media asset or capability.

    Kept open-ended so future subsystems (vision, avatar, sensor, ...) fit
    without changing the core model.
    """

    UNKNOWN = "unknown"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"
    ANIMATION = "animation"
    SENSOR = "sensor"
    DOCUMENT = "document"
    TEXT = "text"

    @classmethod
    def from_value(cls, value: Optional[str]) -> "MediaType":
        """Best-effort coercion from a string; falls back to UNKNOWN."""
        if not value:
            return cls.UNKNOWN
        try:
            return cls(str(value).lower())
        except ValueError:
            return cls.UNKNOWN


class MediaState(Enum):
    """Lifecycle state of a media session or stream."""

    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


class MediaLocality(Enum):
    """Where a media provider actually runs."""

    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"
    REMOTE_DEVICE = "remote_device"


class HealthStatus(Enum):
    """Aggregated health of a media component."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"

    @classmethod
    def from_value(cls, value: Optional[str]) -> "HealthStatus":
        if not value:
            return cls.UNKNOWN
        try:
            return cls(str(value).lower())
        except ValueError:
            return cls.UNKNOWN


@dataclass(frozen=True)
class MediaCapability:
    """A media capability contributed by a provider/runtime.

    Capabilities are the unit of discovery: a provider advertises the media
    types it can serve, and the manager routes requests to the owning
    provider. This is provider- and modality-independent.
    """

    id: str
    media_type: MediaType
    provider_name: str = "unknown"
    runtime_id: str = "media"
    version: str = "1.0.0"
    locality: MediaLocality = MediaLocality.LOCAL
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "media_type": self.media_type.value,
            "provider_name": self.provider_name,
            "runtime_id": self.runtime_id,
            "version": self.version,
            "locality": self.locality.value,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MediaProviderSpec:
    """Lightweight, serializable description of a registered provider.

    Used by the registry for capability discovery and health reporting
    without requiring the concrete provider instance.
    """

    name: str
    media_types: List[MediaType]
    runtime_id: str = "media"
    locality: MediaLocality = MediaLocality.LOCAL
    available: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "media_types": [mt.value for mt in self.media_types],
            "runtime_id": self.runtime_id,
            "locality": self.locality.value,
            "available": self.available,
            "metadata": dict(self.metadata),
        }


def new_id(prefix: str = "media") -> str:
    """Generate a prefixed unique identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now() -> float:
    """Current epoch timestamp (single source of truth for 'created_at')."""
    return time.time()
