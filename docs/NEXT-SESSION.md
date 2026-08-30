# Next session — start here

A prompt and a state snapshot. Rewritten 30 August 2026 at the end of a long
session: the cross-model memory claim was measured for the first time, queue
item 6 finished, ordinary replies learned to carry the conversation, generated
documents stopped looking generated, and three defects were found by the
maintainer pressing things.

**This file is a pointer, not a second handoff.** `docs/MILESTONES.md` Current
state is the handoff and stays the authority on status; `CLAUDE.md` stays the
authority on rules. If this file disagrees with either, they win and this file
is stale — say so and fix it.

Two versions ago this file was wrong about one thing and it cost a whole job:
it listed the per-launch API secret as outstanding when it had shipped eleven
days earlier. **Check the code before starting a task a handoff hands you.**
Every entry below names files so you can check in a minute.

---

## The prompt

Paste this into a new session:

> Read `CLAUDE.md`, then `docs/MILESTONES.md` Current state, then this file.
> For anything touching voice read `docs/SPEECH.md`; before starting the app
> read `docs/RUNNING.md`, and note that launching means three processes — Vite,
> Electron, and TabbyAPI on port 1234.
>
> **That work is now committed** — reviewed against the diff first, grouped
> along file boundaries on `Zaram-V0.1`, not pushed. A test fix found on the
> way is in there too, and so is this file. The previous version of this line said nothing was
> committed and that is no longer true.
>
> Backend **2954 passing, 21 skipped, 2m32s**; frontend **362 passing, 41
> files**, `tsc` clean. Measured 30 August with Ollama up holding `bge-m3`
> and `gemma4:26b-a4b`, and TabbyAPI serving on 127.0.0.1:1234 — so the
> discovery branches really executed. `npm run lint` is broken and was
> already broken: eslint cannot resolve `react-hooks/exhaustive-deps`, which
> takes `check:all` down with it.
>
> **One number does not reconcile and is worth a minute of yours.** The last
> handoff recorded 2959 passing / 16 skipped; this is 2954 / 21, the same
> total of 2975. The raw difference was six — one of those was found and
> fixed, see below, leaving **five tests that ran then and skip now**, still
> unaccounted for.
> Every skip is environment-gated and the gates are: `test_recall_at_scale`
> (9, `ZARAM_SCALE_EVAL=1`), `voice/test_kokoro_onnx_backend` (7, wants
> `onnxruntime`, `onnx` and `misaki` — `onnx` is missing on this machine),
> `test_identity_holds_across_models` and `test_extraction_across_models`
> (3, `ZARAM_LIVE_MODELS=1`), `test_memory_traffic_review` (2, no memory
> runtime in-process). One run with those named should settle it. A stable
> count nobody can explain is how a broken instrument survives, and this
> project has already paid for that twice.
>
> What is left, in the order I would take it:
>
> 1. **The model-pull executor** — half built, and it is the piece that fixes
>    the maintainer's own machine. `providers/models.manifest.json` and
>    `providers/model_manifest.py` landed; the endpoint, the progress UI and
>    the offer beside Settings' "too large for this machine" warning did not.
>    One decision is waiting for the maintainer, below.
> 2. **Phase 0 / packaging** — `CLAUDE.md` still says this is the actual
>    blocker, and the Ollama question below decides what it means.
> 3. **Gemini** — untouched, still an afternoon. `ProviderEntry.chat_endpoint`
>    holds the correct URL and is read nowhere.
> 4. **The desktop decision** — untouched, an architecture call. Do not start
>    it without the maintainer.
>
> **One thing was built and has not been seen working**, and it is the most
> valuable thing in the product: the ambient surface's Electron half. Details
> below with the exact conditions. This project has paid twice for shipping a
> feature whose tests passed and whose eyes never moved.
>
> Read the Ollama question below too. It is not a task, and it changes what
> Phase 0 means.

---

## What happened last session

The through-line: **five complete, tested subsystems could not be reached from
the interface**, and every one was found by connecting something real to it.

