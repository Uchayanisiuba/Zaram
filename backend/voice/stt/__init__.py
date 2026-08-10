"""Speech to text, local only.

The contract is in :mod:`voice.stt.base`; :mod:`voice.stt.whisper` is the first
implementation of it. Callers import from here, so swapping the engine is a
change in one file rather than a change everywhere the recogniser is named —
the same seam TTS keeps for the same reason.

``WhisperRecogniser`` is *not* re-exported eagerly. It imports the egress gate
and reads config at construction, and more to the point importing it from here
would put it on every path that only wants the types. ``recogniser()`` builds
one on demand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import SpeechRecogniser, Transcript, TranscriptSegment

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .whisper import WhisperRecogniser

__all__ = [
    "SpeechRecogniser",
    "Transcript",
    "TranscriptSegment",
    "recogniser",
]


def recogniser(**kwargs: Any) -> "WhisperRecogniser":
    """The recogniser this build listens with.

    One place names the engine. Everything else asks for "the recogniser" and
    gets whatever CLAUDE.md's dependency table currently says, which is what
    keeping speech behind an interface is for.
    """
    from .whisper import WhisperRecogniser

    return WhisperRecogniser(**kwargs)
