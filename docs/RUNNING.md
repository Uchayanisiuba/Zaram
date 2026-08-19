# Running Zaram in development

How to start the real product on a developer machine, and the four ways it
fails to start that look like something else. Written 19 August 2026 after each
one cost time in the same session.

---

## The short version

Two processes, in this order:

```bash
# 1. The renderer. Must be listening before Electron loads it.
cd frontend && npx vite --port 5173 --strictPort

# 2. The app. From the repo root.
env -u ELECTRON_RUN_AS_NODE \
    ZARAM_PYTHON="C:/Zaram/backend/venv/Scripts/python.exe" \
    node_modules/.bin/electron electron/main.js
```

Electron spawns the backend itself, mints this launch's API secret, and hands
it to the renderer over IPC. **Do not start a backend by hand as well** — port
8420 will already be taken, and the one you started will not have the secret.

---

## The traps, in the order they bite

### `npm run dev:desktop` launches the wrong tree

There are **two** Electron mains in this repository:

| Path | Status |
|---|---|
| `electron/main.js` | **The one that ships.** `electron-builder.yml` sets `"main": "electron/main.js"` via `extraMetadata`. `test/*.test.js` requires its modules and asserts them in isolation; `bootstrap.test.js` spawns the real binary when a desktop session exists, and says what is unproven rather than going red when one does not. |
| `desktop/src/main/index.ts` | A parallel TypeScript tree with its own `electron-builder.json`. `npm run dev:desktop` runs this one. |

Nothing has reconciled them. Until something does, launch `electron/main.js`
directly and treat `desktop/` as unverified. **This is a triage decision
somebody has to make** — it is the same shape as the fifteen unreachable
subsystems, only larger, and `check:reachability` cannot see it because both
trees are internally consistent.

### `ELECTRON_RUN_AS_NODE` is set inside a VSCode terminal

Symptom:

```
TypeError: Cannot read properties of undefined (reading 'isPackaged')
    at Object.<anonymous> (C:\Zaram\electron\main.js:23:20)
```

`app` is undefined because Electron ran `main.js` as a plain Node script. The
variable is set by VSCode's own Electron host and inherited by every terminal
it opens. `desktop/start-electron.js` already deletes it for exactly this
reason; a direct launch has to do the same with `env -u`.

It is not a code bug and there is nothing to fix in the app — but the error
names a line in `main.js`, so it reads like one.

**Delete the variable, never blank it.** Electron tests for its *presence*, so
`ELECTRON_RUN_AS_NODE=''` still re-execs as plain Node. `test/bootstrap.test.js`
already carries this reasoning, and it is where the trap was first written
down.

### There are two virtualenvs, and the launcher picks the other one

`electron/backend/backendLauncher.js` resolves in the order **`ZARAM_PYTHON` →
bundled runtime → `backend/.venv` → `../.venv`**, with `cwd` the backend
directory. This repository's working virtualenv is `backend/venv`, which
matches none of them.

**It does not follow that the launcher finds nothing, and the first version of
this section said it did.** `../.venv` is `C:\Zaram\.venv`, and that directory
**exists** — a second, complete environment: fastapi, uvicorn, kokoro, torch,
spaCy. So an unset `ZARAM_PYTHON` does not fail; it silently starts a
*different* interpreter, which is the failure mode this file's own PATH
argument warns about, arriving by the route nobody was watching.

Measured by diffing the two: they were identical but for the mic extra — `av`,
`ctranslate2`, `faster-whisper`, `onnxruntime` were in the root `.venv` and
absent from `backend/venv`. So which one launched decided whether Zaram could
**listen**, and `ZARAM_PYTHON` as documented above pointed at the half that
could not. Both now carry the mic extra, which closes the symptom and leaves
the cause: two interpreters that can drift again the next time either is
touched. **Reconciling them is a triage decision**, the same shape as the two
Electron trees above.

**PATH is deliberately not a fallback**, and that is right: finding *some*
Python on a stranger's machine is worse than finding none, because it will be
the wrong one and the failure arrives later disguised as a broken product. The
lesson here is that the same sentence applies to finding the wrong *venv*.

The same `.venv` / `venv` mismatch has already cost this repository 376 MB in
an installer exclusion that never matched. Worth fixing in one place rather
than documenting twice.

### A browser tab at `localhost:5173` reports "Zaram engine not running"

**Correctly.** It has no desktop host to ask for the secret, and the value Vite
baked in at boot is stale the moment Electron mints a new one. Test in the
Electron window.

If you must use a browser tab — for Playwright, say — start the backend
yourself with a known secret and give Vite the same one:

```bash
cd backend && ZARAM_API_SECRET=dev-secret ZARAM_DATA_DIR=/some/scratch \
  venv/Scripts/python.exe main.py
cd frontend && ZARAM_API_SECRET=dev-secret npx vite --port 5173 --strictPort
```

`ZARAM_DATA_DIR` is what keeps a test run away from your real Spine, egress log
and settings. Use it for anything that writes.

---

## Verifying it actually started

* `curl http://127.0.0.1:8420/health` from another shell returns **401**. That
  is success: the per-launch secret is being enforced and you do not have it.
  A 200 would mean the guard is off.
* The Electron log shows `Health check result: OK current state: available` and
  the renderer's own `GET /egress/pending 200`.
* Logs are at `app.getPath('userData')/logs/desktop.log`, and the backend's
  stdout is forwarded into it under scope `main:backend`.

---

## Running the suites

```bash
cd backend && venv/Scripts/python.exe -m pytest -q   # ~3m with Ollama up, ~20m down
cd frontend && npx vitest run                         # ~20s
npm run test:electron                                 # from the root, no Zaram running
npm run check:all                                     # lint, types, guards, reachability, all suites
```

**Say which condition you measured in.** With Ollama running the backend suite
takes roughly 3–4 minutes; with it down, roughly 20, because every provider
probe waits for a timeout — and it executes *different code*. A crash that
stopped the backend booting hid for two weeks behind a green suite because its
branch only runs when models are discovered and every one is unselectable:
never with Ollama up, always on a stranger's machine.

**Run the Electron suite with no Zaram running.** `electron/main.js` takes a
single-instance lock, so two bootstrap tests spawn an instance that quits
instantly and asserts against an empty log. It looks like a regression and is
not.

---

## Driving the UI for a visual check

Playwright is a devDependency, but **its browsers are not downloaded**. Use the
system Edge rather than spending 150 MB:

```js
const browser = await chromium.launch({ channel: 'msedge' });
```

Scripts living outside `frontend/` cannot resolve `playwright` by name; use
`createRequire('C:/Zaram/frontend/package.json')`.

For anything involving audio, launch with
`--autoplay-policy=no-user-gesture-required`, and **prove playback rather than
assuming it** — patch `HTMLMediaElement.prototype.play` in an init script and
watch `currentTime` advance. A silent failure and a working one look identical
from the outside, and this is precisely how a lip sync bug survived a green
test suite.
