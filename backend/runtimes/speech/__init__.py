"""Speech Runtime package."""

from runtimes.speech.runtime import SpeechRuntime
from runtimes.speech.contracts import (
    SpeechCapability,
    SpeechConnector,
    Voice,
    SynthesisRequest,
    SynthesisResult,
    AudioChunk,
    SynthesisMode,
    VoiceGender,
)
from runtimes.speech.connectors import KokoroConnector

__all__ = [
    "SpeechRuntime",
    "SpeechCapability",
    "SpeechConnector",
    "KokoroConnector",
    "Voice",
    "SynthesisRequest",
    "SynthesisResult",
    "AudioChunk",
    "SynthesisMode",
    "VoiceGender",
]