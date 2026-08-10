"""Speech connectors package."""

from runtimes.speech.contracts import SpeechConnector
from runtimes.speech.connectors.kokoro import KokoroConnector

__all__ = [
    "SpeechConnector",
    "KokoroConnector",
]