"""Configuration for the Kokoro voice provider.

All Kokoro runtime settings live here so nothing is hard-coded across the
provider. Values are resolved from environment variables (``ZARAM_VOICE_*``)
with sensible, project-relative defaults. Paths are resolved relative to the
backend package root, never as absolute literals.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_REPO_ID = "hexgrad/Kokoro-82M"

#: The voice Zaram speaks in when the user has not chosen one.
#:
#: **This is the only place it is decided — 19 August 2026.** The literal
#: `"af_heart"` was written into six places: this constant, two fallbacks in
#: `voice_synthesize` and `voice_stream`, the `zaram_prime` preset, a
#: `voice_map` in the speech runtime, and a `ChatRequest` field that no code
#: ever read. Six spellings of one decision is how they come to disagree, and
#: it is the same shape as the two TTS text cleaners and the two rankers this
#: repository has already paid for. Every one of those now reads this name.
#:
#: `am_michael`, restored on 4 September 2026 after listening to it beside
#: `am_onyx` in the running product.
#:
#: **Four defaults in two days, and the sequence is the useful record**:
#: `af_heart` → `am_michael` → `bm_fable` (too deep) → `am_onyx` (chosen from
#: seven samples) → `am_michael` again. Onyx won a comparison of clips and lost
#: the comparison that counts, which is hearing it answer real questions for a
#: while.
#:
#: **The measurements never predicted a single one of these choices, and that
#: is the finding.** Over the same line, `bm_fable` and `am_michael` have the
#: *same* median F0 — 120.6 Hz each — and differ only in timbre, 949 Hz against
#: 1585 Hz of spectral centroid. Ordered by brightness: `am_onyx` 608,
#: `bm_fable` 949, `am_eric` 1183, `am_puck` 1442, `bm_george` 1527,
#: `am_michael` 1585, `am_fenrir` 1632. So the voice rejected as *too deep* and
#: the voice chosen to replace it sit at opposite ends of that ordering, and
#: the one finally kept is the second brightest of the seven. No number in this
#: list would have got there.
#:
#: `CLAUDE.md`'s fifth integration test — *the maintainer can test the output
#: and judge whether it is good* — is the whole mechanism here. The numbers are
#: kept because they are cheap and occasionally narrow a shortlist; they are
#: never the decision, and a session that tries to pick a voice by centroid is
#: repeating a mistake this comment already paid for twice.
#:
#: A *default* is all this is. `user_settings.voice` overrides it, and
#: `ZARAM_VOICE_DEFAULT_VOICE` overrides that.
DEFAULT_VOICE = "am_michael"

#: Which grapheme-to-phoneme front end runs, derived from the voice.
#:
#: **Kokoro's first letter is a language and the second is a gender**: `af_` is
#: American female, `bm_` British male. The pipeline is built with a language
#: code, and a mismatched one is not a crash — it is an American front end
#: pronouncing a British voice, which sounds like a fault in the *voice*.
#:
#: So this is derived rather than written down. `am_michael` and `a` agreed by
#: hand for two weeks; `bm_fable` and `a` would not have, and nothing in the
#: code would have said so. The default has changed twice more since, and that
#: is precisely what makes the derivation worth having: it is the reason no
#: future change of voice can reintroduce the mismatch by hand. Discovery
#: filtered the voice list by this letter
#: too, so a hand-written mismatch also hid the default voice from the list it
#: is chosen from.
#:
#: Per *request*, the voice still wins over this — see
#: `KokoroProvider._lang_for_voice`. This is the fallback for a voice whose
#: prefix says nothing.
DEFAULT_LANG_CODE = DEFAULT_VOICE[0]

#: Which runtime executes Kokoro: ``"torch"`` or ``"onnx"``.
#:
#: Same weights, same voices, same Apache-2.0 licence — a different tensor
#: library underneath. ``onnx`` drops torch (494 MB) and transformers (96 MB)
#: from the speech extra and reuses the onnxruntime that ``faster-whisper``
#: already pulls in, at the cost of one graph patch documented in
#: ``voice/providers/kokoro_onnx.py``.
#:
#: **It defaults to torch, and that is a deliberate stop rather than a doubt
#: about the code.** Measured on 19 August 2026 against the torch reference,
#: five sentences, ``am_michael``: word timings are *bit-identical* (0.000000 s
#: drift, same words, same order), audio length identical to the sample, and the
#: magnitude spectra correlate at 0.984. One difference is real and stable: the
#: ONNX graph comes out **~3 dB louder** (best-fit gain 1.4385, sd 0.0155),
#: which is the signature of an iSTFT normalisation convention in the export
#: rather than of lost precision.
#:
#: Nobody has *heard* the two side by side. CLAUDE.md's fifth integration test
#: is "the maintainer can test the output and judge whether it is good", and a
#: 3 dB step on the product's own voice is exactly that kind of judgement. Flip
#: this to ``"onnx"`` — or set ``ZARAM_VOICE_BACKEND=onnx`` — after listening.
DEFAULT_BACKEND = "torch"

#: Which exported graph the ONNX backend runs.
#:
#: ``model`` is fp32 at 326 MB and is the default **because fp16 was measured
#: and is not equivalent.** Against the torch reference, fp32 correlates at
#: 0.972 and holds it — 0.960 over the final second. ``model_fp16`` starts at
#: 0.963 and falls to **0.601** by the end of the same sentence, with per-window
#: gain swinging 1.43 to 0.86. That is error accumulating through the decoder,
#: and the sinusoidal source generator's ``CumSum`` is the obvious place for it:
#: a running total in half precision over a hundred thousand samples loses the
#: low bits, and in an excitation generator lost low bits are phase.
#:
#: So fp16 buys 163 MB by degrading the *end* of every utterance more than the
#: start — the worst possible shape, because it is invisible in a short test and
#: audible in a long reply. The integer variants are smaller again and are not
#: the default for the older reason: Kokoro's back half is a vocoder, and int8
#: there does not degrade the way it does in a language model — it buzzes.
#:
#: Any of them may be chosen deliberately, after listening. None of them should
#: be chosen to save a download.
DEFAULT_ONNX_VARIANT = "model"

DEFAULT_SAMPLE_RATE = 24000
DEFAULT_CACHE_SUBDIR = "audio_cache"
ENV_PREFIX = "ZARAM_VOICE_"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _backend_root() -> Path:
    """Resolve the backend/ directory (parent of the voice package)."""
    return Path(__file__).resolve().parent.parent


def _resolve_cache_dir(value: str) -> str:
    """Resolve a cache directory, relative paths anchored to backend root."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = _backend_root() / path
    return str(path)


