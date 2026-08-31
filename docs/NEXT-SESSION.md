# Next session — start here

A prompt and a state snapshot. Rewritten 31 August 2026. The previous session's
work was reviewed and committed, and then a single defect — Zaram looked for
models exactly once, at boot — cost most of a day because it was diagnosed as
four separate problems before it was seen as one.

**This file is a pointer, not a second handoff.** `docs/MILESTONES.md` Current
state is the handoff and stays the authority on status; `CLAUDE.md` stays the
authority on rules. If this file disagrees with either, they win and this file
is stale — say so and fix it.

---

## The prompt

Paste this into a new session:

> Read `CLAUDE.md`, then `docs/MILESTONES.md` Current state, then this file.
> For anything touching voice read `docs/SPEECH.md`; before starting the app
> read `docs/RUNNING.md`.
>
> **Everything is committed.** Seven commits on `Zaram-V0.1`, not pushed.
> Backend **2958 passing, 23 skipped**; frontend **388 passing across 43
> files**, `tsc` clean. `npm run lint` is broken and was already broken —
> eslint cannot resolve `react-hooks/exhaustive-deps`.
>
> **The machine changed and the numbers below are measured, not estimated.**
> The chat model is now `qwen3-14b-8k` on Ollama at **31.6 tok/s**. Read the
> machine state section before assuming anything about VRAM.
>
> What is left, in the order I would take it:
>
> 1. **The residency gate is over-conservative and it is now visibly wrong.**
>    `/providers/models` reports `fits_resident: false` for `qwen3-14b-8k`,
>    which measurably runs at 10.32 GB beside a 0.66 GB embedder on a 12 GB
>    card. It fits. The gate double-counts: it reserves 20% of VRAM for KV
>    cache *and* the model's own `num_ctx` already bounds that cache. Every
>    chat model on this machine now reads `fits=false`, so auto-routing has an
>    empty candidate set and only an explicit pin works.
> 2. **The residency relaxation is vision-only.** `select_model_for_task`
>    relaxes the fit filter when `requires_vision` empties the field, and does
>    not when residency alone empties it — so Zaram refuses rather than
>    answering slowly. `CLAUDE.md`: *"VRAM limits route a task; they do not
>    reject a vertical… warn, never block."* Together with (1) this is why the
>    product said "No model was selected" on a machine with three chat models
>    installed.
> 3. **`lm_studio` is a lie in the interface.** Zaram labels any
>    OpenAI-compatible server on 127.0.0.1:1234 as `lm_studio`. The maintainer
>    runs TabbyAPI there, so the picker named a product they do not have, and
>    that single mislabel cost a long and angry detour. Report the port, or ask
>    the server what it is; never guess the product.
> 4. **The model-pull executor** — unchanged, still half built.
>    `providers/model_manifest.py` and `models.manifest.json` are committed and
>    still have **no caller and no tests**.
> 5. **Phase 0 / packaging** — still the actual blocker, unchanged.
>
> **Do not delete the TabbyAPI model.** The maintainer asked for it and it was
> deliberately not done — see "Held, deliberately" below.

---

## What happened

**The previous session's 38 uncommitted files were reviewed and committed** in
ten commits before anything was built on them. Reading the diff found nothing
wrong with it; reconciling its *skip count* found a test that had never run
(`test_vision_gate.py` — `refresh` is a coroutine called bare, and
`ProviderManager()` builds an empty registry, so it could discover nothing by
construction and reported "no Ollama models installed" on a machine holding
two).

**Then one defect wore four costumes.** The maintainer said a model was
missing. It was diagnosed, in order, as: a stopped server, a hardcoded model
name, an empty candidate set, and a mislabelled provider. Three of those were
real and got fixed. But the actual cause was:

> `ensure_scanned()` sets a flag on its first call. Discovery ran once per
> backend process and never again, so any inference server started *after*
> Zaram was invisible until Zaram itself restarted.

Measured: TabbyAPI serving a model, confirmed answering, while
`/providers/models` returned only what was found at boot. **From outside, "Zaram
lost my model" and "Zaram has not looked since it started" are the same
picture** — and the first is what a person concludes.

`POST /providers/rescan` fixes it, with the offer in the model panel where the
doubt occurs. `CLAUDE.md` had specified this and named it — *"Re-runnable from
Settings as re-scan"* — and it had never been built.

### What shipped

