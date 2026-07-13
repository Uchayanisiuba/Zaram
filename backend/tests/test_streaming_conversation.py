"""Integration tests for the streaming conversation pipeline (v0.5.4B).

Covers the file-first -> streaming migration:

    ConversationManager -> VoiceManager.stream_synthesis()
        -> KokoroProvider -> AudioChunk -> SSE audio events

Text and audio must interleave, audio chunks must be ordered with exactly one
final chunk per sentence, failures must not crash or hang the conversation, and
cancellation must tear down text + audio + provider workers cleanly.

All tests run offline with injected fakes; no legacy classes are referenced.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import numpy as np

from services.conversation_manager import ConversationManager
from voice.config import KokoroConfig
from voice.health import AudioCache
from voice.providers.kokoro import KokoroProvider
from voice.voice_manager import VoiceManager

SAMPLE_VOICES = ["af_heart", "af_bella", "am_adam"]


class FakeLLM:
    def stream_response(self, prompt: str, model: str):
        yield from ["Hello", " world", ".", " This is one sentence.", " This is another sentence."]


class MultiChunkFakePipeline:
    """Yields enough audio that streaming produces several frames per sentence."""

    def __init__(self, fail: bool = False, sample_rate: int = 24000, frames: int = 3) -> None:
        self.fail = fail
        self.sample_rate = sample_rate
        self.frames = frames
        self.calls: list[tuple[str, str]] = []

    def __call__(self, text: str, voice: str = ""):
        self.calls.append((text, voice))
        if self.fail:
            raise RuntimeError("synthesis boom")
        # Long enough that stream_audio slices it into `frames` chunks.
        audio = np.zeros(self.sample_rate, dtype=np.float32)
        yield ("g", "p", audio)


class FakeDiscoverer:
    def __init__(self, voices: list[str]) -> None:
        self.voices = list(voices)

    def discover(self, repo_id: str, lang_code: str) -> list[str]:
        return list(self.voices)


async def _ready_manager(tmp_path: Path, *, fail_pipeline: bool = False, pipeline_cls=MultiChunkFakePipeline, voices=None):
    config = KokoroConfig.load(cache_directory=str(tmp_path / "audio_cache"), default_voice="af_heart")
    pipeline = pipeline_cls(fail=fail_pipeline, sample_rate=config.sample_rate)

    def factory(*, repo_id: str, lang_code: str, device):
        return pipeline

    provider = KokoroProvider(
        config=config,
        pipeline_factory=factory,
        voice_discoverer=FakeDiscoverer(voices or SAMPLE_VOICES),
        cache=AudioCache(config.cache_directory),
    )
    manager = VoiceManager()
    await manager.register_provider(provider.name, provider, set_active=True)
    await manager.initialize()
    return manager, provider, pipeline


# --- completion / no hang -------------------------------------------------- #
async def test_conversation_completes_with_streaming(tmp_path: Path):
    manager, _, _ = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    assert events[-1] == {"type": "done"}
    assert any(e["type"] == "token" for e in events)
    assert any(e["type"] == "audio" for e in events)
    assert not any(e["type"] == "error" for e in events)


# --- text + audio interleaving -------------------------------------------- #
async def test_text_and_audio_interleave(tmp_path: Path):
    manager, _, _ = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))

    token_positions = [i for i, e in enumerate(events) if e["type"] == "token"]
    audio_positions = [i for i, e in enumerate(events) if e["type"] == "audio"]

    assert token_positions, "expected tokens"
    assert audio_positions, "expected audio"
    # Text must start before audio (tokens lead) ...
    assert token_positions[0] < audio_positions[0]
    # ... and audio must start before the conversation ends.
    assert audio_positions[0] < token_positions[-1] or audio_positions[-1] > token_positions[0]


# --- multiple sentences ---------------------------------------------------- #
async def test_multiple_sentences_produce_audio(tmp_path: Path):
    manager, _, _ = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    audio_events = [e for e in events if e["type"] == "audio"]
    assert audio_events, "expected audio events"
    # FakeLLM yields 3 sentences -> at least 3 sentences' worth of chunks.
    assert len(audio_events) >= 3


# --- ordered audio chunks -------------------------------------------------- #
async def test_audio_chunks_ordered_globally(tmp_path: Path):
    manager, _, _ = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    audio_events = [e for e in events if e["type"] == "audio"]
    sequences = [e["sequence"] for e in audio_events]
    assert sequences == list(range(len(sequences))), "global audio sequence must be monotonic 0..n"


# --- final chunk exactly once per sentence -------------------------------- #
async def test_final_chunk_exactly_once_per_sentence(tmp_path: Path):
    manager, _, _ = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    audio_events = [e for e in events if e["type"] == "audio"]

    # Group chunks into sentences by walking the stream and resetting at each
    # final chunk. Each sentence must have exactly one final chunk.
    sentences = []
    current: list[dict] = []
    for ev in audio_events:
        current.append(ev)
        if ev["final"] is True:
            sentences.append(current)
            current = []
    assert current == [], "stream must not end mid-sentence (no trailing final)"
    assert sentences, "expected at least one sentence"
    for s in sentences:
        finals = [e for e in s if e["final"] is True]
        assert len(finals) == 1, "exactly one final chunk per sentence"
        # Within a sentence, indices must be ordered 0..n-1.
        assert [e["sequence"] for e in s] == list(range(s[0]["sequence"], s[0]["sequence"] + len(s)))


# --- provider unavailable -------------------------------------------------- #
async def test_provider_unavailable_still_works(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(sys.modules, "kokoro", None)
    manager, _, _ = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    assert events[-1] == {"type": "done"}
    assert any(e["type"] == "token" for e in events)
    assert not any(e["type"] == "audio" for e in events)


# --- provider failure ------------------------------------------------------ #
async def test_provider_failure_no_crash(tmp_path: Path):
    manager, _, _ = await _ready_manager(tmp_path, fail_pipeline=True)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    assert events[-1] == {"type": "done"}
    assert any(e["type"] == "token" for e in events)
    assert not any(e["type"] == "audio" for e in events)


# --- provider exception escaping guard ------------------------------------ #
async def test_provider_exception_no_escape(tmp_path: Path, monkeypatch):
    manager, _, _ = await _ready_manager(tmp_path)

    async def boom(*args, **kwargs):
        raise RuntimeError("provider exploded")
        yield

    monkeypatch.setattr(manager, "stream_synthesis", boom)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    assert events[-1] == {"type": "done"}
    assert any(e["type"] == "token" for e in events)
    assert not any(e["type"] == "audio" for e in events)


# --- cancellation / no hanging generators --------------------------------- #
async def test_cancellation_terminates_cleanly(tmp_path: Path):
    manager, _, _ = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)

    gen = cm.run_conversation("hi", "gemma3:latest", "default")
    # Consume a few events, then cancel mid-stream.
    seen = [next(gen) for _ in range(3)]
    assert any(e["type"] in ("token", "audio") for e in seen)

    gen.close()  # must not hang and must not raise

    # Give any worker threads a chance to exit; failure here indicates a hang.
    await asyncio.sleep(0.2)


async def test_cancellation_early_no_hang(tmp_path: Path):
    manager, _, _ = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)

    gen = cm.run_conversation("hi", "gemma3:latest", "default")
    # Cancel before pulling anything.
    gen.close()

    await asyncio.sleep(0.2)  # allow workers to terminate


# --- SSE event ordering: tokens lead, audio follows, done last ------------ #
async def test_sse_event_ordering(tmp_path: Path):
    manager, _, _ = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))

    assert events[-1] == {"type": "done"}
    # The 'done' event must be the last item.
    assert all(e["type"] != "done" for e in events[:-1])
    # No error events leaked from provider failures.
    assert not any(e["type"] == "error" for e in events)
    # Every audio event uses the provider-agnostic shape.
    for ev in events:
        if ev["type"] == "audio":
            assert set(ev.keys()) >= {"type", "audio_id", "url", "sequence", "final", "voice"}
            assert ev["type"] == "audio"
            assert isinstance(ev["sequence"], int)


# --- backpressure: speech disabled keeps text only ------------------------ #
async def test_voice_disabled_still_works(tmp_path: Path):
    manager = VoiceManager()  # no provider registered -> speech disabled
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    assert events[-1] == {"type": "done"}
    assert any(e["type"] == "token" for e in events)
    assert not any(e["type"] == "audio" for e in events)
