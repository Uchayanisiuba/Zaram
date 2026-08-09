"""Kokoro Speech Connector - wraps existing KokoroProvider."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from voice.providers.kokoro import KokoroProvider, AudioResult, AudioChunk as KokoroAudioChunk
from voice.config import KokoroConfig
from runtimes.speech.contracts import (
    SpeechConnector,
    Voice,
    VoiceGender,
    SynthesisRequest,
    SynthesisResult,
    AudioChunk,
    SynthesisMode,
)

logger = logging.getLogger(__name__)


class KokoroConnector(SpeechConnector):
    """Wraps KokoroProvider as a SpeechConnector."""

    def __init__(self, config: Optional[KokoroConfig] = None):
        self._provider = KokoroProvider(config=config)
        self._active_requests: Dict[str, bool] = {}
        self._paused_requests: Dict[str, bool] = {}

    @property
    def connector_id(self) -> str:
        return "kokoro"

    @property
    def connector_type(self) -> str:
        return "local"

    async def initialize(self) -> None:
        await self._provider.initialize()

    async def shutdown(self) -> None:
        await self._provider.shutdown()

    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        request_id = request.request_id or f"kokoro-{uuid.uuid4().hex[:8]}"
        voice = request.voice_id or self._provider.config.default_voice

        self._active_requests[request_id] = True
        start = time.perf_counter()

        try:
            result: AudioResult = await self._provider.generate_audio(
                request.text, voice=voice, request_id=request_id
            )
        except Exception as exc:
            logger.error("Kokoro synthesis failed: %s", exc)
            return SynthesisResult(
                request_id=request_id,
                voice_id=voice,
                audio=b"",
                sample_rate=self._provider.config.sample_rate,
                duration_ms=0.0,
                success=False,
                error=str(exc),
            )
        finally:
            self._active_requests.pop(request_id, None)
            self._paused_requests.pop(request_id, None)

        duration_ms = (time.perf_counter() - start) * 1000

        if not result.success or result.audio is None:
            return SynthesisResult(
                request_id=request_id,
                voice_id=voice,
                audio=b"",
                sample_rate=self._provider.config.sample_rate,
                duration_ms=duration_ms,
                success=False,
                error=result.error,
            )

        import numpy as np
        import soundfile as sf
        import io

        audio_data = np.asarray(result.audio)
        buffer = io.BytesIO()
        sf.write(buffer, audio_data, result.sample_rate, format="WAV")
        wav_bytes = buffer.getvalue()

        return SynthesisResult(
            request_id=request_id,
            voice_id=voice,
            audio=wav_bytes,
            sample_rate=result.sample_rate,
            duration_ms=duration_ms,
            success=True,
            audio_id=result.audio_id,
            format="wav",
            channels=1,
            # Flattened to dicts at the boundary, so nothing downstream imports
            # a type out of `voice.providers`. This is the one place that knows
            # both sides, which is what a connector is for.
            timings=[
                {
                    "text": t.text,
                    "phonemes": t.phonemes,
                    "start_s": t.start_s,
                    "end_s": t.end_s,
                }
                for t in (result.timings or [])
            ],
            metadata=result.metadata or {},
        )

    async def stream_synthesis(self, request: SynthesisRequest) -> AsyncIterator[AudioChunk]:
        request_id = request.request_id or f"kokoro-{uuid.uuid4().hex[:8]}"
        voice = request.voice_id or self._provider.config.default_voice

        self._active_requests[request_id] = True
        self._paused_requests[request_id] = False

        try:
            async for chunk in self._provider.stream_audio(request.text, voice=voice, request_id=request_id):
                if not self._active_requests.get(request_id, False):
                    break

                while self._paused_requests.get(request_id, False):
                    await asyncio.sleep(0.05)
                    if not self._active_requests.get(request_id, False):
                        break

                if not self._active_requests.get(request_id, False):
                    break

                audio_np = chunk.audio
                import io
                import soundfile as sf
                buffer = io.BytesIO()
                sf.write(buffer, audio_np, chunk.sample_rate, format="WAV")
                wav_bytes = buffer.getvalue()

                yield AudioChunk(
                    request_id=request_id,
                    voice_id=voice,
                    index=chunk.index,
                    audio=wav_bytes,
                    sample_rate=chunk.sample_rate,
                    final=chunk.final,
                    timestamp_ms=chunk.timestamp,
                    duration_ms=chunk.duration,
                    audio_id=chunk.audio_id,
                )

                if chunk.final:
                    break
        finally:
            self._active_requests.pop(request_id, None)
            self._paused_requests.pop(request_id, None)

    async def stop(self, request_id: str) -> bool:
        if request_id in self._active_requests:
            self._active_requests[request_id] = False
            self._paused_requests.pop(request_id, None)
            return True
        return False

    async def pause(self, request_id: str) -> bool:
        if request_id in self._active_requests:
            self._paused_requests[request_id] = True
            return True
        return False

    async def resume(self, request_id: str) -> bool:
        if request_id in self._active_requests:
            self._paused_requests[request_id] = False
            return True
        return False

    async def list_voices(self) -> List[Voice]:
        voices_data = await self._provider.available_voices()
        voices: List[Voice] = []
        for vid, meta in voices_data.items():
            gender_str = meta.get("gender", "unknown")
            gender = VoiceGender(gender_str) if gender_str in VoiceGender.__members__.values() else VoiceGender.UNKNOWN
            voices.append(Voice(
                id=vid,
                name=vid,
                language=meta.get("language", "unknown"),
                language_code=meta.get("language_code", "a"),
                gender=gender,
                provider=self.connector_id,
                sample_rate=self._provider.config.sample_rate,
                metadata=meta,
            ))
        return voices

    async def health_check(self) -> Dict[str, Any]:
        return await self._provider.health_check()

    def is_available(self) -> bool:
        health = self._provider._last_health
        return health.get("available", False)