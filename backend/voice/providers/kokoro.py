"""Kokoro TTS provider for the Zaram Voice Runtime.

This is the first concrete :class:`~voice.providers.base.VoiceProvider`. The
rest of the application reaches Kokoro *only* through :class:`VoiceManager`, so
no caller imports this module directly.

Design notes
------------
* **Dependency injection.** The Kokoro model factory, the voice discoverer, and
  the cache are all injectable. Tests run fully offline with fakes; production
  uses the real ``KPipeline`` and HuggingFace voice discovery.
* **Never crashes the app.** Any Kokoro failure is caught, logged with
  structured context (provider / request_id / voice / duration), and returned as
  a failed :class:`AudioResult`. Chat keeps working.
* **Future-proof streaming.** ``stream_audio`` already yields
  :class:`AudioChunk` objects so real-time PCM emission (Unreal lip-sync, low
  latency SSE) can be added later without touching the ``VoiceManager`` API.

Which Kokoro is this?
---------------------
**This module is the keeper.** Four copies of Kokoro existed. Two were orphans
with no importer and were deleted on 2026-08-04:
``implementations/kokoro_tts.py`` and ``interfaces/implementation/kokoro_tts.py``.

One copy remains besides this one: ``runtimes/speech/connectors/kokoro.py``,
reached via ``runtimes/speech/connectors/__init__.py`` and ``base.py``. It is
**pending, not kept.** Collapsing it into this provider means rewiring the speech
runtime, and voice is out of scope for v1 (see CLAUDE.md), so the rewiring waits
until voice returns to scope. Do not add features to the connector in the
meantime — anything it grows has to be ported here later.

Both loose ends the deletion left are now closed:

* ``services/speech_manager.py`` did ``from implementations.kokoro_tts import
  KokoroTTS``, which stopped resolving. Nothing imported ``SpeechManager``, so
  the module was unimportable dead code and is deleted.
* ``voice/tests/test_kokoro_provider.py`` had five failures against this file,
  filed as "voice, out of scope". They were nothing of the kind: discovery
  returns an empty set because ``voice_discovery_enabled`` defaults to
  **off** — real discovery contacts huggingface.co at startup and rule 7g
  forbids that before consent — and the tests were never updated. They now
  enable it explicitly against a fake discoverer, so they reach no network.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Protocol

import numpy as np

from core.egress import EgressDenied, get_gate
from voice.config import KokoroConfig
from voice.exceptions import ProviderUnavailableError
from voice.health import AudioCache
from voice.providers.base import SpeechTiming, VoiceProvider


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #
@dataclass
class AudioResult:
    """Outcome of a synthesis request. Always returned; never raises to caller.

    The data structure is provider-agnostic and extensible for real-time systems
    (MetaHuman / ARKit / low-latency voice). ``metadata`` is a free-form bucket
    reserved for future phonemes, visemes, emotion markers, and timing info.
    """

    success: bool
    request_id: str = ""
    voice: str = ""
    audio: Any = None
    path: Optional[str] = None
    sample_rate: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None
    # --- streaming / real-time extensions (all optional) ---
    audio_id: str = ""
    format: str = "wav"
    channels: int = 1
    stream_available: bool = False
    #: When each word is heard, for lip sync. Empty when the engine cannot say.
    #:
    #: These are not free-form metadata: a renderer reads them on every frame,
    #: so they get a typed field rather than a dict key that can silently change
    #: shape. The `metadata` bucket's docstring reserved a spot for "future
    #: phonemes, visemes and timing info" — this is that, promoted out of the
    #: bucket because it now has a consumer.
    timings: List[SpeechTiming] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AudioChunk:
    """A single streamed audio frame in the provider-agnostic stream.

    A stream is an ordered sequence of chunks: chunk 0, chunk 1, ... final chunk.
    ``index`` is the 0-based sequence number. ``timestamp``/``duration`` are in
    milliseconds relative to the start of the utterance. ``audio_id`` links the
    chunk back to its originating :class:`AudioResult`.
    """

    request_id: str
    voice: str
    index: int
    audio: Any
    sample_rate: int
    final: bool
    timestamp: float = 0.0
    duration: float = 0.0
    audio_id: str = ""
    path: Optional[str] = None


# --------------------------------------------------------------------------- #
# Voice discovery
# --------------------------------------------------------------------------- #
class VoiceDiscoverer(Protocol):
    """Returns the Kokoro voice ids available for a given repo + language."""

    def discover(self, repo_id: str, lang_code: str) -> List[str]:
        ...


class HuggingFaceVoiceDiscoverer:
    """Discovers voices by listing the model repo's ``voices/*.pt`` files.

    No voice names are hard-coded; the canonical list comes from the repo.
    Network failure yields an empty list (provider degrades, never crashes).
    """

    def discover(self, repo_id: str, lang_code: str) -> List[str]:
        from huggingface_hub import list_repo_files

        voices: List[str] = []
        for filename in list_repo_files(repo_id=repo_id, repo_type="model"):
            if filename.startswith("voices/") and filename.endswith(".pt"):
                name = filename[len("voices/") : -3]
                if name.startswith(lang_code):
                    voices.append(name)
        return voices


# Language code -> human label, derived from the Kokoro voice prefix convention.
_LANG_NAMES = {
    "a": "American English",
    "b": "British English",
    "e": "Spanish",
    "f": "French",
    "h": "Hindi",
    "i": "Italian",
    "j": "Japanese",
    "z": "Mandarin Chinese",
    "p": "Portuguese",
}


def _default_pipeline_factory(
    *,
    repo_id: str,
    lang_code: str,
    device: Optional[str],
    backend: str = "torch",
    onnx_variant: str = "model_fp16",
) -> Any:
    """Build the pipeline for the configured backend.

    Both return the same shape — called as ``pipeline(text, voice=...)``, yielding
    results with ``.audio`` and ``.tokens`` — so :meth:`KokoroProvider._run_synthesis`
    never learns which one it got. That is the seam ``VoiceProvider`` was written
    for, and it is why swapping the tensor library underneath Kokoro is an
    implementation rather than a rewrite.

    Imports stay lazy on both branches. ``kokoro`` drags in torch and
    ``kokoro_onnx`` drags in onnxruntime; a top-level import of either would make
    this module unimportable on a base install, which is the exact failure that
    once stopped the provider being constructed even to report itself
    unavailable.
    """
    if backend == "onnx":
        from voice.providers.kokoro_onnx import OnnxKokoroPipeline

        return OnnxKokoroPipeline(lang_code=lang_code, variant=onnx_variant, device=device)

    from kokoro import KPipeline

    return KPipeline(lang_code=lang_code, repo_id=repo_id, model=True, device=device)


# --------------------------------------------------------------------------- #
# Provider
# --------------------------------------------------------------------------- #
class KokoroProvider(VoiceProvider):
    name = "kokoro"

    def __init__(
        self,
        config: Optional[KokoroConfig] = None,
        *,
        pipeline_factory: Optional[Callable[..., Any]] = None,
        voice_discoverer: Optional[VoiceDiscoverer] = None,
        cache: Optional[AudioCache] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config or KokoroConfig.load()
        self._pipeline_factory = pipeline_factory
        self._discoverer = voice_discoverer or HuggingFaceVoiceDiscoverer()
        self._cache = cache or AudioCache(self.config.cache_directory)
        self._pipeline: Any = None
        #: Which language front end `_pipeline` was built with, so a voice from
        #: another language rebuilds it instead of borrowing this one.
        self._pipeline_lang: str = ""
        self._kokoro: Any = None
        self._voices: Dict[str, Dict[str, Any]] = {}
        self._initialized = False
        self._available = False
        self._last_health: Dict[str, Any] = {}
        self._request_counter = 0
        self._lock = asyncio.Lock()
        self._log = logger or logging.getLogger(f"voice.provider.{self.name}")

    # --- internal helpers ---
    def _next_request_id(self) -> str:
        self._request_counter += 1
        return f"{self.name}-{int(time.time() * 1000)}-{self._request_counter}"

    def _voice_metadata(self, name: str) -> Dict[str, Any]:
        prefix = (name[:2] or "").lower()
        lang_code = prefix[0] if prefix else ""
        if prefix.endswith("f"):
            gender = "female"
        elif prefix.endswith("m"):
            gender = "male"
        else:
            gender = "unknown"
        return {
            "id": name,
            "language_code": lang_code,
            "language": _LANG_NAMES.get(lang_code, "unknown"),
            "gender": gender,
            "provider": self.name,
        }

    #: Languages that are one choice rather than two, so a voice list built for
    #: one of them must offer both. American and British English differ only in
    #: the front end, both ship in the same pack, and `_lang_for_voice` builds
    #: whichever the chosen voice needs — so listing only the configured half
    #: would hide voices that work perfectly.
    #:
    #: This is not a general "list everything": the other languages need extra
    #: `misaki` dependencies that are not installed, so offering their voices
    #: would be offering choices that fail.
    _INTERCHANGEABLE = (frozenset({"a", "b"}),)

    def _discoverable_langs(self) -> List[str]:
        """Which language codes the voice list should cover."""
        configured = self.config.lang_code
        for group in self._INTERCHANGEABLE:
            if configured in group:
                return sorted(group)
        return [configured]

    def _lang_for_voice(self, voice: str) -> str:
        """The front end a voice needs, read off the voice's own name.

        Kokoro's prefix is `<language><gender>_`: `af_heart` is American
        female, `bm_fable` British male. The pipeline's `lang_code` selects the
        grapheme-to-phoneme front end, and a mismatch is not a failure — it is
        an American front end pronouncing a British voice, which a listener
        hears as something wrong with the voice.

        Taking it from the voice rather than from the config means a user who
        picks a voice in Settings gets the front end that voice was trained
        with, without a second setting they would have to know to change. A
        name whose first letter is not a language Kokoro knows falls back to
        the configured default rather than guessing.
        """
        first = (voice or "")[:1].lower()
        return first if first in _LANG_NAMES else self.config.lang_code

    def _build_pipeline(self, lang_code: str) -> Any:
        factory = self._pipeline_factory or _default_pipeline_factory
        return factory(
            repo_id=self.config.repo_id,
            lang_code=lang_code,
            device=self.config.device,
            backend=self.config.backend,
            onnx_variant=self.config.onnx_variant,
        )

    def _ensure_pipeline(self, lang_code: Optional[str] = None) -> Any:
        """Load the model, asking the gate first if the weights are not here.

        **This used to just construct KPipeline**, which resolves through
        ``huggingface_hub`` and downloads ~315 MB from huggingface.co without
        asking anyone. Worse, ``health_check`` called it as a side effect of
        reporting health and ``initialize`` called ``health_check``, so the
        backend fetched the model on every boot, unlogged, while
        ``load_model_eagerly`` sat at ``False``. A flag deliberately turned off
        and a different path doing the thing anyway is a pattern this codebase
        has now hit five times.

        The remedy is the one ``voice/stt/whisper.py`` uses, and the ordering is
        the point: cached weights are the ordinary case and must touch nothing,
        so the gate is asked only when there is genuinely something to fetch.
        Asking unconditionally would fill the egress log with decisions about
        requests that were never going to happen.

        `lang_code` is the front end the *requested voice* needs. A cached
        pipeline built for a different language is rebuilt rather than reused,
        because reuse is what makes a British voice come out American. Two
        pipelines are not held at once: switching language is rare — it happens
        when the user changes voice in Settings — and a second resident copy of
        the model would cost memory permanently to save a load that happens
        almost never.
        """
        wanted = lang_code or self.config.lang_code
        if self._pipeline is not None and self._pipeline_lang == wanted:
            return self._pipeline
        self._pipeline = None
        self._pipeline_lang = wanted
        if self._kokoro is None:
            raise ProviderUnavailableError("Kokoro package is not available")

        # `KPipeline` has no `local_files_only`, but everything underneath it
        # honours HF_HUB_OFFLINE, so that is the lever. Restored afterwards
        # rather than left set: this process may legitimately fetch other things.
        previous = os.environ.get("HF_HUB_OFFLINE")
        os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            self._pipeline = self._build_pipeline(wanted)
            return self._pipeline
        except Exception as offline_failure:
            self._log.info(
                "Kokoro weights are not cached (%s); asking the gate before fetching",
                type(offline_failure).__name__,
                extra={"provider": self.name},
            )
        finally:
            if previous is None:
                os.environ.pop("HF_HUB_OFFLINE", None)
            else:
                os.environ["HF_HUB_OFFLINE"] = previous

        url = f"https://huggingface.co/{self.config.repo_id}"
        try:
            get_gate().check(url, source="text-to-speech")
        except EgressDenied as denied:
            # Default deny is the ordinary answer, not an error. Raised as
            # unavailable so the caller reports it the way it reports any other
            # missing engine — with a reason a user can act on.
            raise ProviderUnavailableError(
                f"Speech needs the Kokoro voice model, which is not on this machine "
                f"yet. Downloading it from huggingface.co (about 315 MB, one time) "
                f"was blocked: {denied}"
            ) from denied

        self._pipeline = self._build_pipeline(wanted)
        return self._pipeline

    def _to_wav_bytes(self, audio: Any, sample_rate: int) -> bytes:
        # Imported here, not at module scope. soundfile ships with the voice
        # extra, and a top-level import made this whole module unimportable on a
        # base install — which meant the provider could not even be constructed
        # to report itself unavailable. The lazy `import kokoro` further down was
        # written to degrade gracefully and never got the chance, because the
        # module died three lines into its own imports.
        import soundfile as sf

        buffer = io.BytesIO()
        sf.write(buffer, audio, sample_rate, format="WAV")
        return buffer.getvalue()

    def _run_synthesis(
        self, pipeline: Any, text: str, voice: str
    ) -> tuple[Optional[Any], List[SpeechTiming]]:
        """Synthesise, and keep the timings the model already computed.

        The previous body unpacked each result as a 3-tuple. ``KPipeline.Result``
        supports that for backwards compatibility, but ``tokens`` is reachable
        only as an *attribute* — so tuple-unpacking discarded it before anyone
        could want it. Nothing extra is computed here: ``pred_dur`` comes out of
        the same forward pass as the waveform and was simply being thrown away.

        Timings arrive *with* the audio, never before it. ``misaki.en.G2P``
        returns phonemes with ``start_ts``/``end_ts`` set to ``None`` — it knows
        what sounds, not when — and ``KModel`` fills them from ``pred_dur``
        afterwards. There is therefore no "timings first, audio second" sequence
        to build against, and no window in which a renderer could shape a word
        before the sound for it exists.
        """
        chunks: List[Any] = []
        timings: List[SpeechTiming] = []
        # Each chunk's timestamps restart at zero, so they are offset by the
        # audio already emitted. Without this, a second sentence would claim to
        # be spoken at the same moment as the first.
        offset_s = 0.0

        for result in pipeline(text, voice=voice):
            audio = getattr(result, "audio", None)
            if audio is None:
                continue
            chunks.append(audio)

            for token in getattr(result, "tokens", None) or []:
                start = getattr(token, "start_ts", None)
                end = getattr(token, "end_ts", None)
                # A token with no timing is not an error: G2P emits punctuation
                # and whitespace that never becomes sound. Skipping is correct;
                # emitting it with a zero span would put a viseme on silence.
                if start is None or end is None:
                    continue
                timings.append(
                    SpeechTiming(
                        text=(getattr(token, "text", "") or "").strip(),
                        phonemes=getattr(token, "phonemes", "") or "",
                        start_s=float(start) + offset_s,
                        end_s=float(end) + offset_s,
                    )
                )

            offset_s += len(audio) / float(self.config.sample_rate)

        if not chunks:
            return None, []
        if len(chunks) == 1:
            return chunks[0], timings
        return np.concatenate(chunks), timings

    def _compute_availability(self) -> bool:
        checks = self._last_health.get("checks", {})
        kokoro_ok = self._kokoro is not None
        cache_ok = checks.get("cache_writable", self._cache.is_writable())
        model_ok = checks.get("model_available", False)
        voices_ok = bool(self._voices)
        return bool(kokoro_ok and cache_ok and (model_ok or voices_ok))

    # --- VoiceProvider interface ---
    async def initialize(self) -> None:
        async with self._lock:
            if self._initialized:
                return
            self._log.info("Initializing Kokoro provider", extra={"provider": self.name})

            # 1. Kokoro import (optional dependency)
            try:
                import kokoro  # lazy import

                self._kokoro = kokoro
            except Exception as exc:
                self._kokoro = None
                self._log.warning(
                    "Kokoro package unavailable: %s (speech disabled, chat unaffected)",
                    exc,
                    extra={"provider": self.name},
                )

            # 2. Voice discovery (no hard-coded names)
            if self._kokoro is not None and self.config.voice_discovery_enabled:
                try:
                    names: List[str] = []
                    for code in self._discoverable_langs():
                        names.extend(self._discoverer.discover(self.config.repo_id, code))
                    self._voices = {n: self._voice_metadata(n) for n in names}
                except Exception as exc:
                    self._voices = {}
                    self._log.warning(
                        "Voice discovery failed: %s", exc, extra={"provider": self.name}
                    )

            # 3. Cache directory
            self._cache.ensure()

            # 4. Optional eager model load (heavy; off by default)
            if self._kokoro is not None and self.config.load_model_eagerly:
                try:
                    self._ensure_pipeline()
                except Exception as exc:
                    self._log.warning(
                        "Eager model load failed: %s", exc, extra={"provider": self.name}
                    )

            self._initialized = True
            self._last_health = await self.health_check()
            self._available = bool(self._last_health.get("available", False))
            self._log.info(
                "Kokoro provider initialized",
                extra={"provider": self.name, "voices": len(self._voices), "available": self._available},
            )

    async def generate_audio(self, text: str, voice: str = "", **kwargs: Any) -> Optional[Any]:
        request_id = kwargs.get("request_id") or self._next_request_id()
        selected = voice or self.config.default_voice
        start = time.perf_counter()
        extra = {"provider": self.name, "request_id": request_id, "voice": selected}

        if not text or not text.strip():
            self._log.warning("Empty text; skipping synthesis", extra=extra)
            return AudioResult(success=False, request_id=request_id, voice=selected, error="empty_text")

        # Unknown voice -> fall back to the configured default (never crash).
        if self._voices and selected not in self._voices:
            self._log.warning(
                "Voice %r unavailable; falling back to %r",
                selected,
                self.config.default_voice,
                extra=extra,
            )
            selected = self.config.default_voice

        try:
            # The front end the *selected* voice needs, not the configured
            # one. They agree for the default and differ the moment a user
            # picks a voice from another language in Settings.
            pipeline = self._ensure_pipeline(self._lang_for_voice(selected))
        except Exception as exc:
            self._log.error(
                "Kokoro unavailable: %s", exc, extra={**extra, "failure": type(exc).__name__}
            )
            return AudioResult(success=False, request_id=request_id, voice=selected, error=str(exc))

        try:
            audio, timings = await asyncio.to_thread(
                self._run_synthesis, pipeline, text, selected
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            self._log.error(
                "Synthesis failed: %s",
                exc,
                extra={**extra, "duration_ms": round(duration_ms, 2), "failure": type(exc).__name__},
            )
            return AudioResult(success=False, request_id=request_id, voice=selected, error=str(exc))

        if audio is None:
            duration_ms = (time.perf_counter() - start) * 1000
            self._log.error("Synthesis produced no audio", extra={**extra, "duration_ms": round(duration_ms, 2)})
            return AudioResult(success=False, request_id=request_id, voice=selected, error="no_audio")

        try:
            data = self._to_wav_bytes(audio, self.config.sample_rate)
            path = self._cache.write(
                data, voice=selected, text=text, request_id=request_id, ext="wav"
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            self._log.error("Cache write failed: %s", exc, extra={**extra, "duration_ms": round(duration_ms, 2)})
            return AudioResult(success=False, request_id=request_id, voice=selected, error=str(exc))

        duration_ms = (time.perf_counter() - start) * 1000
        self._log.info(
            "Synthesis complete",
            extra={**extra, "duration_ms": round(duration_ms, 2), "path": path},
        )
        return AudioResult(
            success=True,
            request_id=request_id,
            voice=selected,
            audio=audio,
            path=path,
            sample_rate=self.config.sample_rate,
            duration_ms=duration_ms,
            timings=timings,
            audio_id=request_id,
            format="wav",
            channels=1,
            stream_available=True,
            metadata={},
        )

    async def stream_audio(self, text: str, voice: str = "", **kwargs: Any) -> AsyncIterator[Any]:
        """Stream an utterance as an ordered sequence of :class:`AudioChunk`.

        Kokoro generates a complete utterance, so we simulate streaming by
        slicing the audio into ~100 ms frames and yielding them in order. The
        contract (ordered chunks, timestamps, ``final`` flag, ``audio_id`` link)
        is provider-independent, so a future native-streaming engine can replace
        this simulation without any caller changes.

        The event loop is never blocked: synthesis runs in a worker thread and
        control is yielded between frames so the stream can be cancelled.
        """
        request_id = kwargs.get("request_id") or self._next_request_id()
        extra = {"provider": self.name, "request_id": request_id}

        try:
            result = await self.generate_audio(text, voice=voice, request_id=request_id)
        except Exception as exc:
            self._log.error(
                "Streaming aborted: synthesis error",
                extra={**extra, "failure": type(exc).__name__},
            )
            return

        if not result.success or result.audio is None:
            self._log.error(
                "Streaming aborted: synthesis failed",
                extra={**extra, "error": result.error},
            )
            return

        audio = np.asarray(result.audio)
        sample_rate = result.sample_rate or self.config.sample_rate
        frame = max(1, sample_rate // 10)
        frame_ms = (frame / sample_rate) * 1000.0
        total = max(1, (len(audio) + frame - 1) // frame)

        self._log.info("Streaming started", extra={**extra, "chunks": total, "voice": result.voice})
        start = time.perf_counter()
        for idx in range(total):
            is_final = idx == total - 1
            chunk = audio[idx * frame : (idx + 1) * frame]
            yield AudioChunk(
                request_id=request_id,
                voice=result.voice,
                index=idx,
                audio=chunk,
                sample_rate=sample_rate,
                final=is_final,
                timestamp=round(idx * frame_ms, 2),
                duration=round(len(chunk) / sample_rate * 1000.0, 2),
                audio_id=result.audio_id,
                path=result.path if idx == 0 else None,
            )
            # Yield control between frames so the loop stays responsive and the
            # stream can be cancelled mid-utterance.
            if not is_final:
                await asyncio.sleep(0)

        self._log.info(
            "Streaming complete",
            extra={**extra, "chunks": total, "duration_ms": round((time.perf_counter() - start) * 1000, 2)},
        )

    async def available_voices(self) -> Dict[str, Any]:
        return dict(self._voices)

    async def health_check(self, *, probe_model: bool = False) -> Dict[str, Any]:
        """Report health. **Does not load the model unless asked.**

        ``probe_model`` defaults to False, and that default is the whole fix.
        This method used to call ``_ensure_pipeline()`` unconditionally, and
        ``initialize()`` calls this method — so reporting health was how the
        model got loaded, and the boot sequence fetched ~315 MB from
        huggingface.co on every launch while the eager-load flag said no.

        A health check that changes what it is measuring is not a health check.
        The model loads on the first synthesis, which is where it belongs.
        """
        checks: Dict[str, Any] = {}
        checks["kokoro_import"] = self._kokoro is not None

        model_ok = self._pipeline is not None
        if probe_model and not model_ok:
            try:
                self._ensure_pipeline()
                model_ok = True
            except Exception as exc:
                checks["model_error"] = f"{type(exc).__name__}: {exc}"
        checks["model_available"] = model_ok
        checks["model_loaded"] = self._pipeline is not None

        checks["voices_detected"] = len(self._voices)
        checks["cache_writable"] = self._cache.is_writable()

        synthesis_test: Optional[Dict[str, Any]] = None
        latency_ms: Optional[float] = None
        if self.config.run_synthesis_probe and model_ok:
            try:
                probe = await self.generate_audio(
                    "health check", voice=self.config.default_voice, request_id="health-probe"
                )
                synthesis_test = {"success": probe.success, "error": probe.error}
                latency_ms = probe.duration_ms or None
            except Exception as exc:
                synthesis_test = {"success": False, "error": str(exc)}
        checks["synthesis_test"] = synthesis_test

        # "The engine is installed and can write its output." Deliberately *not*
        # "the weights are here": establishing that would mean loading them, and
        # loading them at health-check time is the defect this method just had.
        #
        # Different from `WhisperRecogniser.is_available()`, which does require a
        # loaded model — and the asymmetry is the honest one. Listening decides
        # whether to *offer a button*, so it must know before the user presses.
        # Speaking follows a reply that has already arrived, so resolving the
        # weights on first use costs a delay rather than a dead control, and the
        # refusal carries its own reason when it comes.
        available = bool(checks["kokoro_import"] and checks["cache_writable"])

        report = {
            "provider": self.name,
            "available": available,
            "status": "healthy" if available else "unavailable",
            "voices": checks["voices_detected"],
            "cache": "ok" if checks["cache_writable"] else "not_writable",
            "default_voice": self.config.default_voice,
            "sample_rate": self.config.sample_rate,
            "latency_ms": latency_ms,
            "checks": checks,
        }
        self._last_health = report
        return report

    async def shutdown(self) -> None:
        async with self._lock:
            self._pipeline = None
            self._kokoro = None
        self._log.info("Kokoro provider shut down", extra={"provider": self.name})


# --------------------------------------------------------------------------- #
# Bootstrap helper (kept here so the Voice Runtime stays engine-agnostic)
# --------------------------------------------------------------------------- #
async def bootstrap_kokoro(
    manager: Any,
    config: Optional[KokoroConfig] = None,
    *,
    logger: Optional[logging.Logger] = None,
) -> KokoroProvider:
    """Register, initialize, and verify the Kokoro provider on a VoiceManager.

    Safe to call during app startup: any failure is logged, never raised, so
    chat remains fully operational even if speech is unavailable.
    """
    log = logger or logging.getLogger("voice.runtime")
    provider = KokoroProvider(config=config, logger=log)
    await manager.register_provider(provider.name, provider, set_active=True)
    await manager.initialize()

    voices = await provider.available_voices()
    report = await provider.health_check()

    log.info("✓ Kokoro Provider loaded")
    log.info("✓ Voices detected: %d", len(voices))
    log.info("✓ Default provider: %s", provider.name)
    log.info(
        "Provider: Kokoro | Status: %s | Voices: %d | Cache: %s",
        report["status"].title(),
        report["voices"],
        report["cache"],
    )
    return provider
