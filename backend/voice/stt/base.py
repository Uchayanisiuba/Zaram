"""Speech-to-text contract.

The interface only. No engine is implemented here, for the same reason TTS has
``voice/providers/base.py``: CLAUDE.md keeps speech behind an interface so the
choice is replaceable rather than embedded, and the binding constraints for
listening are the same ones that chose Kokoro for speaking — permissive licence,
runs without competing for VRAM with a resident local model, works on Macs and
AMD.

**Transcription happens on this machine.** That is not a quality target, it is
the product. Rule 5 is default deny, and a microphone is the most sensitive
input Zaram will ever take. The browser's Web Speech API would be three lines
and better accuracy, and it streams the user's *audio* — not a transcript — to
Google, where no gate could see or log it. ``frontend/scripts/
check-no-cloud-speech.mjs`` bans it outright for exactly that reason. Any
implementation of this interface that reaches the network is a bug, and the
egress chokepoint is what proves it did not.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TranscriptSegment:
    """A span of speech with its own timing.

    Mirrors ``SpeechTiming`` on the way out deliberately: the same shape that
    carries "when was this word said" for lip sync carries "when was this word
    heard" for a transcript, so a caller learns one structure rather than two.
    """

    text: str
    start_s: float
    end_s: float


@dataclass
class Transcript:
    """What was heard.

    ``text`` is the whole utterance; ``segments`` may be empty, because an
    engine that cannot produce timings is a supported engine. Absence is
    representable rather than an error, which is the same seam TTS uses for
    phoneme timings — a caller checks and falls back.
    """

    text: str
    segments: List[TranscriptSegment] = field(default_factory=list)
    #: Detected language, or ``None`` when the engine does not say. Never
    #: defaulted to "en": a guessed language is a wrong value rendered
    #: confidently, and CLAUDE.md forbids exactly that.
    language: Optional[str] = None
    duration_s: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SpeechRecogniser(ABC):
    """Provider-agnostic speech-to-text contract."""

    #: Unique name (e.g. "faster-whisper", "vosk").
    name: str = "base"

    @abstractmethod
    async def initialize(self) -> None:
        """Load the model, or record why it could not be loaded.

        Must not raise on a machine where the engine is not installed. The
        Kokoro provider learned this the hard way: a top-level import made the
        whole module unimportable on a base install, so the provider could not
        even be constructed to report itself unavailable, and the lazy import
        written to degrade gracefully never got the chance.
        """
        ...

    @abstractmethod
    async def transcribe(self, audio: bytes, *, language: Optional[str] = None) -> Transcript:
        """Turn an audio buffer into text. Never leaves the device."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Whether a transcribe() call could succeed right now."""
        ...

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Structured report. Must include ``available`` and, when it is
        False, a ``reason`` a user could act on — including the download size
        where the fix is an install, the way the OCR extra names its 321 MB."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Release the model."""
        ...
