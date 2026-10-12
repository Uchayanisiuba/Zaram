"""Configuration for the Zaram Voice Runtime — all TTS tiers.

All runtime settings live here so nothing is hard-coded across the
providers. Values are resolved from environment variables with sensible,
project-relative defaults. Paths are resolved relative to the backend
package root, never as absolute literals.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# =============================================================================
# Shared defaults
# =============================================================================

DEFAULT_SAMPLE_RATE = 24000
DEFAULT_CACHE_SUBDIR = "audio_cache"
ENV_PREFIX = "ZARAM_VOICE_"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    return raw.strip() if raw is not None else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw.strip()) if raw is not None else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw.strip()) if raw is not None else default


def _backend_root() -> Path:
    """Resolve the backend/ directory (parent of the voice package)."""
    return Path(__file__).resolve().parent.parent


def _resolve_cache_dir(value: str) -> str:
    """Resolve a cache directory, relative paths anchored to backend root."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = _backend_root() / path
    return str(path)


# =============================================================================
# Tier 4: Kokoro 82M (Universal Fallback)
# =============================================================================

DEFAULT_KOKORO_REPO_ID = "hexgrad/Kokoro-82M"

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
DEFAULT_KOKORO_VOICE = "am_michael"

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
DEFAULT_KOKORO_LANG_CODE = DEFAULT_KOKORO_VOICE[0]

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
DEFAULT_KOKORO_BACKEND = "torch"

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
DEFAULT_KOKORO_ONNX_VARIANT = "model"


# Backward compatibility aliases for existing tests
DEFAULT_VOICE = DEFAULT_KOKORO_VOICE
DEFAULT_LANG_CODE = DEFAULT_KOKORO_LANG_CODE
DEFAULT_REPO_ID = DEFAULT_KOKORO_REPO_ID
DEFAULT_BACKEND = DEFAULT_KOKORO_BACKEND
DEFAULT_ONNX_VARIANT = DEFAULT_KOKORO_ONNX_VARIANT


@dataclass
class KokoroConfig:
    """Configuration for Tier 4: Kokoro 82M (universal fallback)."""

    default_provider: str = "kokoro"
    default_voice: str = DEFAULT_KOKORO_VOICE
    sample_rate: int = DEFAULT_SAMPLE_RATE
    cache_directory: str = DEFAULT_CACHE_SUBDIR
    lang_code: str = DEFAULT_KOKORO_LANG_CODE
    repo_id: str = DEFAULT_KOKORO_REPO_ID
    device: Optional[str] = None
    backend: str = DEFAULT_KOKORO_BACKEND
    onnx_variant: str = DEFAULT_KOKORO_ONNX_VARIANT
    load_model_eagerly: bool = False
    run_synthesis_probe: bool = False
    voice_discovery_enabled: bool = False

    def resolved_cache_directory(self) -> str:
        return _resolve_cache_dir(self.cache_directory)

    @classmethod
    def load(cls, **overrides: object) -> "KokoroConfig":
        """Build a config from environment variables plus explicit overrides."""
        config = cls(
            default_provider=_env_str(f"{ENV_PREFIX}DEFAULT_PROVIDER", cls.default_provider),
            default_voice=_env_str(f"{ENV_PREFIX}DEFAULT_VOICE", cls.default_voice),
            sample_rate=_env_int(f"{ENV_PREFIX}SAMPLE_RATE", cls.sample_rate),
            cache_directory=_env_str(f"{ENV_PREFIX}CACHE_DIR", cls.cache_directory),
            lang_code=_env_str(f"{ENV_PREFIX}LANG_CODE", cls.lang_code),
            repo_id=_env_str(f"{ENV_PREFIX}REPO_ID", cls.repo_id),
            device=_env_str(f"{ENV_PREFIX}DEVICE", "") or None,
            backend=_env_str(f"{ENV_PREFIX}BACKEND", cls.backend).strip().lower(),
            onnx_variant=_env_str(f"{ENV_PREFIX}ONNX_VARIANT", cls.onnx_variant),
            load_model_eagerly=_env_bool(f"{ENV_PREFIX}EAGER_LOAD", cls.load_model_eagerly),
            run_synthesis_probe=_env_bool(f"{ENV_PREFIX}SYNTHESIS_PROBE", cls.run_synthesis_probe),
            voice_discovery_enabled=_env_bool(f"{ENV_PREFIX}DISCOVERY", cls.voice_discovery_enabled),
        )
        for key, value in overrides.items():
            setattr(config, key, value)
        config.cache_directory = config.resolved_cache_directory()
        return config


