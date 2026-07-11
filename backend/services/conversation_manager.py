import queue
import threading
import time
from typing import Iterator, Any
from core.events import TokenGenerated, AudioChunkReady
from implementations.ollama_llm import OllamaLLM
from implementations.kokoro_tts import KokoroTTS
from services.speech_planner import SpeechPlanner
from services.speech_manager import SpeechManager

class ConversationManager:
    def __init__(self, llm: OllamaLLM, tts: KokoroTTS):
        self.llm = llm
        self.tts = tts

    def run_conversation(self, prompt: str, model: str, personality: str) -> Iterator[Any]:
        planner = SpeechPlanner()
        manager = SpeechManager(self.tts)
        manager.set_voice(personality)
        
        out_queue = queue.Queue()
        error_occurred = [False]

        def llm_and_planner_worker():
            try:
                for token in self.llm.stream_response(prompt, model):
                    out_queue.put({'type': 'token', 'content': token})
                    sentence_event = planner.process_token(token)
                    if sentence_event:
                        manager.submit_sentence(sentence_event)
                
                last_sentence = planner.flush()
                if last_sentence:
                    manager.submit_sentence(last_sentence)
            except Exception as e:
                print(f"❌ LLM/Planner Worker Error: {e}")
                out_queue.put({'type': 'error', 'content': str(e)})
                error_occurred[0] = True
            finally:
                out_queue.put({'type': 'llm_done'})

        threading.Thread(target=llm_and_planner_worker, daemon=True).start()

        llm_done = False
        while True:
            got_event = False
            
            try:
                event = out_queue.get(timeout=0.1)
                got_event = True
                if event.get('type') == 'llm_done':
                    llm_done = True
                elif event.get('type') == 'error':
                    yield event
                    break
                else:
                    yield event
            except queue.Empty:
                pass

            try:
                audio_event = manager.output_queue.get_nowait()
                got_event = True
                yield {
                    'type': 'audio',
                    'url': f"http://127.0.0.1:8000/audio/{audio_event.sentence_id}.wav"
                }
            except queue.Empty:
                pass

            if error_occurred[0]:
                break
            
            # FIX: Use pending_tasks instead of input_queue.empty() to prevent race condition
            if llm_done and manager.pending_tasks == 0 and manager.output_queue.empty():
                break
            
            if not got_event:
                time.sleep(0.01)
                
        yield {"type": "done"}