import os
import time
import queue
import threading
import soundfile as sf
from core.events import SentenceReady, AudioChunkReady
from implementations.kokoro_tts import KokoroTTS

class SpeechManager:
    """Manages the single TTS worker thread and automatically cleans up audio files."""
    def __init__(self, tts_engine: KokoroTTS, audio_dir: str = "audio_cache"):
        self.tts_engine = tts_engine
        self.audio_dir = audio_dir
        self.voice = "af_heart"
        os.makedirs(self.audio_dir, exist_ok=True)
        
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        
        # FIX: Track active tasks to prevent the stream from cutting off prematurely
        self.pending_tasks = 0 
        
        threading.Thread(target=self._tts_worker, daemon=True).start()
        threading.Thread(target=self._cleanup_janitor, daemon=True).start()

    def set_voice(self, voice: str):
        self.voice = voice

    def submit_sentence(self, event: SentenceReady):
        self.input_queue.put(event)
        self.pending_tasks += 1

    def _tts_worker(self):
        while True:
            sentence_event = self.input_queue.get()
            if sentence_event is None:
                break
            try:
                audio_array = self.tts_engine.generate_audio(sentence_event.text, self.voice)
                if audio_array is not None:
                    file_path = os.path.join(self.audio_dir, f"{sentence_event.sentence_id}.wav")
                    sf.write(file_path, audio_array, 24000, format='WAV')
                    self.output_queue.put(AudioChunkReady(
                        file_path=file_path,
                        sentence_id=sentence_event.sentence_id
                    ))
            except Exception as e:
                print(f"❌ Speech Manager Worker Error: {e}")
            finally:
                self.input_queue.task_done()
                # FIX: Decrement when the task is fully complete
                self.pending_tasks -= 1 

    def _cleanup_janitor(self):
        while True:
            try:
                time.sleep(30)
                current_time = time.time()
                for filename in os.listdir(self.audio_dir):
                    file_path = os.path.join(self.audio_dir, filename)
                    if os.path.isfile(file_path) and file_path.endswith(".wav"):
                        if current_time - os.path.getmtime(file_path) > 60:
                            os.remove(file_path)
            except Exception as e:
                print(f"⚠️ Janitor cleanup error: {e}")