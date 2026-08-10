"""Speech Runtime - first-class runtime for speech synthesis.

Implements the Runtime protocol and owns:
- VoiceManager (wrapped)
- SpeechPlanner
- SpeechManager
- SpeechConnectors (Kokoro, future: Piper, XTTS, ElevenLabs, Azure, OpenAI)
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from core.contracts import Runtime, RuntimeMetadata, Capability, RuntimeState, CapabilityLocality
from core.event_bus import EventBus, ZaramEvent

from runtimes.speech.contracts import (
    SpeechCapability,
    SpeechConnector,
    SynthesisRequest,
    SynthesisResult,
    AudioChunk,
    Voice,
    SynthesisMode,
)
from runtimes.speech.connectors import KokoroConnector

logger = logging.getLogger(__name__)

RUNTIME_ID = "speech"
RUNTIME_VERSION = "1.0.0"


@dataclass
class SpeechRuntimeStats:
    total_syntheses: int = 0
    streaming_syntheses: int = 0
    failed_syntheses: int = 0
    total_latency_ms: float = 0.0
    total_characters: int = 0
    active_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


class SpeechRuntime(Runtime):
    """First-class Speech Runtime implementing the Runtime protocol."""

    def __init__(
        self,
        event_bus: EventBus,
        audio_dir: str = "audio_cache",
        #: Prefix for the audio URL. **Empty by default, which makes the URL
        #: relative** — and relative is what the caller actually wants.
        #:
        #: It used to default to `http://127.0.0.1:8420`, hardcoded, and nothing
        #: ever passed a different value. That is wrong three ways: the backend
        #: does not always run on 8420 (the port is configurable and the dev
        #: machine runs two), an absolute URL bypasses the Vite proxy and turns
        #: an audio fetch into a cross-origin request, and a packaged build
        #: pointing at a bundled backend has no reason to hardcode a loopback
        #: address. A relative URL is correct in all three cases because the
        #: frontend already prefixes it with its configured API base.
        base_url: str = "",
    ):
        self._event_bus = event_bus
        self._state = RuntimeState.UNINITIALIZED
        self._start_time = time.time()
        self._stats = SpeechRuntimeStats()

        self._connectors: Dict[str, SpeechConnector] = {}
        self._active_connector_id: Optional[str] = None
        self._voice_cache: List[Voice] = []
        self._voice_cache_time = 0.0
        self._voice_cache_ttl = 300.0  # 5 minutes

        # SpeechPlanner for token buffering and sentence boundary detection
        self._speech_planner = None

        # Pending speech queue (for executive:speak events)
        self._pending_speech: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

        # Audio cache directory
        self._audio_dir = audio_dir
        self._base_url = base_url

        # Active synthesis tracking for pause/resume/stop
        self._active_syntheses: Dict[str, Dict[str, Any]] = {}

        # Executive event handlers
        self._unsubscribe_executive_speak = None
        self._unsubscribe_executive_pause = None
        self._unsubscribe_executive_stop = None

    def get_runtime_id(self) -> str:
        return RUNTIME_ID

    def get_version(self) -> str:
        return RUNTIME_VERSION

    def get_metadata(self) -> RuntimeMetadata:
        capabilities = [
            Capability(id=SpeechCapability.TTS, runtime_id=RUNTIME_ID, category="speech", locality=CapabilityLocality.LOCAL),
            Capability(id=SpeechCapability.STREAM, runtime_id=RUNTIME_ID, category="speech", locality=CapabilityLocality.LOCAL),
            Capability(id=SpeechCapability.STOP, runtime_id=RUNTIME_ID, category="speech", locality=CapabilityLocality.LOCAL),
            Capability(id=SpeechCapability.PAUSE, runtime_id=RUNTIME_ID, category="speech", locality=CapabilityLocality.LOCAL),
            Capability(id=SpeechCapability.RESUME, runtime_id=RUNTIME_ID, category="speech", locality=CapabilityLocality.LOCAL),
            Capability(id=SpeechCapability.VOICES, runtime_id=RUNTIME_ID, category="speech", locality=CapabilityLocality.LOCAL),
            Capability(id=SpeechCapability.HEALTH, runtime_id=RUNTIME_ID, category="speech", locality=CapabilityLocality.LOCAL),
            Capability(id=SpeechCapability.DEVICES, runtime_id=RUNTIME_ID, category="speech", locality=CapabilityLocality.LOCAL),
        ]
        return RuntimeMetadata(
            runtime_id=RUNTIME_ID,
            version=RUNTIME_VERSION,
            priority="high",
            capabilities=capabilities,
            dependencies=["event_bus"],
            auto_start=True,
            restart_policy=RestartPolicy.ON_FAILURE,
        )

    def get_state(self) -> RuntimeState:
        return self._state

    async def initialize(self) -> None:
        self._state = RuntimeState.INITIALIZING
        logger.info("Speech Runtime initializing...")

        # Register default Kokoro connector
        kokoro = KokoroConnector()
        await self.register_connector(kokoro)
        await self.set_active_connector("kokoro")

        # Initialize active connector
        if self._active_connector_id:
            connector = self._connectors[self._active_connector_id]
            await connector.initialize()

        # Subscribe to Executive events
        self._subscribe_executive_events()

        self._state = RuntimeState.READY

        # Publish runtime ready event
        self._event_bus.publish(ZaramEvent(
            source_runtime=RUNTIME_ID,
            event_type="runtime.ready",
            data={"runtime_id": RUNTIME_ID, "connectors": list(self._connectors.keys())},
        ))
        logger.info("Speech Runtime ready with connectors: %s", list(self._connectors.keys()))

    def _subscribe_executive_events(self) -> None:
        """Subscribe to Executive Runtime speech events."""
        self._unsubscribe_executive_speak = self._event_bus.subscribe(
            "executive:speak", self.handle_executive_speak
        )
        self._unsubscribe_executive_pause = self._event_bus.subscribe(
            "executive:pause_speech", self.handle_executive_pause_speech
        )
        self._unsubscribe_executive_stop = self._event_bus.subscribe(
            "executive:stop_speech", self.handle_executive_stop_speech
        )
        logger.info("Subscribed to executive speech events")

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        logger.info("Speech Runtime shutting down...")

        # Unsubscribe from executive events. These are tokens, not callables —
        # calling them raised TypeError on every kernel shutdown, which left the
        # rest of this method unreachable and the Spine's SQLite connection
        # closed by process exit rather than by us.
        for token in (
            self._unsubscribe_executive_speak,
            self._unsubscribe_executive_pause,
            self._unsubscribe_executive_stop,
        ):
            if token:
                self._event_bus.unsubscribe(token)

        # Stop all active syntheses
        for request_id in list(self._active_syntheses.keys()):
            await self.stop_synthesis(request_id)

        # Shutdown all connectors
        for connector in self._connectors.values():
            try:
                await connector.shutdown()
            except Exception as exc:
                logger.warning("Error shutting down connector %s: %s", connector.connector_id, exc)

        self._connectors.clear()
        self._active_connector_id = None
        self._state = RuntimeState.STOPPED
        logger.info("Speech Runtime stopped")

    def health_check(self) -> Dict[str, Any]:
        connector_health = {}
        for cid, connector in self._connectors.items():
            try:
                health = connector.health_check() if hasattr(connector, 'health_check') else {}
                if asyncio.iscoroutine(health):
                    # Reached from FastAPI's /health, where a loop is already
                    # running and asyncio.run() would raise.
                    from core.async_bridge import run_sync
                    health = run_sync(health)
                connector_health[cid] = health
            except Exception as exc:
                connector_health[cid] = {"available": False, "error": str(exc)}

        active_connector = self._connectors.get(self._active_connector_id) if self._active_connector_id else None
        active_health = connector_health.get(self._active_connector_id, {}) if self._active_connector_id else {}

        return {
            "runtime_id": RUNTIME_ID,
            "state": self._state.value,
            "healthy": self._state == RuntimeState.READY,
            "active_connector": self._active_connector_id,
            "connectors": connector_health,
            "active_connector_health": active_health,
            "voices_cached": len(self._voice_cache),
            "stats": {
                "total_syntheses": self._stats.total_syntheses,
                "streaming_syntheses": self._stats.streaming_syntheses,
                "failed_syntheses": self._stats.failed_syntheses,
                "avg_latency_ms": self._stats.total_latency_ms / max(self._stats.total_syntheses, 1),
                "total_characters": self._stats.total_characters,
                "active_requests": self._stats.active_requests,
                "cache_hits": self._stats.cache_hits,
                "cache_misses": self._stats.cache_misses,
            },
            "uptime_seconds": time.time() - self._start_time,
        }

    # --- Connector Management ---

    async def register_connector(self, connector: SpeechConnector) -> None:
        if connector.connector_id in self._connectors:
            raise ValueError(f"Connector {connector.connector_id} already registered")
        self._connectors[connector.connector_id] = connector
        logger.info("Registered speech connector: %s (%s)", connector.connector_id, connector.connector_type)

    async def unregister_connector(self, connector_id: str) -> None:
        connector = self._connectors.pop(connector_id, None)
        if connector:
            await connector.shutdown()
            if self._active_connector_id == connector_id:
                self._active_connector_id = None
            logger.info("Unregistered speech connector: %s", connector_id)

    async def set_active_connector(self, connector_id: str) -> None:
        if connector_id not in self._connectors:
            raise ValueError(f"Connector {connector_id} not registered")
        self._active_connector_id = connector_id
        logger.info("Active speech connector set to: %s", connector_id)

    def get_active_connector(self) -> SpeechConnector:
        if not self._active_connector_id:
            raise RuntimeError("No active speech connector")
        return self._connectors[self._active_connector_id]

    def list_connectors(self) -> List[Dict[str, Any]]:
        result = []
        for cid, connector in self._connectors.items():
            result.append({
                "connector_id": cid,
                "connector_type": connector.connector_type,
                "active": cid == self._active_connector_id,
                "available": connector.is_available(),
            })
        return result

    # --- Capability Execution ---

    async def execute(self, capability_id: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a speech capability via the Capability Router."""
        connector = self.get_active_connector()

        if capability_id == SpeechCapability.TTS:
            return await self._execute_tts(connector, input_data)
        elif capability_id == SpeechCapability.STREAM:
            return await self._execute_stream(connector, input_data)
        elif capability_id == SpeechCapability.STOP:
            return await self._execute_stop(input_data)
        elif capability_id == SpeechCapability.PAUSE:
            return await self._execute_pause(input_data)
        elif capability_id == SpeechCapability.RESUME:
            return await self._execute_resume(input_data)
        elif capability_id == SpeechCapability.VOICES:
            return await self._execute_voices(connector, input_data)
        elif capability_id == SpeechCapability.HEALTH:
            return self.health_check()
        elif capability_id == SpeechCapability.DEVICES:
            return await self._execute_devices()
        else:
            raise ValueError(f"Unknown speech capability: {capability_id}")

    async def _execute_tts(self, connector: SpeechConnector, input_data: Dict[str, Any]) -> Dict[str, Any]:
        request = SynthesisRequest(
            text=input_data.get("text", ""),
            voice_id=input_data.get("voice", ""),
            provider_id=input_data.get("provider", ""),
            mode=SynthesisMode.NON_STREAMING,
            request_id=input_data.get("request_id", f"tts-{uuid.uuid4().hex[:8]}"),
            metadata=input_data.get("metadata", {}),
        )

        start = time.perf_counter()
        self._stats.active_requests += 1
        self._stats.total_syntheses += 1
        self._stats.total_characters += len(request.text)

        try:
            result: SynthesisResult = await connector.synthesize(request)
        finally:
            self._stats.active_requests -= 1
            self._stats.total_latency_ms += (time.perf_counter() - start) * 1000

        if not result.success:
            self._stats.failed_syntheses += 1
            self._publish_event("speech.error", {"request_id": request.request_id, "error": result.error})
            return {"success": False, "error": result.error, "request_id": request.request_id}

        # Publish completion event
        self._publish_event("speech.completed", {
            "request_id": request.request_id,
            "voice": result.voice_id,
            "duration_ms": result.duration_ms,
            "audio_id": result.audio_id,
        })

        # Return audio URL for frontend.
        #
        # Built from the filename the engine actually wrote. It used to be built
        # from `audio_id` — the *request* id — while AudioCache names files
        # `{voice}_{hash}.wav`, so the URL pointed at a file that never existed
        # and every reply 404'd on playback. Nothing failed loudly: synthesis
        # succeeded, the response looked right, and the browser got a dead link.
        audio_url = (
            f"{self._base_url}/audio/{result.audio_filename}"
            if result.audio_filename
            else ""
        )
        return {
            "success": True,
            "request_id": request.request_id,
            "audio_url": audio_url,
            "audio_id": result.audio_id,
            "voice": result.voice_id,
            "duration_ms": result.duration_ms,
            "sample_rate": result.sample_rate,
            # Word timings for lip sync, absolute seconds from the start of the
            # utterance. Always present, empty when the engine cannot say — a
            # renderer checks and falls back rather than branching on absence.
            "timings": result.timings,
        }

    async def _execute_stream(self, connector: SpeechConnector, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Streaming synthesis returns async iterator - handled specially by router."""
        request = SynthesisRequest(
            text=input_data.get("text", ""),
            voice_id=input_data.get("voice", ""),
            provider_id=input_data.get("provider", ""),
            mode=SynthesisMode.STREAMING,
            request_id=input_data.get("request_id", f"stream-{uuid.uuid4().hex[:8]}"),
            metadata=input_data.get("metadata", {}),
        )

        self._stats.active_requests += 1
        self._stats.streaming_syntheses += 1
        self._stats.total_characters += len(request.text)

        self._publish_event("speech.started", {
            "request_id": request.request_id,
            "voice": request.voice_id,
            "text_preview": request.text[:100],
        })

        # Return the async iterator directly (router handles streaming)
        return {
            "stream": connector.stream_synthesis(request),
            "request_id": request.request_id,
            "voice": request.voice_id,
        }

    async def _execute_stop(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        request_id = input_data.get("request_id")
        if not request_id:
            return {"success": False, "error": "request_id required"}

        connector = self.get_active_connector()
        success = await connector.stop(request_id)
        self._active_syntheses.pop(request_id, None)

        self._publish_event("speech.stopped", {"request_id": request_id})
        return {"success": success, "request_id": request_id}

    async def _execute_pause(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        request_id = input_data.get("request_id")
        if not request_id:
            return {"success": False, "error": "request_id required"}

        connector = self.get_active_connector()
        success = await connector.pause(request_id)

        self._publish_event("speech.paused", {"request_id": request_id})
        return {"success": success, "request_id": request_id}

    async def _execute_resume(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        request_id = input_data.get("request_id")
        if not request_id:
            return {"success": False, "error": "request_id required"}

        connector = self.get_active_connector()
        success = await connector.resume(request_id)

        self._publish_event("speech.resumed", {"request_id": request_id})
        return {"success": success, "request_id": request_id}

    async def _execute_voices(self, connector: SpeechConnector, input_data: Dict[str, Any]) -> Dict[str, Any]:
        # Check cache
        now = time.time()
        if self._voice_cache and (now - self._voice_cache_time) < self._voice_cache_ttl:
            self._stats.cache_hits += 1
            return {"voices": [v.__dict__ for v in self._voice_cache], "cached": True}

        self._stats.cache_misses += 1
        voices = await connector.list_voices()
        self._voice_cache = voices
        self._voice_cache_time = now

        return {"voices": [v.__dict__ for v in voices], "cached": False}

    async def _execute_devices(self) -> Dict[str, Any]:
        # Audio output devices - future implementation
        return {
            "output_devices": [
                {"id": "default", "name": "Default Output Device", "default": True}
            ],
            "input_devices": [
                {"id": "default", "name": "Default Input Device", "default": True}
            ],
        }

    # --- Event Publishing ---

    def _publish_event(self, event_type: str, data: Dict[str, Any]) -> None:
        self._event_bus.publish(ZaramEvent(
            source_runtime=RUNTIME_ID,
            event_type=event_type,
            data=data,
        ))

    # --- Executive Integration ---

    async def handle_executive_speak(self, event: ZaramEvent) -> None:
        """Handle executive:speak event - synthesize and stream speech."""
        data = event.data
        text = data.get("text", "")
        persona = data.get("persona", "zaram_prime")
        voice = data.get("voice", "")

        if not text:
            logger.warning("executive:speak received with empty text")
            return

        logger.info("Executive requested speech: persona=%s, text=%s...", persona, text[:50])

        # Map persona to voice (future: use voice registry)
        voice_map = {
            "zaram_prime": "af_heart",
            "zaram_alt": "am_michael",
        }
        selected_voice = voice or voice_map.get(persona, "af_heart")

        request_id = f"exec-{uuid.uuid4().hex[:8]}"
        self._active_syntheses[request_id] = {
            "text": text,
            "voice": selected_voice,
            "persona": persona,
            "started_at": time.time(),
        }

        self._publish_event("voice.started", {
            "request_id": request_id,
            "voice": selected_voice,
            "text": text,
            "persona": persona,
        })

        connector = self.get_active_connector()
        self._stats.active_requests += 1

        try:
            async for chunk in connector.stream_synthesis(SynthesisRequest(
                text=text,
                voice_id=selected_voice,
                mode=SynthesisMode.STREAMING,
                request_id=request_id,
            )):
                self._publish_event("voice.chunk", {
                    "request_id": chunk.request_id,
                    "voice": chunk.voice_id,
                    "index": chunk.index,
                    "final": chunk.final,
                    "timestamp_ms": chunk.timestamp_ms,
                    "duration_ms": chunk.duration_ms,
                    "audio_id": chunk.audio_id,
                })

                # Also publish audio level for orb visualization
                if chunk.audio:
                    import numpy as np
                    audio_np = np.frombuffer(chunk.audio, dtype=np.int16)
                    if len(audio_np) > 0:
                        rms = float(np.sqrt(np.mean(audio_np.astype(np.float32) ** 2)))
                        level = min(1.0, rms / 32768.0 * 10)  # Scale for visualization
                        self._publish_event("voice.level", {
                            "request_id": chunk.request_id,
                            "level": level,
                            "timestamp": time.time(),
                        })

                if chunk.final:
                    break

            self._publish_event("voice.finished", {
                "request_id": request_id,
                "voice": selected_voice,
                "duration": time.time() - self._active_syntheses[request_id]["started_at"],
            })

        except Exception as exc:
            logger.error("Speech synthesis failed: %s", exc)
            self._publish_event("voice.failed", {
                "request_id": request_id,
                "error": str(exc),
            })
        finally:
            self._stats.active_requests -= 1
            self._active_syntheses.pop(request_id, None)

    async def handle_executive_pause_speech(self, event: ZaramEvent) -> None:
        """Handle executive:pause_speech event."""
        request_id = event.data.get("request_id")
        if request_id:
            connector = self.get_active_connector()
            await connector.pause(request_id)
            self._publish_event("speech.paused", {"request_id": request_id})

    async def handle_executive_stop_speech(self, event: ZaramEvent) -> None:
        """Handle executive:stop_speech event."""
        request_id = event.data.get("request_id")
        if request_id:
            connector = self.get_active_connector()
            await connector.stop(request_id)
            self._active_syntheses.pop(request_id, None)
            self._publish_event("speech.stopped", {"request_id": request_id})

    def register_capabilities(self) -> None:
        """Called by Capability Router to register capabilities."""
        # Capabilities are registered via get_metadata()
        pass


# Import RestartPolicy after definition to avoid circular import
from core.contracts import RestartPolicy