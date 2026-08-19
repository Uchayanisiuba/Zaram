"""The ONNX backend must produce the same speech, and the same timings, as torch.

Why this file is a comparison and not a unit test
-------------------------------------------------
Every individual piece of a TTS swap can be correct while the result is wrong,
and this repository has paid for that shape repeatedly: the viseme mapping, its
unit tests and ``check:visemes`` were all green while the avatar's mouth stayed
shut for a whole session. A test asserting that ``OnnxKokoroPipeline`` returns
*a* float array and *some* timings would pass on a backend that hums.

So the assertion is differential. The torch pipeline is the reference — it is
what shipped, what was driven in a browser, and what the lip sync was verified
against — and the ONNX backend has to agree with it about two things:

* **the audio**, closely enough that the same sentence lasts the same time; and
* **the timings**, which are what ``SpeechTiming`` carries and what the avatar
  scrubs against ``audio.currentTime``.

``docs/SPEECH.md``: *"the constraint that decides any TTS swap is not size but
word timings"*. This file is where that is decided.

On skipping
-----------
These tests need model weights, and weights are a download. They skip when the
weights are absent — but a silent skip is how the speech acceptance suite read
as passing for a session while testing nothing, so each skip names exactly which
asset is missing, and ``test_backends_are_both_reachable`` runs unconditionally
so this module can never report zero.
"""

from __future__ import annotations

import numpy as np
import pytest

from voice.config import DEFAULT_VOICE, KokoroConfig
from voice.providers.kokoro import _default_pipeline_factory

SENTENCE = "The harbour lane was quiet, and the invoice was already overdue."
SAMPLE_RATE = 24000