# =============================================================================
# Tier 1: Breeze TTS 2 (Cloud Premium)
# =============================================================================

DEFAULT_BREEZE_REPO_ID = "breeze-tts/breeze-tts-2"  # Placeholder - update when available
DEFAULT_BREEZE_VOICE = "breeze-default"
DEFAULT_BREEZE_API_ENDPOINT = "https://api.breeze-tts.com/v1"


@dataclass
class BreezeTTSConfig:
    """Configuration for Tier 1: Breeze TTS 2 (Cloud Premium)."""

    default_provider: str = "breeze_tts"
    default_voice: str = DEFAULT_BREEZE_VOICE
    sample_rate: int = DEFAULT_SAMPLE_RATE
    cache_directory: str = DEFAULT_CACHE_SUBDIR
    repo_id: str = DEFAULT_BREEZE_REPO_ID
    api_endpoint: str = DEFAULT_BREEZE_API_ENDPOINT
    api_key_env: str = "ZARAM_BREEZE_API_KEY"
    timeout_seconds: float = 30.0
    streaming_enabled: bool = True

    def resolved_cache_directory(self) -> str:
        return _resolve_cache_dir(self.cache_directory)

    @classmethod
    def load(cls, **overrides: object) -> "BreezeTTSConfig":
        config = cls(
            default_provider=_env_str(f"{ENV_PREFIX}BREEZE_DEFAULT_PROVIDER", cls.default_provider),
            default_voice=_env_str(f"{ENV_PREFIX}BREEZE_DEFAULT_VOICE", cls.default_voice),
            sample_rate=_env_int(f"{ENV_PREFIX}BREEZE_SAMPLE_RATE", cls.sample_rate),
            cache_directory=_env_str(f"{ENV_PREFIX}BREEZE_CACHE_DIR", cls.cache_directory),
            repo_id=_env_str(f"{ENV_PREFIX}BREEZE_REPO_ID", cls.repo_id),
            api_endpoint=_env_str(f"{ENV_PREFIX}BREEZE_API_ENDPOINT", cls.api_endpoint),
            api_key_env=_env_str(f"{ENV_PREFIX}BREEZE_API_KEY_ENV", cls.api_key_env),
            timeout_seconds=_env_float(f"{ENV_PREFIX}BREEZE_TIMEOUT", cls.timeout_seconds),
            streaming_enabled=_env_bool(f"{ENV_PREFIX}BREEZE_STREAMING", cls.streaming_enabled),
        )
        for key, value in overrides.items():
            setattr(config, key, value)
        config.cache_directory = config.resolved_cache_directory()
        return config

    def get_api_key(self) -> Optional[str]:
        """Get API key from environment."""
        return os.getenv(self.api_key_env)


# =============================================================================
# Tier 2: Chatterbox Turbo (VRAM-Efficient Local GPU)
# =============================================================================

DEFAULT_CHATTERBOX_REPO_ID = "ResembleAI/chatterbox-turbo"
DEFAULT_CHATTERBOX_VOICE = "chatterbox-default"
DEFAULT_CHATTERBOX_DEVICE = "cuda"
DEFAULT_CHATTERBOX_MAX_VRAM_GB = 2.0