**The cross-model memory claim had never been measured.** It is what the
product is for, and the pieces were each covered separately while the property
joining them was not. Now measured live in both directions — a fact told to
TabbyAPI/Qwen was recalled and cited by Ollama/gemma4 at relevance 0.821 in a
different session, and back the other way at 0.779; deleting it changed the
answer. `test_memory_holds_across_providers.py`, 10 cases.

**Ordinary replies could not follow up.** *"What is the capital of Portugal?"*
→ *"Lisbon."* → *"And roughly how many people live there?"* → *"I don't have
the place you're referring to."* One model, one session, seconds apart. The
turn buffer, the transcript rehydration, the window-fitting and the renderer
all existed; the only caller was the *document* branch. Fixed, and verified
across a provider switch.

**The reply could not be stopped.** `chatStore.cancel()` had no UI caller.

**Word output ignored the design.** The `.docx` was rebuilt block by block
against `python-docx`'s 2007 template — Calibri, Word-blue headings, 1.25 inch
margins, a box around every table cell — while the HTML carried a considered
A4 stylesheet. Both renderers now read `artifacts/theme.py`.

**A CV had no kind**, so "write my CV" got a proposal's layout with somebody's
career inside it.

And the search offer built mid-session shipped **as a refusal with no remedy** —
see the two mistakes below.

### A test that had never run, found while accounting for a skip

Not from the last session's work — it is older than that, and it was found by
refusing to accept a skip count that did not reconcile.

`test_vision_gate.py` reported *"no Ollama models installed"* on a machine
holding two. `ProviderManager.refresh` is a coroutine and was called bare, so
discovery never ran; and `ProviderManager()` builds an **empty**
`ProviderRegistry`, so even awaited there was nothing to scan — the real path
registers `OllamaAdapter` in `providers/runtime.py`. Both failures produce an
empty model list, and `if not local: pytest.skip(...)` read that as a fact
about the hardware.

So a check whose own docstring says it exists because *"`supports_vision`
could be correct in every fixture and still be `False` for every real model"*
had never executed a single assertion, and its claim to have caught exactly
that on first run cannot be true.

The two assertions underneath were worthless anyway: `any(x) or all(not x)` is
a tautology. Replaced with the real contract — each model's `supports_vision`
against Ollama's own `/api/show` capabilities, which is the enrichment that
does the work, since `/api/tags` does not report vision at all. Both
polarities are exercised on this machine. Verified by inverting the assertion
and watching it fail.

The capability was fine. The instrument was broken, and it was broken quietly.

### Three mistakes of mine, all instructive

**I shipped a refusal with no remedy, one day after reading about the last
one.** The search offer turned web search on and granted the destination
nothing, so the search was refused by default-deny and the reply said the web
had returned no results. Rule 7j is explicit that requiring a second host rule
*"asks the same question twice and reads as the product being broken"*. Found
by the maintainer on the first press.

**A test of mine passed against deliberately broken code — again.** The
reference-document case went green with the outline read from the excerpt,
because the excerpt happened to contain the headings. The **fixture** was
rewritten, not the assertion.

**I left a component stuck in a working state.** The notice card sat on
"Turning it on…" for the rest of the session because its phase was never reset
on success. Notices are not persisted, so the stale card was a live component
and a reload was the user's only escape.

---

## Not seen working, and how to see it

**The ambient surface's Electron half.** `electron/native/ambient.js` and
`globalShortcuts.js` are built and wired in `electron/main.js`, and
`CLAUDE.md` calls this the highest-leverage item on the whole daily-driver
list. The **renderer** was verified: `http://localhost:5173/ambient.html` in
the Browser pane answered *"Name the capital of Portugal in one word."* with
**Lisbon**, from TabbyAPI on loopback, with the egress line reading *"Local ·
cloud ready — Answers are running on this machine."*

What was **not** checked, and cannot be from a browser tab: the global
accelerator registering (`CommandOrControl+Shift+Space` by default), the panel
appearing over another application, and the screen-edge handle. That needs
`docs/RUNNING.md`'s real launch — Vite, then Electron, with no backend started
by hand. **If it works, the most valuable feature in the product is already
shipped and nobody knows.**