# --------------------------------------------------------------------------- #
# Availability, named rather than guessed
# --------------------------------------------------------------------------- #
def _missing(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is None


def _onnx_pipeline():
    from voice.providers.kokoro_onnx import OnnxKokoroPipeline

    return OnnxKokoroPipeline(lang_code="a", variant=KokoroConfig().onnx_variant)


def _torch_pipeline():
    return _default_pipeline_factory(
        repo_id="hexgrad/Kokoro-82M", lang_code="a", device="cpu", backend="torch"
    )


needs_onnx = pytest.mark.skipif(
    _missing("onnxruntime") or _missing("onnx") or _missing("misaki"),
    reason="ONNX backend needs onnxruntime, onnx and misaki",
)
needs_torch = pytest.mark.skipif(
    _missing("torch") or _missing("kokoro"),
    reason="the torch reference needs torch and the kokoro package",
)


def _synthesise(pipeline, text: str = SENTENCE):
    """Run one pipeline and flatten it the way ``_run_synthesis`` does."""
    audio_chunks = []
    timings = []
    offset = 0.0
    for result in pipeline(text, voice=DEFAULT_VOICE):
        audio = getattr(result, "audio", None)
        if audio is None:
            continue
        audio = np.asarray(audio, dtype=np.float32)
        audio_chunks.append(audio)
        for token in getattr(result, "tokens", None) or []:
            start = getattr(token, "start_ts", None)
            end = getattr(token, "end_ts", None)
            if start is None or end is None:
                continue
            timings.append(
                ((getattr(token, "text", "") or "").strip(), float(start) + offset, float(end) + offset)
            )
        offset += len(audio) / SAMPLE_RATE
    return (np.concatenate(audio_chunks) if audio_chunks else np.zeros(0, np.float32)), timings


# --------------------------------------------------------------------------- #
# Reachability — runs everywhere, so this module never reports zero
# --------------------------------------------------------------------------- #
def test_backends_are_both_reachable():
    """The config switch must actually select a backend, in both directions.

    A settings control that stores, round-trips and displays while nothing
    downstream reads it is a defect this repository found twice in one session.
    ``backend`` is exactly that shape of control, so the wiring is asserted here
    rather than assumed from the fact that the field exists.
    """
    import inspect

    source = inspect.getsource(_default_pipeline_factory)
    assert 'backend == "onnx"' in source
    assert "OnnxKokoroPipeline" in source
    assert "KPipeline" in source

    config = KokoroConfig.load()
    assert config.backend in {"torch", "onnx"}


def test_default_variant_is_full_precision():
    """Neither integer-quantised nor fp16 may become the default by being small.

    fp16 was measured on 19 August 2026 and is *not* equivalent: correlation
    against torch starts at 0.963 and decays to 0.601 by the end of a five-second
    sentence, because error accumulates through the decoder. That shape — fine at
    the start, wrong at the end — is invisible in a short test and audible in a
    long reply, which is the worst way for a defect to be distributed.

    CLAUDE.md's rule is that a number built for one purpose must not silently
    decide another. Here the number is a download size, and letting it pick the
    weights trades audible quality for megabytes with nobody listening.
    """
    variant = KokoroConfig().onnx_variant
    assert variant == "model", (
        f"the default ONNX variant is {variant!r}; fp32 is the only one measured "
        f"to hold its accuracy across a whole utterance"
    )


def test_default_backend_is_the_one_a_human_has_heard():
    """torch stays the default until somebody listens to the ONNX output.

    Every objective measure agrees the two are equivalent — bit-identical
    timings, identical length, spectra correlated at 0.984 — and one measure
    says they differ: ONNX is ~3 dB louder. CLAUDE.md's fifth integration test
    is that the maintainer can judge whether output is good, and no measurement
    in this file is that judgement.

    This test exists so flipping the default is a deliberate edit that trips a
    named assertion, rather than a constant changing in a diff nobody reads.
    """
    assert KokoroConfig().backend == "torch"


# --------------------------------------------------------------------------- #
# The graph patch — the thing that makes lip sync survive the swap
# --------------------------------------------------------------------------- #
@needs_onnx
def test_patched_graph_exposes_durations():
    """``pred_dur`` must be an output, or the viseme chain has nothing to read."""
    from voice.providers.kokoro_onnx import _DURATION_TENSOR, _resolve_model

    import onnxruntime as ort

    try:
        path = _resolve_model(KokoroConfig().onnx_variant)
    except Exception as exc:  # pragma: no cover - depends on the weight cache
        pytest.skip(f"Kokoro ONNX weights are not on this machine: {exc}")

    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    outputs = {out.name for out in session.get_outputs()}
    assert "waveform" in outputs
    assert _DURATION_TENSOR in outputs, (
        "The export ships waveform only. Without the duration tensor this backend "
        "would speak with a shut mouth and no test would notice."
    )


@needs_onnx
def test_missing_duration_tensor_refuses_loudly():
    """A graph without durations must raise, never degrade to empty timings.

    Empty timings are a legal state at the ``SpeechTiming`` interface. *Arriving*
    at them by accident is the failure mode that costs a session, so the patcher
    refuses rather than producing a model that works and says nothing.
    """
    from voice.providers.kokoro_onnx import DurationOutputMissing, expose_duration_output

    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper

    node = helper.make_node("Identity", ["x"], ["y"])
    graph = helper.make_graph(
        [node],
        "no-durations",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])],
    )
    model = helper.make_model(graph)

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "plain.onnx"
        onnx.save(model, str(source))
        with pytest.raises(DurationOutputMissing):
            expose_duration_output(source, Path(tmp) / "patched.onnx")


# --------------------------------------------------------------------------- #
# The differential test — ONNX against the torch reference
# --------------------------------------------------------------------------- #
@needs_onnx
def test_onnx_speaks_and_reports_timings():
    """Sound, and a timing per word, from the ONNX path alone."""
    try:
        audio, timings = _synthesise(_onnx_pipeline())
    except Exception as exc:  # pragma: no cover - depends on the weight cache
        pytest.skip(f"Kokoro ONNX assets are not on this machine: {exc}")

    assert audio.size > SAMPLE_RATE, "less than a second of audio for a full sentence"
    assert float(np.abs(audio).max()) > 0.01, "the waveform is silence"
    assert len(timings) >= 8, f"expected a timing per word, got {len(timings)}"

    for text, start, end in timings:
        assert end > start, f"{text!r} ends before it begins"
    starts = [t[1] for t in timings]
    assert starts == sorted(starts), "timings are out of order"
    assert timings[-1][2] <= audio.size / SAMPLE_RATE + 0.5, "a word is spoken after the audio ends"


