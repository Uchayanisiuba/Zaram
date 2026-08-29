# Next session — start here

A prompt and a state snapshot. Rewritten 29 August 2026 at the end of the
session that deleted three dead subsystems, gave rule 7j its second dimension,
and made the first-run cloud key real.

**This file is a pointer, not a second handoff.** `docs/MILESTONES.md` Current
state is the handoff and stays the authority on status; `CLAUDE.md` stays the
authority on rules. If this file disagrees with either, they win and this file
is stale — say so and fix it.

The version before last was wrong about one thing and it cost a whole job: it
listed the per-launch API secret as outstanding when it had shipped eleven days
earlier. **Check the code before starting a task a handoff hands you.** Every
entry below names files so you can check in a minute.

---

## The prompt

Paste this into a new session:

> Read `CLAUDE.md`, then `docs/MILESTONES.md` Current state, then this file.
> For anything touching voice read `docs/SPEECH.md`; before starting the app
> read `docs/RUNNING.md`, and note that launching means three processes — Vite,
> Electron, and TabbyAPI on port 1234.
>
> **Everything from the last session is committed** (`Zaram-V0.1`). Backend
> 2873 passing, frontend 331, `tsc` clean, guards clean.
>
> **The seven-item queue is finished.** What is left is four things, and only
> one of them is a plain build:
>
> 1. **The Advanced type-in model field** — item 6's last piece. Its hardest
>    condition already shipped: a name Zaram cannot place is refused before
>    dispatch instead of falling through to Ollama. What remains is the field
>    itself and the sentence beside it. **Take this one if you want to build.**
> 2. **Gemini** — investigated last session and smaller than the deck says.
>    `ProviderEntry.chat_endpoint` already holds the exact URL and **is read
>    nowhere**. An afternoon, not an integration. Details below.
> 3. **The desktop decision** — an architecture call rather than a task. Do not
>    start it without the maintainer.
> 4. **Phase 0 / packaging** — `CLAUDE.md` says this is the actual blocker, and
>    with the free-tier key path now real it is the next big piece.
>
> **Two things were built and have not been seen on screen.** Both are named
> below with the exact conditions to reach them. This project has paid once for
> shipping a feature whose tests passed and whose eyes never moved; do not add
> a third.
>
> Read the Ollama question below too. It is not a task, and it changes what
> Phase 0 means.

---

## What happened last session

Nine commits. The through-line is worth stating because it decided what got
built: **three separate things existed, were tested, and could not work**, and
each was found by connecting something real to it rather than by reading it.

**The second entrance to inference is gone.** `POST /vision/analyze` reached
`OllamaEngine.stream_vision_response`, which by its own docstring bypassed
routing *and the egress gate*, against a hardcoded `qwen2.5vl:7b` nobody had
installed. Three things were true of it that the route table could not show:
its only caller sent no credential and had been getting 401 since the secret
shipped; it called `_parse_legacy_sse`, which is defined nowhere; and nothing
tested it. Deleted rather than repaired.

> The deletion had a trap in it. `IntentPlanner` still emits a `vision.*` step
> on a keyword when nothing is attached, and the dispatcher's vision branch was
> the only thing catching it. Removing that branch would have let the step fall
> through to generation, and a model asked to describe a picture nobody
> supplied writes a confident description of nothing. **Deleting a side door
> into a rule 9 failure would have been a poor trade.**

**`backend/orchestrator/` is gone** — 1,261 lines, zero importers, and the
merged "can see = can draw" scorer plus a ranker that treated a missing
*required* capability as a warning. `CLAUDE.md` had said to delete it for
weeks while three files carried prose warning about it. A warning about a
loaded gun is worth less than removing it.

**Two more desktop capability packs** went the same way as the vision one:
uncredentialed, unreachable, duplicating paths that work. What is left of that
audit is a decision, not a cleanup — see below.

**Rule 7j got its second dimension.** `EgressPolicy` was keyed on host alone,
so "you connected this provider for chat" silently read as permission to send
it anything. It is now keyed `(host, DataClass)` with one asymmetry: a plain
host rule covers `PROMPT` and nothing else. That unblocked cloud vision, which
had been finished and refused one consent question short of working.

