"""Speech starts up behind the first screen instead of in front of it.

Asked for 4 October 2026: *"perhaps we should delay Kokoro."* Stack-sampling a slow boot
had put the last ten to twenty seconds of it inside `KokoroProvider.initialize`, where
`import kokoro` -- torch, spaCy -- ran **synchronously, on the event loop**, for everyone
with the voice extra installed, whether or not they ever spoke. For that long the whole
backend answered nothing, `/health` included.

Four properties, and each is the reason a plain "make it lazy" would have been wrong:

* **The import is off the event loop.** Moving *when* it runs is worthless if it still
  blocks the loop wherever it runs, so this asserts the loop keeps ticking during it.
* **An utterance that arrives early waits; it does not fail.** The first reply of a
  session can land while the engine is still loading, and "unavailable" would be a false
  report about a voice that is installed and a moment from ready.
* **A provider nobody initialised does not wait.** The wait exists for a start-up in
  progress; waiting for one that is not coming would be a hang.
* **Boot does not await it, and shutdown does not wait for it.**
"""

from __future__ import annotations

import asyncio
import inspect
import time

import numpy as np
import pytest

from voice.config import KokoroConfig
from voice.providers import kokoro as kokoro_module
from voice.providers.kokoro import KokoroProvider
from voice.tests.conftest import FakeResult


class _Pipeline:
    def __init__(self, rate):
        self.rate = rate

    def __call__(self, text, voice=""):
        yield FakeResult(np.zeros(self.rate, dtype=np.float32))


class _Discoverer:
    def discover(self, repo_id, lang_code):
        return ["af_heart"]


def _provider(tmp_path):
    config = KokoroConfig.load(cache_directory=str(tmp_path / "audio"), default_voice="af_heart")
    return KokoroProvider(
        config=config,
        pipeline_factory=lambda **_kw: _Pipeline(config.sample_rate),
        voice_discoverer=_Discoverer(),
    )


def _slow_load(provider, seconds):
    """Replace the import with something slow and blocking, like the real one."""

    def load():
        time.sleep(seconds)
        provider._kokoro = object()  # present, so the pipeline path is reachable
        provider._voices = {"af_heart": {}}

    provider._load_package = load


class TestTheImportIsOffTheEventLoop:
    @pytest.mark.asyncio
    async def test_the_loop_keeps_running_while_the_engine_loads(self, tmp_path):
        """**The reason this change is not merely a reordering.** `import kokoro` took
        ten to twenty seconds and sat inside an `async def` with nothing awaited, so it
        blocked the event loop and the backend answered nothing for that long. Delaying
        it behind the first screen only helps if the loop is free while it runs."""
        provider = _provider(tmp_path)
        _slow_load(provider, 0.6)

        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.02)
                ticks += 1

        watcher = asyncio.ensure_future(ticker())
        try:
            await provider.initialize()
        finally:
            watcher.cancel()
        # ~30 ticks if the loop was free; a blocked loop gets one or none.
        assert ticks >= 10, f"the event loop was blocked during start-up (ticks={ticks})"

    def test_the_import_and_discovery_are_one_method_that_can_run_in_a_thread(self):
        assert hasattr(KokoroProvider, "_load_package")
        source = inspect.getsource(KokoroProvider.initialize)
        assert "to_thread(self._load_package)" in source
        # And the import itself is no longer written inside the coroutine.
        assert "import kokoro" not in source


