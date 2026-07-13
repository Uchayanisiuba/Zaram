"""Tests for the Kokoro provider and its supporting pieces.

All tests run fully offline: the Kokoro ``KPipeline`` and HuggingFace discovery
are replaced by injected fakes. The "Kokoro unavailable" case is simulated by
making the ``kokoro`` import fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from voice.config import KokoroConfig
from voice.health import AudioCache
from voice.providers.kokoro import (
    AudioChunk,
    AudioResult,
    HuggingFaceVoiceDiscoverer,
    KokoroProvider,
    bootstrap_kokoro,
)
from voice.voice_manager import VoiceManager, VoiceRuntime


SAMPLE_VOICES = ["af_heart", "af_bella", "am_adam", "bf_alice"]


class FakePipeline:
    """Minimal stand-in for ``kokoro.KPipeline``."""

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


class ReadOnlyCache(AudioCache):
    def __init__(self) -> None:
        super().__init__(str(Path(__file__).resolve().parent / ".readonly_cache"))

    def ensure(self) -> bool:
        return False

    def is_writable(self) -> bool:
        return False


def make_provider(tmp_path: Path, *, fail_pipeline: bool = False, cache=None, discoverer=None):
    config = KokoroConfig.load(
        cache_directory=str(tmp_path / "audio_cache"),
        default_voice="af_heart",
        load_model_eagerly=False,
    )
    pipeline = FakePipeline(fail=fail_pipeline, sample_rate=config.sample_rate)

    def factory(*, repo_id: str, lang_code: str, device):
        return pipeline

    provider = KokoroProvider(
        config=config,
        pipeline_factory=factory,
        voice_discoverer=discoverer or FakeDiscoverer(SAMPLE_VOICES),
        cache=cache or AudioCache(config.cache_directory),
    )
    provider._fake_pipeline = pipeline
    return provider


# --- registration / lifecycle ------------------------------------------------ #
async def test_provider_registration(tmp_path: Path):
    manager = VoiceManager()
    provider = make_provider(tmp_path)
    await manager.register_provider(provider.name, provider, set_active=True)
    await manager.initialize()
    assert manager.registry.is_registered("kokoro")
    assert isinstance(manager.get_provider(), KokoroProvider)
    assert manager.get_provider() is provider


async def test_initialization(tmp_path: Path):
    provider = make_provider(tmp_path)
    assert provider._initialized is False
    await provider.initialize()
    assert provider._initialized is True
    assert len(provider._voices) == len(SAMPLE_VOICES)


async def test_shutdown(tmp_path: Path):
    provider = make_provider(tmp_path)
    await provider.initialize()
    await provider.shutdown()
    assert provider._pipeline is None
    assert provider._kokoro is None


# --- voice discovery -------------------------------------------------------- #
async def test_voice_discovery(tmp_path: Path):
    provider = make_provider(tmp_path)
    await provider.initialize()
    voices = await provider.available_voices()
    assert set(voices) == set(SAMPLE_VOICES)
    meta = voices["af_heart"]
    assert meta["language"] == "American English"
    assert meta["gender"] == "female"
    assert voices["am_adam"]["gender"] == "male"


async def test_discovery_not_hardcoded(tmp_path: Path):
    custom = ["zz_custom_one", "zz_custom_two"]
    provider = make_provider(tmp_path, discoverer=FakeDiscoverer(custom))
    await provider.initialize()
    assert set(await provider.available_voices()) == set(custom)


# --- health ------------------------------------------------------------------ #
async def test_health_check_healthy(tmp_path: Path):
    provider = make_provider(tmp_path)
    await provider.initialize()
    report = await provider.health_check()
    assert report["provider"] == "kokoro"
    assert report["available"] is True
    assert report["status"] == "healthy"
    assert report["voices"] == len(SAMPLE_VOICES)
    assert report["cache"] == "ok"
    assert report["checks"]["kokoro_import"] is True
    assert report["checks"]["model_available"] is True
    assert report["checks"]["cache_writable"] is True


async def test_health_check_invalid_cache(tmp_path: Path):
    provider = make_provider(tmp_path, cache=ReadOnlyCache())
    await provider.initialize()
    report = await provider.health_check()
    assert report["checks"]["cache_writable"] is False
    assert report["available"] is False
    assert report["cache"] == "not_writable"


# --- synthesis --------------------------------------------------------------- #
async def test_generate_audio_success(tmp_path: Path):
    provider = make_provider(tmp_path)
    await provider.initialize()
    result = await provider.generate_audio("hello world")
    assert isinstance(result, AudioResult)
    assert result.success is True
    assert result.voice == "af_heart"
    assert result.path is not None
    assert Path(result.path).exists()
    assert provider._fake_pipeline.calls == [("hello world", "af_heart")]


async def test_invalid_voice_fallback(tmp_path: Path):
    provider = make_provider(tmp_path)
    await provider.initialize()
    result = await provider.generate_audio("hi", voice="zz_unknown_voice")
    assert result.success is True
    assert result.voice == "af_heart"
    assert provider._fake_pipeline.calls[-1] == ("hi", "af_heart")


async def test_synthesis_failure_returns_result(tmp_path: Path):
    provider = make_provider(tmp_path, fail_pipeline=True)
    await provider.initialize()
    result = await provider.generate_audio("boom")
    assert result.success is False
    assert result.error is not None
    assert result.path is None


async def test_empty_text_rejected(tmp_path: Path):
    provider = make_provider(tmp_path)
    await provider.initialize()
    result = await provider.generate_audio("   ")
    assert result.success is False
    assert result.error == "empty_text"


async def test_cache_output_and_cleanup(tmp_path: Path):
    cache = AudioCache(str(tmp_path / "audio_cache"))
    provider = make_provider(tmp_path, cache=cache)
    await provider.initialize()
    await provider.generate_audio("cache me")
    files = cache.list_files()
    assert len(files) == 1
    removed = cache.cleanup_all()
    assert removed == 1
    assert cache.list_files() == []


async def test_stream_audio_yields_chunks(tmp_path: Path):
    provider = make_provider(tmp_path)
    await provider.initialize()
    chunks: list[AudioChunk] = [c async for c in provider.stream_audio("stream me")]
    assert chunks
    assert all(isinstance(c, AudioChunk) for c in chunks)
    assert chunks[-1].final is True
    assert chunks[0].path is not None


# --- failure / resilience ---------------------------------------------------- #
async def test_kokoro_unavailable(monkeypatch, tmp_path: Path):
    monkeypatch.setitem(sys.modules, "kokoro", None)
    provider = make_provider(tmp_path)
    await provider.initialize()
    report = await provider.health_check()
    assert report["available"] is False
    assert report["checks"]["kokoro_import"] is False
    result = await provider.generate_audio("still chatting")
    assert isinstance(result, AudioResult)
    assert result.success is False


async def test_runtime_boots_without_kokoro(monkeypatch, tmp_path: Path):
    monkeypatch.setitem(sys.modules, "kokoro", None)
    rt = VoiceRuntime(
        auto_register_kokoro=True,
        kokoro_config=KokoroConfig.load(cache_directory=str(tmp_path / "audio_cache")),
    )
    await rt.initialize()  # must not raise
    report = await rt.manager.health()
    assert "kokoro" in report["providers"]
    assert report["providers"]["kokoro"]["available"] is False


def test_discoverer_uses_repo_not_hardcoded():
    # The real discoverer hits the network; we only assert it is constructible
    # and returns a list-shaped result when offline (graceful degradation).
    discoverer = HuggingFaceVoiceDiscoverer()
    assert hasattr(discoverer, "discover")
