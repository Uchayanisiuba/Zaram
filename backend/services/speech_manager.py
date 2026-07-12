import os
import queue
import threading
import time

import soundfile as sf
from core.events import AudioChunkReady, SentenceReady

from implementations.kokoro_tts import KokoroTTS


class SpeechManager:
    def __init__(self, tts_engine: KokoroTTS):
        self.tts = tts_engine
        self.audio_dir = "backend/audio_cache"
        self.voice = "af_heart"
        os.makedirs(self.audio_dir, exist_ok=True)

        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()

        # FIX: Track active tasks to prevent the stream from cutting off prematurely
        self.pending_tasks = 0

        threading.Thread(target=self._tts_worker, daemon=True).start()
        threading.Thread(target=self._cleanup_janitor, daemon=True).start()

    def set_voice(self, personality: str):
        self.voice = "af_heart"

    def submit_sentence(self, event: SentenceReady):
        self.pending_tasks += 1
        self.input_queue.put(event)

    def _tts_worker(self):
        while True:
            try:
                event = self.input_queue.get()
                if event is None:
                    break

                audio = self.tts.generate_audio(event.text, self.voice)

                if audio is not None:
                    filename = f"{event.sentence_id}.wav"
                    filepath = os.path.join(self.audio_dir, filename)
                    sf.write(filepath, audio, 24000)

                    self.output_queue.put(AudioChunkReady(
                        sentence_id=event.sentence_id,
                        audio_path=filepath
                    ))

                self.input_queue.task_done()
                # FIX: Decrement when the task is fully complete
                self.pending_tasks -= 1
            except Exception as e:
                print(f"❌ TTS Worker Error: {e}")
                self.pending_tasks -= 1

    def _cleanup_janitor(self):
        while True:
            try:
                time.sleep(30)
                current_time = time.time()
                for filename in os.listdir(self.audio_dir):
                    file_path = os.path.join(self.audio_dir, filename)
                    # FIX: Combined nested if statements into one line
                    if os.path.isfile(file_path) and file_path.endswith(".wav") and current_time - os.path.getmtime(file_path) > 60:
                        os.remove(file_path)
            except Exception as e:
                print(f"⚠️ Janitor cleanup error: {e}")