@dataclass
class KokoroConfig:
    default_provider: str = "kokoro"
    default_voice: str = DEFAULT_VOICE
    sample_rate: int = DEFAULT_SAMPLE_RATE
    cache_directory: str = DEFAULT_CACHE_SUBDIR
    lang_code: str = DEFAULT_LANG_CODE
    repo_id: str = DEFAULT_REPO_ID
    device: Optional[str] = None
    backend: str = DEFAULT_BACKEND
    onnx_variant: str = DEFAULT_ONNX_VARIANT
    load_model_eagerly: bool = False
    run_synthesis_probe: bool = False
    #: Off by default. Discovery lists the voice files in a HuggingFace repo,
    #: which contacts huggingface.co — and it ran on every launch, before any
    #: egress policy existed and without appearing in any log. Rule 5's default
    #: deny applies to Zaram's own startup traffic exactly as it does to a
    #: search provider's. Voice is out of scope for v1 in any case; anyone who
    #: wants discovery back can set ZARAM_VOICE_DISCOVERY=1 and will then be
    #: making that choice deliberately.
    voice_discovery_enabled: bool = False

    def resolved_cache_directory(self) -> str:
        return _resolve_cache_dir(self.cache_directory)

    @classmethod
    def load(cls, **overrides: object) -> "KokoroConfig":
        """Build a config from environment variables plus explicit overrides."""
        config = cls(
            default_provider=os.getenv(f"{ENV_PREFIX}DEFAULT_PROVIDER", cls.default_provider),
            default_voice=os.getenv(f"{ENV_PREFIX}DEFAULT_VOICE", cls.default_voice),
            sample_rate=int(os.getenv(f"{ENV_PREFIX}SAMPLE_RATE", cls.sample_rate)),
            cache_directory=os.getenv(f"{ENV_PREFIX}CACHE_DIR", cls.cache_directory),
            lang_code=os.getenv(f"{ENV_PREFIX}LANG_CODE", cls.lang_code),
            repo_id=os.getenv(f"{ENV_PREFIX}REPO_ID", cls.repo_id),
            device=os.getenv(f"{ENV_PREFIX}DEVICE") or None,
            backend=os.getenv(f"{ENV_PREFIX}BACKEND", cls.backend).strip().lower(),
            onnx_variant=os.getenv(f"{ENV_PREFIX}ONNX_VARIANT", cls.onnx_variant),
            load_model_eagerly=_env_bool(f"{ENV_PREFIX}EAGER_LOAD", cls.load_model_eagerly),
            run_synthesis_probe=_env_bool(f"{ENV_PREFIX}SYNTHESIS_PROBE", cls.run_synthesis_probe),
            voice_discovery_enabled=_env_bool(f"{ENV_PREFIX}DISCOVERY", cls.voice_discovery_enabled),
        )
        for key, value in overrides.items():
            setattr(config, key, value)
        config.cache_directory = config.resolved_cache_directory()
        return config
