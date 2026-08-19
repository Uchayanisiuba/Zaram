"""Kokoro on onnxruntime — the same weights and the same voices, without torch.

Why this exists
---------------
Kokoro-82M is small; the runtime it is written against is not. Measured on disk
in ``backend/venv`` on 19 August 2026: the ``kokoro`` package is ~1 MB and the
weights 315 MB, while **torch is 494 MB** and transformers a further 96. The
905 MB speech extra is therefore mostly a tensor library, and onnxruntime —
which ``faster-whisper`` already pulls in for the microphone extra, so it is
*already in the tree* — does the same job in 43 MB.

This module is a second backend behind the seam
:func:`voice.providers.kokoro._default_pipeline_factory` already provided. It
duck-types ``KPipeline``: it is called ``pipeline(text, voice=...)`` and yields
results carrying ``.audio`` and ``.tokens``. ``KokoroProvider._run_synthesis``
is unchanged and cannot tell the difference, which is the whole point of
``VoiceProvider`` — CLAUDE.md keeps TTS behind an interface *"so the choice is
replaceable rather than embedded"*.

The thing that nearly stopped it
--------------------------------
**The community ONNX export emits ``waveform`` and nothing else.** Measured, not
assumed::

    INPUTS:   input_ids [1, seq]  style [1, 256]  speed [1]
    OUTPUTS:  waveform  [1, num_samples]

``docs/SPEECH.md`` names the constraint that decides any TTS swap, and it is not
size: *"an engine that cannot produce word timings costs the viseme chain"*.
``pred_dur`` is what fills ``SpeechTiming``, the avatar's mouth is scrubbed
against it, and a swap that dropped it would have traded a mouth that moves for
an installer that is smaller — after a whole session was spent finding out why
that mouth was shut.

It does not have to be dropped. ``pred_dur`` is still **computed** inside the
graph; the export simply never wired it to an output. Walking back from the
encoder's ``CumSum`` recovers ``KModel.forward`` line for line::

    duration_proj → Sigmoid → ReduceSum → Div(speed) → Round → Clip → Cast → Gather

so ``/encoder/Gather_output_0`` *is* ``pred_dur`` for batch 0. Adding an existing
internal tensor to ``graph.output`` is local surgery on a file already on disk:
no re-export from torch, no second set of weights, and nothing for anyone to
host. The patched copy is cached, so the cost is paid once.

**If the tensor is not there, this backend refuses to load.** It does not fall
back to silence-with-audio. An engine returning empty timings is a legitimate
state at the interface, but arriving there *by accident* is how lip sync breaks
invisibly — the viseme code, its unit tests and ``check:visemes`` were all green
throughout the session where the mouth never opened. A loud failure sends the
provider down its existing "speech unavailable, chat unaffected" path with a
reason attached; a quiet one costs another session. The export revision is
pinned for the same reason: the graph we operate on is the graph that was tested.

What is kept
------------
* **misaki for G2P**, and therefore spaCy. It is what knows that *read* is not
  *read* and *lead* is not *lead*, and it is torch-free (checked: no module under
  ``misaki/`` imports torch). Dropping it saves 125 MB and makes heteronyms wrong
  out loud, which is a bad trade on the half of the stack the user hears.
* **The timing arithmetic verbatim.** ``join_timestamps`` below is a port of
  ``KPipeline.join_timestamps``, half-frames, magic divisor and ``-3`` offset
  included. It is not re-derived, because re-deriving it would produce timings
  that are *nearly* right, and nearly right is exactly what nobody would notice
  until the mouth drifted.
* **Everything above the pipeline.** The egress gate, the audio cache, health,
  voice resolution and streaming all live in ``KokoroProvider`` and are untouched.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, List, Optional, Sequence, Tuple

import numpy as np

from core.egress import EgressDenied, get_gate
from voice.exceptions import ProviderUnavailableError

logger = logging.getLogger("voice.provider.kokoro.onnx")

#: The export this module was written against and tested on. Pinned rather than
#: floating: the graph surgery below names an internal tensor, and an internal
#: tensor is not an API. A newer revision may rename it, and finding that out on
#: a user's machine is not the plan — see ``_DURATION_TENSOR``.
ONNX_REPO_ID = "onnx-community/Kokoro-82M-v1.0-ONNX"
ONNX_REVISION = "1939ad2a8e416c0acfeecc08a694d14ef25f2231"

#: The vocabulary lives in the *torch* repo's ``config.json`` and not in the ONNX
#: repo's, whose config carries only ``model_type``. It is a few kilobytes, so
#: the cost of reaching two repos is a rounding error against the model itself.
VOCAB_REPO_ID = "hexgrad/Kokoro-82M"

#: ``pred_dur`` for batch 0, by its name inside the exported graph. Verified to
#: exist in ``ONNX_REVISION``; asserted at load time, never assumed.
_DURATION_TENSOR = "/encoder/Gather_output_0"

#: Kokoro's positional style packs are ``[510, 1, 256]`` — one style row per
#: possible phoneme count — so 510 is also the hard limit on a chunk.
MAX_PHONEMES = 510

#: ``pred_dur`` frames run at 24000/600 = 40 Hz. Timestamps are counted in
#: *half* frames so a space can be split down the middle, hence 80.
_MAGIC_DIVISOR = 80


class DurationOutputMissing(RuntimeError):
    """The export does not expose ``pred_dur``, so lip sync cannot be driven.

    Raised at load time rather than tolerated at synthesis time. See the module
    docstring: empty timings are a valid state to *declare* and a terrible one to
    *discover*.
    """


# --------------------------------------------------------------------------- #
# Result type — duck-types KPipeline.Result for `_run_synthesis`
# --------------------------------------------------------------------------- #
@dataclass
class OnnxResult:
    """What one synthesised chunk produced.

    ``KokoroProvider._run_synthesis`` reads ``.audio`` and ``.tokens`` and gets
    ``start_ts``/``end_ts``/``text``/``phonemes`` off each token. Those are the
    only attributes it touches, so those are the only ones promised here.
    """

    graphemes: str
    phonemes: str
    audio: Optional[np.ndarray]
    tokens: List[Any] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Ported from KPipeline — see module docstring on why these are copied
# --------------------------------------------------------------------------- #
def tokens_to_ps(tokens: Sequence[Any]) -> str:
    return "".join(t.phonemes + (" " if t.whitespace else "") for t in tokens).strip()


def tokens_to_text(tokens: Sequence[Any]) -> str:
    return "".join(t.text + t.whitespace for t in tokens).strip()


def waterfall_last(
    tokens: Sequence[Any],
    next_count: int,
    waterfall: Sequence[str] = ("!.?…", ":;", ",—"),
    bumps: Sequence[str] = (")", "”"),
) -> int:
    """Find the latest sentence-ish boundary that keeps a chunk under the limit."""
    for w in waterfall:
        z = next((i for i, t in reversed(list(enumerate(tokens))) if t.phonemes in set(w)), None)
        if z is None:
            continue
        z += 1
        if z < len(tokens) and tokens[z].phonemes in bumps:
            z += 1
        if next_count - len(tokens_to_ps(tokens[:z])) <= MAX_PHONEMES:
            return z
    return len(tokens)


def en_tokenize(tokens: Sequence[Any]) -> Iterator[Tuple[str, str, List[Any]]]:
    """Split a token stream into chunks the model can accept in one pass."""
    tks: List[Any] = []
    pcount = 0
    for t in tokens:
        t.phonemes = "" if t.phonemes is None else t.phonemes
        next_ps = t.phonemes + (" " if t.whitespace else "")
        next_pcount = pcount + len(next_ps.rstrip())
        if next_pcount > MAX_PHONEMES:
            z = waterfall_last(tks, next_pcount)
            yield tokens_to_text(tks[:z]), tokens_to_ps(tks[:z]), tks[:z]
            tks = tks[z:]
            pcount = len(tokens_to_ps(tks))
            if not tks:
                next_ps = next_ps.lstrip()
        tks.append(t)
        pcount += len(next_ps)
    if tks:
        yield tokens_to_text(tks), tokens_to_ps(tks), tks


def join_timestamps(tokens: Sequence[Any], pred_dur: np.ndarray) -> None:
    """Write ``start_ts``/``end_ts`` onto tokens, in place.

    A verbatim port of ``KPipeline.join_timestamps``. ``pred_dur`` arrives here as
    a numpy array rather than a ``torch.LongTensor``; every operation used —
    ``len``, indexing, ``.item()``, ``[i:j].sum().item()`` — means the same thing
    on both, which is why the body reads identically to the original. Keep it
    that way: the point of this function is to *not* be a second opinion about
    when a word is heard.
    """
    if len(tokens) == 0 or len(pred_dur) < 3:
        # At least <bos>, one token, <eos>.
        return
    left = right = 2 * max(0, int(pred_dur[0].item()) - 3)
    i = 1
    for t in tokens:
        if i >= len(pred_dur) - 1:
            break
        if not t.phonemes:
            if t.whitespace:
                i += 1
                left = right + int(pred_dur[i].item())
                right = left + int(pred_dur[i].item())
                i += 1
            continue
        j = i + len(t.phonemes)
        if j >= len(pred_dur):
            break
        t.start_ts = left / _MAGIC_DIVISOR
        token_dur = int(pred_dur[i:j].sum().item())
        space_dur = int(pred_dur[j].item()) if t.whitespace else 0
        left = right + (2 * token_dur) + space_dur
        t.end_ts = left / _MAGIC_DIVISOR
        right = left + space_dur
        i = j + (1 if t.whitespace else 0)


# --------------------------------------------------------------------------- #
# Model assets
# --------------------------------------------------------------------------- #
def _guard_full_scale(waveform: np.ndarray) -> np.ndarray:
    """Scale back anything that would clip when written as 16-bit PCM.

    This backend runs about **3 dB hotter than torch** — best-fit gain 1.4385
    with a standard deviation of 0.0155 across five sentences, so it is a stable
    property of the export rather than noise. Peaks measured 0.52–0.65 where
    torch measured 0.35–0.44, which still has headroom; a louder utterance need
    not.

    ``_to_wav_bytes`` hands the array to ``soundfile``, which converts to 16-bit
    PCM and **clips** silently past full scale. Clipping is the one difference
    between the backends that would be unambiguously audible as a fault rather
    than as a level, so it is the one worth spending code on.

    What this deliberately does *not* do is divide by 1.4385 to match torch. The
    number is measured on one voice and it has no derivation — CLAUDE.md's rule
    is that a number built for one purpose must not quietly decide another, and
    an unexplained constant on the audio path is exactly that. Correcting the
    level is a decision for whoever listens to both; refusing to clip is not.
    """
    peak = float(np.abs(waveform).max()) if waveform.size else 0.0
    if peak <= 0.99:
        return waveform
    logger.info("Kokoro ONNX output peaked at %.3f; scaling to avoid clipping", peak)
    return (waveform * (0.99 / peak)).astype(np.float32)


def _patched_model_dir() -> Path:
    """Where the graph-patched copy of the model is kept.

    **Not the Zaram data directory, and that is a correction rather than a
    preference.** ``in_data_dir`` resolves to the *backend source directory* in
    a checkout — deliberately, so a developer's Spine is not relocated by a
    ``git pull`` — and a 326 MB derived blob dropped there is picked up by
    ``test_installer_payload.py``, which fails the build because the installer's
    allow-list does not carry ``.onnx``. It was right to fail: this is a
    regenerable cache keyed to a pinned upstream revision, not the user's data,
    and it must not be in the payload or in anybody's working tree.

    So it lives beside the weights it is derived from, under the Hugging Face
    cache, which already has the right lifecycle and already honours ``HF_HOME``.
    ``ZARAM_VOICE_ONNX_DIR`` overrides it for anyone who wants it elsewhere.
    """
    override = (os.getenv("ZARAM_VOICE_ONNX_DIR") or "").strip()
    if override:
        path = Path(override).expanduser()
    else:
        from huggingface_hub.constants import HF_HUB_CACHE

        path = Path(HF_HUB_CACHE) / "zaram-kokoro-onnx"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _fetch(repo_id: str, filename: str, revision: Optional[str], what: str, size: str) -> str:
    """Resolve one file from the hub, asking the egress gate before any download.

    The ordering is the point, and it is the same one ``KokoroProvider._ensure_pipeline``
    and ``voice/stt/whisper.py`` both use: **cached files are the ordinary case
    and must touch nothing**, so ``HF_HUB_OFFLINE`` is set first and the gate is
    consulted only when the offline attempt fails and there is genuinely
    something to fetch. Asking unconditionally would fill the egress log with
    decisions about requests that were never going to be made.

    Every path into this module funnels through here — the graph, the voices and
    the vocabulary alike. **The voices are the reason this function exists.**
    They are loaded lazily at synthesis time, from ``__call__``, which is outside
    the window ``_ensure_pipeline`` wraps, so routing them through the provider's
    gate check was not an option and leaving them ungated would have been an
    unlogged download triggered by typing a sentence. The torch pipeline has that
    hole today: ``KPipeline.load_voice`` calls ``hf_hub_download`` when a voice is
    first used, with nothing asked and nothing logged.
    """
    from huggingface_hub import hf_hub_download

    previous = os.environ.get("HF_HUB_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        return hf_hub_download(repo_id=repo_id, filename=filename, revision=revision)
    except Exception:
        logger.info("%s is not cached; asking the gate before fetching", what)
    finally:
        if previous is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = previous

    try:
        get_gate().check(f"https://huggingface.co/{repo_id}", source="text-to-speech")
    except EgressDenied as denied:
        raise ProviderUnavailableError(
            f"Speech needs {what}, which is not on this machine yet. Downloading it "
            f"from huggingface.co ({size}, one time) was blocked: {denied}"
        ) from denied

    return hf_hub_download(repo_id=repo_id, filename=filename, revision=revision)


def expose_duration_output(source: str | Path, destination: str | Path) -> Path:
    """Copy an exported Kokoro graph, adding ``pred_dur`` to its outputs.

    The tensor already exists; only the declaration is missing. ``onnx`` is
    imported here rather than at module scope because this runs once per install
    and the import costs more than the surgery does.

    Raises :class:`DurationOutputMissing` when the graph does not contain the
    tensor — deliberately, and see the module docstring for why that is louder
    than degrading to no timings.
    """
    import onnx
    from onnx import TensorProto, helper

    model = onnx.load(str(source))
    produced = {out for node in model.graph.node for out in node.output}
    if _DURATION_TENSOR not in produced:
        raise DurationOutputMissing(
            f"{_DURATION_TENSOR!r} is not produced by this graph, so per-phoneme "
            f"durations cannot be recovered and lip sync would be silently dead. "
            f"This export is not the pinned revision {ONNX_REVISION}."
        )
    if any(out.name == _DURATION_TENSOR for out in model.graph.output):
        onnx.save(model, str(destination))
        return Path(destination)

    model.graph.output.append(
        helper.make_tensor_value_info(_DURATION_TENSOR, TensorProto.INT64, ["sequence_length"])
    )
    onnx.save(model, str(destination))
    return Path(destination)


def _resolve_model(variant: str) -> Path:
    """Download the export if needed, patch it once, and return the patched path.

    Downloading happens through ``huggingface_hub``, which honours
    ``HF_HUB_OFFLINE`` — and that is exactly how ``KokoroProvider._ensure_pipeline``
    asks the egress gate before anything is fetched. This backend therefore
    inherits the gate rather than re-implementing it, and must keep resolving its
    weights *here*, at construction, where that wrapper can see the failure.
    """
    patched = _patched_model_dir() / f"{variant}.duration.onnx"
    if patched.exists():
        return patched
    source = _fetch(
        ONNX_REPO_ID, f"onnx/{variant}.onnx", ONNX_REVISION,
        "the Kokoro speech model", "about 326 MB",
    )
    logger.info("Exposing pred_dur in the Kokoro ONNX graph (once): %s", patched)
    return expose_duration_output(source, patched)


def _load_vocab() -> dict:
    import json

    path = _fetch(VOCAB_REPO_ID, "config.json", None, "the Kokoro phoneme vocabulary", "a few kB")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["vocab"]


def _load_voice(name: str) -> np.ndarray:
    """Load one voice as ``[510, 1, 256]`` float32.

    The ONNX repo ships voices as raw ``.bin`` rather than the torch repo's
    ``.pt``, which is what lets this backend read them with ``numpy.frombuffer``
    and no tensor library at all. Same numbers, same 511 KB per voice.
    """
    path = _fetch(
        ONNX_REPO_ID, f"voices/{name}.bin", ONNX_REVISION,
        f"the {name} voice", "about 0.5 MB",
    )
    data = np.frombuffer(Path(path).read_bytes(), dtype=np.float32)
    return data.reshape(-1, 1, 256)


# --------------------------------------------------------------------------- #
# The pipeline
# --------------------------------------------------------------------------- #
class OnnxKokoroPipeline:
    """A ``KPipeline``-shaped object backed by onnxruntime.

    Constructed by :func:`voice.providers.kokoro._default_pipeline_factory` when
    ``KokoroConfig.backend`` is ``"onnx"``. Only English (``lang_code`` ``a`` or
    ``b``) is served: misaki's other language packs are separate installs, and
    answering for a language this has not been run against would be a confident
    wrong answer of exactly the kind ``vram_bytes`` returns ``None`` to avoid.
    """

    def __init__(
        self,
        *,
        lang_code: str = "a",
        variant: str = "model_fp16",
        device: Optional[str] = None,
        providers: Optional[Sequence[str]] = None,
    ) -> None:
        lang_code = (lang_code or "a").lower()
        if lang_code not in ("a", "b"):
            raise ValueError(
                f"The ONNX backend serves English only (lang_code 'a' or 'b'); "
                f"got {lang_code!r}. Use the torch backend for other languages."
            )
        self.lang_code = lang_code
        self.variant = variant
        self._vocab = _load_vocab()
        self._voices: dict[str, np.ndarray] = {}
        self._g2p = self._build_g2p(lang_code)

        import onnxruntime as ort

        model_path = _resolve_model(variant)
        chosen = list(providers) if providers else self._providers_for(device, ort)
        self._session = ort.InferenceSession(str(model_path), providers=chosen)

        names = {out.name for out in self._session.get_outputs()}
        if _DURATION_TENSOR not in names:
            raise DurationOutputMissing(
                f"The patched model at {model_path} does not expose {_DURATION_TENSOR!r}. "
                f"Delete it and let it be rebuilt."
            )
        logger.info(
            "Kokoro ONNX pipeline ready", extra={"variant": variant, "providers": chosen}
        )

    @staticmethod
    def _providers_for(device: Optional[str], ort: Any) -> List[str]:
        """Prefer CUDA when it was asked for *and* onnxruntime can actually do it.

        Asking for a provider onnxruntime was not built with does not fail; it
        warns and silently uses CPU. A capability this reports must be one it has,
        so the available list is consulted rather than trusted to a config string.
        """
        available = set(ort.get_available_providers())
        if device and device.lower().startswith("cuda") and "CUDAExecutionProvider" in available:
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    @staticmethod
    def _build_g2p(lang_code: str) -> Any:
        from misaki import en, espeak

        try:
            fallback = espeak.EspeakFallback(british=lang_code == "b")
        except Exception as exc:  # pragma: no cover - depends on espeak presence
            logger.warning("EspeakFallback unavailable (%s); rare words will be skipped", exc)
            fallback = None
        return en.G2P(trf=False, british=lang_code == "b", fallback=fallback, unk="")

    def load_voice(self, voice: str) -> np.ndarray:
        if voice not in self._voices:
            self._voices[voice] = _load_voice(voice)
        return self._voices[voice]

    def _encode(self, phonemes: str) -> List[int]:
        """Phonemes to input ids, wrapped in the boundary tokens the model expects.

        Unknown phonemes are dropped rather than mapped to a placeholder, which is
        what ``KModel`` does — ``filter(None, map(vocab.get, phonemes))``.
        """
        ids = [self._vocab[p] for p in phonemes if p in self._vocab]
        return [0, *ids, 0]

    def __call__(
        self,
        text: str | Sequence[str],
        voice: str = "",
        speed: float = 1.0,
        split_pattern: Optional[str] = r"\n+",
    ) -> Iterator[OnnxResult]:
        if not voice:
            raise ValueError("Specify a voice, e.g. pipeline(text, voice='am_michael')")
        pack = self.load_voice(voice)

        segments = (
            re.split(split_pattern, text.strip()) if isinstance(text, str) and split_pattern
            else ([text] if isinstance(text, str) else list(text))
        )

        for segment in segments:
            if not segment.strip():
                continue
            _, tokens = self._g2p(segment)
            for graphemes, phonemes, chunk in en_tokenize(tokens):
                if not phonemes:
                    continue
                if len(phonemes) > MAX_PHONEMES:
                    logger.warning("Truncating a %d-phoneme chunk to %d", len(phonemes), MAX_PHONEMES)
                    phonemes = phonemes[:MAX_PHONEMES]
                audio, pred_dur = self._infer(phonemes, pack, speed)
                join_timestamps(chunk, pred_dur)
                yield OnnxResult(
                    graphemes=graphemes, phonemes=phonemes, audio=audio, tokens=chunk
                )

    def _infer(
        self, phonemes: str, pack: np.ndarray, speed: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        input_ids = np.array([self._encode(phonemes)], dtype=np.int64)
        # The style row is chosen by phoneme count, exactly as `KPipeline.infer`
        # does with `pack[len(ps)-1]`. Kokoro's packs are positional: a different
        # row is a different prosody, not a different voice.
        style = pack[len(phonemes) - 1].astype(np.float32)
        outputs = self._session.run(
            ["waveform", _DURATION_TENSOR],
            {
                "input_ids": input_ids,
                "style": style,
                "speed": np.array([speed], dtype=np.float32),
            },
        )
        waveform = np.asarray(outputs[0]).squeeze().astype(np.float32)
        pred_dur = np.asarray(outputs[1]).squeeze()
        return _guard_full_scale(waveform), pred_dur
