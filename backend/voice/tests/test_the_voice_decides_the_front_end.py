"""The voice picks the pronunciation, whichever voice is the default.

Written 3 September 2026 when the default moved from `am_michael` (American
male) to `bm_fable` (British male), and kept through two more changes the same
day, and once more the next: `bm_fable` was judged too deep, `am_onyx` was
chosen from seven samples, and `am_michael` was restored after living with
Onyx in the running product. Kokoro's prefix is `<language><gender>_`, and that letter is not
decoration: it selects the grapheme-to-phoneme front end the pipeline is built
with.

**Four changes in two days is why these tests are about the derivation rather
than about the name.** A default that moves that often is not a contract; the
letter agreeing with the voice, on every future move, is — including the three
here that stayed American and would have hidden a hand-written mismatch.

**The interesting part is what would have shipped silently.** `lang_code` was a
separately written constant, `"a"`, which agreed with `am_michael` by hand for
two weeks. Changing only the voice would have left a British voice being
phonemised by an American front end — not a crash, not a failed test, just a
voice that sounds subtly wrong, which a listener attributes to the voice rather
than to a configuration letter. And `HuggingFaceVoiceDiscoverer` filters the
voice list by that same letter, so the new default would also have been absent
from the list it is chosen from, and every request for it would have logged
*"voice unavailable, falling back"* — to itself.

So the letter is derived from the voice in both directions: the default lang
comes from the default voice, and a *request* naming a voice from another
language rebuilds the pipeline for that language rather than borrowing the one
already loaded.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from voice.config import DEFAULT_LANG_CODE, DEFAULT_VOICE, KokoroConfig
from voice.providers.kokoro import KokoroProvider

from voice.tests.test_kokoro_provider import FakeDiscoverer, FakePipeline


class _RecordingFactory:
    """Builds a pipeline and remembers which language it was asked for."""

    def __init__(self, sample_rate: int) -> None:
        self.langs: list[str] = []
        self._sample_rate = sample_rate

    def __call__(self, *, repo_id: str, lang_code: str, device, **_):
        self.langs.append(lang_code)
        return FakePipeline(sample_rate=self._sample_rate)


def _provider(tmp_path: Path, *, voices: list[str]) -> tuple[KokoroProvider, _RecordingFactory]:
    config = KokoroConfig.load(
        cache_directory=str(tmp_path / "audio_cache"),
        load_model_eagerly=False,
        voice_discovery_enabled=True,
    )
    factory = _RecordingFactory(config.sample_rate)
    provider = KokoroProvider(
        config=config,
        pipeline_factory=factory,
        voice_discoverer=FakeDiscoverer(voices),
    )
    # The import guard, not the model: these tests never touch real weights.
    provider._kokoro = object()
    return provider, factory


class TestTheDefaultIsOneDecision:
    def test_the_default_voice_is_michael(self):
        assert DEFAULT_VOICE == "am_michael"

    def test_the_language_is_read_off_the_voice_rather_than_written_twice(self):
        """The regression this file exists for.

        Two constants that must agree, written separately, is how they come to
        disagree — the same shape as the six spellings of `af_heart` that the
        19 August note in `voice/config.py` records collapsing into one.
        """
        assert DEFAULT_LANG_CODE == DEFAULT_VOICE[0]

    def test_a_config_takes_the_pair_together(self):
        assert KokoroConfig().default_voice == "am_michael"
        assert KokoroConfig().lang_code == "a"


class TestTheVoiceChoosesTheFrontEnd:
    def test_a_british_voice_asks_for_the_british_front_end(self, tmp_path):
        provider, _ = _provider(tmp_path, voices=["bm_fable"])
        assert provider._lang_for_voice("bm_fable") == "b"

    def test_an_american_voice_asks_for_the_american_one(self, tmp_path):
        provider, _ = _provider(tmp_path, voices=["af_heart"])
        assert provider._lang_for_voice("af_heart") == "a"

    def test_a_name_that_says_nothing_falls_back_rather_than_guessing(self, tmp_path):
        provider, _ = _provider(tmp_path, voices=["bm_fable"])
        assert provider._lang_for_voice("") == provider.config.lang_code
        assert provider._lang_for_voice("qq_nobody") == provider.config.lang_code

    def test_a_pipeline_built_for_one_language_is_not_reused_for_another(
        self, tmp_path
    ):
        """Reuse is exactly what makes a British voice come out American."""
        provider, factory = _provider(tmp_path, voices=["bm_fable", "af_heart"])

        provider._ensure_pipeline(provider._lang_for_voice("bm_fable"))
        provider._ensure_pipeline(provider._lang_for_voice("af_heart"))
        provider._ensure_pipeline(provider._lang_for_voice("af_bella"))

        assert factory.langs == ["b", "a"], (
            "the second language must build its own front end, and a third "
            "voice in a language already loaded must reuse it"
        )


class TestTheListStillOffersBothEnglishes:
    async def test_american_voices_survive_a_british_default(self, tmp_path):
        """Filtering the list by the configured letter would hide half of it.

        American and British voices ship in one pack and differ only in the
        front end, which now follows the voice — so both are offered. The other
        languages are not, because their `misaki` dependencies are not
        installed and offering a voice that fails is worse than not offering
        it.
        """
        provider, _ = _provider(tmp_path, voices=["af_heart", "bm_fable"])
        assert provider._discoverable_langs() == ["a", "b"]

        await provider.initialize()
        listed = await provider.available_voices()

        assert "af_heart" in listed and "bm_fable" in listed


@pytest.mark.measure
class TestAgainstRealKokoro:
    """The half a fake cannot assert: that this voice makes a sound.

    Every test above would pass against a voice id that does not exist in the
    pack — which is the failure mode a hand-typed voice name has. Skips when
    the weights are not cached, because fetching them is an egress decision and
    a test does not get to make one.
    """

    def test_the_default_voice_synthesises(self, tmp_path):
        pytest.importorskip("kokoro")
        import numpy as np

        from voice.providers.kokoro import KokoroProvider as Provider

        config = KokoroConfig.load(
            cache_directory=str(tmp_path / "audio_cache"),
            load_model_eagerly=False,
            voice_discovery_enabled=False,
        )
        provider = Provider(config=config)
        import kokoro  # noqa: F401  — present, per the skip above

        provider._kokoro = kokoro

        try:
            pipeline = provider._ensure_pipeline(
                provider._lang_for_voice(config.default_voice)
            )
        except Exception as exc:  # weights not cached, or gate said no
            pytest.skip(f"Kokoro weights unavailable here: {exc}")

        audio, _timings = provider._run_synthesis(
            pipeline, "The deposit clause matters.", config.default_voice
        )

        assert audio is not None
        assert np.asarray(audio).size > config.sample_rate // 4, (
            "a quarter second of audio is less than that sentence takes to say"
        )
