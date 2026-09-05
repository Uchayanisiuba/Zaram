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

`qwen3-14b-8k` is capped at **8192 tokens** by its Modelfile — `num_ctx 8192`,
against a trained 40960. Aider has no partial-file mode: a file it edits is
sent whole. So the window is a hard gate on which files are reachable at all.

| file | ~tokens | verdict |
|---|---|---|
| `backend/core/readiness.py` | 2,100 | fits, room to work |
| `backend/providers/model_manifest.py` | 1,700 | fits, room to work |
| `backend/runtimes/mcp/config.py` | 2,100 | fits, room to work |
| `frontend/src/components/firstrun/FirstRunPanel.tsx` | 2,300 | fits, room to work |
| `backend/runtimes/mcp/runtime.py` | 3,500 | fits once — tight |
| `frontend/src/components/chat/ChatSurface.tsx` | 15,000 | **out of reach** |
| `frontend/src/workspaces/SettingsWorkspace.tsx` | 16,700 | **out of reach** |
| `backend/main.py` | 54,600 | **out of reach — 6.6× the window** |

`main.py` is 5,143 lines. No edit format and no prompt gets around a file that
does not fit in the window once. **Do not point Aider at it.** The structural
fix is extracting routers — `app.include_router` is already the pattern at
`main.py:193` — and that is worth doing on its own merits, not only for this.

Raising `num_ctx` does not rescue `main.py` either: 54,600 tokens of KV cache
for a 14B model does not fit in 12 GB beside the weights. A smaller model with
a much larger window would reach further, and is the change to make if Aider
needs to touch the big files.

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
