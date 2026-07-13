"""Provider-independent media provider interface (v0.5.5).

:class:`MediaProvider` is the base contract that *every* future media backend
will implement — VoiceProvider, VisionProvider, AvatarProvider, CameraProvider,
ScreenProvider, VideoProvider, and beyond. It is intentionally stripped of any
modality-specific method (no ``generate_audio``): the Media Runtime talks to all
providers through this uniform surface.

VoiceProvider is NOT migrated here in this milestone; it remains untouched. This
abstraction is established so future providers can be added without changing the
Media Runtime, the registry, or the manager.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .contracts import MediaCapability, MediaLocality, MediaType


class MediaProvider(ABC):
    """Base class for all media subsystems.

    Implementations only need to report their identity, the media types they
    serve, and their health. Request routing is handled by the Media Manager,
    which never assumes a particular media modality.
    """

    #: Unique provider name (e.g. ``"kokoro"``, ``"vision"``, ``"avatar"``).
    name: str = "base"
    #: Runtime that owns this provider (defaults to the media runtime).
    runtime_id: str = "media"

    @abstractmethod
    async def initialize(self) -> None:
        """Acquire models / open devices / validate the environment."""
        ...

    @abstractmethod
    def capabilities(self) -> List[MediaCapability]:
        """Return the media capabilities this provider can currently serve."""
        ...

    @abstractmethod
    def media_types(self) -> List[MediaType]:
        """Return the media modalities this provider serves."""
        ...

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Return a structured health report (must include ``available``)."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Release models / devices / resources held by the provider."""
        ...

    # --- shared defaults (not abstract; safe for subclasses) ---
    def locality(self) -> MediaLocality:
        """Where this provider runs (override for cloud/remote providers)."""
        return MediaLocality.LOCAL

    def to_spec(self) -> Dict[str, Any]:
        """Best-effort serializable description (used by the registry)."""
        try:
            media_types = self.media_types()
        except Exception:
            media_types = []
        try:
            health = self.health_check()
        except Exception:
            health = {"available": False}
        return {
            "name": self.name,
            "runtime_id": self.runtime_id,
            "media_types": [mt.value for mt in media_types],
            "locality": self.locality().value,
            "available": bool(health.get("available", False)),
            "metadata": {"health": health},
        }
