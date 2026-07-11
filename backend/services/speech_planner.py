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
        if last_char in ['.', '!', '?', '\n']:
            if word_count >= self.MIN_CHUNK_WORDS:
                return self._emit_chunk()
                
        # 2. SOFT BOUNDARIES: Commas, semicolons, colons.
        # If the sentence is getting long, split here to get audio to the user faster.
        if last_char in [',', ';', ':']:
            if char_count > self.SOFT_PAUSE_THRESHOLD and word_count >= self.MIN_CHUNK_WORDS:
                return self._emit_chunk()
                
        # 3. EMERGENCY SPLITS: If the AI generates a massive run-on sentence,
        # force a split at the last space to prevent Kokoro from timing out or sounding robotic.
        if char_count > self.MAX_CHUNK_CHARS:
            last_space = stripped.rfind(' ')
            if last_space != -1:
                # Cut the buffer at the last space
                self.buffer = stripped[:last_space]
                return self._emit_chunk()
                
        return None

    def flush(self) -> SentenceReady | None:
        """Flushes any remaining text in the buffer at the end of the stream."""
        if self.buffer.strip():
            return self._emit_chunk()
        return None

    def _emit_chunk(self) -> SentenceReady:
        """Cleans the text and creates the event."""
        clean_text = self._clean_text_for_tts(self.buffer)
        event = SentenceReady(
            text=clean_text,
            is_first=self.is_first_chunk,
            sentence_id=uuid.uuid4().hex[:8]
        )
        self.buffer = ""
        self.is_first_chunk = False
        return event

    def _clean_text_for_tts(self, text: str) -> str:
        """Strips emojis, markdown, and fixes abbreviations so Kokoro sounds human."""
        # 1. Kill Emojis
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        text = emoji_pattern.sub(r'', text)
        
        # 2. Remove Markdown and Actions
        text = re.sub(r'\*[^*]+\*', '', text)
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`[^`]+`', '', text)
        text = text.replace('*', '').replace('_', '').replace('~', '').replace('#', '')
        
        # 3. Fix Pronunciation Pitfalls (Crucial for human-like intonation)
        text = text.replace("AI", "A. I.")
        text = text.replace("OS", "O. S.")
        text = text.replace("Dr.", "Doctor")
        text = text.replace("Mr.", "Mister")
        text = text.replace("Mrs.", "Missus")
        text = text.replace("etc", "et cetera")
        
        return re.sub(r'\s+', ' ', text).strip()