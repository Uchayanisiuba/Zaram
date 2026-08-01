"""Speech Runtime connectors package."""

from runtimes.speech.connectors.base import SpeechConnector
from runtimes.speech.connectors.kokoro import KokoroConnector

__all__ = [
    "SpeechConnector",
    "KokoroConnector",
]