@dataclass
class ChatterboxTurboConfig:
    """Configuration for Tier 2: Chatterbox Turbo (VRAM-efficient)."""

    default_provider: str = "chatterbox_turbo"
    default_voice: str = DEFAULT_CHATTERBOX_VOICE
    sample_rate: int = DEFAULT_SAMPLE_RATE
    cache_directory: str = DEFAULT_CACHE_SUBDIR
    repo_id: str = DEFAULT_CHATTERBOX_REPO_ID
    device: str = DEFAULT_CHATTERBOX_DEVICE
    max_vram_gb: float = DEFAULT_CHATTERBOX_MAX_VRAM_GB
    compile_model: bool = True  # torch.compile for speed
    fp16: bool = True
    zero_shot_cloning: bool = True

    def resolved_cache_directory(self) -> str:
        return _resolve_cache_dir(self.cache_directory)

    @classmethod
    def load(cls, **overrides: object) -> "ChatterboxTurboConfig":
        config = cls(
            default_provider=_env_str(f"{ENV_PREFIX}CHATTERBOX_DEFAULT_PROVIDER", cls.default_provider),
            default_voice=_env_str(f"{ENV_PREFIX}CHATTERBOX_DEFAULT_VOICE", cls.default_voice),
            sample_rate=_env_int(f"{ENV_PREFIX}CHATTERBOX_SAMPLE_RATE", cls.sample_rate),
            cache_directory=_env_str(f"{ENV_PREFIX}CHATTERBOX_CACHE_DIR", cls.cache_directory),
            repo_id=_env_str(f"{ENV_PREFIX}CHATTERBOX_REPO_ID", cls.repo_id),
            device=_env_str(f"{ENV_PREFIX}CHATTERBOX_DEVICE", cls.device).strip().lower(),
            max_vram_gb=_env_float(f"{ENV_PREFIX}CHATTERBOX_MAX_VRAM", cls.max_vram_gb),
            compile_model=_env_bool(f"{ENV_PREFIX}CHATTERBOX_COMPILE", cls.compile_model),
            fp16=_env_bool(f"{ENV_PREFIX}CHATTERBOX_FP16", cls.fp16),
            zero_shot_cloning=_env_bool(f"{ENV_PREFIX}CHATTERBOX_ZERO_SHOT", cls.zero_shot_cloning),
        )
        for key, value in overrides.items():
            setattr(config, key, value)
        config.cache_directory = config.resolved_cache_directory()
        return config


# =============================================================================
# Tier 3: Qwen3-TTS / VoxCPM2 (CPU Lightweight)
# =============================================================================

DEFAULT_QWEN3_REPO_ID = "Qwen/Qwen3-TTS-GGUF"
DEFAULT_QWEN3_VOICE = "qwen3-default"
DEFAULT_QWEN3_DEVICE = "cpu"
DEFAULT_QWEN3_N_THREADS = max(1, (os.cpu_count() or 4) - 1)


@dataclass
class Qwen3TTSConfig:
    """Configuration for Tier 3: Qwen3-TTS / VoxCPM2 (GGUF via llama.cpp-omni)."""

    default_provider: str = "qwen3_tts"
    default_voice: str = DEFAULT_QWEN3_VOICE
    sample_rate: int = DEFAULT_SAMPLE_RATE
    cache_directory: str = DEFAULT_CACHE_SUBDIR
    repo_id: str = DEFAULT_QWEN3_REPO_ID
    device: str = DEFAULT_QWEN3_DEVICE
    n_threads: int = DEFAULT_QWEN3_N_THREADS
    n_gpu_layers: int = 0
    context_size: int = 4096
    use_mlock: bool = True
    use_mmap: bool = True

    def resolved_cache_directory(self) -> str:
        return _resolve_cache_dir(self.cache_directory)

    @classmethod
    def load(cls, **overrides: object) -> "Qwen3TTSConfig":
        config = cls(
            default_provider=_env_str(f"{ENV_PREFIX}QWEN3_DEFAULT_PROVIDER", cls.default_provider),
            default_voice=_env_str(f"{ENV_PREFIX}QWEN3_DEFAULT_VOICE", cls.default_voice),
            sample_rate=_env_int(f"{ENV_PREFIX}QWEN3_SAMPLE_RATE", cls.sample_rate),
            cache_directory=_env_str(f"{ENV_PREFIX}QWEN3_CACHE_DIR", cls.cache_directory),
            repo_id=_env_str(f"{ENV_PREFIX}QWEN3_REPO_ID", cls.repo_id),
            device=_env_str(f"{ENV_PREFIX}QWEN3_DEVICE", cls.device).strip().lower(),
            n_threads=_env_int(f"{ENV_PREFIX}QWEN3_N_THREADS", cls.n_threads),
            n_gpu_layers=_env_int(f"{ENV_PREFIX}QWEN3_N_GPU_LAYERS", cls.n_gpu_layers),
            context_size=_env_int(f"{ENV_PREFIX}QWEN3_CONTEXT_SIZE", cls.context_size),
            use_mlock=_env_bool(f"{ENV_PREFIX}QWEN3_MLOCK", cls.use_mlock),
            use_mmap=_env_bool(f"{ENV_PREFIX}QWEN3_MMAP", cls.use_mmap),
        )
        for key, value in overrides.items():
            setattr(config, key, value)
        config.cache_directory = config.resolved_cache_directory()
        return config
