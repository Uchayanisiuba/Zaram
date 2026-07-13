"""Integration tests for the migrated speech pipeline.

Verifies the single canonical path:

    ConversationManager -> VoiceManager -> VoiceRegistry -> KokoroProvider -> AudioResult

All tests run offline with injected fakes; no legacy classes are referenced.
"""

from __future__ import annotations

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


class FakePipeline:
    def __init__(self, fail: bool = False, sample_rate: int = 24000) -> None:
        self.fail = fail
        self.sample_rate = sample_rate
        self.calls: list[tuple[str, str]] = []

    def __call__(self, text: str, voice: str = ""):
        self.calls.append((text, voice))
        if self.fail:
            raise RuntimeError("synthesis boom")
        audio = np.zeros(self.sample_rate // 10, dtype=np.float32)
        yield ("g", "p", audio)


class FakeDiscoverer:
    def __init__(self, voices: list[str]) -> None:
        self.voices = list(voices)

    def discover(self, repo_id: str, lang_code: str) -> list[str]:
        return list(self.voices)


async def _ready_manager(tmp_path: Path, *, fail_pipeline: bool = False, voices=None):
    config = KokoroConfig.load(cache_directory=str(tmp_path / "audio_cache"), default_voice="af_heart")
    pipeline = FakePipeline(fail=fail_pipeline, sample_rate=config.sample_rate)

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


# --- chat streaming --------------------------------------------------------- #
async def test_chat_streams_normally(tmp_path: Path):
    manager, _, _ = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    assert events[-1] == {"type": "done"}
    assert any(e["type"] == "token" for e in events)
    assert not any(e["type"] == "error" for e in events)


async def test_voice_disabled_still_works(tmp_path: Path):
    manager = VoiceManager()  # no provider registered -> speech disabled
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    assert events[-1] == {"type": "done"}
    assert any(e["type"] == "token" for e in events)
    assert not any(e["type"] == "audio" for e in events)


async def test_provider_unavailable_still_works(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(sys.modules, "kokoro", None)
    manager, _, _ = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    assert events[-1] == {"type": "done"}
    assert any(e["type"] == "token" for e in events)
    assert not any(e["type"] == "audio" for e in events)


# --- audio events ----------------------------------------------------------- #
async def test_audio_event_emitted(tmp_path: Path):
    manager, _, pipeline = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    audio_events = [e for e in events if e["type"] == "audio"]
    assert audio_events, "expected at least one audio event"
    ev = audio_events[0]
    assert ev["url"].startswith("http://127.0.0.1:8000/audio/")
    assert ev["url"].endswith(".wav")
    assert ev["voice"] == "af_heart"
    assert pipeline.calls  # synthesis actually ran through the provider


async def test_invalid_voice_fallback(tmp_path: Path):
    manager, _, pipeline = await _ready_manager(tmp_path)
    manager.set_voice_mapping({"default": "zz_unknown_voice"})
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    audio_events = [e for e in events if e["type"] == "audio"]
    assert audio_events
    assert audio_events[0]["voice"] == "af_heart"  # fell back to default
    assert pipeline.calls
    assert all(v == "af_heart" for _, v in pipeline.calls)


# --- failure handling ------------------------------------------------------- #
async def test_synthesis_failure_no_crash(tmp_path: Path):
    manager, _, _ = await _ready_manager(tmp_path, fail_pipeline=True)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    assert events[-1] == {"type": "done"}
    assert any(e["type"] == "token" for e in events)
    assert not any(e["type"] == "audio" for e in events)


async def test_provider_exception_no_crash(tmp_path: Path, monkeypatch):
    manager, _, _ = await _ready_manager(tmp_path)

    async def boom(*args, **kwargs):
        raise RuntimeError("provider exploded")
        yield  # make it an async generator so async-for fails on first step

    monkeypatch.setattr(manager, "stream_synthesis", boom)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    assert events[-1] == {"type": "done"}
    assert any(e["type"] == "token" for e in events)
    assert not any(e["type"] == "audio" for e in events)


# --- chain integrity -------------------------------------------------------- #
async def test_conversation_provider_audioresult_chain(tmp_path: Path):
    manager, provider, _ = await _ready_manager(tmp_path)
    cm = ConversationManager(FakeLLM(), manager)
    events = list(cm.run_conversation("hi", "gemma3:latest", "default"))
    audio_events = [e for e in events if e["type"] == "audio"]
    assert audio_events
    # Emitted voice must match what the provider actually synthesized.
    assert audio_events[0]["voice"] == provider.config.default_voice


def test_no_legacy_classes_in_conversation_manager():
    import services.conversation_manager as cm_mod

    source = Path(cm_mod.__file__).read_text(encoding="utf-8")
    # No active import of the legacy implementations.
    assert "from implementations.kokoro_tts import" not in source
    assert "from services.speech_manager import" not in source
    # The single active dependency is the VoiceManager.
    assert "from voice.voice_manager import VoiceManager" in source
