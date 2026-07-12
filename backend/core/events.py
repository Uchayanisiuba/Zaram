from dataclasses import dataclass


@dataclass(slots=True)
class SentenceReady:
    """A sentence ready to be synthesized."""

    sentence_id: str
    text: str


@dataclass(slots=True)
class AudioChunkReady:
    """Audio generated for a sentence."""

    sentence_id: str
    audio_path: str
