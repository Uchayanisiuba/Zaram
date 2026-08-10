"""Phoneme timings survive the trip out of Kokoro.

`docs/EMBODIMENT-SPIKE.md` established that Kokoro already computes word
timings and Zaram threw them away: ``KPipeline.Result`` supports tuple
unpacking for backwards compatibility, ``tokens`` is reachable only as an
attribute, and the provider unpacked. Nothing was broken, nothing errored, and
the data was gone before anyone could want it.

The cost of keeping them is zero — ``pred_dur`` comes out of the same forward
pass as the waveform. So these tests are not about performance. They are about
the shape of the seam: an engine that cannot produce timings returns an empty
list, timings cross the boundary as a plain structure rather than as Kokoro's
``MToken``, and offsets are absolute across a multi-chunk utterance.
"""

from __future__ import annotations

import numpy as np
import pytest

from voice.config import KokoroConfig
from voice.providers.base import SpeechTiming
from voice.providers.kokoro import KokoroProvider
from voice.tests.conftest import FakeResult, FakeToken

SR = 24000


class TimedPipeline:
    """Yields results carrying tokens, the way the real pipeline does."""

    def __init__(self, *results):
        self._results = results

    def __call__(self, text: str, voice: str = ""):
        yield from self._results


def _provider() -> KokoroProvider:
    return KokoroProvider(KokoroConfig(sample_rate=SR))


def _tenth_second() -> np.ndarray:
    return np.zeros(SR // 10, dtype=np.float32)


class TestTimingsSurvive:
    def test_tokens_are_not_discarded(self):
        """The defect itself: unpacking the result dropped `tokens`."""
        pipeline = TimedPipeline(
            FakeResult(
                _tenth_second(),
                [
                    FakeToken("Harbour", "hˈɑɹbəɹ", 0.10, 0.45),
                    FakeToken("Lane", "lˈAn", 0.45, 0.80),
                ],
            )
        )
        _audio, timings = _provider()._run_synthesis(pipeline, "Harbour Lane", "af_heart")

        assert [t.text for t in timings] == ["Harbour", "Lane"]
        assert timings[0].phonemes == "hˈɑɹbəɹ"
        assert (timings[0].start_s, timings[0].end_s) == (0.10, 0.45)

    def test_they_cross_the_boundary_as_a_plain_structure(self):
        """Not as Kokoro's MToken.

        CLAUDE.md keeps TTS behind an interface so the engine stays replaceable.
        Lip sync is where that coupling would creep in: if the renderer received
        MTokens, swapping the engine would mean rewriting the renderer.
        """
        pipeline = TimedPipeline(FakeResult(_tenth_second(), [FakeToken("hi", "h", 0.0, 0.2)]))
        _audio, timings = _provider()._run_synthesis(pipeline, "hi", "af_heart")

        assert all(isinstance(t, SpeechTiming) for t in timings)
        assert type(timings[0]).__module__.startswith("voice.providers.base")

    def test_untimed_tokens_are_skipped_not_zeroed(self):
        """G2P returns None timestamps for anything that never becomes sound.

        Punctuation and whitespace arrive with `start_ts` of None. Emitting them
        with a zero span would put a viseme on silence — a mouth moving for a
        full stop.
        """
        pipeline = TimedPipeline(
            FakeResult(
                _tenth_second(),
                [
                    FakeToken("Yes", "jˈɛs", 0.0, 0.30),
                    FakeToken(".", "", None, None),
                    FakeToken(" ", "", None, None),
                ],
            )
        )
        _audio, timings = _provider()._run_synthesis(pipeline, "Yes.", "af_heart")

        assert [t.text for t in timings] == ["Yes"]

    def test_offsets_are_absolute_across_chunks(self):
        """A caller must never learn that the engine synthesised in pieces.

        Each chunk's timestamps restart at zero. Without offsetting by the audio
        already emitted, a second sentence claims to be spoken at the same
        moment as the first — and the mouth for the whole utterance fires in the
        opening tenth of a second.
        """
        chunk = _tenth_second()  # 0.1s each
        pipeline = TimedPipeline(
            FakeResult(chunk, [FakeToken("one", "wˈʌn", 0.0, 0.09)]),
            FakeResult(chunk, [FakeToken("two", "tˈu", 0.0, 0.09)]),
        )
        _audio, timings = _provider()._run_synthesis(pipeline, "one two", "af_heart")

        assert len(timings) == 2
        assert timings[0].start_s == pytest.approx(0.0)
        # Offset by exactly one chunk of audio, not by the second chunk's own
        # relative zero.
        assert timings[1].start_s == pytest.approx(0.10)
        assert timings[1].end_s == pytest.approx(0.19)

    def test_timings_rise(self):
        """Monotonic, because a renderer scrubs them against playback time."""
        chunk = _tenth_second()
        pipeline = TimedPipeline(
            FakeResult(chunk, [FakeToken("a", "a", 0.0, 0.04), FakeToken("b", "b", 0.04, 0.09)]),
            FakeResult(chunk, [FakeToken("c", "c", 0.0, 0.05)]),
        )
        _audio, timings = _provider()._run_synthesis(pipeline, "a b c", "af_heart")

        starts = [t.start_s for t in timings]
        assert starts == sorted(starts)
        assert all(t.end_s >= t.start_s for t in timings)


class TestAbsenceIsRepresentable:
    def test_an_engine_with_no_timings_returns_an_empty_list(self):
        """The seam a second implementation slots into.

        Not None, and not a raise. A renderer checks `if timings` and falls back
        to what it can do without them.
        """
        pipeline = TimedPipeline(FakeResult(_tenth_second(), []))
        audio, timings = _provider()._run_synthesis(pipeline, "hi", "af_heart")

        assert audio is not None
        assert timings == []

    def test_no_audio_yields_no_timings(self):
        pipeline = TimedPipeline()
        audio, timings = _provider()._run_synthesis(pipeline, "hi", "af_heart")

        assert audio is None
        assert timings == []