* **The routing chip** beside the composer: mode, plus separate **On this
  machine** and **Cloud** model lists, each model naming its data policy and,
  where it will not fit, the numbers. Both decisions previously lived in
  Settings alone — six actions and a context switch to keep one question local.
* **"Ask another"** under a reply, which makes `chosenBy: 'request'` reachable
  for the first time: the per-message model path was complete end to end with
  no caller.
* **The hardcoded `gemma3:latest`** removed from `OllamaEngine` — the fourth
  instance of a class this repo had documented three times. The test now scans
  every engine module and fails on *any* model name written into source.
* **Escape** no longer closes the conversation behind a popover.

### Three mistakes of mine, all instructive

**I answered "it's down" twice instead of testing.** When the maintainer first
said their model was missing, the whole diagnosis was two steps — start the
server, see whether Zaram lists it — and I asserted the first step's
conclusion without doing the second. That turned a two-minute finding into
hours.

**I estimated a fit from a file size.** I recommended `qwen3:14b` as "~9 GB,
fits" from its download size. Its resident size at Ollama's default context is
**12.18 GB** — 97% of a 12 GB card, with no room for the embedder. `CLAUDE.md`
warns about exactly this substitution and the provider layer makes the same one
in code. The fix was `num_ctx 8192`, which brings it to 10.32 GB; the lesson is
that a download size is not a residency measurement and must never be quoted as
one.

**I let a diagnosis sprawl into product strategy.** Several long answers about
agents, MCP and packaging were interleaved with an active bug hunt. They were
not wrong, and they were not what was being asked for.

---

## Machine state — measured 31 August 2026

Ollama holds:

| model | disk | resident | note |
|---|---|---|---|
| `qwen3-14b-8k` | 9.3 GB | **10.32 GB** | `num_ctx 8192`. **31.6 tok/s warm.** The daily driver. |
| `qwen3:14b` | 9.3 GB | 12.18 GB | Ollama's default context. Spills; 12.6 tok/s. Kept as the base layer. |
| `gemma4:26b-a4b-it-q4_K_M` | 18.0 GB | — | Does not fit. ~3m20s per short reply. **The only model here that can read images.** |
| `bge-m3` | 1.2 GB | 0.66 GB | Embeddings. Must stay resident for recall. |

`qwen3-14b-8k` was created with a two-line Modelfile over `qwen3:14b`; it
re-uses the same blobs, so it cost no download.

**TabbyAPI is not running** and its `Qwen3.8-27B-exl3-2.20bpw` is untouched on
disk. Start it from `C:\Users\user\tabbyAPI` with
`C:\Users\user\tabbyapi-env\Scripts\python.exe main.py` — **not** `start.bat`.

**Running Ollama and TabbyAPI together is what makes either slow.** Neither
knows the other's VRAM.

Zaram's settings, in the **scratch** data dir under the session scratchpad:
`routing_preference: prefer_local`, `default_model: qwen3-14b-8k:latest`. The
real Spine was never touched this session.

### Held, deliberately

**The TabbyAPI model was asked to be deleted and was not.** Two reasons, both
of which should be put to the maintainer again rather than assumed away: it is
a large, irreversible delete, and the comparison that would justify it had not
been run. It is also the only remaining exl3 model, so removing it removes the
option entirely.

The honest technical position: `qwen3-14b-8k` at Q4_K_M stores each weight at
roughly twice the precision of a 2.20bpw quant, and quality falls off sharply
below about 3 bits — so a 14B here very likely matches or beats that 27B. That
is a prediction, not a measurement, and it should be tested before anything is
deleted.

---

## Running it

`docs/RUNNING.md` is the authority. The browser-tab route:

```bash
cd backend && ZARAM_API_SECRET=dev-secret ZARAM_DATA_DIR=/some/scratch \
  ../.venv/Scripts/python.exe main.py
```

then the `zaram-frontend` entry in `.claude/launch.json` for Vite.

The API credential header is **`X-Zaram-Auth`**. `X-Zaram-Client` is a label
and is enforced nowhere.

Three tool traps, all paid for this session: an emulated viewport can push the
whole conversation panel off-screen — reset to the desktop preset before
concluding a control is dead; real `computer` clicks reach framer-motion
elements where JS-dispatched ones do not, so **say which you used**; and a
`grep` across the repo hits `backend/venv` and takes minutes — scope it or use
the Grep tool.
