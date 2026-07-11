from typing import Protocol
import numpy as np

class TTSEngine(Protocol):
    """Abstract interface for ANY TTS model."""
    def generate_audio(self, text: str, voice: str) -> np.ndarray | None:
        """Synthesizes text into a numpy array of audio samples."""
        ...