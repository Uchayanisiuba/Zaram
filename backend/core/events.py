from dataclasses import dataclass

# --- THE ZARAM EVENT BUS DEFINITIONS ---
# These dataclasses represent the exact state changes in our system.
# In Phase 4, these will be broadcasted to the entire app.

@dataclass
class TokenGenerated:
    """Emitted when the LLM produces a single word/character."""
    token: str

@dataclass
class SentenceReady:
    """Emitted by the Speech Planner when a full sentence is buffered and cleaned."""
    text: str
    is_first: bool
    sentence_id: str

@dataclass
class AudioChunkReady:
    """Emitted by the Speech Manager when Kokoro finishes generating audio.
    Note: In Phase 1, this is a file path. In Phase 2, this will be raw PCM bytes."""
    file_path: str
    sentence_id: str

@dataclass
class SpeechCancelled:
    """Emitted when the user interrupts the AI (Future Phase)."""
    reason: str = "user_interruption"