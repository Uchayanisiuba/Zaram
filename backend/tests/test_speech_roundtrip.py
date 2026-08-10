"""Zaram speaks, and Zaram hears what it said.

The acceptance test for both halves of the speech path, minus the human. Every
piece of this was green for a whole session while nobody had heard a sound,
which is the failure `cfaa191` already cost once: written-and-inert is worse
than broken, because the suite agrees with you.

**What this closes that the unit tests cannot.** Everything above `MediaRecorder`
is driven by fakes, so three things were claims rather than observations:

1. that PyAV decodes what a browser actually produces. The recording arrives as
   Opus in a WebM container and is handed straight to a decoder that believes
   the content type, so the two libraries have to agree. The fixtures here really
   are Opus in WebM — not perfect, since Chromium's muxer is not the one that
   wrote them, but it exercises the format rather than asserting a keyword
   argument.
2. that `vad_filter=True` earns its place. Whisper hallucinates on silence —
   "Thank you.", subtitle credits — and push-to-talk audio is mostly leading and
   trailing silence, so a hallucination lands as invented words in the user's own
   input box. `test_silence_is_heard_as_silence` is that guard, and it is the
   one test here that would have failed on a plausible wrong default.
3. that the two engines agree about the audio at all. Kokoro emits 24 kHz mono;
   Opus wants 48 kHz. A resample bug produces a chipmunk or a drone, and a
   transcript is the only thing that notices.

**Two classes of test, split because one of them cannot be made deterministic.**

`TestZaramHears` runs on **committed fixtures**. It needs the mic extra and the
Whisper weights, and nothing else — no torch, no spaCy, no 905 MB. That matters
beyond convenience: the listening half is now verifiable on the machine a
listening user actually has.

`TestZaramHearsItself` synthesises live and is the only thing proving the two
engines meet. It asserts loosely, and the reason is measured rather than
assumed: **Kokoro's output is not byte-identical across calls.** Two synthesis
runs of one sentence produced different waveforms, and the difference was enough
to change how Whisper parsed a spoken number. Whisper itself is deterministic —
the same clip transcribed three times gave one answer — so the variance is
entirely upstream. Asserting an exact transcript here would be a flaky test
blamed on the recogniser.

**Nothing here reaches the network.** `HF_HUB_OFFLINE` is set for the module, so
a missing weight is a skip with an actionable reason rather than a silent
141 MB download inside a test run. Rule 7g is not suspended because it would be
convenient: a suite that fetches model weights is a suite that cannot run on a
metered connection, and the first person to notice would be a stranger.
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import os
from pathlib import Path

import pytest

# Set before anything imports huggingface_hub, which reads it at import time.
os.environ["HF_HUB_OFFLINE"] = "1"

SPOKEN = "My day rate for Harbour Lane is four hundred and twenty five thousand naira."

FIXTURES = Path(__file__).parent / "fixtures"
#: Kokoro saying SPOKEN, re-encoded to Opus in WebM. Committed rather than
#: generated, so the listening tests are deterministic and need neither torch
#: nor the 905 MB voice extra.
SPOKEN_CLIP = FIXTURES / "spoken-day-rate.webm"
#: Three seconds of nothing, in the same container. Not an empty buffer — that
#: is the trivial case the provider short-circuits. This is what a user produces
#: when they press the button, say nothing, and press it again.
SILENCE_CLIP = FIXTURES / "silence.webm"

#: Content that must survive Opus compression and transcription.
#:
#: **This list was wrong on the first run and the correction is the useful part
#: of this file.** It asked for "harbour", "four hundred" and "twenty five", and
#: got back *"My day rate for Harbor Lane is 425,000 Nira."* — which is a correct
#: transcription. Whisper normalises two things, and neither is a defect:
#:
#: * **spelling follows the voice's locale.** ``af_heart`` is American English,
#:   so "Harbour" is heard and written "Harbor". Asserting the British spelling
#:   tested Kokoro's accent, not the path.
#: * **spoken numbers become digits.** "four hundred and twenty five thousand"
#:   arrives as "425,000". For an invoicing product that is the good outcome —
#:   a dictated day rate lands as a figure — but see
#:   ``test_a_dictated_figure_is_not_guaranteed`` for why it cannot be relied on.
#:
#: So the check is on a normalised transcript, and on *content*: a proper noun
#: the model had to actually hear, and the phrase the sentence is about.
MUST_HEAR = ["day rate", "lane"]

HF_CACHE = Path.home() / ".cache" / "huggingface" / "hub"


def _installed(*modules: str) -> str:
    """The first missing module name, or "" when they are all present."""
    for module in modules:
        if importlib.util.find_spec(module) is None:
            return module
    return ""


def _cached(repo_dir: str) -> bool:
    return (HF_CACHE / repo_dir).is_dir()


def _normalise(text: str) -> str:
    """Lowercase and strip digit grouping, so the assertion is about what was
    heard rather than about how Whisper writes it down."""
    return text.lower().replace(",", "")


_MISSING_MIC = _installed("faster_whisper", "av")
_MISSING_VOICE = _installed("kokoro", "spacy", "soundfile")

#: Everything in this module needs to be able to listen.
pytestmark = [
    pytest.mark.skipif(
        bool(_MISSING_MIC),
        reason=(
            f"mic extra not installed ({_MISSING_MIC} missing) — "
            "pip install -r backend/requirements-mic.txt"
        ),
    ),
    pytest.mark.skipif(
        not _cached("models--Systran--faster-whisper-base"),
        reason="Whisper weights are not cached; this test will not download them",
    ),
]

#: Only the round trip additionally needs to be able to speak.
needs_voice = pytest.mark.skipif(
    bool(_MISSING_VOICE) or not _cached("models--hexgrad--Kokoro-82M"),
    reason=(
        f"voice extra or Kokoro weights absent ({_MISSING_VOICE or 'weights'}) — "
        "pip install -r backend/requirements-voice.txt"
    ),
)


@pytest.fixture(scope="module")
def recogniser():
    """The real recogniser, on real cached weights, offline."""
    from voice.stt.whisper import WhisperRecogniser

    instance = WhisperRecogniser()
    asyncio.run(instance.initialize())
    if not instance.is_available():
        pytest.skip(f"recogniser unavailable: {asyncio.run(instance.health_check())}")
    return instance


def _transcribe(recogniser, path: Path):
    return asyncio.run(recogniser.transcribe(path.read_bytes()))


# --------------------------------------------------------------------------- #
# Listening, on fixed audio
# --------------------------------------------------------------------------- #
class TestZaramHears:
    def test_a_browser_recording_is_decoded_and_transcribed(self, recogniser):
        """Opus in WebM, straight from bytes, with nothing written to disk."""
        transcript = _transcribe(recogniser, SPOKEN_CLIP)
        heard = _normalise(transcript.text)

        missing = [phrase for phrase in MUST_HEAR if phrase not in heard]
        assert not missing, (
            f"Zaram did not hear {missing}.\n"
            f"  said:  {SPOKEN}\n"
            f"  heard: {transcript.text}"
        )

    def test_the_timings_arrive_with_the_words(self, recogniser):
        """Segments are the half of the contract that mirrors `SpeechTiming`.

        An engine that cannot produce them is supported, so an empty list is not
        an error — but this engine can, and silently losing them would make the
        contract's symmetry a comment rather than a fact.
        """
        transcript = _transcribe(recogniser, SPOKEN_CLIP)

        assert transcript.segments, "no segments came back from an utterance with words"
        assert transcript.segments[0].end_s > transcript.segments[0].start_s
        assert transcript.duration_s > 0

    def test_the_language_is_reported_rather_than_assumed(self, recogniser):
        transcript = _transcribe(recogniser, SPOKEN_CLIP)
        assert transcript.language == "en"

    def test_transcription_is_deterministic_within_one_process(self, recogniser):
        """Measured, and scoped to exactly what was measured.

        The round trip below is not stable, and the first instinct was to blame
        the recogniser. Half wrong: **within one loaded model this is exact**,
        three runs for three identical strings, which is what located the
        variance upstream in Kokoro.

        **Across processes it is not.** The same committed fixture, through the
        same model, gave "425,000" in the suite and "$400,000 and $25,000" over
        HTTP from a fresh server. `cpu_threads=0` lets CTranslate2 size its own
        thread pool from machine load, and floating-point reduction order
        follows thread count — so run-to-run variation is expected rather than
        surprising.

        This test is named for the weaker claim on purpose. A test called
        `test_transcription_is_deterministic` would be asserting something false
        while passing, which is the most expensive kind of green.
        """
        answers = {_transcribe(recogniser, SPOKEN_CLIP).text for _ in range(3)}
        assert len(answers) == 1, f"same audio, different transcripts: {answers}"

    def test_silence_is_heard_as_silence(self, recogniser):
        """The guard that earns `vad_filter` its default.

        Without voice-activity filtering Whisper reliably invents text over
        silence, and this path feeds its output into the user's own input box.
        A push-to-talk button that fills the composer with "Thank you." because
        somebody changed their mind is the invention rule 9 forbids, one surface
        earlier than a document.
        """
        transcript = _transcribe(recogniser, SILENCE_CLIP)

        assert transcript.text.strip() == "", (
            "Whisper invented words over silence: "
            f"{transcript.text!r}. vad_filter is meant to prevent exactly this."
        )


# --------------------------------------------------------------------------- #
# Both halves, live
# --------------------------------------------------------------------------- #
def _to_webm_opus(wav: bytes) -> bytes:
    """Re-encode WAV to Opus-in-WebM, which is what `MediaRecorder` emits.

    Opus is fixed at 48 kHz, and Kokoro produces 24 kHz, so the resample is not
    incidental — getting it wrong is exactly the class of defect that survives
    every unit test and produces a transcript of nonsense.

    Also how the committed fixtures were made. Kept here rather than in a script
    so regenerating them is a one-liner against code that is itself under test.
    """
    import av

    source = av.open(io.BytesIO(wav))
    buffer = io.BytesIO()
    target = av.open(buffer, mode="w", format="webm")
    stream = target.add_stream("libopus", rate=48000)
    stream.layout = "mono"
    resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)

    for frame in source.decode(audio=0):
        for resampled in resampler.resample(frame):
            resampled.pts = None
            for packet in stream.encode(resampled):
                target.mux(packet)
    for resampled in resampler.resample(None):
        resampled.pts = None
        for packet in stream.encode(resampled):
            target.mux(packet)
    for packet in stream.encode(None):
        target.mux(packet)

    target.close()
    source.close()
    return buffer.getvalue()


@needs_voice
class TestZaramHearsItself:
    def test_the_two_engines_meet(self, recogniser):
        """Kokoro speaks it, Whisper hears it, live.

        Asserts loosely on purpose. Kokoro's waveform is not byte-identical
        between calls, so an exact assertion here is a flaky test wearing the
        recogniser's name.
        """
        from voice.providers.kokoro import KokoroProvider

        async def synthesise() -> bytes:
            provider = KokoroProvider()
            await provider.initialize()
            result = await provider.generate_audio(SPOKEN, voice="af_heart")
            assert result.success, f"Kokoro could not speak: {result.error}"
            assert result.path, "Kokoro produced no file"
            return Path(result.path).read_bytes()

        clip = _to_webm_opus(asyncio.run(synthesise()))
        heard = _normalise(asyncio.run(recogniser.transcribe(clip)).text)

        missing = [phrase for phrase in MUST_HEAR if phrase not in heard]
        assert not missing, f"Zaram did not hear {missing} in its own speech: {heard!r}"

    def test_the_returned_audio_url_names_a_file_that_exists(self):
        """The defect that made the avatar silent, as a test.

        Synthesis succeeded, the response looked right, and `audio_url` pointed
        at a file that never existed — the URL was built from `audio_id` (the
        *request* id, `tts-f68ca98d`) while `AudioCache` names files
        `{voice}_{hash}.wav`. Two naming schemes that could never agree, so
        **every utterance 404'd on playback** while every test passed.

        Nothing covered this seam: the provider tests assert a file is written,
        the runtime tests assert a URL is returned, and no test asked whether
        they were the same file. That gap is the whole reason `cfaa191`'s
        "the avatar speaks its replies" shipped silent.
        """
        import asyncio as _asyncio
        from pathlib import Path as _Path

        from runtimes.speech.connectors.kokoro import KokoroConnector
        from runtimes.speech.contracts import SynthesisRequest

        async def synthesise():
            connector = KokoroConnector()
            await connector.initialize()
            return await connector.synthesize(
                SynthesisRequest(text="Testing one two three.", voice_id="af_heart")
            )

        result = _asyncio.run(synthesise())

        assert result.success, f"synthesis failed: {result.error}"
        assert result.audio_filename, (
            "the connector returned no filename, so the runtime has nothing to "
            "build a URL from and will fall back to an empty audio_url"
        )
        # A bare filename, never a path — `/audio/{filename}` rejects separators.
        assert "/" not in result.audio_filename
        assert "\\" not in result.audio_filename

        from voice.config import KokoroConfig

        cache_dir = _Path(KokoroConfig.load().resolved_cache_directory())
        assert (cache_dir / result.audio_filename).is_file(), (
            f"{result.audio_filename} is not in {cache_dir}. The URL the API "
            "returns would 404, which is exactly how the avatar stayed silent."
        )

    def test_a_dictated_figure_is_not_guaranteed(self, recogniser):
        """A finding, recorded as a test so it cannot be quietly forgotten.

        One sentence, one voice, one model, three observed transcripts:

            My day rate for Harbor Lane is 425,000 Nira.
            My day rate for Harbor Lane is 400 and 25,000 Nira.
            My day rate for Harbor Lane is $400,000 and $25,000.

        Two separate defects, and the second is much worse than the first.

        **The figure is unstable.** "four hundred and twenty five thousand"
        parses as 425,000 or as two numbers, depending on the run.

        **The currency is invented.** The audio says *naira*. The third
        transcript says **$**, twice, and says it with no hedging — a Nigerian
        day rate rendered as dollars is wrong by a factor of about fifteen
        hundred, and it is wrong in the direction that looks reasonable on an
        invoice. Nothing downstream can detect it, because "$400,000" is a
        perfectly well-formed amount.

        **So a dictated figure must never reach an invoice unreviewed.** That is
        a constraint on the business layer rather than a bug to fix here, and it
        is precisely the case rule 9 exists for: the number leaves the building.
        Speech is for prose. Amounts get typed, or get confirmed.

        This asserts only that *some* digits arrive, which is the weakest true
        statement available. If a larger model makes the strong version true,
        this test is the place that says so.
        """
        from voice.providers.kokoro import KokoroProvider

        async def synthesise() -> bytes:
            provider = KokoroProvider()
            await provider.initialize()
            result = await provider.generate_audio(SPOKEN, voice="af_heart")
            return Path(result.path).read_bytes()

        clip = _to_webm_opus(asyncio.run(synthesise()))
        heard = asyncio.run(recogniser.transcribe(clip)).text

        assert any(character.isdigit() for character in heard), (
            f"no figure survived at all, which is worse than an imprecise one: {heard!r}"
        )
