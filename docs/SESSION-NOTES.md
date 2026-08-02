# Session notes — 2 August 2026

Facts recorded at the end of a working session. What changed, what was learned by
running the code, and what was left undone.

---

## What changed

### Documentation reset (committed as `2ad240a`)

- `CLAUDE.md` replaced with the project contract; `docs/VISION.md` added.
- ~161 accumulated markdown files deleted, including nine prior audit documents,
  the `.ai/` constitution, `00_ZARAM_CONSTITUTION/`, `03_ARCHITECTURE/`, `doc/`
  and the old `docs/`.
- `README.md`, `CHANGELOG.md` and the frontend/desktop/electron READMEs rewritten
  against verified state.
- `.kilocode/instructions.md`, `.continue/rules.md`, `.trae/rules/zaram.md` and
  `.trae/context/CONTEXT.md` rewritten for the new direction.
- Deleted `.trae/context/OVERRIDE_PERMISSIONS.md`, which instructed agents to treat
  permission denials as transient glitches and route around them.
- Deleted a stale `figma-assets/project A/CLAUDE.md`, which Claude Code would have
  auto-loaded as nested project instructions.

### Milestone 0 — the recall loop (uncommitted at time of writing)

New file:

- `backend/core/async_bridge.py` — `run_sync(coro)`, runs a coroutine from sync code
  whether or not an event loop is already running.

Modified:

- `backend/core/bootstrapper.py` — the Spine is now SQLite at `backend/spine.db`
  with Ollama `bge-m3` embeddings (1024-dim); the memory runtime is given the event
  bus it previously never received. Overridable via `ZARAM_SPINE_PATH`,
  `ZARAM_EMBED_BACKEND`, `ZARAM_EMBED_MODEL`, `ZARAM_EMBED_DIM`.
- `backend/core/execution_engine.py` — added `_recall`, `_augment_system_prompt`,
  `_provenance_events`, `_remember`. Retrieves relevant memories before planning,
  folds them into the system prompt with `[M1]`-style citation markers, emits one
  `StreamEvent.source` per recalled memory, and stores the exchange afterwards.
  Memory is resolved through the capability router, not imported directly.
- `backend/core/chat_router.py` — forwards `StreamEvent` objects from the engine
  unchanged; plain strings are still wrapped as tokens. Threads `session_id`.
- `backend/runtimes/memory/index.py` — `rebuild()` now actually rebuilds from
  records. It previously only set a timestamp.
- `backend/runtimes/memory/runtime.py` — rebuilds the index from the store on boot;
  `health_check` uses `run_sync`; `consolidate` and `auto_link_memories` no longer
  reach into `store._records` (which only existed on the in-memory store).
- `backend/runtimes/memory/store.py`, `contracts.py` — added `all_records()` to both
  stores and the protocol; `MemoryIndex.rebuild` now takes optional records.
- `backend/runtimes/memory/embeddings.py` — falls back to hash embeddings with a
  single warning if Ollama or the embedding model is unavailable.
- `backend/main.py` — `/audio/{filename}` path traversal fixed (basename-only check
  plus `commonpath` containment); `ChatRequest` gained `session_id`; the
  `zaram_prime` persona prompt no longer orders the model to answer solely from
  internet search results that may not exist.
- `backend/core/dispatcher.py`, `backend/knowledge/providers/memory_provider.py`,
  `backend/knowledge/runtime.py`, `backend/runtimes/speech/runtime.py` — replaced
  `asyncio.run()` / `new_event_loop()` with `run_sync`.
- `backend/knowledge/runtime.py` — two swallowed exceptions now log.
- `backend/tests/test_kernel_flow.py` — the path traversal and 404 tests were not
  awaiting the endpoint coroutine, so they never executed their assertions; fixed
  and extended. `test_main_module_imports_cleanly` asserted `/api/chat`; the app
  serves `/chat`.
- `.gitignore` — excludes `spine.db`.

---

## What was learned by running the code

Verified by execution, not by reading:

- **The chat path works end to end.** `POST /chat` returns live tokens from Ollama
  through the kernel. An earlier claim in this session that the streaming feature was
  broken was wrong; the 11 failing streaming tests are caused by a stale test double
  (`_FakeLLM.stream_response` takes 2 args, production passes 3), not by broken code.
- **The recall loop now works across a restart.** Verified: told the backend a fact,
  killed the process, started it cold, asked again, and got the correct answer plus
  one provenance event naming the source record. Boot log reported
  `Reindexed 1 persisted record(s)`.
- **Before this session, memory was never called during a chat.** The runtime booted,
  registered 12 capabilities, and was never invoked. Confirmed behaviourally: turn 2
  had no knowledge of turn 1.
- **`CapabilityRouter` already mapped `"conversation"` to
  `["memory.retrieve", "reasoning.generate"]`**, but `IntentPlanner` only ever emitted
  `knowledge.search` and `reasoning.generate`. The seam existed and was unconnected.
