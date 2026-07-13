"""Conversation orchestration with the Voice Runtime (streaming).

This is the single active speech path. The conversation streams tokens from the
LLM, chunks them into sentences via :class:`SpeechPlanner`, and routes each
sentence through ``VoiceManager.stream_synthesis()`` -> ``KokoroProvider`` ->
:class:`AudioChunk`. Each chunk is converted to a provider-agnostic audio event
(with ``voice.audio_events`` builders) and interleaved with the text tokens.

Text and audio run on independent worker threads so neither blocks the other:
tokens are emitted as soon as the LLM produces them, and audio chunk events are
emitted as soon as synthesis produces them (mid-response, not at the end).

Lifecycle guarantees
---------------------
* **Text first.** Tokens stream exactly as before; text is never delayed by audio.
* **Audio alongside.** Each sentence's audio chunks are emitted in order while
  the LLM keeps producing the next sentences.
* **Failure-safe.** A failed sentence / unavailable provider / raised exception
  is logged and skipped; text continues and the conversation still completes.
* **Cancellable.** Closing the generator (``GeneratorExit``) immediately stops
  the LLM stream, the audio stream, and the provider workers — no hangs, no
  orphaned tasks.

Legacy ``SpeechManager`` / ``KokoroTTS`` were deprecated in v0.5.3 (removal
planned for v0.5.6). This module no longer references them.
"""

import asyncio
import contextlib
import logging
import queue
import threading
import time
from collections.abc import Iterator
from typing import Any

from implementations.ollama_llm import OllamaLLM
from services.speech_planner import SpeechPlanner
from voice.audio_events import audio_event_from_chunk
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

    # --- main flow (sync iterator: API preserved for SSE streaming) ---
    def run_conversation(self, prompt: str, model: str, personality: str) -> Iterator[Any]:
        planner = SpeechPlanner()
        voice = self._resolve_voice(personality)
        speech_enabled = self._speech_available()

        out_queue: queue.Queue[dict] = queue.Queue()
        audio_queue: queue.Queue[dict] = queue.Queue()
        audio_input: queue.Queue | None = queue.Queue() if speech_enabled else None
        pending_lock = threading.Lock()
        pending = [0]
        error_occurred = [False]
        stop_event = threading.Event()
        audio_seq = [0]

        def synthesis_worker() -> None:
            """Drain the audio-request queue, streaming each sentence to events.

            Runs an isolated asyncio loop per sentence so the stream (and any
            provider workers) can be cancelled cleanly via ``stop_event``.
            """
            assert audio_input is not None
            while True:
                if stop_event.is_set():
                    return
                try:
                    item = audio_input.get(timeout=0.1)
                except queue.Empty:
                    continue
                if item is None:
                    return
                sentence_id, text = item
                self._stream_sentence_to_queue(
                    text, voice, sentence_id, audio_queue, audio_seq, stop_event
                )
                with pending_lock:
                    pending[0] -= 1

        def llm_and_planner_worker() -> None:
            nonlocal error_occurred
            try:
                for token in self.llm.stream_response(prompt, model):
                    if stop_event.is_set():
                        break
                    out_queue.put({"type": "token", "content": token})
                    sentence = planner.process_token(token)
                    if sentence is not None and speech_enabled:
                        with pending_lock:
                            pending[0] += 1
                        audio_input.put((sentence.sentence_id, sentence.text))  # type: ignore[union-attr]
                if not stop_event.is_set():
                    last = planner.flush()
                    if last is not None and speech_enabled:
                        with pending_lock:
                            pending[0] += 1
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

        try:
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

                with pending_lock:
                    pending_now = pending[0]
                if (
                    llm_done
                    and pending_now == 0
                    and (not speech_enabled or audio_queue.empty())
                ):
                    break

                if not got_event:
                    time.sleep(0.01)
        finally:
            # Cancellation / cleanup: tear down workers and provider tasks.
            stop_event.set()
            if audio_input is not None:
                with contextlib.suppress(Exception):
                    audio_input.put(None)
            for thread in threads:
                thread.join(timeout=2.0)

        yield {"type": "done"}

    # --- audio streaming (runs off the event loop in a worker thread) ---
    def _stream_sentence_to_queue(
        self,
        text: str,
        voice: str,
        request_id: str,
        audio_queue: "queue.Queue[dict]",
        audio_seq: list,
        stop_event: threading.Event,
    ) -> None:
        """Stream one sentence to completion, pushing audio events in order.

        Failure-safe: any provider/synthesis error is logged and emits no
        events, so the conversation keeps going without the audio.
        """
        base_url = self.voice_manager.base_url

        async def _drain() -> None:
            async for chunk in self.voice_manager.stream_synthesis(text, voice=voice):
                if stop_event.is_set():
                    return
                try:
                    event = audio_event_from_chunk(chunk, base_url=base_url)
                except Exception as exc:
                    logger.error(
                        "Audio event build failed: %s",
                        exc,
                        extra={"request_id": request_id, "failure": type(exc).__name__},
                    )
                    continue
                seq = audio_seq[0]
                audio_seq[0] += 1
                event["sequence"] = seq
                audio_queue.put(event)

        try:
            asyncio.run(_drain())
        except ProviderUnavailableError as exc:
            logger.warning(
                "Speech disabled (no active provider): %s",
                exc,
                extra={"request_id": request_id, "voice": voice},
            )
        except Exception as exc:
            logger.error(
                "Speech synthesis failed: %s",
                exc,
                extra={"request_id": request_id, "voice": voice, "failure": type(exc).__name__},
            )
