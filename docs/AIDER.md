# Aider on this repository

What it can do here, what it structurally cannot, and the gate every change
has to pass before it counts. Measured 5 September 2026 on the maintainer's
machine, with Ollama up.

## Where it lives

The venv is `%LOCALAPPDATA%\aider-venv`, **outside the repository**, because
Aider is a tool the maintainer runs rather than something Zaram ships or
depends on. Only its configuration is version-controlled: `.aider.conf.yml`
and `.aiderignore`, both of which encode facts about *this* repository.

    "%LOCALAPPDATA%\aider-venv\Scripts\aider.exe" backend/core/readiness.py

Run it from the repository root so it picks up the config and the ignore file.

## The context ceiling, which decides everything else

**Rewritten 10 September 2026.** Everything below this heading used to be
computed against `qwen3-14b-8k` and its 8,192-token window. That model is not
installed — Ollama answers `model not found` — so the config had been pointed
at nothing, and every verdict in the old table was arithmetic on a number that
no longer applies to anything.

What is actually installed, measured against `/api/tags`, `/api/show` and
TabbyAPI's `/v1/model`:

| engine · model | window | on disk | fits 12 GB? |
|---|---|---|---|
| TabbyAPI `Qwen3.8-27B-exl3-2.20bpw` | **65,536** | 8.48 GiB resident | **yes, whole** |
| Ollama `qwen3-coder-30b-32k` | 32,768 | 18.56 GB | no — spills to CPU |
| Ollama `qwen3-14b-16k` | 16,384 | 9.28 GB | yes |
| Ollama `gemma4-26b-32k` | 32,768 | 17.99 GB | no — spills to CPU |

TabbyAPI is the default in `.aider.conf.yml` because it is the only one that
holds the largest window *and* fits VRAM whole: 26.3 tok/s, 0.7 s to first
token. The 30B coder is the better model for code and the worse model to wait
for, and nothing has compared the two on output quality — `exl3-2.20bpw`
against `Q4_K_M` is roughly 2.2 bits per weight against 4.5, and that gap is
unmeasured here. Treat the default as the fast option, not the good one, until
somebody measures it.

What the 64k window reaches:

| file | ~tokens | verdict |
|---|---|---|
| `backend/core/readiness.py` | 2,100 | comfortable |
| `backend/runtimes/mcp/runtime.py` | 3,500 | comfortable |
| `frontend/src/components/chat/ChatSurface.tsx` | 15,000 | **now reachable** |
| `frontend/src/workspaces/SettingsWorkspace.tsx` | 16,700 | **now reachable** |
| `backend/main.py` | 54,600 | fits once, no room to work |

`main.py` is 5,143 lines and 54,600 tokens. It now fits inside a 65,536 window
*once* — which is not the same as being editable, because the reply and the
repo map need room in the same window. **Still do not point Aider at it.** The
structural fix is unchanged and still worth doing on its own merits: extract
routers, `app.include_router` is already the pattern at `main.py:193`.

The old advice here — *"a smaller model with a much larger window would reach
further"* — has been taken. That is what the TabbyAPI default is.

## Output tokens, not input, decide how long you wait

The window governs what is *reachable*; the edit format governs what it
*costs*. `whole` re-emits an entire file for a three-line change, so a
15,000-token file is 15,000 output tokens — about ten minutes at 26 tok/s
before anything useful appears. A diff costs the edited lines.

`.aider.conf.yml` therefore sets `edit-format: diff`, reversing the old
`whole`. The old choice was correct for its evidence: a 14B produced malformed
search/replace blocks often enough that retries cost more than resending the
file. That was a different model. If this one produces malformed blocks, fall
back with `--edit-format whole` on the command line and write down what you
saw — the point is that the trade is now measurable in both directions.

## Measured, 10 September 2026

One small edit to `backend/core/readiness.py` — add a comment line — on an
otherwise idle card, `--dry-run`, repo map at 2048.

