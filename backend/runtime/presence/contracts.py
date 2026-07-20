"""Presence Runtime contracts (v0.9.0).

This module owns *no implementations*. It defines the renderer-independent
data shapes and protocols that the rest of Zaram uses to communicate with
any visual embodiment.

The key invariant: no runtime outside the Presence Runtime may import
embodiment or renderer code. They interact only through these contracts
and the event bus.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Protocol


class EmbodimentStatus(str, Enum):
    """Lifecycle state of an embodiment."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass(frozen=True)
class VisualParams:
    """High-level visual expressiveness parameters."""

    presence: float = 0.5
    energy: float = 0.5
    focus: float = 0.5
    activity: float = 0.5


@dataclass(frozen=True)
class AudioParams:
    """Audio-related expressive parameters."""

    voice_level: float = 0.0
    microphone_level: float = 0.0


@dataclass(frozen=True)
class EmotionParams:
    """Emotional expression parameters.

    Every value is a normalized float in [0.0, 1.0].  The renderer maps
    these to visual cues; the Presence Runtime never interprets them.
    """

    calmness: float = 0.5
    confidence: float = 0.5
    curiosity: float = 0.5
    warmth: float = 0.5
    empathy: float = 0.5
    playfulness: float = 0.5


@dataclass(frozen=True)
class SystemParams:
    """System-level state consumed by the renderer."""

    state: str = "Idle"
    cognitive_load: float = 0.0
    visual_identity: float = 0.5


@dataclass(frozen=True)
class FrameMetadata:
    """Provenance and sequencing metadata for a FrameState."""

    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""
    version: str = "1.0.0"


@dataclass(frozen=True)
class FrameState:
    """Immutable snapshot of expressive state for a single render frame.

    This is the *only* data structure the rest of Zaram may send to an
    embodiment.  It contains no rendering logic and no renderer-specific
    types.
    """

    visual: VisualParams = field(default_factory=VisualParams)
    audio: AudioParams = field(default_factory=AudioParams)
    emotion: EmotionParams = field(default_factory=EmotionParams)
    system: SystemParams = field(default_factory=SystemParams)
    metadata: FrameMetadata = field(default_factory=FrameMetadata)
    sequence: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "visual": {
                "presence": self.visual.presence,
                "energy": self.visual.energy,
                "focus": self.visual.focus,
                "activity": self.visual.activity,
            },
            "audio": {
                "voiceLevel": self.audio.voice_level,
                "microphoneLevel": self.audio.microphone_level,
            },
            "emotion": {
                "calmness": self.emotion.calmness,
                "confidence": self.emotion.confidence,
                "curiosity": self.emotion.curiosity,
                "warmth": self.emotion.warmth,
                "empathy": self.emotion.empathy,
                "playfulness": self.emotion.playfulness,
            },
            "system": {
                "state": self.system.state,
                "cognitiveLoad": self.system.cognitive_load,
                "visualIdentity": self.system.visual_identity,
            },
            "metadata": {
                "timestamp": self.metadata.timestamp,
                "correlationId": self.metadata.correlation_id,
                "version": self.metadata.version,
            },
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FrameState:
        visual = data.get("visual", {})
        audio = data.get("audio", {})
        emotion = data.get("emotion", {})
        system = data.get("system", {})
        metadata = data.get("metadata", {})
        return cls(
            visual=VisualParams(
                presence=float(visual.get("presence", 0.5)),
                energy=float(visual.get("energy", 0.5)),
                focus=float(visual.get("focus", 0.5)),
                activity=float(visual.get("activity", 0.5)),
            ),
            audio=AudioParams(
                voice_level=float(audio.get("voiceLevel", 0.0)),
                microphone_level=float(audio.get("microphoneLevel", 0.0)),
            ),
            emotion=EmotionParams(
                calmness=float(emotion.get("calmness", 0.5)),
                confidence=float(emotion.get("confidence", 0.5)),
                curiosity=float(emotion.get("curiosity", 0.5)),
                warmth=float(emotion.get("warmth", 0.5)),
                empathy=float(emotion.get("empathy", 0.5)),
                playfulness=float(emotion.get("playfulness", 0.5)),
            ),
            system=SystemParams(
                state=str(system.get("state", "Idle")),
                cognitive_load=float(system.get("cognitiveLoad", 0.0)),
                visual_identity=float(system.get("visualIdentity", 0.5)),
            ),
            metadata=FrameMetadata(
                timestamp=float(metadata.get("timestamp", time.time())),
                correlation_id=str(metadata.get("correlationId", "")),
                version=str(metadata.get("version", "1.0.0")),
            ),
            sequence=int(data.get("sequence", 0)),
        )


class EmbodimentHealth:
    """Aggregated health snapshot for diagnostics."""

    def __init__(self) -> None:
        self.status: EmbodimentStatus = EmbodimentStatus.UNINITIALIZED
        self.frame_sequence: int = 0
        self.last_frame_timestamp: float = 0.0
        self.error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "frame_sequence": self.frame_sequence,
            "last_frame_timestamp": self.last_frame_timestamp,
            "error": self.error,
        }


class IEmbodiment(Protocol):
    """Renderer-independent embodiment interface.

    Every future embodiment (Living Orb, Unreal Character, XR Avatar,
    Robot, ...) must implement this protocol.  The Presence Runtime is
    the *only* code that may import or reference implementations.
    """

    async def initialize(self) -> None:
        """Prepare the embodiment for operation (load assets, connect, etc.)."""
        ...

    async def start(self) -> None:
        """Begin accepting FrameState updates."""
        ...

    async def pause(self) -> None:
        """Temporarily halt processing without full teardown."""
        ...

    async def resume(self) -> None:
        """Resume after a pause."""
        ...

    async def shutdown(self) -> None:
        """Tear down cleanly and release resources."""
        ...

    def set_frame_state(self, frame_state: FrameState) -> None:
        """Deliver the latest expressive state to the embodiment."""
        ...

    def get_status(self) -> EmbodimentStatus:
        """Return the current lifecycle status."""
        ...
