"""Abstract voice provider interface.

This defines the contract only. No TTS engine is implemented here. Every
backend (Kokoro, XTTS, ElevenLabs, OpenAI, a custom Unreal voice, ...) must
implement :class:`VoiceProvider`. Application code talks to providers only
through :class:`~voice.voice_manager.VoiceManager`, never directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Optional


class VoiceProvider(ABC):
    """Provider-agnostic, async TTS contract."""

    #: Unique provider name (e.g. "kokoro", "xtts", "elevenlabs").
    name: str = "base"

    @abstractmethod
    async def initialize(self) -> None:
        """Load models / validate the environment."""
        ...

    @abstractmethod
    async def generate_audio(self, text: str, voice: str = "", **kwargs) -> Optional[Any]:
        """Synthesize a full utterance, returning an audio buffer (or None)."""
        ...

    @abstractmethod
    async def stream_audio(self, text: str, voice: str = "", **kwargs) -> AsyncIterator[Any]:
        """Yield audio chunks as they are produced (future-ready streaming)."""
        ...

    @abstractmethod
    async def available_voices(self) -> Dict[str, Any]:
        """Return the voices this provider can currently serve."""
        ...

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Return a structured health report (must include ``available``)."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Release models / resources held by the provider."""
        ...