- **`asyncio.run()` inside FastAPI's loop appears in at least five places.** It was
  live in `/health` output as
  `"kokoro": {"available": false, "error": "asyncio.run() cannot be called from a
  running event loop"}` and was why `knowledge_providers` returned `{}`.
- **The frontend makes zero network calls.** No `fetch`, no API client. Chat replies
  come from a hardcoded string; the memory graph is fabricated sample data.
- **`RuntimePanel.tsx` renders a "LIVE" badge over hardcoded numbers** and a fake
  `code-reviewer` agent.
- **All seven files in `frontend/src/accessibility/` are 0 bytes with 0 importers.**
  So are 19 files in `frontend/src/runtime/`.
- **`frontend/tests/*.test.ts` are all 0 bytes**, `vitest.config.ts` only scans
  `src/`, and its `setupFiles` points at `src/test-setup.ts`, which does not exist.
- **`backend/venv/Scripts/python.exe` exists and has ruff 0.15.21 installed.** Running
  it reports 1,264 lint errors, 1,012 auto-fixable. An earlier claim this session that
  the venv path was wrong was incorrect — that check had been run from the wrong
  directory.
- **The full backend suite takes 1h 33m** (`16 failed, 676 passed in 5627.53s`).
  Excluding `backend/tests/discovery` brings it to about 3 minutes; those 111 tests
  call the live DuckDuckGo API and all pass.
- **Packaging cannot currently produce a working build.** `electron-builder.yml` sets
  `asar: true` while listing `backend` in `files`, so Python source would be packed
  into an archive it cannot execute from. No PyInstaller spec exists. Ollama is never
  referenced in packaging. `desktop/electron-builder.json` contains TypeScript, not
  JSON. The root `build:desktop` script compiles `desktop/` and packages `electron/`.
- **Only two model adapters are needed, not eight.** OpenRouter exposes Claude, GPT,
  Qwen, Kimi, GLM, DeepSeek and Llama behind one OpenAI-compatible endpoint.
- **`OpenAICompatibleAdapter` in `backend/garage/` does discovery only** — it has
  `discover_models()` and `health()`, and no inference method. There is no cloud
  inference path anywhere in the codebase.

---

## Test results

Excluding `backend/tests/discovery`, which calls the live network.

| | Before | After |
|---|---|---|
| Passed | 565 | **568** |
| Failed | 16 | **13** |
| Duration | 181s | **56s** |

Three failures fixed: the two `/audio/{filename}` tests (which never ran their
assertions because the endpoint coroutine was not awaited) and
`test_main_module_imports_cleanly` (asserted a route that does not exist).

The 3× speedup came from replacing per-call event loop creation in
`knowledge/runtime.py` with the shared background loop.

The 13 remaining failures were all present before this session: 11 are the stale
`_FakeLLM.stream_response` signature (10 in `test_streaming_conversation.py`, 1 in
`test_kernel_flow.py`), and 2 are in `test_alpha10c_acceptance.py`.

## Left undone

- The 11 `_FakeLLM` failures remain. They require normalising the `LLMEngine`
  interface, which is Milestone 1 work.
- `run_sync` was first written to create a thread pool per call, which made the
  suite far slower. It now uses one long-lived background loop. Anything that calls
  it still blocks the calling thread for the duration.
- **Memory is retrieved twice per search query** — once by the engine's recall, and
  again by `MemoryProvider` inside `knowledge.search`. The duplicate provenance
  output is suppressed by deduplication, but the duplicate work (including a second
  embedding call to Ollama) still happens. Removing it means changing whether the
  knowledge runtime includes memory, which touches other callers.

## Follow-up committed after the above (`d5dd510`)

`knowledge.search` raw JSON was streaming to the user before the answer. Fixed by
adding `INTERNAL_CAPABILITIES` to the engine: steps in that set gather context for
later steps and are not streamed. Search results are now folded into the system
prompt with `[S1]` markers and emitted as `StreamEvent.source`.

Two defects that fix exposed, also fixed:

- The model was echoing the internal `[S1]` / `[M1]` citation markers into its
  prose. Both prompt blocks now say explicitly not to print them.
- Provenance was duplicated (4 events for 2 records) because memory is consulted
  twice per search query. Deduplicated per request by URL.

Re-verified on a fresh Spine after a cold restart: correct answer, exactly one
provenance source, no JSON and no markers in the reply.

## What I would do next

1. Finish suppressing internal step output from the user stream, so search results
   feed context rather than appearing in the reply.
2. Confirm the full suite result and investigate the runtime increase.
3. Normalise `LLMEngine` to yield tokens rather than SSE-framed strings; this also
   repairs the 11 streaming test failures.
4. Add an OpenRouter adapter and provider selection.
5. Build the egress log as a single chokepoint before any cloud call goes live.
