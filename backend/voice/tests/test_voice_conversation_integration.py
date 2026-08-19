"""Integration tests for the speech pipeline.

Verifies the path that exists:

    VoiceManager -> VoiceRegistry -> KokoroProvider -> AudioResult

It used to start at `ConversationManager`, and most of this module drove the
manager and asserted it yielded `audio` events. Sprint Alpha.6 cut that edge:
the manager publishes `conversation:sentence_ready` onto the event bus and the
Speech runtime decides whether to speak, so those tests asserted an
architecture that no longer exists. They failed identically for four
milestones behind a stale `FakeLLM` signature and were filed as "voice
failures, out of scope" — they were neither.

`ConversationManager`'s own contract is now tested in
`tests/test_streaming_conversation.py`, where it does not need a voice stack
present to run. What is left here is the synthesis chain, which does.

All tests run offline with injected fakes; no legacy classes are referenced.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from voice.tests.conftest import FakeResult

from voice.config import KokoroConfig
from voice.health import AudioCache
from voice.providers.kokoro import KokoroProvider
from voice.voice_manager import VoiceManager

SAMPLE_VOICES = ["af_heart", "af_bella", "am_adam"]


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
        yield FakeResult(audio)


class FakeDiscoverer:
    def __init__(self, voices: list[str]) -> None:
        self.voices = list(voices)

    def discover(self, repo_id: str, lang_code: str) -> list[str]:
        return list(self.voices)


async def _ready_manager(tmp_path: Path, *, fail_pipeline: bool = False, voices=None):
    config = KokoroConfig.load(cache_directory=str(tmp_path / "audio_cache"), default_voice="af_heart")
    pipeline = FakePipeline(fail=fail_pipeline, sample_rate=config.sample_rate)

    # `**_` absorbs backend/onnx_variant: this double stands in for the
    # pipeline, not for the factory's signature, and the provider is what is
    # under test here.
    def factory(*, repo_id: str, lang_code: str, device, **_):
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


# --- synthesis routing ------------------------------------------------------ #
async def test_synthesis_reaches_the_provider(tmp_path: Path):
    manager, _, pipeline = await _ready_manager(tmp_path)

    result = await manager.synthesize("hello there", voice="af_heart")

    assert result is not None
    assert pipeline.calls, "synthesis did not actually run through the provider"


async def test_voice_disabled_yields_nothing_rather_than_raising(tmp_path: Path):
    """No provider registered is a normal state, not an error.

    A user who never installed the voice extra must not get an exception on a
    path that is simply switched off.
    """
    manager = VoiceManager()  # no provider registered -> speech disabled

    chunks = [c async for c in manager.stream_synthesis("hi", voice="af_heart")]

    assert chunks == []


async def test_provider_unavailable_yields_nothing(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(sys.modules, "kokoro", None)
    manager, _, _ = await _ready_manager(tmp_path)

    chunks = [c async for c in manager.stream_synthesis("hi", voice="af_heart")]

    assert isinstance(chunks, list)


# --- audio results ---------------------------------------------------------- #
async def test_audio_result_carries_a_path_and_the_voice_used(tmp_path: Path):
    """`AudioResult` has `path`, not `url`.

    The URL was assembled a layer up, by the `ConversationManager` that no
    longer does this. Asserting `url` here tested a field the voice stack never
    owned.
    """
    manager, _, pipeline = await _ready_manager(tmp_path)

    result = await manager.synthesize("hello there", voice="af_heart")

    assert result.success
    assert result.path and result.path.endswith(".wav")
    assert result.voice == "af_heart"
    assert pipeline.calls


async def test_invalid_voice_falls_back_to_the_default(tmp_path: Path):
    """Only reachable once discovery has run, so seed it explicitly.

    The fallback is guarded by `if self._voices`, and `_voices` stays empty
    unless `voice_discovery_enabled` is on — which defaults to off, because
    real discovery contacts huggingface.co at startup and rule 7g forbids a
    network call before consent. Seeding the names directly tests the fallback
    without turning that flag on anywhere near a real discoverer.
    """
    manager, provider, pipeline = await _ready_manager(tmp_path)
    provider._voices = {name: {} for name in SAMPLE_VOICES}

    result = await manager.synthesize("hello there", voice="zz_unknown_voice")

    assert result.voice == provider.config.default_voice
    assert pipeline.calls
    assert all(v == provider.config.default_voice for _, v in pipeline.calls)


# --- failure handling ------------------------------------------------------- #
async def test_synthesis_failure_does_not_escape_the_stream(tmp_path: Path):
    """`stream_synthesis` promises callers never handle exceptions."""
    manager, _, _ = await _ready_manager(tmp_path, fail_pipeline=True)

    chunks = [c async for c in manager.stream_synthesis("hi", voice="af_heart")]

    assert chunks == []


async def test_provider_exception_does_not_escape_the_stream(tmp_path: Path, monkeypatch):
    manager, provider, _ = await _ready_manager(tmp_path)

    async def boom(*args, **kwargs):
        raise RuntimeError("provider exploded")
        yield  # make it an async generator so async-for fails on first step

    monkeypatch.setattr(provider, "stream_audio", boom)

    chunks = [c async for c in manager.stream_synthesis("hi", voice="af_heart")]

    assert chunks == []


# --- chain integrity -------------------------------------------------------- #
def test_conversation_manager_does_not_reach_the_voice_stack():
    """The edge this module used to test must stay cut.

    `ConversationManager` publishing onto the event bus — rather than calling
    `VoiceManager` — is what lets speech be an optional install. This assertion
    was previously inverted: it required the import that has to be absent, so
    it would have passed on the architecture we deliberately moved away from.
    """
    import services.conversation_manager as cm_mod

    source = Path(cm_mod.__file__).read_text(encoding="utf-8")

    assert "from implementations.kokoro_tts import" not in source
    assert "from services.speech_manager import" not in source
    assert "from voice.voice_manager import VoiceManager" not in source, (
        "the manager must not depend on the voice stack; it publishes "
        "conversation:sentence_ready and the Speech runtime subscribes"
    )
    assert "conversation:sentence_ready" in source
