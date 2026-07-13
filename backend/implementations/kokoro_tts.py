"""DEPRECATED (v0.5.3) — scheduled for removal in v0.5.6.

Replaced by ``voice.providers.kokoro.KokoroProvider``. No active runtime code
imports this module anymore; kept only for rollback. Do not call Kokoro
directly from application code.
"""

import numpy as np
from kokoro import KPipeline


class KokoroTTS:
    def __init__(self):
        print("Loading Kokoro TTS model...")
        self.pipeline = KPipeline(lang_code='a')
        print("✅ Kokoro TTS model loaded!")

        # Warmup to prevent first-request lag
        print(" Warming up audio engine...")
        try:
            for _, _, _audio in self.pipeline("hi", voice="af_heart"):
                pass
            print("✅ Audio engine warmed up.")
        except Exception as e:
            print(f"❌ Kokoro TTS Warmup Error: {e}")

    def generate_audio(self, text: str, voice: str = "af_heart") -> np.ndarray | None:
        try:
            audio_chunks = []
            for _, _, audio in self.pipeline(text, voice=voice):
                audio_chunks.append(audio)

            if audio_chunks:
                return np.concatenate(audio_chunks)
            return None
        except Exception as e:
            print(f"❌ Kokoro TTS Error: {e}")
            return None