class TestAnUtteranceThatArrivesEarly:
    @pytest.mark.asyncio
    async def test_it_waits_for_the_engine_and_then_speaks(self, tmp_path):
        provider = _provider(tmp_path)
        _slow_load(provider, 0.4)
        start = asyncio.ensure_future(provider.initialize())
        await asyncio.sleep(0.05)  # start-up is in progress, not finished
        assert provider._initializing and not provider._initialized

        result = await provider.generate_audio("hello there", voice="af_heart")

        assert result.success, result.error
        assert provider._initialized
        await start

    @pytest.mark.asyncio
    async def test_it_does_not_report_a_loading_voice_as_unavailable(self, tmp_path):
        """A voice that is installed and a few seconds from ready is not unavailable,
        and saying so is the false claim this whole change is built around avoiding."""
        provider = _provider(tmp_path)
        _slow_load(provider, 0.3)
        start = asyncio.ensure_future(provider.initialize())
        await asyncio.sleep(0.05)
        result = await provider.generate_audio("hello", voice="af_heart")
        await start
        assert "unavailable" not in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_it_gives_up_with_an_honest_sentence_if_start_up_never_ends(self, tmp_path, monkeypatch):
        monkeypatch.setattr(kokoro_module, "STARTUP_WAIT_SECONDS", 0.2)
        provider = _provider(tmp_path)
        provider._initializing = True  # a start-up that has begun and will not finish
        result = await provider.generate_audio("hello", voice="af_heart")
        assert result.success is False
        assert "still starting" in result.error

    @pytest.mark.asyncio
    async def test_a_provider_nobody_initialised_does_not_wait(self, tmp_path):
        """The wait is for a start-up in progress. Waiting for one that is not coming
        would be a hang, so an uninitialised provider fails at once."""
        provider = _provider(tmp_path)
        started = time.monotonic()
        result = await provider.generate_audio("hello", voice="af_heart")
        assert time.monotonic() - started < 2
        assert result.success is False

    @pytest.mark.asyncio
    async def test_a_failed_start_up_releases_anything_waiting_on_it(self, tmp_path):
        """Released whichever way it ends. A start-up that raised must not leave an
        utterance waiting out the whole timeout for something that is not coming."""
        provider = _provider(tmp_path)

        def boom():
            time.sleep(0.2)
            raise RuntimeError("import exploded")

        provider._load_package = boom
        start = asyncio.ensure_future(provider.initialize())
        await asyncio.sleep(0.05)
        waiter = asyncio.ensure_future(provider.generate_audio("hello", voice="af_heart"))
        with pytest.raises(RuntimeError):
            await start
        result = await asyncio.wait_for(waiter, timeout=5)
        assert result.success is False
        assert provider._initializing is False


class TestTheRuntime:
    def _runtime(self):
        from core.event_bus import EventBus
        from runtimes.speech.runtime import SpeechRuntime

        return SpeechRuntime(EventBus())

    @pytest.mark.asyncio
    async def test_it_reads_as_initialising_the_instant_it_is_asked_to_start(self, monkeypatch):
        """Set synchronously, so there is no moment at which it reads as anything else.
        A gap there is where a status check would say 'not installed'."""
        runtime = self._runtime()
        gate = asyncio.Event()

        async def slow_initialize():
            await gate.wait()

        monkeypatch.setattr(runtime, "initialize", slow_initialize)
        runtime.start_in_background()
        assert runtime.health_check()["state"] == "initializing"
        gate.set()
        await asyncio.wait_for(runtime._startup_task, timeout=5)

    @pytest.mark.asyncio
    async def test_it_does_not_block_the_caller(self, monkeypatch):
        runtime = self._runtime()

        async def never():
            await asyncio.sleep(30)

        monkeypatch.setattr(runtime, "initialize", never)
        started = time.monotonic()
        runtime.start_in_background()
        assert time.monotonic() - started < 0.5
        runtime._startup_task.cancel()

    @pytest.mark.asyncio
    async def test_a_failure_becomes_an_error_state_not_a_silent_background_exception(self, monkeypatch):
        runtime = self._runtime()

        async def broken():
            raise RuntimeError("no engine")

        monkeypatch.setattr(runtime, "initialize", broken)
        runtime.start_in_background()
        await asyncio.wait_for(runtime._startup_task, timeout=5)
        assert runtime.health_check()["state"] == "error"

    @pytest.mark.asyncio
    async def test_speak_requests_are_subscribed_before_the_slow_part(self, monkeypatch):
        """Start-up is behind the first screen now, so a speak request can arrive while
        the engine is still loading. Subscribing afterwards would drop it silently."""
        from runtimes.speech import runtime as runtime_module

        runtime = self._runtime()
        gate = asyncio.Event()
        seen = {}

        class SlowConnector:
            connector_id = "kokoro"
            connector_type = "local"

            async def initialize(self):
                seen["subscribed_while_loading"] = runtime._unsubscribe_executive_speak is not None
                await gate.wait()

            async def shutdown(self):
                pass

        monkeypatch.setattr(runtime_module, "KokoroConnector", SlowConnector)
        runtime.start_in_background()
        await asyncio.sleep(0.1)
        assert seen.get("subscribed_while_loading") is True
        gate.set()
        await asyncio.wait_for(runtime._startup_task, timeout=5)

    @pytest.mark.asyncio
    async def test_shutdown_ends_a_start_up_still_in_progress(self, monkeypatch):
        """The provider's own shutdown takes the lock start-up holds during the import,
        so without this, quitting would wait out a load nobody wants any more."""
        runtime = self._runtime()

        async def long_initialize():
            await asyncio.sleep(60)

        monkeypatch.setattr(runtime, "initialize", long_initialize)
        runtime.start_in_background()
        await asyncio.sleep(0.05)
        started = time.monotonic()
        await asyncio.wait_for(runtime.shutdown(), timeout=10)
        assert time.monotonic() - started < 5
        assert runtime._startup_task.done()