| | thinking on | thinking off |
|---|---|---|
| wall clock | 62.3 s | **34.9 s** |
| tokens sent | 7.5k | 7.5k |
| tokens received | 229 | **77** |
| diff produced | valid | valid |

**Output tokens fall 66%, wall clock 44%**, and the diff is identical — same
anchor, same well-formed SEARCH/REPLACE block, no retry. Wall clock improves
less than tokens because a fixed cost dominates a small edit: 7.5k of prompt
processing, the repo-map refresh, startup. Only generation scales, so the
saving grows with the size of the reply.

`edit-format: diff` is therefore proven on this model. The old `whole` setting
was a 14B's limitation, not this one's.

### Turning thinking off is not the setting you would guess

`--thinking-tokens 0` is accepted by Aider and **ignored by TabbyAPI**. A run
with it set still returned a full reasoning trace — the reply opened with
*"The user wants me to add a single comment line…"*. It was removed from
`.aider.conf.yml` rather than left as a hopeful no-op.

What works is passing `enable_thinking: false` through to the chat template.
Both spellings are accepted by the server — `chat_template_kwargs` and
`template_vars` — and a request carrying either returned the literal two
characters `OK` with no trace at all. It lives in
`.aider.model.settings.yml` under `extra_params.extra_body`.

`reasoning_tag: think` stays as a belt-and-braces and cannot work alone:
Qwen3's template prefills the opening tag, so a reply carries reasoning
terminated by a bare `</think>` and there is no `<think>` to match on.

**The same finding applies to Zaram**, which routes to this model too. The
Tabby config's own `reasoning: true` fails identically, and `reasoning_content`
comes back `null`.

### Run it from PowerShell, not Git Bash

A run under Git Bash exited 0 after the repo scan without ever calling the
model. The same invocation from PowerShell works. Both print
`Can't initialize prompt toolkit`, so **that is not the explanation** and the
real mechanism is unproven — recorded as an observation rather than a cause.

### Aider needs about 26k tokens, and has 65,536

| | tokens |
|---|---|
| Aider system prompt, diff format | ~3,300 |
| repo map at `map-tokens: 2048` | ~2,000 |
| `SettingsWorkspace.tsx`, the biggest reachable file | ~16,700 |
| history and reply | ~4,000 |
| **total** | **~26,000** |

So context is not the constraint and `cache_size` is not an Aider lever. The
KV cache is allocated lazily — the card sits at 9.4 GB idle against 9.61 GiB
of weights — so the large window costs nothing until it is used.

## The gate

A change is not done because it runs. It is done when something **calls** it
and the repository's own checks pass. Fifteen complete, tested, unreachable
subsystems have been found here; that is the base rate, and it is what this
gate exists for.

| what changed | run |
|---|---|
| backend Python | `backend/venv/Scripts/python.exe -m pytest backend/tests/<file> -q` |
| anything, always | `npm run check:reachability` |
| a new route prefix | `npm run --prefix frontend check:proxy` |
| frontend | `cd frontend && npx tsc --noEmit && npx vitest run` |

`check:proxy` is not optional for a new route: the prefix must be added to
**both** `frontend/vite.config.js` and `electron/config.js`, and missing either
produces a 200 with `index.html` rather than a 404 — an error naming neither
the route nor the proxy.

The whole backend suite takes **14m20s** and is not the inner loop. Run the
one file, then the suite once before committing.

## What must not be delegated

- Anything touching **egress**, **consent**, or the **Spine**. Those are the
  rules the product exists to keep, and a plausible-looking change to one is
  the most expensive thing that can happen here.
- `frontend/src/legacy/` is quarantined and in `.aiderignore`.
  `check-no-cloud-speech.mjs` asserts nothing live imports from it.
- Anything where a **ranking score** meets a **permission or selection**
  decision. That confusion has cost this codebase three times.