**First run can store a cloud key.** `FirstRunPanel` had been greying that
offer out since it was built; `CloudKeyForm` is its executor, and it went first
because `POST /providers/cloud` already existed and takes effect without a
restart.

**A name Zaram cannot place is refused before dispatch** — the third door the
last handoff predicted. It used to fall through to Ollama and report
`model 'anthropic/claude-sonnet-4.5' not found` against a server the user never
named. The safety was never wrong; the sentence was.

### Two mistakes of mine, both instructive

**A test of mine passed against deliberately broken code.** The no-socket
fixture *raised*, the engine caught it in its "could not reach the provider"
handler, and the resulting `[ERROR]` line named the host — which is exactly
what the test checked for. A network failure and a refusal had become
indistinguishable to the test. It records attempts now instead of raising.
**Falsify a new guard before keeping it**; this one would have been decorative.

**I shipped a refusal with no remedy.** The policy started refusing images to a
chat-approved host, correctly and with a message naming the missing decision —
while `PUT /egress/policy` took a host and a mode and nothing else, so there
was no way in the product to make that decision. Wiring the pane afterwards
also exposed that a host `DENY` did not beat a standing image grant, so the
"cut everything" control would have left a destination able to receive
photographs. **Both were at the seam, and neither was visible until something
real was connected.**

---

## Not seen on screen, and how to see them

Two pieces shipped tested and unwitnessed. The VRM-gaze precedent is the
reason this section exists: the maths had unit tests, the rig was confirmed,
and the fringe covered the eyes.

**The first-run cloud key form.** Reaching it needs `can_chat: false`, and this
machine has Ollama with models, so it cannot be got to without breaking the
local setup. To verify: **empty `ZARAM_DATA_DIR`, Ollama stopped**, open the
conversation. The panel should stand where the composer does with a live key
offer under it; choosing it opens the form in place.

**The Activity images row.** Under each destination's mode buttons, shown only
once that destination has a rule. To verify: connect any provider, send one
message so the host appears, then look for the `images` line.

---

## What is left

### 1. The Advanced type-in model field — the last of queue item 6

**Agreed in principle, one third built.** A dropdown cannot hold OpenRouter's
catalogue, so a person must be able to type a name. Three conditions, and the
first one shipped last session:

* **It must resolve before sending — DONE.** `_unplaceable_model_refusal` in
  `main.py` refuses a name the catalogue cannot place, before dispatch, with a
  sentence that names the model and says what to do.
  `tests/test_a_model_nobody_can_place.py`, 14 cases, two of them driving
  `POST /chat` to prove it is wired rather than merely written. Every
  uncertainty resolves to *no refusal* — no provider layer, an empty
  catalogue, a lookup that raised all proceed, because a guard built on our own
  missing bookkeeping would fire hardest on the first message after a boot.
* **It must state the data policy while the user is choosing.** Not built.
  `selectable_by_default` stops *Zaram* picking a `:free` model and must never
  stop the *user* picking one knowingly — the line between a consent gate and a
  paternalism gate. `CloudKeyForm.tsx` already does exactly this with the
  catalogue's `note`; copy its shape, and read its tests, which assert the
  words *connected*, *verified*, *valid* and *working* never appear.
* **A typed name widens nothing.** Same rule as a tool description: nothing
  supplied from outside may enlarge what is permitted. The refusal above is
  most of this already — an unknown name reaches nothing — but the field must
  not, for example, imply a host rule.

Where it goes: **Settings, behind Advanced.** `CLAUDE.md`'s three tiers put
per-task assignment there so a non-technical user never meets it.

### 2. Gemini — smaller than it looks, and the deck oversells the problem

**Investigated last session, not started.** `catalogue.py` already grades this
correctly and separates it from the harder cases:

* Anthropic is genuinely a different wire format (`/v1/messages`, `x-api-key`)
  and needs an adapter that does not exist.
* **Gemini is not.** Its OpenAI-compatible root ends in `/openai` with the chat
  path hanging directly off it, and both halves of Zaram's cloud path assume
  `<root>/v1/...` — `OpenAICompatibleEngine._normalise` appends `/v1`, and
  `openai_compat.py` strips and re-adds it. So a Gemini root is sent to
  `.../openai/v1/chat/completions`, which is not where it listens. The
  catalogue's own words: *"The wire format is fine; the assumption is not."*

