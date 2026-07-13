"""Provider-independent media asset model (v0.5.5).

A :class:`MediaAsset` is a generic handle over *any* media payload — audio,
image, video, animation, sensor data, documents, or future modalities. It is
deliberately free of voice/audio-specific fields so the Media Runtime can treat
every modality uniformly.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .contracts import MediaType, new_id


@dataclass
class MediaAsset:
    """A generic, modality-agnostic media asset.

    Attributes:
        id: Stable unique identifier for the asset.
        type: Modality of the asset (audio, image, video, ...).
        provider: Name of the provider that produced the asset.
        mime_type: IANA media type (e.g. ``audio/wav``, ``image/png``).
        created_at: Epoch timestamp when the asset was created.
        metadata: Free-form, provider/modality-specific information.
        location: Where the asset lives (path, URL, or device handle).
        streamable: Whether the asset can be consumed incrementally.
        duration: Length in seconds, when applicable (None otherwise).
        format: Container/codec format string (e.g. ``wav``, ``mp4``).
        size: Size in bytes, when known (None otherwise).
    """

    type: MediaType = MediaType.UNKNOWN
    provider: str = "unknown"
    mime_type: str = ""
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    location: Optional[str] = None
    streamable: bool = False
    duration: Optional[float] = None
    format: str = ""
    size: Optional[int] = None
    id: str = field(default_factory=lambda: new_id("asset"))

    # --- classification helpers ---
    @property
    def is_streamable(self) -> bool:
        return self.streamable

    @property
    def is_persisted(self) -> bool:
        """True when ``location`` points at a real, existing file."""
        if not self.location:
            return False
        try:
            return Path(self.location).expanduser().resolve().is_file()
        except (OSError, ValueError):
            return False

    @property
    def type_value(self) -> str:
        return self.type.value

    # --- construction ---
    @classmethod
    def create(
        cls,
        *,
        type: Union[MediaType, str],
        provider: str,
        mime_type: str = "",
        location: Optional[str] = None,
        streamable: bool = False,
        duration: Optional[float] = None,
        format: str = "",
        size: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        asset_id: Optional[str] = None,
    ) -> "MediaAsset":
        """Convenience constructor with string/enum-flexible ``type``."""
        media_type = (
            type if isinstance(type, MediaType) else MediaType.from_value(type)
        )
        return cls(
            id=asset_id or new_id("asset"),
            type=media_type,
            provider=provider,
            mime_type=mime_type,
            location=location,
            streamable=streamable,
            duration=duration,
            format=format,
            size=size,
            metadata=dict(metadata or {}),
        )

    # --- serialization ---
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "provider": self.provider,
            "mime_type": self.mime_type,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
            "location": self.location,
            "streamable": self.streamable,
            "duration": self.duration,
            "format": self.format,
            "size": self.size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MediaAsset":
        return cls(
            id=data.get("id", new_id("asset")),
            type=MediaType.from_value(data.get("type", "unknown")),
            provider=data.get("provider", "unknown"),
            mime_type=data.get("mime_type", ""),
            created_at=data.get("created_at", time.time()),
            metadata=dict(data.get("metadata", {})),
            location=data.get("location"),
            streamable=data.get("streamable", False),
            duration=data.get("duration"),
            format=data.get("format", ""),
            size=data.get("size"),
        )