Two earlier items are now seen: the Advanced model field and the Activity
images row both rendered in the browser-tab route, screenshotted.

---

## What is left

### 1. The model-pull executor — half built

**The problem it solves is the maintainer's own machine.** The only chat model
installed is 18.2 GB against a ~9.1 GB resident budget, so every reply runs
half on the processor — `CLAUDE.md`'s whole speed thesis, inverted. Settings
warns correctly and can offer nothing, because `FirstRunPanel` still greys out
"pull a model": there is no executor.

Landed: `providers/models.manifest.json` — dated, VRAM-tiered, sizes marked
approximate — and `providers/model_manifest.py`, which recommends against a
measured budget, treats `None` as "unmeasurable, take the smallest tier",
never fails closed, and carries `smaller_than` for the *"your model does not
fit"* case.

Not built: `POST /models/pull` streaming Ollama's progress, `GET
/models/recommended`, the progress UI, and the offer attached to the oversized
warning. `readiness.py` already models the offer shape (`OfferKind.PULL_MODEL`,
`SMALLEST_CHAT_MODEL`, a real byte count) — reuse it rather than inventing a
second vocabulary.

> **One decision is waiting for the maintainer, and it should not be made
> unilaterally.** Ollama downloads the model over **its own socket**, so
> `EgressGate` cannot see it and Activity will not show it — the same blind
> spot the local-proxy idea was rejected for. The proposal is one egress-log
> entry marked as a *delegated* download, naming the registry host and the
> size, rather than letting a download Zaram initiated leave no trace.
> `EgressLog.append` already takes a `kind`, and `KIND_REQUEST` is what the
> counts filter on, so a new kind would not pollute "what Zaram sent". Ask
> before building it either way.

### 2. Phase 0 — still the actual blocker

Unchanged from the last two handoffs, and now with a second half: the free-tier
key path is real, the model-pull path is not. Read `canBeCarriedOut` in
`FirstRunPanel.tsx` — that function is where each offer is admitted and its
docstring says why nothing may be invented there.

PDF belongs here too. `pip install weasyprint` now succeeds in the backend
venv; the GTK native libraries are what is missing, which on Windows means
MSYS2. **Whether the installer bundles them is a packaging decision**, and it
is the difference between a designed PDF and a Word file being the only
output anyone sees.

### 3. Gemini — unchanged, still an afternoon

`catalogue.py` grades it correctly and separates it from Anthropic, which is a
genuinely different wire format. Gemini speaks the dialect Zaram speaks; its
address does not fit the `<root>/v1/...` pattern both halves of the cloud path
assume. `ProviderEntry.chat_endpoint` holds the exact correct URL, appears nine
times in `catalogue.py` and **is read nowhere**. Honour it in the engine, relax
the discoverer, pin the URL with a test. The local Node proxy is still refused —
`is_local()` returns true for localhost, so the gate would record nothing.

### 4. Does the desktop runtime keep a backend-facing half?

Unchanged. `callBackendChat` and `VoiceRuntime` remain, uncredentialed and
unreachable, and `ExecutiveRuntime` feeds the orb's presence snapshot, so the
planning half and the presence half must be separated before anything is
removed. A decision, not a task.

### Found and not fixed

* **A client stop may not stop the backend.** The abort closes the stream; the
  next reply was unusually slow, consistent with the abandoned generation still
  holding the card. Unmeasured.
* **The two intent classifiers disagree about a document request.** A bare
  `IntentPlanner` reads *"Write that up as a proposal document"* as
  `CONVERSATION`, while the semantic router the backend boots read *"Now add
  ten to that number"* as a document request and silently wrote a `.docx`.
* **The embedder fallback is silent, and it is the worst place for it.**
  Without Ollama, `bootstrapper.py` drops to the hash backend and recall runs
  on keyword overlap with nothing said. Measured: a question matching a stored
  fact word-for-word scores **0.064** against a shipped floor of **0.42**. A
  stranger with no Ollama gets working chat and a Spine that retrieves nothing.
  `CLAUDE.md`: *"Disabled capabilities are visible, not silent."*
* **`npm run lint` is broken** — eslint cannot resolve
  `react-hooks/exhaustive-deps`. Pre-existing, one line, two possible fixes
  that are not equivalent.
* **Favicons on citations** were asked for and declined for now; the honest
  build route is recorded in the MILESTONES entry if it is ever wanted.

---

## The Ollama question — sharpened, 30 August

*Does a user need Ollama?* Three questions hide in that one:

* **Running a local model — no.** Any OpenAI-compatible local server is
  discovered and used. TabbyAPI answered every question this session on
  127.0.0.1:1234 as `lm_studio`, `local_ai_server`, `never_leaves_device`.
* **Installing a model from inside Zaram — there is no path at all today**, and
  the executor above uses Ollama's `/api/pull`, so building it that way makes
  Ollama required for that one job.
* **Recall — yes, and silently.** See the embedder note above.

**Bundling Ollama: still no.** It is a *product* — a background service that
claims port 11434 and updates itself — not a library, and larger than Docling,
which was refused at 321 MB.

> **`llama-server` closes all three at once.** One MIT binary spawned as a
> child process, Zaram picks the port, it exits when Zaram exits; it can serve
> a GGUF chat model *and* the embedder, and Zaram can fetch a model file
> without asking anyone to install a second product. Ship the CPU build; GPU as
> an opt-in download **with the size named**, the `zaram[ingest]` precedent.

A Phase 0 decision, not a task. Nothing has been changed on it.

---

## Running it for a visual check

`docs/RUNNING.md` is the authority, and it carries the leftover-process trap.
Three things learned this session that are about the agent's tools rather than
the product:

* **The browser-tab route works and is much cheaper than Electron.** Start the
  backend with `ZARAM_API_SECRET=dev-secret` and a scratch `ZARAM_DATA_DIR`,
  then Vite with the same secret. There is a `zaram-frontend` entry in
  `.claude/launch.json` that does the Vite half.
* **An emulated viewport can hide the whole conversation panel.** Twenty
  minutes went on an orb that appeared not to open the chat; the chat *was*
  open, letterboxed off-screen by a 1440×900 emulation in an 800px pane.
  Reset to the desktop preset before concluding a control is dead.
* **Synthetic clicks do not always reach framer-motion elements.** Real
  `computer` clicks did; `javascript_tool`-dispatched ones did not, on the orb.
  **Say which you used** — a JS-dispatched click is weaker evidence.

---

## Machine state

* Ollama holds `gemma4:26b-a4b-it-q4_K_M` (18.2 GB) and `bge-m3`. The chat
  model **does not fit** the ~9.1 GB budget, so every reply is slow — about
  **3m20s** for a short question, measured this session.
* TabbyAPI serves `Qwen3.8-27B-exl3-2.20bpw` on 127.0.0.1:1234, ~6–9s for a
  short reply when it has the card to itself. Start it with
  `C:\Users\user\tabbyapi-env\Scripts\python.exe main.py` from
  `C:\Users\user\tabbyAPI` — **not** `start.bat`, which would create a second
  venv and reinstall everything.
* **Running both at once is what makes either slow.** With gemma4 resident,
  TabbyAPI timed out at 120s on a question it normally answers in seconds.
  `curl http://127.0.0.1:11434/api/generate -d '{"model":"...","keep_alive":0}'`
  unloads Ollama's copy.
* The scratch Spine from this session is under the session scratchpad, holding
  the Harbour Lane and Northwind facts and the search grants. The **real**
  Spine was never touched.
* `duckduckgo.com` now has an `allow` rule in the scratch policy, created by
  the search offer. The real machine's policy is unchanged.
* **Say which environment you measured in.** The backend suite ran 3m31s with
  the GPU idle and 9m43s with models contending — same suite, same commit.
