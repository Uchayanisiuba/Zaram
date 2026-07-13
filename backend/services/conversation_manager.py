"""Conversation orchestration with the Voice Runtime.

This is the single active speech path. The conversation streams tokens from the
LLM, chunks them into sentences via :class:`SpeechPlanner`, and routes each
sentence through ``VoiceManager`` -> ``VoiceRegistry`` -> ``KokoroProvider``.
The provider returns an :class:`AudioResult`; on success a provider-agnostic
audio event is emitted. Any speech failure is logged and skipped so chat never
blocks or crashes.

Legacy ``SpeechManager`` / ``KokoroTTS`` were deprecated in v0.5.3 (removal
planned for v0.5.6). This module no longer references them.
"""

import asyncio
import logging
import queue
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Optional

from implementations.ollama_llm import OllamaLLM
from services.speech_planner import SpeechPlanner
from voice.exceptions import ProviderUnavailableError
from voice.voice_manager import VoiceManager

logger = logging.getLogger(__name__)


class ConversationManager:
    def __init__(self, llm: OllamaLLM, voice_manager: VoiceManager) -> None:
        self.llm = llm
        self.voice_manager = voice_manager

    # --- voice resolution / availability ---
    def _resolve_voice(self, personality: str) -> str:
        """Resolve a personality to a voice id, or '' to use the provider default."""
        voice = self.voice_manager.resolve_voice(personality)
        return voice or ""

    def _speech_available(self) -> bool:
        try:
            self.voice_manager.get_provider()
            return True
        except ProviderUnavailableError:
            return False

    # --- synthesis (runs off the event loop in a worker thread) ---
    def _synthesize(self, text: str, voice: str, request_id: str) -> Optional[dict]:
        try:
            result = asyncio.run(self.voice_manager.synthesize(text, voice=voice))
        except ProviderUnavailableError as exc:
            logger.warning(
                "Speech disabled (no active provider): %s",
                exc,
                extra={"request_id": request_id, "voice": voice},
            )
            return None
        except Exception as exc:
            logger.error(
                "Speech synthesis failed: %s",
                exc,
                extra={"request_id": request_id, "voice": voice, "failure": type(exc).__name__},
            )
            return None

        if result is None or not getattr(result, "success", False):
            logger.error(
                "Speech synthesis returned failure",
                extra={"request_id": request_id, "voice": voice, "error": getattr(result, "error", "unknown")},
            )
            return None

        filename = Path(result.path).name
        base_url = self.voice_manager.base_url
        return {
            "type": "audio",
            "url": f"{base_url}/audio/{filename}",
            "voice": result.voice,
        }

    # --- main flow ---
    def run_conversation(self, prompt: str, model: str, personality: str) -> Iterator[Any]:
        planner = SpeechPlanner()
        voice = self._resolve_voice(personality)
        speech_enabled = self._speech_available()

        out_queue: queue.Queue = queue.Queue()
        audio_queue: queue.Queue = queue.Queue()
        audio_input: Optional[queue.Queue] = queue.Queue() if speech_enabled else None
        pending = 0
        error_occurred = [False]

        def synthesis_worker() -> None:
            nonlocal pending
            while True:
                item = audio_input.get()  # type: ignore[union-attr]
                if item is None:
                    break
                sentence_id, text = item
                event = self._synthesize(text, voice, request_id=sentence_id)
                if event is not None:
                    audio_queue.put(event)
                pending -= 1

        def llm_and_planner_worker() -> None:
            nonlocal pending
            try:
                for token in self.llm.stream_response(prompt, model):
                    out_queue.put({"type": "token", "content": token})
                    sentence = planner.process_token(token)
                    if sentence is not None and speech_enabled:
                        pending += 1
                        audio_input.put((sentence.sentence_id, sentence.text))  # type: ignore[union-attr]
                last = planner.flush()
                if last is not None and speech_enabled:
                    pending += 1
                    audio_input.put((last.sentence_id, last.text))  # type: ignore[union-attr]
            except Exception as exc:
                logger.error("LLM/planner worker error: %s", exc, exc_info=True)
                out_queue.put({"type": "error", "content": str(exc)})
                error_occurred[0] = True
            finally:
                out_queue.put({"type": "llm_done"})
                if audio_input is not None:
                    audio_input.put(None)

        threads = [threading.Thread(target=llm_and_planner_worker, daemon=True)]
        if speech_enabled:
            threads.append(threading.Thread(target=synthesis_worker, daemon=True))
        for thread in threads:
            thread.start()

        llm_done = False
        while True:
            got_event = False

            try:
                event = out_queue.get(timeout=0.1)
                got_event = True
                if event.get("type") == "llm_done":
                    llm_done = True
                elif event.get("type") == "error":
                    yield event
                    break
                else:
                    yield event
            except queue.Empty:
                pass

            if speech_enabled:
                try:
                    audio_event = audio_queue.get_nowait()
                    got_event = True
                    yield audio_event
                except queue.Empty:
                    pass

            if error_occurred[0]:
                break

            if llm_done and pending == 0 and (not speech_enabled or audio_queue.empty()):
                break

            if not got_event:
                time.sleep(0.01)

        yield {"type": "done"}
