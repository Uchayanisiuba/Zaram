# backend/services/speech_planner.py
import re
import uuid
from core.events import SentenceReady

class SpeechPlanner:
    """Buffers raw LLM tokens, cleans them, and detects adaptive speech boundaries."""
    def __init__(self):
        self.buffer = ""
        self.is_first_chunk = True
        # ADAPTIVE CHUNKING CONFIGURATION
        # Kokoro needs at least a few words to sound human (prosody)
        self.MIN_CHUNK_WORDS = 5
        # If a chunk gets this long, we start looking for soft pauses (commas)
        self.SOFT_PAUSE_THRESHOLD = 120
        # Hard limit: Never let Kokoro receive more than this many characters at once
        self.MAX_CHUNK_CHARS = 250

    def process_token(self, token: str) -> SentenceReady | None:
        self.buffer += token
        stripped = self.buffer.rstrip()
        if not stripped:
            return None
        last_char = stripped[-1]
        word_count = len(stripped.split())
        char_count = len(stripped)
        # 1. HARD BOUNDARIES: Periods, exclamation marks, question marks, newlines.
        # Only split if we have enough words to sound natural.
        # FIX: Combined nested if statements
        if last_char in ['.', '!', '?', '\n'] and word_count >= self.MIN_CHUNK_WORDS:
            return self._emit_chunk()
        # 2. SOFT BOUNDARIES: Commas, semicolons, colons.
        # If the sentence is getting long, split here to get audio to the user faster.
        # FIX: Combined nested if statements
        if last_char in [',', ';', ':'] and char_count > self.SOFT_PAUSE_THRESHOLD and word_count >= self.MIN_CHUNK_WORDS:
            return self._emit_chunk()
        # 3. EMERGENCY SPLITS: If the AI generates a massive run-on sentence,
        # force a split at the last space to prevent Kokoro from timing out or sounding robotic.
        if char_count >= self.MAX_CHUNK_CHARS:
            last_space = stripped.rfind(' ')
            if last_space != -1:
                self.buffer = stripped[:last_space]
                return self._emit_chunk()
        return None

    def flush(self) -> SentenceReady | None:
        if self.buffer.strip():
            return self._emit_chunk()
        return None

    def _emit_chunk(self) -> SentenceReady:
        text = self.buffer.strip()
        self.buffer = ""
        text = self._clean_text_for_tts(text)
        return SentenceReady(
            sentence_id=str(uuid.uuid4()),
            text=text
        )

    def _clean_text_for_tts(self, text: str) -> str:
        # 1. Remove Emojis
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        text = emoji_pattern.sub(r'', text)
        # 2. Remove Markdown and Actions
        text = re.sub(r'\*[^*]+\*', '', text)
        text = re.sub(r'`[^`]+`', '', text)
        text = text.replace('*', '').replace('_', '').replace('~', '').replace('#', '')
        # 3. Fix Pronunciation Pitfalls (Crucial for human-like intonation)
        text = text.replace("AI", "A. I.")
        text = text.replace("Mr.", "Mister")
        text = text.replace("Mrs.", "Missus")
        text = text.replace("etc", "et cetera")
        return re.sub(r'\s+', ' ', text).strip()