class TestBootDoesNotAwaitIt:
    def test_the_bootstrapper_starts_speech_without_waiting_for_it(self):
        """Asserted on the code, because the property is that something is *not*
        awaited -- and a test that boots the kernel and times it would pass or fail
        on how fast the machine happens to be."""
        import core.bootstrapper as bootstrapper

        source = inspect.getsource(bootstrapper)
        assert "speech_runtime.start_in_background()" in source
        assert "await self.speech_runtime.initialize()" not in source

    def test_the_startup_message_no_longer_claims_it_is_initialised(self):
        import main

        assert "Speech Runtime starting in the background" in inspect.getsource(main.startup_event)


class TestTheFirstUtteranceDoesNotFreezeTheBackend:
    """**The second blocking call, found by measuring the first fix.** Moving the import
    off the event loop and then speaking early showed a `/health` that did not answer for
    ~25 s: `generate_audio` called `_ensure_pipeline` -- ~300 MB of weights -- directly from
    a coroutine, so the first utterance of every session froze the whole backend while
    Kokoro loaded. Pre-existing, and the same defect as the import."""

    @staticmethod
    def _slow_pipeline(provider, seconds, built):
        real = provider._pipeline_factory

        def build(*, lang_code="a", **kw):
            built.append(lang_code)
            time.sleep(seconds)  # blocking, like a real weights load
            return real(lang_code=lang_code, **kw)

        provider._pipeline_factory = build

    @pytest.mark.asyncio
    async def test_the_loop_keeps_running_while_the_weights_load(self, tmp_path):
        provider = _provider(tmp_path)
        provider._kokoro = object()
        provider._initialized = True
        provider._voices = {"af_heart": {}}
        self._slow_pipeline(provider, 0.6, [])

        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.02)
                ticks += 1

        watcher = asyncio.ensure_future(ticker())
        try:
            result = await provider.generate_audio("hello", voice="af_heart")
        finally:
            watcher.cancel()
        assert result.success, result.error
        assert ticks >= 10, f"the event loop was blocked while the model loaded (ticks={ticks})"

    @pytest.mark.asyncio
    async def test_two_first_utterances_build_one_pipeline(self, tmp_path):
        provider = _provider(tmp_path)
        provider._kokoro = object()
        provider._initialized = True
        provider._voices = {"af_heart": {}}
        built: list = []
        self._slow_pipeline(provider, 0.3, built)

        first, second = await asyncio.gather(
            provider.generate_audio("one", voice="af_heart"),
            provider.generate_audio("two", voice="af_heart"),
        )
        assert first.success and second.success
        assert len(built) == 1, f"the pipeline was built {len(built)} times"

    def test_neither_blocking_call_is_made_from_the_coroutine(self):
        """Asserted on the code as well, because the behavioural tests above pass or fail
        on timing and this does not: the loader and the voice fetch are reached only
        through `_pipeline_for`, which hands them to a worker thread."""
        source = inspect.getsource(KokoroProvider.generate_audio)
        assert "self._ensure_pipeline(" not in source
        assert "self._ensure_voice(" not in source
        assert "_pipeline_for(" in source
        assert "to_thread(self._ensure_pipeline" in inspect.getsource(KokoroProvider._pipeline_for)
