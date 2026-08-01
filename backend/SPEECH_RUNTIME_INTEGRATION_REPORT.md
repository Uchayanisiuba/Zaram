# Speech Runtime Integration Report

## Architecture Overview

Speech has been promoted to a first-class Runtime following the same architecture as Memory, Filesystem, Internet, Knowledge, Tool, and Models Runtimes.

```
┌─────────────────────────────────────────────────────────────────┐
│                        ZARAM KERNEL                             │
├─────────────────────────────────────────────────────────────────┤
│  RuntimeRegistry                                                 │
│  ├─ MemoryRuntime                                               │
│  ├─ FilesystemRuntime                                           │
│  ├─ InternetRuntime                                             │
│  ├─ KnowledgeRuntime                                            │
│  ├─ ToolRuntime                                                 │
│  ├─ ModelsRuntime                                               │
│  └─ SpeechRuntime          ← NEW (this sprint)                  │
└─────────────────────────────────────────────────────────────────┘
```

## Capability Registration

The Speech Runtime registers the following capabilities via `get_metadata()`:

| Capability ID | Description | Locality |
|--------------|-------------|----------|
| `speech.tts` | Non-streaming text-to-speech synthesis | LOCAL |
| `speech.stream` | Streaming synthesis (async iterator) | LOCAL |
| `speech.stop` | Stop active synthesis | LOCAL |
| `speech.pause` | Pause active synthesis | LOCAL |
| `speech.resume` | Resume paused synthesis | LOCAL |
| `speech.voices` | List available voices | LOCAL |
| `speech.health` | Health diagnostics | LOCAL |
| `speech.devices` | Audio I/O device enumeration | LOCAL |

All capabilities route through `CapabilityRouter` → `SpeechRuntime.execute()`.

## Connector Architecture

**Before (Legacy):**
```
VoiceManager → VoiceProvider (KokoroProvider) → TTS Engine
```

**After (Runtime Architecture):**
```
SpeechRuntime → SpeechConnector (KokoroConnector) → KokoroProvider → KPipeline
                ├─ PiperConnector (future)
                ├─ XTTSConnector (future)
                ├─ ElevenLabsConnector (future)
                ├─ AzureConnector (future)
                └─ OpenAIConnector (future)
```

The Runtime owns the connector registry and active connector selection. Connectors implement `SpeechConnector` protocol - the Runtime never knows provider internals.

## Event Flow

### Executive Integration
```
ExecutiveRuntime (decides to speak)
    │ emits 'executive:speak' { text, persona, voice? }
    ▼
SpeechRuntime (subscribes)
    │ calls connector.stream_synthesis()
    ▼
EventBus publishes:
    • voice.started       { request_id, voice, text, persona }
    • voice.chunk         { request_id, index, audio_id, rmsLevel }
    • voice.level         { request_id, level (0-1), timestamp }
    • voice.finished      { request_id, voice, duration }
    • voice.failed        { request_id, error }
```

### Presence Integration
```
SpeechRuntime publishes voice.* events
    ▼
PresenceRuntime subscribes to:
    • voice.started     → setPresenceState('Speaking')
    • voice.finished    → setPresenceState('Idle')
    • voice.failed      → setPresenceState('Error')
    • voice.level       → setAudioLevel(level)  ← orb visualization
    • voice.chunk       → emitPresenceEvent('presence:voice_chunk')
    ▼
Living Orb receives FrameState with audio.voiceLevel populated
```

### Conversation Integration
```
ConversationManager (LLM tokens)
    │ SpeechPlanner detects sentence boundary
    ▼ emits 'conversation:sentence_ready' { text, persona }
    ▼
ExecutiveRuntime subscribes
    │ setPendingSpeech(text, persona)
    ▼
Executive decides intent='reply'
    │ emits 'executive:speak' { text, persona }
    ▼
SpeechRuntime handles synthesis
```

**Key Change**: Conversation no longer calls TTS directly. It produces text; Executive decides when to speak; Speech Runtime executes.

## Health Dashboard

Speech Runtime reports to central `HealthDashboard`:

```json
{
  "runtime_id": "speech",
  "state": "ready",
  "healthy": true,
  "active_connector": "kokoro",
  "connectors": {
    "kokoro": {
      "status": "healthy",
      "latency_ms": 245.3,
      "voices": 54,
      "cache": "ok",
      "model_available": true,
      "synthesis_test": { "success": true }
    }
  },
  "voices_cached": 54,
  "stats": {
    "total_syntheses": 127,
    "streaming_syntheses": 89,
    "failed_syntheses": 2,
    "avg_latency_ms": 180.5,
    "total_characters": 45230,
    "active_requests": 0,
    "cache_hits": 23,
    "cache_misses": 12
  },
  "uptime_seconds": 3600
}
```

## Migration Summary

### Removed Legacy Services
| Legacy Component | Replaced By |
|-----------------|-------------|
| `VoiceManager` (direct TTS calls) | `SpeechRuntime` + `SpeechConnector` |
| `VoiceRuntime` (bootstrap wrapper) | KernelBootstrapper registers SpeechRuntime |
| `SpeechManager` (queue-based worker) | Connector async streaming |
| `ConversationManager` (direct TTS) | Event-driven via Executive |

### Preserved Functionality
- KokoroProvider synthesis logic (unchanged)
- AudioChunk pipeline (streaming frames)
- Voice discovery from HuggingFace
- AudioCache for WAV persistence
- Persona→voice mapping

### New Capabilities
- Pause/resume/stop mid-synthesis
- Multi-connector support (Kokoro + future providers)
- Executive-driven speech decisions
- Presence-driven orb visualization
- Centralized health monitoring

## Technical Debt / Future Work

1. **Connector Implementations**: Piper, XTTS, ElevenLabs, Azure, OpenAI connectors need implementation
2. **Audio Device Selection**: `speech.devices` returns stub; needs real device enumeration
3. **Streaming SSE**: Desktop VoiceRuntime needs to consume SpeechRuntime streaming events instead of polling `/voice/stream`
4. **Voice Registry**: Persona→voice mapping should move to a shared VoiceRegistry capability
4. **Metrics Export**: Prometheus/Grafana integration for synthesis latency, cache hit rate, failure rates

## Verification Checklist

- ✅ SpeechRuntime implements Runtime protocol (initialize, shutdown, health_check, get_metadata, execute)
- ✅ Registered in KernelBootstrapper alongside ModelsRuntime
- ✅ Capabilities registered in RuntimeRegistry → CapabilityRouter
- ✅ Executive emits `executive:speak`/`pause_speech`/`stop_speech`
- ✅ SpeechRuntime subscribes and executes via KokoroConnector
- ✅ Voice events published to EventBus for Presence
- ✅ PresenceRuntime updates audio level for Living Orb
- ✅ ConversationManager emits `conversation:sentence_ready` (no direct TTS)
- ✅ HealthDashboard includes Speech Runtime with connector health
- ✅ Legacy VoiceManager/VoiceRuntime/SpeechManager removed from boot path

## Sprint Completion Status

```
✅ Memory Runtime
✅ Filesystem Runtime
✅ Internet Runtime
✅ Knowledge Runtime
✅ Tool Runtime
✅ Models Runtime
✅ Speech Runtime        ← THIS SPRINT
⬜ World Runtime         (future)
```

All seven core subsystems now follow the single consistent Runtime Architecture.