def test_onnx_requirements_exclude_the_torch_plugin():
    """The ONNX extra must not pull anything that imports torch.

    ``spacy-curated-transformers`` is the specific trap: it is a spaCy plugin,
    spaCy loads plugins from whatever is installed rather than from what asked
    for them, and it imports torch at module scope. Adding it — or letting it
    arrive as somebody's transitive dependency — silently restores the 494 MB
    this whole backend exists to remove, and nothing would fail.

    It is the same shape as the dependency lesson already in CLAUDE.md: misaki
    reaches spaCy without declaring it, so metadata could not see the edge.
    Here the edge runs the other way and metadata still cannot see it, because
    the dependency is expressed as an entry point rather than as a requirement.
    """
    from pathlib import Path

    requirements = Path(__file__).resolve().parents[2] / "requirements-voice-onnx.txt"
    assert requirements.exists(), "the ONNX voice extra has no requirements file"

    pinned = [
        line.split("==")[0].strip().lower().replace("_", "-")
        for line in requirements.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    for banned in ("torch", "transformers", "kokoro", "spacy-curated-transformers"):
        assert banned not in pinned, f"{banned} is pinned into the ONNX voice extra"
    for required in ("onnxruntime", "onnx", "misaki", "spacy"):
        assert required in pinned, f"the ONNX voice extra does not pin {required}"


@needs_onnx
def test_onnx_backend_speaks_with_torch_unimportable():
    """The point of the whole exercise, proved rather than asserted.

    torch is 494 MB of the 905 MB speech extra. Claiming the ONNX path does not
    need it is easy; the claim is only worth anything if it is checked in a
    process where importing torch **fails**, because torch is installed in this
    virtualenv and every other test in this file would happily use it without
    saying so.

    So this runs in a subprocess with a meta-path hook that refuses ``torch``,
    ``kokoro`` and ``transformers``, and synthesises real audio through it. If
    any of them is reached — directly, or by misaki, or by huggingface_hub — the
    import raises and this test fails with the name of whatever reached for it.

    This is the same discipline as ``docs/RUNNING.md``'s point about two
    virtualenvs: a capability that depends on the environment must be measured
    in the environment, not inferred from a dependency graph. ``pip show`` said
    spaCy had no dependents while misaki was reaching it at runtime.

    **What it found on first run, which is why the skip below is narrow.** It
    failed — and correctly. spaCy loads plugin entry points from every installed
    package, ``spacy_curated_transformers`` is one such plugin, and it imports
    torch at module scope. So on *this* development machine the ONNX path does
    reach torch, through a package that is in nobody's requirements file and
    that a clean install does not have. Blocking it too is not a fix: spaCy
    raises rather than skipping a plugin it cannot import.

    The contaminant is therefore named, skipped on, and pinned from the other
    side by :func:`test_onnx_requirements_exclude_the_torch_plugin`, so the
    thing this test cannot check here is checked where it can be.
    """
    import subprocess
    import sys
    import textwrap
    from pathlib import Path

    if not _missing("spacy_curated_transformers"):
        pytest.skip(
            "spacy_curated_transformers is installed in this virtualenv. It is a "
            "spaCy plugin that imports torch at module scope, spaCy loads it "
            "automatically, and spaCy raises rather than skipping a plugin that "
            "will not import — so torch is reachable here no matter what this "
            "backend does. It is in no requirements file; see "
            "test_onnx_requirements_exclude_the_torch_plugin."
        )

    program = textwrap.dedent(
        '''
        import sys

        BANNED = {"torch", "kokoro", "transformers"}

        class Refuse:
            def find_module(self, name, path=None):
                return self.find_spec(name, path)

            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in BANNED:
                    raise ImportError(f"BANNED: something imported {name!r}")
                return None

        sys.meta_path.insert(0, Refuse())
        for name in list(sys.modules):
            if name.split(".")[0] in BANNED:
                del sys.modules[name]

        from voice.providers.kokoro_onnx import OnnxKokoroPipeline

        pipeline = OnnxKokoroPipeline(lang_code="a", variant="model")
        samples = 0
        timed = 0
        for result in pipeline("The deposit clause matters.", voice="am_michael"):
            samples += 0 if result.audio is None else len(result.audio)
            timed += sum(1 for t in result.tokens if t.start_ts is not None)

        assert samples > 12000, samples
        assert timed >= 3, timed
        for banned in BANNED:
            assert banned not in sys.modules, f"{banned} got imported after all"
        print(f"OK samples={samples} timed={timed}")
        '''
    )

    backend_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=str(backend_root),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if "Kokoro ONNX" in completed.stderr and "not on this machine" in completed.stderr:
        pytest.skip("Kokoro ONNX weights are not on this machine")
    assert completed.returncode == 0, (
        f"the ONNX backend could not speak without torch.\n"
        f"stdout: {completed.stdout}\nstderr: {completed.stderr[-2000:]}"
    )
    assert "OK samples=" in completed.stdout


@needs_onnx
@needs_torch
def test_onnx_matches_torch_on_audio_length_and_timings():
    """The differential assertion: same sentence, same voice, same result.

    **The timing tolerance is zero, because the measured drift is zero.** Five
    sentences of 1.2 to 5.9 seconds, 19 August 2026: identical word lists,
    identical sample counts, and ``start_ts``/``end_ts`` agreeing to the last
    bit. That is not luck — ``pred_dur`` is integer frames out of a ``Round``,
    and both backends round the same predictor's output, so anything other than
    equality means something structural has changed. A loose tolerance here
    would let exactly that through, which is how a lip sync defect hides.

    The audio itself is compared on length rather than samples. The two are not
    sample-identical — ONNX runs about 3 dB hotter and their magnitude spectra
    correlate at 0.984, not 1.0 — and asserting on waveform equality would be
    asserting on the export's arithmetic rather than on anything a user hears.
    """
    try:
        onnx_audio, onnx_timings = _synthesise(_onnx_pipeline())
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Kokoro ONNX assets are not on this machine: {exc}")
    try:
        torch_audio, torch_timings = _synthesise(_torch_pipeline())
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Kokoro torch assets are not on this machine: {exc}")

    assert onnx_audio.size == torch_audio.size, (
        f"the same sentence is {onnx_audio.size} samples on ONNX and "
        f"{torch_audio.size} on torch — the backends disagree about the speech itself"
    )

    assert [t[0] for t in onnx_timings] == [t[0] for t in torch_timings], (
        "the two backends timed different words"
    )
    assert onnx_timings == torch_timings, (
        "word timings differ between backends. pred_dur is integer frames out of "
        "the same Round, so any difference at all means the graphs have diverged "
        "— and the avatar scrubs its mouth against exactly these numbers."
    )


@needs_onnx
@needs_torch
def test_onnx_is_louder_than_torch_and_that_is_known():
    """Pin the one measured difference so it cannot drift unnoticed.

    ONNX comes out ~3 dB hot: best-fit gain 1.4385, sd 0.0155 over five
    sentences, flat across the spectrum. It reads as an iSTFT normalisation
    convention in the export rather than lost precision, and it is deliberately
    *not* corrected in code — see ``_guard_full_scale``.

    Asserting it has a purpose beyond documentation. If a future export changes
    the convention, this test fails and somebody reads the number, instead of
    the product quietly getting quieter.
    """
    onnx_audio, _ = _synthesise(_onnx_pipeline())
    torch_audio, _ = _synthesise(_torch_pipeline())
    n = min(onnx_audio.size, torch_audio.size)
    a = onnx_audio[:n].astype(np.float64)
    b = torch_audio[:n].astype(np.float64)
    gain = float((a @ b) / (b @ b))
    assert 1.3 < gain < 1.6, f"level relationship to torch has changed: gain {gain:.4f}"


@needs_onnx
def test_full_scale_guard_only_touches_what_would_clip():
    """Loud output is scaled back; ordinary output is passed through untouched.

    ``soundfile`` clips past full scale without saying so, and clipping is the
    one difference between the backends that a listener would hear as a fault
    rather than as a level.
    """
    from voice.providers.kokoro_onnx import _guard_full_scale

    ordinary = np.array([0.0, 0.5, -0.62], dtype=np.float32)
    assert _guard_full_scale(ordinary) is ordinary

    hot = np.array([0.0, 1.8, -2.4], dtype=np.float32)
    guarded = _guard_full_scale(hot)
    # float32 cannot hold 0.99 exactly, so the bound is the thing that matters —
    # inside full scale — not the literal the code divides by.
    assert float(np.abs(guarded).max()) < 1.0
    # Shape is preserved: this attenuates, it does not reshape the waveform.
    np.testing.assert_allclose(guarded / np.abs(guarded).max(), hot / np.abs(hot).max(), rtol=1e-6)
