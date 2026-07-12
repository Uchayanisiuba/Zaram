# Migration Report — Zaram v0.4 "kernel-stable"

**Date:** 2026-07-12
**Scope:** Completion and stabilization of Sprint 3 (Kernel / Execution Engine).
**Status:** ✅ Verified — 7/7 regression tests pass, app imports cleanly, full execution flow confirmed against a live Ollama backend.

This milestone intentionally does **not** begin the Phase 1 Voice Architecture
(`VoiceManager`, `VoiceProvider`, UI redesign, or Electron migration). Those
remain pending per the stated sequencing.

---

## 1. Completed Work

### 1.1 Removed accidental nested package
- Deleted `backend/core/backend/` — a partial recursive copy of `backend/core/`
  left behind when the package-move operation was interrupted. The project now
  has a single canonical `backend/core/` package.

### 1.2 Restored missing imports & fixed `/audio` endpoint
- `backend/main.py`: re-added `HTTPException` to the FastAPI import
  (it had been dropped during the interrupted edit, causing a guaranteed
  `NameError` on the audio route).
- Rewrote `GET /audio/{filename}` to resolve paths with `pathlib.Path` against
  a canonical `AUDIO_CACHE_DIR = BASE_DIR / "audio_cache"`, with
  **path-traversal protection** (rejects `..` escapes with `400`).

### 1.3 Consolidated duplicate packages
- Removed orphaned root-level shells: `implementations/`, `interfaces/`,
  `services/` (empty `__init__.py` only) and empty `parsers/`, `processors/`.
- Canonical backend packages now live exclusively under `backend/`
  (`implementations/`, `interfaces/`, `services/`, `runtimes/`, `core/`).
- Verified no project file imported the root shells.

### 1.4 Stabilized the legacy voice path
- `backend/services/speech_manager.py`: `SpeechManager` now guards against a
  `None` TTS engine (gracefully skips audio instead of raising
  `AttributeError`), keeping `pending_tasks` accounting correct so
  conversations still terminate.
- Resolved the audio cache directory from the module location
  (`Path(__file__).resolve().parent.parent / "audio_cache"`) instead of the
  cwd-relative `"backend/audio_cache"`, so written audio lands in the same
  directory the endpoint serves.

### 1.5 Verified the execution flow
End-to-end path confirmed via `core/test_execution_engine.py` (live Ollama):
`IntentPlanner` → `CapabilityRouter` → `ExecutionDispatcher` →
`ModelsRuntime` → `ModelsService` → `OllamaEngine`.

### 1.6 Regression tests added
- `backend/conftest.py` — puts `backend/` on `sys.path` for test discovery.
- `backend/tests/test_kernel_flow.py` — 7 tests:
  - kernel token streaming (no live LLM needed)
  - plan-created event emission
  - unknown-capability routing failure (`KeyError`)
  - audio endpoint path-traversal rejection (`400`)
  - audio endpoint missing file (`404`)
  - `main` module imports cleanly with expected routes
  - legacy conversation terminates cleanly with **no TTS** (`{"type":"done"}`)
- `backend/core/test_execution_engine.py` — added a `sys.path` bootstrap and
  removed an emoji from the success print (it crashed on the cp1252 console,
  violating the no-emoji-logging principle).

### 1.7 Tagged release
- Git tag `v0.4-kernel-stable` marks the stabilized Sprint 3 state.

---

## 2. Remaining Technical Debt

| # | Item | Severity | Notes |
|---|------|----------|-------|
| D1 | `backend/venv/` and `node_modules/` are **not** git-ignored | High | `.gitignore` only covers `.venv/`. A careless `git add -A` would commit them. Add `backend/venv/` and `node_modules/`. |
| D2 | Root-level `src/` vs `frontend/src/` duplication | Med | Frontend appears in two places. Out of Sprint 3 scope (UI work deferred). |
| D3 | `core/events.py` duplication | Low | `backend/core/events.py` (minimal) vs the richer `SentenceReady`/`AudioChunkReady` definitions. Unify when voice work resumes. |
| D4 | `print()` logging throughout | Med | Kernel still uses `print()` (bootstrapper, registry, models_runtime). Must be replaced with `logging` before production (Phase 1 requirement). |
| D5 | Legacy path still uses `ConversationManager(llm, None)` and emits `data: [DONE]` | Med | Preserved for rollback; must be migrated to `VoiceManager` + `{"type":"done"}` in Phase 1. |
| D6 | Frontend `characters.json` fields (`gender`, `description`) added but **only 3 personalities** exist | Low | Phase 1 requires 8 built-in personalities driven by config. |
| D7 | No `pytest` configured in `pyproject.toml` at root; tests rely on `conftest.py` path injection | Low | Add an explicit `[tool.pytest.ini_options]` `pythonpath`/`testpaths` for CI. |

---

## 3. Readiness for VoiceManager Implementation

**Ready to start.** The kernel provides a clean seam:

- `ExecutionEngine` orchestrates via `CapabilityRouter` → `Runtime.get_service()`.
- Adding voice is a new **Runtime** (e.g. `VoiceRuntime`) exposing a
  `VoiceManager`/`VoiceProvider` service, registered in `lifespan()` exactly
  like `ModelsRuntime`. No changes to `ExecutionEngine`, `Planner`,
  `Dispatcher`, or `Router` are required.
- The legacy `ConversationManager` → `SpeechManager` path is isolated and can
  be replaced behind the `VoiceManager` abstraction without touching the kernel.

**Preconditions before VoiceManager work:**
1. Resolve D1 (ignore `backend/venv/`, `node_modules/`).
2. Replace `print()` with `logging` (D4).
3. Remove the legacy `ConversationManager(llm, None)` anti-pattern (D5).
