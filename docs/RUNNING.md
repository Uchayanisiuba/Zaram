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

### Port 5173 is "held" and cannot be moved

It is held by **your own last session**, and it looks exactly like an external
process squatting on it. `strictPort: true` plus the backend's CORS allow-list
naming that exact origin makes it unmovable, so the reasonable conclusion is
that the port is the problem. It is not; the leftovers are.

This cost a whole session once. The 28 August handoff recorded *"port 5173 was
held for the whole session"* as an environmental fact, and the panel that
session shipped went unrendered because of it. The next session found the
holder was that session's own Vite — started 11 hours earlier — beside a
complete orphaned Electron tree still running its own backend on 8420.

**Check start times, not just ports.** `netstat` shows an eleven-hour-old
process and a live one identically:

```bash
netstat -ano | grep LISTENING | grep -E ":(5173|8420) "
powershell -NoProfile -Command \
  "Get-Process electron,node -EA SilentlyContinue | Select Id,ProcessName,StartTime"
```

Anything predating the session you are in is a leftover. Stop the whole tree —
Electron spawns the backend, so killing Electron alone can leave 8420 taken.
**TabbyAPI on 1234 is not yours**; leave it alone.

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

## Getting the image model

Zaram draws with **FLUX.1 [schnell]**, and ships no weights. What it needs is a
diffusers-layout pipeline directory under `backend/models/image` — the folder,
not a single `.safetensors`.

```bash
cd backend && venv/Scripts/python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('magespace/FLUX.1-schnell-bnb-nf4', local_dir=r'models/image/flux1-schnell-nf4')"
```

**13.4 GB, and no account.** That mirror is chosen over Black Forest Labs' own
upload for one reason: theirs is marked *gated*, so it needs a HuggingFace login
and a token even though the licence is Apache 2.0. Open licence, gated door. The
mirror is the same model, already quantised to NF4 — which is also why it is
13.4 GB rather than the 57.9 GB the bf16 originals would cost to quantise on
load.

Two dependencies beyond `zaram[image]`: `bitsandbytes` reads the 4-bit weights,
`sentencepiece` the T5 tokeniser. Both go in `backend/venv`.

**Expect it to be slow and to stall.** Unauthenticated downloads are rate
limited: measured 4 September 2026, the 6.69 GB transformer took 57 minutes, and
`snapshot_download` hung outright after the small files and had to be restarted
per-file. `hf_hub_download` on the two large files individually resumes and
retries; a stalled `snapshot_download` does not recover on its own.

**An interrupted download does not leave a working model, and Zaram says so.**
`model_index.json` lands in the first seconds, so a half-finished fetch looks
like a pipeline. `find_model` reads the index and checks that every component it
names has weights beside it, and the availability message distinguishes *"only
partly downloaded — it resumes where it stopped"* from *"no image model
installed"*.

---

## The local 27B on TabbyAPI, and the two keys that are not in this repository

The dev machine serves `Qwen3.8-27B` through TabbyAPI on **127.0.0.1:1234**,
where Zaram's generic OpenAI-compatible adapter finds it with no
configuration. The config that makes it behave lives in **TabbyAPI's own
`config.yml`**, not here, and on 20 September 2026 two of its keys turned
out to have been silently ignored since 3 September. Written down so the
next machine does not lose native tool calls without a warning on either side.

**The rule that bit: with `inline_model_loading: true`, a key set under
`model:` reaches an API-driven load only if it is also named in
`use_as_default`.** The startup load reads every key; an inline load — which
is every real request, since `model_name` is empty on purpose — reads only
the named ones. A key that is set but not named looks correct in the file
and changes nothing.

Two keys, both load-time, both needed:

| Key | Value | Without it |
|---|---|---|
| `reasoning` | `true` | The template opens `<think>` and the server never splits it: the monologue arrives as the answer. |
| `tool_format` | `qwen3_5` | A tool call comes back as `<tool_call>` *text* in `content`, `finish_reason: stop`, `tool_calls: null` — theroyallab/tabbyAPI #479. Zaram's text-marker fallback still works, at 61.7 s with the load against 3.4 s native. |

```yaml
model:
  model_name:
  inline_model_loading: true
  use_as_default: ["cache_mode", "cache_size", "max_seq_len", "gpu_split_auto",
                   "autosplit_reserve", "vision", "vision_offload",
                   "reasoning", "tool_format"]
  reasoning: true
  tool_format: qwen3_5
```

`tests/test_tabby_parses_the_call_it_is_sent.py` (`-m measure`) asks the
served model for one tool call and asserts it arrives as `tool_calls`, not
text — it is the check that the two keys are reaching the load. When it
fails on a fresh machine, look at `use_as_default` before anything else.
The full annotated config is backed up beside the live one as
`config.yml.bak-before-tool-format-20260920` in the TabbyAPI checkout.

---

## Running the suites

```bash
cd backend && venv/Scripts/python.exe -m pytest -q   # ~8m with the card free (4,286 tests, 20 Sep 2026); ~20m with Ollama down; run it detached
cd frontend && npx vitest run                         # ~20s
npm run test:electron                                 # from the root, no Zaram running
npm run check:all                                     # lint, types, the five guards, reachability, payload, all suites
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
