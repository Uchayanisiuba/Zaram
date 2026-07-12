# Migration Report — Zaram v0.5.1 Voice Runtime Foundation

**Date:** 2026-07-12
**Tag:** `v0.5.1-voice-runtime-foundation`
**Scope:** Architecture layer only. No Kokoro integration, no frontend changes,
no personality migration, no audio streaming, no Unreal integration.

---

## 1. Objective

Replace the tightly-coupled speech path

```
ConversationManager -> KokoroTTS
```

with a modular, provider-agnostic Voice Runtime that sits **independently**
from the Kernel:

```
Kernel Runtime
      |
   Event Bus
      |
 Voice Runtime
      |
 Voice Manager
      |
 Voice Provider
```

The application must never depend on a concrete TTS engine.

---

## 2. Files Created

```
backend/voice/
├── __init__.py            # Public exports (VoiceManager, VoiceRegistry, events, exceptions)
├── voice_manager.py       # VoiceManager (registry/lifecycle/routing) + VoiceRuntime bootstrap wrapper
├── registry.py            # VoiceRegistry (register / retrieve / validate / duplicate / missing)
├── events.py              # Voice event types + create_voice_event() -> ZaramEvent
├── exceptions.py          # VoiceRuntimeError, ProviderNotFoundError, DuplicateProviderError, ProviderUnavailableError
├── providers/
│   ├── __init__.py        # Exports VoiceProvider
│   └── base.py            # Abstract VoiceProvider (async interface, contract only)
└── tests/
    ├── test_voice_manager.py
    └── test_voice_registry.py
```

## 3. Files Modified

- `backend/main.py`
  - Imported `VoiceRuntime` from `voice.voice_manager`.
  - Added `voice_runtime` global.
  - In `lifespan()`: initialize the `VoiceRuntime` after the Models Runtime
    (logs `✓ Voice Runtime ready`), and shut it down on exit.
  - Replaced the startup `print()` calls with `logging` (`logger.info`),
    producing the unified readiness report:
    `✓ Kernel Runtime ready` / `✓ Models Runtime ready` / `✓ Voice Runtime ready`.
  - Voice init is wrapped in `try/except` so a voice failure can never block
    application startup.
- `pyproject.toml`
  - Extended `testpaths` to include `backend/voice/tests`.

## 4. Architecture

- **`VoiceProvider` (ABC, async)** — the only contract a TTS backend must
  satisfy: `initialize`, `generate_audio`, `stream_audio`, `available_voices`,
  `health_check`, `shutdown`. No TTS engine is implemented here.
- **`VoiceRegistry`** — maps a provider **name** to a provider **class or
  instance** (`registry.register("kokoro", KokoroProvider)`). Enforces
  duplicate protection, missing-provider errors, and type validation.
  Lazily instantiates via `get_instance()`.
- **`VoiceManager`** — owns the registry and the active provider. Handles
  provider lifecycle (`initialize` / `shutdown`), request routing
  (`synthesize` delegates to the selected provider), health reporting, and a
  config-driven `set_voice_mapping` / `resolve_voice` hook for future
  personality→voice selection. It does **not** know about Kokoro.
- **`VoiceRuntime`** — a thin, bootstrap-friendly wrapper around
  `VoiceManager` providing the async `initialize` / `shutdown` lifecycle used
  by `main.lifespan`. It is intentionally **not** registered in the Kernel
  registry, keeping the Voice Runtime independent from the Kernel.
- **Events** — `create_voice_event()` returns a standard `core.event_bus.ZaramEvent`
  (types: `speech.requested`, `speech.started`, `speech.chunk_generated`,
  `speech.audio_generated`, `speech.completed`, `speech.interrupted`,
  `speech.error`), carrying `request_id` + metadata in `data` and an automatic
  `timestamp`. Fully compatible with the existing event bus.

Dependency injection: providers are injected into the manager/registry and
never instantiated by conversation or UI code.

## 5. Test Results

```
backend/voice/tests/test_voice_registry.py ... 6 passed
backend/voice/tests/test_voice_manager.py .... 6 passed
backend/tests/test_kernel_flow.py ........... 7 passed   (no regressions)
============================= 19 passed =============================
```

Coverage of the required cases:
- Manager initializes (with and without a provider).
- Provider registry works (register, retrieve, activate, initialize).
- Missing provider handled correctly (`ProviderUnavailableError` /
  `ProviderNotFoundError`).
- Shutdown works.
- Registry: registration, retrieval, duplicate protection, missing errors,
  invalid-provider rejection, listing.

Run with: `pytest backend/voice/tests`

## 6. Backwards Compatibility

- `/chat`, `/api/chat`, kernel execution, Ollama integration and the frontend
  are untouched and still function.
- The application starts successfully; the Voice Runtime reaches the
  `ready` state with **no TTS provider** loaded (by design for this milestone).
- No `print()` added in new code; structured `logging` is used.

## 7. Remaining Technical Debt

| # | Item | Notes |
|---|------|-------|
| D1 | No concrete provider yet | Kokoro / XTTS / cloud providers are stubbed/deferred. `VoiceProvider` is interface-only. |
| D2 | `backend/venv/` and `node_modules/` not git-ignored | `.gitignore` only covers `.venv/`. A careless `git add -A` would commit them. |
| D3 | Event-bus wiring for speech requests not yet connected | `create_voice_event` exists; the publish/subscribe flow activates when a provider is added. |
| D4 | Personality→voice mapping is a config hook only | `set_voice_mapping`/`resolve_voice` implemented; the 8-personality library and characters.json migration are a later milestone. |
| D5 | Audio pipeline / streaming deferred | Synthesis returns an opaque audio buffer; file/stream delivery is a later milestone. |

## 8. Next Milestone (not started)

Implement a concrete `KokoroProvider` (model load, voice detection, fallback),
wire `speech.requested` through the Event Bus to `VoiceManager`, and replace the
legacy `ConversationManager` speech path. Do **not** begin until this
foundation is reviewed.
