import numpy as np
from kokoro import KPipeline

class KokoroTTS:
    """Concrete implementation of the TTSEngine interface using Kokoro."""
    def __init__(self):
        print("⏳ Loading Kokoro TTS model into memory...")
        self.pipeline = KPipeline(lang_code='a')
        print("✅ Kokoro TTS model loaded!")
        
        # Warmup to prevent first-request lag
        print("🔥 Warming up audio engine...")
        try:
            for _, _, audio in self.pipeline("hi", voice="af_heart"):
                pass
            print("✅ Audio engine warmed up.")
        except Exception as e:
            print(f"⚠️ Warmup failed, but model is loaded: {e}")

    def generate_audio(self, text: str, voice: str) -> np.ndarray | None:
        try:
            audio_chunks = []
            for _, _, audio in self.pipeline(text, voice=voice):
                audio_chunks.append(audio)
            if not audio_chunks:
                return None
            return np.concatenate(audio_chunks)
        except Exception as e:
            print(f"❌ Kokoro TTS Error: {e}")
            return None