**The fix is half-built already.** `ProviderEntry.chat_endpoint` exists,
carries the exact correct Gemini URL, and appears **nine times in
`catalogue.py` and nowhere else** — carried and never read. The work is to
honour it in the engine and relax the discoverer, with a test pinning the URL.

> **A local Node/Express proxy was proposed and should not be built.** It fails
> on four counts and the first is fatal: `is_local()` returns true for
> `localhost`, so `EgressGate.check` returns before the policy is consulted and
> **records nothing** — every Gemini request would leave the machine invisibly,
> from the proxy, which is rule 3 broken on the product's central claim and the
> same shape as the `/vision/analyze` side door just deleted. It also does not
> stream (`generateContent`, one JSON body, where the engine consumes SSE
> frames), implements no `/v1/models` so discovery catalogues nothing, and
> silently substitutes `gemini-2.5-flash` for an unrecognised name — Zaram
> naming one model while another answers. Behind all of it: a Node sidecar is
> another process to ship in a product whose stated blocker is that a stranger
> cannot install it, which is the ground `CLAUDE.md` rejected TencentDB on.
>
> If an adapter is ever needed it belongs **in-process, in Python, behind the
> gate**. For Gemini it is not needed at all.

### 3. Does the desktop runtime keep a backend-facing half?

**A decision, not a task.** The audit is finished to the point where the rest
is one call, and doing it piecemeal is what made it keep widening.

Every backend-calling handler in `desktop/` sends `Content-Type` and nothing
else while `RequireApiSecret` wants `X-Zaram-Auth` and exempts nothing, so all
of them have returned 401 since the secret shipped. Three are deleted (Vision,
Knowledge, Speech). These remain:

* `callBackendChat` (`bootstrap.ts:585`) → `POST /chat`, behind
  `conversation.runtime` and `reasoning.generate`. Also hardcodes
  `gemma3:latest`, which is not installed here.
* `VoiceRuntime` (full) executes `speech.tts`, whose handler is now gone.
  Commented in place at `voice/voice-runtime.ts:120`.

**Nothing invokes any of it.** `executeCapability` is on the preload bridge at
`electron/preload.js:111` with no caller in the live frontend; `executive.plan`
likewise; `desktop-bridge.ts` is imported only by `PresenceContext` and
`OrbEngine`, both for presence and orb state.

**The rule that decides it is already written.** `CLAUDE.md`: *"Frontend calls
the backend directly over HTTP, not through Electron IPC."* On that reading the
backend-facing half should not exist and what stays is the native work —
filesystem, VS Code, workspace, presence, world. The counter is that
`ExecutiveRuntime` also feeds the orb's presence snapshot through `main.js`, so
the planning half and the presence half must be separated first.

**One consequence to fold in.** `npm run check:reachability` now lists
`POST /knowledge/search` as a route no frontend file mentions — the deleted
desktop pack was its only HTTP caller. The *capability* is alive
(`ExecutionDispatcher` calls `service.search_knowledge()` in process), so the
route lost its caller, not the feature. Check whether the frontend reaches
search by another prefix before removing it; `/memory/maintenance` and
`/memory/traffic` were already on that list and are unrelated.

### 4. Phase 0 — the actual blocker

`CLAUDE.md` is unambiguous: *"A stranger cannot install this. Capability is not
what stands between the current state and a 15-person retention test —
packaging is."*

The free-tier key path is now real, which was half of it. What remains is an
installer and a guided first run, plus the two offers `FirstRunPanel` still
greys out — installing an engine and pulling a model — neither of which has an
executor. Read `canBeCarriedOut` in `FirstRunPanel.tsx`; that function is where
each one is admitted, and its docstring says why nothing may be invented there.

### Not yet scoped: generated documents look subpar

Reported 28 August against templates available online. Still not diagnosed and
still needs one thing before it can be: **a specific example, and a statement
of what is wrong** — layout, typography, structure, or the content itself. Ask
before starting.

---

## The Ollama question — raised by the maintainer, 28 August

*Does Zaram need to ship with Ollama?* Recorded because it reframes Phase 0.

