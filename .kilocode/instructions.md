# Kilo Code — Zaram

## Source of truth

`CLAUDE.md` at the repo root is the project contract: vocabulary, immutable rules,
v1 scope, technical decisions. Read it first. `docs/VISION.md` holds the rationale —
read it before proposing any product change, not before routine implementation.

Nothing in this file overrides `CLAUDE.md`. Where they disagree, `CLAUDE.md` wins.

## Before you write anything

The repo contains a large amount of code that is built, tested, and **not connected to
the running product**. Do not assume a subsystem is live because it exists and has
passing tests. Verified state as of 3 August 2026:

**Working — do not "fix" these:**

- **The recall loop works end to end.** The Spine persists to SQLite at
  `backend/spine.db` with Ollama `bge-m3` embeddings, the index rebuilds from the
  store on boot, `ExecutionEngine` retrieves before planning and stores after
  answering, and each recalled memory emits a `StreamEvent.source`. Verified across a
  process restart.
- **`POST /chat` works** against local Ollama through the kernel.
- **13 backend tests fail**, 11 of them a stale `_FakeLLM.stream_response` signature
  (it takes 2 args; production passes 3). The streaming pipeline itself is not broken.

**Not connected:**

- **The frontend makes zero network calls.** It does not talk to the backend at all.
  Chat replies are a hardcoded string; the memory graph is fabricated sample data.
  It also has nowhere to display the provenance the backend now emits.
- **Only four runtimes boot** (`backend/core/bootstrapper.py`): memory, knowledge,
  models, speech. Agent, artifacts, capability, filesystem, intent, internet,
  reliability, tool, discovery and presence are reachable **only from their own tests**.
- **One model provider is wired.** `models_runtime.py` imports `OllamaEngine` and
  nothing else. `backend/garage/` discovers OpenAI-compatible providers but has no
  inference method, so there is no cloud path at all.
- **There is no egress log.** Rule 3 is currently unimplemented.

If a task depends on any of the above, verify the current state yourself before
building on it. Report what you find rather than assuming the docs are current.

## Scope guard

`CLAUDE.md` lists what is out of scope for v1. That list is binding. Agents, IDE
integration, marketplace, updates feed, voice, document generation, multi-user, and
additional workspaces are **not to be built**, extended, or wired up — including when
the code for them already exists in the repo.

Encountering dormant code for an out-of-scope feature is not permission to activate it.
If a task would require it, stop and say so.

The current milestone is the recall demo: ask model A something, ask model B about it
later, get a cited answer, delete the fact, watch the answer change, open the egress
log and see what left.

## Architecture constraints

- **MCP is the tool protocol.** Never invent a plugin or shim format.
  `backend/runtimes/tool/connectors/base.py` already speaks stdio-subprocess — extend
  that, do not replace it.
- **Runtimes never import each other.** Communicate via the `EventBus` in
  `backend/core/event_bus.py`. Capability calls go through the registry and execution
  engine — that single mediated path is what makes permissions and audit enforceable.
- **Egress belongs behind one chokepoint.** Outbound calls that leave the machine
  originate independently from `knowledge/providers/*` (Wikipedia, GitHub, DuckDuckGo,
  RSS) and `runtimes/internet/*`. Do not add a new independent egress site. Route new
  outbound traffic through a single gate so per-source consent and the egress log stay
  mechanically true. (`runtimes/memory/embeddings.py` calls Ollama on `localhost` —
  local inference, not egress.)
- **Context assembly has no single point.** `system_prompt` is a bare `str` threaded
  through five layers and concatenated wherever something needs adding. Anything you
  inject into it must also emit a `StreamEvent.source`, or you have put an
  unattributable claim in front of the user. `backend/tests/test_provenance_invariant.py`
  asserts this and will fail if you skip it.
- **Every recalled fact carries provenance.** An answer that cites nothing is a bug,
  not a missing feature.
- **Do not build a memory engine from scratch.** Evaluate Letta or an equivalent first.

## Working method

- **Read before you write.** Verify against the code, not against documentation. This
  repo's docs have been wrong more often than they have been right.
- **Verify by observation.** Run it, look at it. Do not report progress you have not
  seen work.
- **Prefer narrow and working over broad and demoable.** One honest path end to end.
- **When a plan and the codebase disagree, the codebase wins.** Say so rather than
  building against a stale assumption.
- **Multi-file changes:** use `backend/templates/` as the starting point for new
  runtime scaffolding, and add a matching test under `backend/tests/` for every new
  module.
- Do not modify `backend/core/` unless the task explicitly calls for it.

## Quality gates

Run before finishing. These commands are verified working:

```bash
# Backend lint — currently ~1264 outstanding errors, ~1012 auto-fixable.
# Do not mass-fix unrelated files; leave the tree no worse than you found it.
./backend/venv/Scripts/python.exe -m ruff check backend/

# Frontend typecheck — currently CLEAN (0 errors). Keep it that way.
cd frontend && npx tsc --noEmit

# Backend tests. Skip the discovery folder: those 111 tests call the live
# DuckDuckGo API and take ~91 minutes. Without them: 568 pass, 13 fail, ~60s.
# Do not let the failure count rise above 13.
./.venv/Scripts/python.exe -m pytest backend/tests --ignore=backend/tests/discovery -q
```

Known gate problems — fix them if a task touches them, do not work around them:

- `npm run lint` in `frontend/` crashes; `eslint` is not installed.
- `frontend/tests/*.test.ts` are all 0 bytes, `vitest.config.ts` only scans `src/`,
  and its `setupFiles` points at `src/test-setup.ts`, which does not exist.
- `npm run dev:backend` and `build:desktop` reference paths that do not resolve.

## Security

Zaram's pitch is that it makes tool use safe for people who cannot audit it. That
raises the bar on our own code.

- Validate and reject any user-controlled path segment. Never `os.path.join` a request
  value onto a directory without normalising and confirming containment.
  `/audio/{filename}` in `backend/main.py` is the worked example — basename-only plus a
  `commonpath` containment check. It was a live path traversal until 3 August 2026.
- No `eval`, `exec`, `shell=True`, or `pickle.loads` on external input.
- Never claim absolute security in code comments, UI copy, or commit messages. State
  what is verifiable: inference ran locally, index is on disk, egress is logged.

## Vocabulary

Use: **Spine**, **Recall**, **Provenance**, **Routing**, **Egress log**, **Orb**,
**Workspace**.

Retired — do not use in code, comments, identifiers, UI copy or commits:
"faculty", "nursery", "aperture", "synapse web", "AI operating system".

Note that the existing codebase still uses OS-metaphor naming internally (kernel,
bootstrapper, runtimes, registry). That is acceptable in existing code. Do not
propagate it into user-facing strings.
