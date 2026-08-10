# backend/services/conversation_manager.py
import queue
import threading
import time
from typing import Iterator, Any
from core.events import TokenGenerated, SentenceReady
from core.event_bus import ZaramEvent
from implementations.ollama_llm import OllamaLLM
from services.speech_planner import SpeechPlanner

class ConversationManager:
    """
    Manages conversation flow: LLM streaming -> sentence planning -> emits to Event Bus.
    
    The new flow:
    1. LLM streams tokens
    2. SpeechPlanner buffers tokens and detects sentence boundaries
    3. When sentence is ready, emits 'conversation:sentence_ready' event to Event Bus
    4. Executive Runtime subscribes to this event and decides when to speak
    5. Speech Runtime handles executive:speak event
    
    No direct TTS calls - everything goes through the Runtime layer.
    """
    def __init__(self, llm: OllamaLLM, event_bus, persona: str = "zaram_prime"):
        self.llm = llm
        self.event_bus = event_bus
        self.persona = persona

    def run_conversation(self, prompt: str, model: str, system_prompt: str = "", persona: str = "zaram_prime") -> Iterator[Any]:
        planner = SpeechPlanner()
        out_queue = queue.Queue()
        error_occurred = [False]

        def llm_and_planner_worker():
            try:
                # Argument order is `LLMEngine`'s, not this call site's history:
                # (prompt, system_prompt, model).
                for token in self.llm.stream_response(prompt, system_prompt, model):
                    out_queue.put({'type': 'token', 'content': token})
                    sentence_event = planner.process_token(token)
                    if sentence_event:
                        # Emit sentence to Event Bus for Executive to consume
                        self._emit_sentence_ready(sentence_event.text, persona)
                last_sentence = planner.flush()
                if last_sentence:
                    self._emit_sentence_ready(last_sentence.text, persona)
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
            if error_occurred[0]:
                break
            if llm_done:
                break
            if not got_event:
                time.sleep(0.01)
        yield {"type": "done"}

    def _emit_sentence_ready(self, text: str, persona: str = "zaram_prime"):
        """Emit a sentence-ready event to the Event Bus for Executive consumption."""
        if not text or not text.strip():
            return
        event = ZaramEvent(
            source_runtime="conversation",
            event_type="conversation:sentence_ready",
            data={
                "text": text,
                "persona": persona,
            },
            priority="high",
        )
        self.event_bus.publish(event)