**Bundling it: no.** Docling was refused at 321 MB against a 267 MB base, and
the Ollama installer is larger once GPU runners are counted. Unlike Docling it
is not a library — it is a background service that claims port 11434 and
updates itself. That is shipping a second product inside this one.

**Depending on it: currently yes, in three places, and one is quiet.**

| Where | Without Ollama |
|---|---|
| `bootstrapper.py:150` — embedder defaults to `ollama/bge-m3` | Falls back to the hash backend. Recall keeps working, on **keyword overlap**, and says nothing. |
| `LocalDispatchEngine` — Ollama is the fallback for anything unplaceable | Connection refused, surfaced as a model error |
| Context budget, warming, `keep_alive` | All read `/api/ps`, which is Ollama-only |

The embedder is the real one. A stranger with no Ollama gets a Spine that
retrieves on word overlap and is never told — `CLAUDE.md`'s *"disabled
capabilities are visible, not silent"* broken on the product's central claim.

> **Ollama is a product. `llama-server` is a component.**

A single binary spawned as a child process — no installer, no service, no tray
icon, no port collision because Zaram chooses the port, and it exits when Zaram
exits. MIT. Caveat that decides the packaging: a CPU build is small, GPU builds
drag the CUDA runtime. Ship CPU, make GPU an opt-in download **with the size
named** — the `zaram[ingest]` precedent, *"321 MB, one time"*.

**A Phase 0 decision, not a task.** Nothing has been changed on it.

---

## Running it for a visual check

`docs/RUNNING.md` is the authority, and it carries the leftover-process trap
that cost one session its screenshot — read it before concluding a port is held
by something external.

Two things not in it, because they are about the agent's tools rather than the
product:

* **The Browser pane may not be displayed**, and then screenshots fail outright
  and synthetic clicks silently do not reach the page. `read_page`,
  `get_page_text` and `javascript_tool` all work; dispatching a pointer
  sequence through `javascript_tool` is what actually opens the orb. **Say
  which of these you used** — a JS-dispatched click is weaker evidence than a
  real one.
* **Another session may already hold the dev server.** It is not reachable from
  a second session's Browser tools. Start your own, or say plainly that you did
  not look.

---

## Roadmap

<https://claude.ai/code/artifact/b5c802a5-0701-43c1-aff1-5f9835ffbc65>

Phase 1 is done. Phase 0 — free-tier first run, import ChatGPT/Claude history —
is the gate everything else waits behind, and the key half of it now exists.

There is also a published page describing the product to a potential user:
<https://claude.ai/code/artifact/bf05fa1c-fcc8-4c8b-8183-5c5f290f34ea>

---

## Machine state

* Ollama holds `gemma4:26b-a4b-it-q4_K_M` (18.2 GB) and `bge-m3`. The chat
  model **does not fit** — the resident budget on a 12 GB card is ~9.1 GB — so
  it runs half on the processor and every reply is slow. Settings says so
  before it is chosen.
* `select_default_model` returns `None`, which is correct and is the ordinary
  path here. Any code assuming a default model exists is exercised on this
  machine.
* TabbyAPI serves Qwen3.8-27B EXL3 on `127.0.0.1:1234`, discovered as
  "LM Studio", routed by `LocalDispatchEngine`, reachable by either of its two
  names. ~2.2 s to first token.
* **`gemma4:26b-a4b` can see**, and local vision through it works end to end —
  165.8 s to first token with the `oversized` warning shown, which is the
  designed behaviour rather than a fault.
* **Qwen3.8-27B can see too**, confirmed from its own config: 987 vision
  tensors, `language_model_only: False`. TabbyAPI's `/v1/model` reports
  `"use_vision": false` for it, which is the measurement the discovery question
  needs.
* **Say which environment you measured in.** The backend suite runs ~4 minutes
  with Ollama up and idle, ~7 with `gemma4` resident and contending, and far
  longer with Ollama *down* — where it also **executes different code**.
* **The residency gate is inert under pytest.** `vram_known` is `False` in a
  bare test process, so `model_fits_resident` returns `None` for everything and
  the filter never fires. Any test about residency must stub
  `resident_budget_bytes` or it asserts nothing.
