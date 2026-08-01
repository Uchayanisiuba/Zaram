"""Speech Runtime contracts - provider-agnostic interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional


class SpeechCapability(str, Enum):
    TTS = "speech.tts"
    STREAM = "speech.stream"
    STOP = "speech.stop"
    PAUSE = "speech.pause"
    RESUME = "speech.resume"
    VOICES = "speech.voices"
    HEALTH = "speech.health"
    DEVICES = "speech.devices"


class SynthesisMode(str, Enum):
    NON_STREAMING = "non_streaming"
    STREAMING = "streaming"


class VoiceGender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    language: str
    language_code: str
    gender: VoiceGender
    provider: str
    sample_rate: int = 24000
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SynthesisRequest:
    text: str
    voice_id: str = ""
    provider_id: str = ""
    mode: SynthesisMode = SynthesisMode.NON_STREAMING
    request_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AudioChunk:
    request_id: str
    voice_id: str
    index: int
    audio: bytes
    sample_rate: int
    final: bool
    timestamp_ms: float = 0.0
    duration_ms: float = 0.0
    audio_id: str = ""


@dataclass(frozen=True)
class SynthesisResult:
    request_id: str
    voice_id: str
    audio: bytes
    sample_rate: int
    duration_ms: float
    success: bool
    error: Optional[str] = None
    audio_id: str = ""
    format: str = "wav"
    channels: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


class SpeechConnector(ABC):
    """Abstract base class for speech connectors (providers)."""

    @property
    @abstractmethod
    def connector_id(self) -> str:
        """Unique connector identifier (e.g., 'kokoro', 'piper', 'elevenlabs')."""

    @property
    @abstractmethod
    def connector_type(self) -> str:
        """Connector type category (e.g., 'local', 'cloud', 'hybrid')."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the connector (load models, validate credentials)."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Release resources."""

    @abstractmethod
    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Synthesize speech (non-streaming)."""

    @abstractmethod
    async def stream_synthesis(self, request: SynthesisRequest) -> AsyncIterator[AudioChunk]:
        """Stream synthesized audio chunks."""

    @abstractmethod
    async def stop(self, request_id: str) -> bool:
        """Stop an ongoing synthesis."""

    @abstractmethod
    async def pause(self, request_id: str) -> bool:
        """Pause an ongoing synthesis."""

    @abstractmethod
    async def resume(self, request_id: str) -> bool:
        """Resume a paused synthesis."""

    @abstractmethod
    async def list_voices(self) -> List[Voice]:
        """List available voices."""

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Return health status including 'available' boolean."""

    @abstractmethod
    def is_available(self) -> bool:
        """Quick availability check."""


class SpeechRuntimeProtocol(ABC):
    """Protocol that Speech Runtime implements."""

    @abstractmethod
    def get_runtime_id(self) -> str: ...

    @abstractmethod
    def get_metadata(self) -> RuntimeMetadata: ...

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def shutdown(self) -> None: ...

    @abstractmethod
    def get_state(self) -> RuntimeState: ...

    @abstractmethod
    def health_check(self) -> Dict[str, Any]: ...


from core.contracts import RuntimeMetadata, RuntimeState