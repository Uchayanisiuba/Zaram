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
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Protocol

import numpy as np
import soundfile as sf

from voice.config import KokoroConfig
from voice.exceptions import ProviderUnavailableError
from voice.health import AudioCache
from voice.providers.base import VoiceProvider


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #
@dataclass
class AudioResult:
    """Outcome of a synthesis request. Always returned; never raises to caller."""

    success: bool
    request_id: str = ""
    voice: str = ""
    audio: Any = None
    path: Optional[str] = None
    sample_rate: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class AudioChunk:
    """A single streamed audio frame (future-ready for real-time emission)."""

    request_id: str
    voice: str
    index: int
    audio: Any
    sample_rate: int
    final: bool
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
    *, repo_id: str, lang_code: str, device: Optional[str]
) -> Any:
    """Build a real Kokoro ``KPipeline`` (lazy import keeps kokoro optional)."""
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

    def _ensure_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        if self._kokoro is None:
            raise ProviderUnavailableError("Kokoro package is not available")
        factory = self._pipeline_factory or _default_pipeline_factory
        self._pipeline = factory(
            repo_id=self.config.repo_id,
            lang_code=self.config.lang_code,
            device=self.config.device,
        )
        return self._pipeline

    def _to_wav_bytes(self, audio: Any, sample_rate: int) -> bytes:
        buffer = io.BytesIO()
        sf.write(buffer, audio, sample_rate, format="WAV")
        return buffer.getvalue()

    def _run_synthesis(self, pipeline: Any, text: str, voice: str) -> Optional[Any]:
        chunks: List[Any] = []
        for _graphemes, _phonemes, audio in pipeline(text, voice=voice):
            chunks.append(audio)
        if not chunks:
            return None
        if len(chunks) == 1:
            return chunks[0]
        return np.concatenate(chunks)

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
                    names = self._discoverer.discover(self.config.repo_id, self.config.lang_code)
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
            pipeline = self._ensure_pipeline()
        except Exception as exc:
            self._log.error(
                "Kokoro unavailable: %s", exc, extra={**extra, "failure": type(exc).__name__}
            )
            return AudioResult(success=False, request_id=request_id, voice=selected, error=str(exc))

        try:
            audio = await asyncio.to_thread(self._run_synthesis, pipeline, text, selected)
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
        )

    async def stream_audio(self, text: str, voice: str = "", **kwargs: Any) -> AsyncIterator[Any]:
        """Yield audio as :class:`AudioChunk` frames.

        Kokoro currently emits a complete utterance; we slice it into ~100 ms
        frames so future real-time backends (Unreal lip-sync, SSE) can stream
        without changing this method's contract.
        """
        result = await self.generate_audio(text, voice=voice, **kwargs)
        if not result.success or result.audio is None:
            self._log.error(
                "Streaming aborted: synthesis failed",
                extra={"provider": self.name, "request_id": result.request_id, "error": result.error},
            )
            return
        audio = np.asarray(result.audio)
        frame = max(1, self.config.sample_rate // 10)
        total = (len(audio) + frame - 1) // frame
        for idx in range(total):
            chunk = audio[idx * frame : (idx + 1) * frame]
            yield AudioChunk(
                request_id=result.request_id,
                voice=result.voice,
                index=idx,
                audio=chunk,
                sample_rate=result.sample_rate,
                final=idx == total - 1,
                path=result.path if idx == 0 else None,
            )

    async def available_voices(self) -> Dict[str, Any]:
        return dict(self._voices)

    async def health_check(self) -> Dict[str, Any]:
        checks: Dict[str, Any] = {}
        checks["kokoro_import"] = self._kokoro is not None

        model_ok = False
        try:
            self._ensure_pipeline()
            model_ok = True
        except Exception as exc:
            checks["model_error"] = f"{type(exc).__name__}: {exc}"
        checks["model_available"] = model_ok

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

        available = bool(
            checks["kokoro_import"]
            and checks["cache_writable"]
            and (model_ok or checks["voices_detected"] > 0)
        )

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
