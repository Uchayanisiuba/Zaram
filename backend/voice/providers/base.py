"""Abstract voice provider interface.

This defines the contract only. No TTS engine is implemented here. Every
backend (Kokoro, XTTS, ElevenLabs, OpenAI, a custom Unreal voice, ...) must
implement :class:`VoiceProvider`. Application code talks to providers only
through :class:`~voice.voice_manager.VoiceManager`, never directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional


@dataclass(frozen=True)
class SpeechTiming:
    """One spoken unit and when it is heard, in seconds from the start.

    This lives at the interface rather than in the Kokoro module on purpose.
    CLAUDE.md keeps TTS behind an interface so the engine stays replaceable, and
    lip sync is the exact place that coupling would creep in: passing Kokoro's
    ``MToken`` across this boundary would make every renderer depend on Kokoro's
    types, and swapping the engine would then mean rewriting the renderer too.

    So timings cross as a plain structure. An engine that cannot produce them
    returns an empty list, and a renderer with no timings falls back to whatever
    it can do without them — amplitude, or nothing. That is the seam a second
    implementation slots into rather than a rewrite.

    ``start_s``/``end_s`` are offsets into the *whole* utterance, not into the
    chunk that produced them. A caller must never have to know that the engine
    synthesised in pieces.
    """

    #: The word as written. Empty when the engine reports phonemes only.
    text: str
    #: IPA for this unit. Empty when the engine reports graphemes only.
    phonemes: str
    start_s: float
    end_s: float


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
