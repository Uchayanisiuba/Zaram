"""Tests for the Audio Streaming Foundation (v0.5.4A).

Covers AudioResult/AudioChunk data structures, the provider + manager streaming
interfaces, failure/cancellation safety, and the prepared audio-event contracts.
All run offline with injected fakes.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import numpy as np
import pytest

from voice.audio_events import audio_event_from_chunk, audio_event_from_result, to_audio_event
from voice.config import KokoroConfig
from voice.health import AudioCache
from voice.providers.kokoro import AudioChunk, AudioResult, KokoroProvider
from voice.voice_manager import VoiceManager

SAMPLE_VOICES = ["af_heart", "af_bella", "am_adam"]


class FakePipeline:
    def __init__(self, fail: bool = False, sample_rate: int = 24000, block: bool = False) -> None:
        self.fail = fail
        self.sample_rate = sample_rate
        self.block = block
        self.calls: list[tuple[str, str]] = []

    def __call__(self, text: str, voice: str = ""):
        self.calls.append((text, voice))
        if self.block:
            import time as _t

            _t.sleep(0.2)
        if self.fail:
            raise RuntimeError("synthesis boom")
        audio = np.zeros(self.sample_rate, dtype=np.float32)  # ~10 x 100ms frames
        yield ("g", "p", audio)


class SlowFakePipeline(FakePipeline):
    def __init__(self, fail: bool = False, sample_rate: int = 24000) -> None:
        super().__init__(fail=fail, sample_rate=sample_rate, block=True)


class FakeDiscoverer:
    def __init__(self, voices: list[str]) -> None:
        self.voices = list(voices)

    def discover(self, repo_id: str, lang_code: str) -> list[str]:
        return list(self.voices)


async def _ready_manager(tmp_path, *, fail_pipeline: bool = False, pipeline_cls=FakePipeline):
    config = KokoroConfig.load(cache_directory=str(tmp_path / "audio_cache"), default_voice="af_heart")
    pipeline = pipeline_cls(fail=fail_pipeline, sample_rate=config.sample_rate)

    def factory(*, repo_id: str, lang_code: str, device):
        return pipeline

    provider = KokoroProvider(
        config=config,
        pipeline_factory=factory,
        voice_discoverer=FakeDiscoverer(SAMPLE_VOICES),
        cache=AudioCache(config.cache_directory),
    )
    manager = VoiceManager()
    await manager.register_provider(provider.name, provider, set_active=True)
    await manager.initialize()
    return manager, provider, pipeline


# --- AudioResult ------------------------------------------------------------ #
def test_audio_result_metadata_fields():
    result = AudioResult(
        success=True,
        request_id="r1",
        audio_id="a1",
        format="wav",
        channels=2,
        stream_available=True,
        metadata={"visemes": [1, 2], "emotion": "calm"},
    )
    assert result.audio_id == "a1"
    assert result.format == "wav"
    assert result.channels == 2
    assert result.stream_available is True
    assert result.metadata == {"visemes": [1, 2], "emotion": "calm"}


def test_audio_result_backwards_compatible():
    result = AudioResult(
        success=True,
        request_id="r1",
        voice="af_heart",
        path="/x.wav",
        sample_rate=24000,
        duration_ms=123.0,
        error=None,
    )
    assert result.success and result.request_id == "r1"
    assert result.audio_id == ""
    assert result.format == "wav"
    assert result.channels == 1
    assert result.stream_available is False
    assert result.metadata == {}


# --- AudioChunk ------------------------------------------------------------- #
def test_audio_chunk_ordering_timestamps_completion():
    chunks = [
        AudioChunk(
            request_id="r",
            voice="v",
            index=i,
            audio=None,
            sample_rate=24000,
            final=(i == 2),
            timestamp=i * 100.0,
            duration=100.0,
            audio_id="a",
        )
        for i in range(3)
    ]
    assert [c.index for c in chunks] == [0, 1, 2]
    assert [c.timestamp for c in chunks] == [0.0, 100.0, 200.0]
    assert chunks[0].final is False
    assert chunks[-1].final is True


# --- streaming: provider ---------------------------------------------------- #
async def test_stream_successful_multiple_chunks(tmp_path):
    manager, provider, _ = await _ready_manager(tmp_path)
    chunks = [c async for c in provider.stream_audio("hello", voice="af_heart")]
    assert chunks, "expected streamed chunks"
    assert len(chunks) > 1
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert chunks[0].final is False
    assert chunks[-1].final is True
    assert chunks[0].audio_id
    assert chunks[0].timestamp == 0.0
    assert chunks[1].timestamp > chunks[0].timestamp
    assert chunks[0].path is not None
    assert all(c.path is None for c in chunks[1:])


async def test_stream_final_chunk_only_once(tmp_path):
    manager, provider, _ = await _ready_manager(tmp_path)
    chunks = [c async for c in provider.stream_audio("hi", voice="af_heart")]
    assert sum(1 for c in chunks if c.final) == 1
    assert chunks[-1].final


async def test_stream_provider_failure_closes_cleanly(tmp_path):
    manager, provider, _ = await _ready_manager(tmp_path, fail_pipeline=True)
    chunks = [c async for c in provider.stream_audio("hi", voice="af_heart")]
    assert chunks == []  # closes cleanly, no exception, no hang


async def test_stream_unavailable_provider_closes_cleanly(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "kokoro", None)
    manager, provider, _ = await _ready_manager(tmp_path)
    chunks = [c async for c in provider.stream_audio("hi", voice="af_heart")]
    assert chunks == []  # Kokoro gone -> clean close


# --- streaming: manager ----------------------------------------------------- #
async def test_manager_stream_successful(tmp_path):
    manager, provider, _ = await _ready_manager(tmp_path)
    chunks = [c async for c in manager.stream_synthesis("hello", voice="af_heart")]
    assert chunks and chunks[-1].final


async def test_manager_stream_unavailable_provider_closes(tmp_path):
    manager = VoiceManager()  # no provider registered
    chunks = [c async for c in manager.stream_synthesis("hi")]
    assert chunks == []  # closes cleanly, no ProviderUnavailableError raised


async def test_manager_stream_provider_failure_closes(tmp_path):
    manager, provider, _ = await _ready_manager(tmp_path, fail_pipeline=True)
    chunks = [c async for c in manager.stream_synthesis("hi")]
    assert chunks == []


# --- cancellation safety ---------------------------------------------------- #
async def test_stream_cancellation_via_aclose(tmp_path):
    manager, provider, _ = await _ready_manager(tmp_path)
    gen = provider.stream_audio("hello", voice="af_heart")
    first = await gen.__anext__()
    assert first.index == 0
    await gen.aclose()  # must not hang


async def test_stream_cancellation_during_synthesis(tmp_path):
    manager, provider, _ = await _ready_manager(tmp_path, pipeline_cls=SlowFakePipeline)

    collected: list = []

    async def collect():
        async for chunk in manager.stream_synthesis("hello"):
            collected.append(chunk)

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.05)
    task.cancel()
    done, pending = await asyncio.wait({task}, timeout=2.0)
    assert not pending, "streaming task hung instead of cancelling"
    assert task in done


# --- audio event contracts -------------------------------------------------- #
def test_audio_event_contract_shape():
    event = to_audio_event(audio_id="a1", url="/audio/x.wav", sequence=3, final=True, voice="af_heart")
    assert event == {
        "type": "audio",
        "audio_id": "a1",
        "url": "/audio/x.wav",
        "sequence": 3,
        "final": True,
        "voice": "af_heart",
    }


def test_audio_event_from_result(tmp_path):
    result = AudioResult(
        success=True,
        request_id="r",
        voice="af_heart",
        path=str(tmp_path / "audio_cache" / "abc.wav"),
        audio_id="a1",
    )
    event = audio_event_from_result(result, base_url="http://127.0.0.1:8000")
    assert event["type"] == "audio"
    assert event["audio_id"] == "a1"
    assert event["url"] == "http://127.0.0.1:8000/audio/abc.wav"
    assert event["sequence"] == 0 and event["final"] is True


def test_audio_event_from_chunk():
    chunk = AudioChunk(
        request_id="r",
        voice="af_heart",
        index=2,
        audio=None,
        sample_rate=24000,
        final=False,
        audio_id="a1",
        path="/abs/abc.wav",
    )
    event = audio_event_from_chunk(chunk, base_url="http://x")
    assert event["sequence"] == 2
    assert event["final"] is False
    assert event["audio_id"] == "a1"
    assert event["url"] == "http://x/audio/abc.wav"
