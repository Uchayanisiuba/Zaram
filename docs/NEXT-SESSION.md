# Next session — start here

A prompt and a state snapshot. Rewritten 28 August 2026 at the end of the
session that rendered the conversation history panel and fixed the local
routing defect it exposed.

**This file is a pointer, not a second handoff.** `docs/MILESTONES.md` Current
state is the handoff and stays the authority on status; `CLAUDE.md` stays the
authority on rules. If this file disagrees with either, they win and this file
is stale — say so and fix it.

Note that the previous version of this file was wrong about one thing, and it
cost a whole job: it listed the per-launch API secret as the remaining Phase 1
item when it had shipped eleven days earlier. **Check the code before starting
a task a handoff hands you.**

---

## The prompt

Paste this into a new session:

> Read `CLAUDE.md`, then `docs/MILESTONES.md` Current state, then this file.
> For anything touching voice read `docs/SPEECH.md`; before starting the app
> read `docs/RUNNING.md`, and note that launching means three processes — Vite,
> Electron, and TabbyAPI on port 1234.
>
> **Everything from the last session is committed and pushed** (`Zaram-V0.1`).
>
> **Start with the queue below — seven items, all root-caused.** They were
> raised by the maintainer while using the product on 28 August, so every one
> is a thing that actually happened rather than a thing that might.
>
> **Items 1 and 2 are done**, both verified by driving the running product
> rather than by tests alone. **Item 4 is half done** — local vision works and
> was measured; only the TabbyAPI half remains. **Items 3, 5, 6 and 7 are
> untouched.**
>
> **Take item 3 next** — paste an image into the chat box. It is the smallest
> of what is left, it is a plain feature rather than a defect, and there is a
> working `paste` handler in `KnowledgeWorkspace.tsx` to model it on. Item 4's
> remaining half is the natural follow-on, since both are about getting images
> into a model.
>
> If you would rather fix than build: **item 5** (the VRAM budget cannot see a
> second local server) is the one blocking real work — nothing about task
> routing can be trusted until it is done.
>
> **Before starting any item, read its section and then read the code.** Two
> handoff claims were stale this session and one of them sent a whole job at
> work that had shipped eleven days earlier. The queue entries name files and
> line numbers so you can check in a minute.
>
> Longer-horizon, and both still open:
>
> * **Phase 0** — the free-tier first run. A stranger with no GPU and no key
>   still gets nothing, and `CLAUDE.md` says packaging is the actual blocker,
>   not capability. Queue item 6 is the design for half of it.
> * **The vision side door.** `POST /vision/analyze` still reaches
>   `stream_vision_response`, which hardcodes an uninstalled `qwen2.5vl:7b` and
>   by its own docstring bypasses routing **and the egress gate**. The chat
>   path no longer touches it. It is a deletion question, not a gating one.
>
> Read the Ollama question below too. It is not a task yet, but it changes what
> Phase 0 means.

---

## What happened last session

Two things, and the second came out of the first.

**The history panel was rendered and works** — list, real count, day grouping,
resume with full transcript, delete. The port that blocked it the session
before was held by that session's own leftover Vite and Electron, eleven hours
stale. Nothing was wrong with `strictPort` or the CORS allow-list.

**A live routing defect surfaced on the first real message**, and it is the
one worth reading:

    model="lm_studio:Qwen3.8-27B-exl3-2.20bpw"  -> TabbyAPI, generated
    model="Qwen3.8-27B-exl3-2.20bpw"            -> Ollama, model not found

Same model, two names. `_local_endpoint_for` resolved the provider with a
`split(":", 1)` while its four siblings resolve through `_catalogued`, which
normalises a bare provider-native name. The `answering` event told the user
`provider: lm_studio` while the request went to Ollama.

It was green because `test_local_dispatch.py` **stubs the resolver it was
testing around**. `_local_endpoint_for` had no tests at all.

**Then a second door, which was the one actually biting.** Fixing the above
only helps a request that *names* a model. `_resolve_model` returns
`_ModelChoice(None, "zaram")` whenever nobody named one — every ordinary
message — and `LocalDispatchEngine` resolved only when `model` was truthy,
while its `default_model` setter stored the runtime's pick on `self._ollama`
and nowhere else. So the default was recorded on the one engine that could not
reach it.

**Two doors, one assumption, and a third is possible.** Anywhere that treats
*"no model named"* or *"cannot place this name"* as **therefore Ollama** is the
same bug waiting. That is also the concrete case for the Ollama question below.

Three smaller things came out of the same report — leading blank lines on every
reply, no sampling parameters on the local OpenAI path, and Zaram not knowing
who made it.

**Then local vision, which was three defects deep.** Asked to read an attached
PNG, Zaram answered *"No model on this machine can read images"* — while
`gemma4:26b-a4b` sat in the catalogue with `supports_vision: True`. Behind that:
residency was answering a capability question; the planner matched the *word*
"image" and emitted a `vision.analyze` step without knowing an image was
actually attached; and the dispatcher reads `input_data["image"]` while the
engine writes `input_data["images"]`. Each hid the next. It now works, measured
— a red circle and a blue rectangle, named correctly, 165.8 s to first token
with the `oversized` warning shown.

**One shape runs through all of it: a guess overriding a fact.** A keyword beat
an attachment, a speed judgement beat a capability, a stubbed resolver beat the
real one, a ranking score beat a measurement. When something here is wrong,
that is the first thing to look for.

Full account of all of it in `docs/MILESTONES.md`.

---

## The Ollama question — raised by the maintainer, 28 August

*Does Zaram need to ship with Ollama?* Recorded because it reframes Phase 0
and because the session found the evidence for it by accident.

**Bundling it: no.** Docling was refused at 321 MB against a 267 MB base, and
the Ollama installer is larger once its GPU runners are counted. Unlike Docling
it is not a library — it is a background service that claims port 11434 and
updates itself. That is shipping a second product inside this one.

**Depending on it: currently yes, in three places, and one of them is quiet.**

| Where | Without Ollama |
|---|---|
| `bootstrapper.py:150` — embedder defaults to `ollama/bge-m3` | Falls back to the hash backend. Recall keeps working, on **keyword overlap**, and says nothing. |
| `LocalDispatchEngine` — Ollama is the fallback for anything unplaceable | Connection refused, surfaced as a model error |
| Context budget, warming, `keep_alive` | All read `/api/ps`, which is Ollama-only |

The embedder is the real one. A stranger with no Ollama gets a Spine that
retrieves on word overlap and is never told — which is `CLAUDE.md`'s
*"disabled capabilities are visible, not silent"* broken on the product's
central claim. The chat model at least fails loudly.

**The direction: stop assuming Ollama rather than ship it.** The abstraction
already exists and was watched working this session — TabbyAPI answered a
request through `LocalDispatchEngine` on this machine. In order of cost:
detect-and-offer with the size stated (the shape `zaram[ingest]` already uses,
consented and logged); the free-tier key path Phase 0 owns for a user with no
GPU; and only if measurement says neither carries a stranger, a bundled
`llama-server` — MIT, library-shaped, CPU build with GPU opt-in.

**"Would users notice Ollama?" — asked 28 August, and it sharpens the answer.**
Today they notice a great deal: they install it themselves, it runs as a
background service, it holds port 11434, it has a tray icon, and it updates
itself. That *is* the "a stranger cannot install this" blocker, stated
concretely.

Bundling does not fix that. It puts another product's installer inside this
one, which then installs a service and a tray icon anyway. The distinction to
carry:

> **Ollama is a product. `llama-server` is a component.**

A single binary spawned as a child process — no installer, no service, no tray
icon, no port collision because Zaram chooses the port, and it exits when Zaram
exits. MIT. That is what "invisible" actually requires, and it is why Ollama is
specifically the wrong thing to ship if invisibility is the goal: a product
cannot be invisible.

Caveat that decides the packaging: a CPU `llama-server` build is small, GPU
builds drag the CUDA runtime and are not. Ship CPU, make GPU an opt-in download
**with the size named** — the `zaram[ingest]` precedent, *"321 MB, one time"*.

This is a **Phase 0 decision, not a task.** Nothing has been changed on the
strength of it.

---

## The queue — seven items, none started

Raised by the maintainer on 28 August while using the product. Each was
root-caused during the conversation; none has been touched. Ordered by
"the product is lying to the user" first, features after.

### 1. "Open Settings →" does nothing — **DONE, verified in the browser**

`NoticeCard` called `openWorkspace`, which was
`useConversationStore.setActiveNode`. That writes `activeNode` — and **nothing
outside `legacy/` reads it**. The real navigation is `navigate()`, plain React
state in `App.tsx`, never exposed to `ChatSurface` (rendered as
`<ChatSurface />`, no props). Second dead call site: `openWorkspace('activity')`
in the citation panel.

`ChatSurface` now takes `navigate` as a **required prop**, passed from `App`,
and both call sites use it. Not a store: `App`'s `navigate` also closes the
chat, closes the command palette and sets the conversation's context, so a
second implementation would drift — and drifting navigation is how this broke.
Required rather than optional so `tsc` fails at the call site instead of a
button failing silently. `NoticeCard`'s `DESTINATIONS` is now typed
`Record<string, { node: WorkspaceId; … }>`, the way `LeftRail` types its own.

**Verified by driving it**: asked for today's date, the notice appeared, clicked
*Open Settings →*, landed on the Settings workspace. Four tests in
`NoticeCard.test.tsx` pin which node each action resolves to — and their
docstring is explicit that they would **all have passed on the day the bug was
reported**, because the card was never the broken part. The wiring is guarded
by the required prop, which is a compile error rather than a test.

`src/legacy/` is inside `tsconfig`'s `include`, so `activeNode` and
`setActiveNode` stay in `conversationStore` — removing them breaks legacy
compilation. After this change **`conversationStore` has no live consumer at
all**; auditing it is a separate job.

**`npm run check:reachability` cannot see this class of defect**, and it is
worth being precise about why: the export *was* used, and the call *did* go
somewhere. It simply had no effect — a shape no import graph can tell apart
from working code.

### 2. The "web search is off" notice fired on a date question — **DONE**

Asked for today's date, the user got the amber *"This looks like it needs
current information"* card. But `identity.py` supplies the date — `_today_line`
exists precisely because a model asked outright answered `04-07-2026` from
training data on 17 August.

So the classifier flagged a question whose answer was already in the prompt.
The disclosure is not wrong in general; it is wrong here. The fix is a
precondition, not a wording change: a question the system supplies a fact for
does not need search.

**Confirmed by driving it, 28 August**, while verifying item 1. Asked *"What is
today's date?"*, Zaram answered **"Today's date is 28 August 2026"** — correct,
from the supplied fact — and rendered the amber card underneath it anyway. So
the reply and the warning about the reply contradict each other on screen.

Same shape as the vision chain: a **guess overriding a fact**. A keyword
classifier overruling something the system stated as certain one paragraph
earlier in the same prompt. Two patterns matched — `_TIME_RE` on the bare word
"today", `_FACTUAL_RE` on "what is the".

`_ANSWERED_BY_SUPPLIED_DATE` in `core/query_classifier.py` now exempts it,
checked before every other pattern. Verified live, both directions:

    "What is today's date?"            -> "Today's date is 28 August 2026."  no notice
    "What happened in the news today?" -> notice still fires

**Three constraints on it, and they are the reason it is not just another
keyword list.** It is **anchored to the whole question**, because `_TIME_RE`
matching "today" *anywhere* is precisely how the bug happened — an unanchored
exemption would be the same defect with the sign reversed, and reversed is
worse, since a missing warning is quieter than a false one. It is **scoped to
the date**, because `_today_line` supplies a date and nothing finer, so "what
time is it" is deliberately not exempt. And it is **coupled to the fact**:
`TestTheExemptionIsCoupledToTheSuppliedFact` asserts `identity.py` still puts
the date in the preamble, so if that ever stops, the exemption fails rather
than silently suppressing a warning that has become true.

No general "answerable from supplied facts" mechanism was built. There is one
supplied fact, and designing an abstraction from a single example is what the
pack-system rule explicitly forbids. **If a second time-varying fact is ever
supplied, that is the moment to generalise** — not before.

### 3. Paste an image into the chat box

Straight feature request, and there is a working implementation to copy:
`KnowledgeWorkspace.tsx:305` already handles `paste` for ingesting sources. The
chat composer has a file input and no paste handler.

### 4. Images on the OpenAI-compatible path — **partly done, read carefully**

**Local vision through Ollama now works and was measured.** A PNG of a red
circle and a blue rectangle, attached to a chat message, answered correctly by
`gemma4:26b-a4b` at 165.8 s to first token with the `oversized` warning shown.
Three defects were fixed to get there — residency answering a capability
question, the planner not knowing an image was attached, and singular `image`
versus plural `images` between dispatcher and engine. Full account in
`docs/MILESTONES.md`; do not re-derive it.

**What remains under this heading is the TabbyAPI half**, and it is two
separate things:

`OpenAICompatibleEngine.stream_response` accepts an `images` parameter and
**never uses it** — `_body()` does not take images at all. An image attached
while a TabbyAPI model is selected is discarded, and the model answers about a
picture it never saw. Rule 9 in a new medium, and it would bite even with a
vision-capable model on that endpoint.

And the model on this machine **can** see, which was checked rather than
assumed. `C:/Users/user/models/Qwen3.8-27B-exl3-2.20bpw/config.json` reports
`architectures: ['Qwen3_5ForConditionalGeneration']`, a `vision_config`, an
`image_token_id`, and `language_model_only: False`; the weight index holds
**987 vision tensors** out of 3,080. Zaram's `supports_vision: false` for it is
`OpenAICompatibleAdapter._to_model` never setting the flag — a **default, not a
measurement**. Do not treat it as one.

Fixing that needs a decision, not a line: TabbyAPI's `/v1/models` advertises no
modality field at all. `/v1/model` returns the loaded model's parameters and
its chat template, and that template does contain `image_count` and
`video_count` handling — a usable signal, but inference rather than a stated
fact, so it needs to be argued for before it is shipped. The two halves are
independent: `_body()` dropping images is a plain bug and can be fixed now;
the modality flag is a discovery question.

### 5. The VRAM budget cannot see a second local server

Two defects, and together they make every residency decision on a two-server
machine wrong:

* **`ProviderManager._resident_models()` returns the first adapter that
  answers** — it `return`s on the first non-`None` result instead of merging
  across adapters. With Ollama *and* TabbyAPI registered, only one is ever
  seen.
* **`resident_budget_bytes()`** subtracts the embedder and a 20% KV reserve
  from total VRAM and knows nothing about another server's footprint.

Measured 28 August on the 12 GB card: `nvidia-smi` reported **10,630 MiB used**
with TabbyAPI holding a 9.7 GB model, while `resident_budget_bytes()` would
compute roughly **8.7 GB available**. `swap_preflight` — which exists to make
swaps honest and whose logic is right — would confidently report "fits, just a
cold start".

**Do not build task routing on top of this.** It is the *"a score built for
ranking is not a score for deciding"* lesson in a new place: the machinery is
sound and its inputs are off by ten gigabytes.

Note also the asymmetry that makes local↔local routing expensive here: Ollama
unloads after `keep_alive` (observed — `bge-m3` dropped out mid-session);
**TabbyAPI holds for the process lifetime**. One server lets go, the other
never does. TabbyAPI does expose `/v1/model/unload` and `/v1/model/load`
(confirmed in its OpenAPI), so a driven handoff is possible — but it is still a
~100 s round trip, so it belongs behind an offer, never a silent route.

### 6. Cloud routing, the setup offer, and a type-in model field

The design discussion, recorded so it is not re-derived. **Agreed in principle,
nothing built.**

*Suggest OpenRouter at first run.* One key fronts most of the frontier —
`CLAUDE.md` already notes it fronts Anthropic and Gemini. It stays **step 4 of
first run and optional**: *"everything works without this."* The moment it
reads as required, the product needs an account, which is the opposite of the
pitch. Provider suggestions belong in the **dated manifest** beside model
recommendations, not hardcoded — refreshable without a network call (rule 7g)
and honest about their age.

*What cannot change:* `test_openrouter_policy.py` asserts that **no OpenRouter
model is ever `selectable_by_default`** — provider policy UNKNOWN, `:free` and
zero-pricing marked `LOGGED_AND_TRAINED_ON`, paid models claiming nothing. Its
framing is the rule: *we can sometimes prove a model logs; we can never prove
one does not.* So automatic cloud routing is **earned by a named grant** under
rule 7j — propose, accept once per destination and data class, then remember —
never defaulted.

*How to know local cannot cope.* Preconditions are decidable and may route on
their own once granted: needs vision; prompt exceeds the local model's real
window (`context_budget.py` measures it from `/api/ps` rather than trusting the
advertised number); or **no local model is selectable at all** — which is the
*ordinary* state on this machine, not an edge case. "Too hard for the local
model" is **not** decidable in advance: do not predict it, react to it with an
offer under the reply.

*A type-in model field:* yes, behind Advanced — a dropdown cannot hold
OpenRouter's catalogue. Three conditions. It must **resolve before sending**:
measured 28 August, asking for `anthropic/claude-sonnet-4.5` returned
`locality: null, provider: null` from the identity layer — honest — and was then
**sent to Ollama anyway**, producing *"Ollama refused the request for
anthropic/claude-sonnet-4.5"*. The safety direction is right (`_is_remote_model`
returns `False` for the unresolvable, so nothing leaks) and the message is
useless. It must **state the data policy while the user is choosing**, because
`selectable_by_default` stops *Zaram* picking a `:free` model and must never
stop the *user* picking one knowingly. And a typed name **widens nothing** —
same rule as a tool description.

### 7. Cloud discovery throws modality away, and it is the only thing missing

**This is smaller than it looks and unblocks more than it looks.** Everything
needed to route an image to a cloud model that can read one is already built
except this.

`OpenAICompatibleAdapter._to_model` hardcodes `category=ModelCategory.LLM` and
never sets `supports_vision`. Its comment justifies that correctly for plain
OpenAI — *"/v1/models exposes only an id + ownership; deeper metadata is not
part of the spec"* — and that reasoning does **not** carry to OpenRouter, whose
`/api/v1/models` returns `architecture` with input and output modalities. It
arrives in the same response `OpenRouterAdapter._to_model` already parses,
because that override exists specifically to read `pricing` for the free-tier
policy. The modality sits beside the pricing and is discarded.

What is already built and verified reachable, so do not rebuild it:

* `select_model_for_task(requires_vision=True)` — the gate, live callers at
  `main.py:372` and `main.py:682`
* the refusal, `main.py:682` — *"No model on this machine can read images.
  Zaram will not answer about a picture it cannot see."* Rule 9, correct
* `_resolve_model(..., has_images=bool(images))` at `main.py:1167` — the
  requirement comes from a real attachment, not from wording
* `main.py:1351` passes `images` into the chat path; `chat_router` carries
  them and its legacy path **refuses** rather than ignoring
* `OllamaEngine.stream_response` carries images on whichever model was routed

So today the cloud behaviour **fails closed, not open**: Zaram refuses rather
than handing a picture to a blind model — the right refusal built on missing
data. A user with a connected OpenRouter account and a dozen vision-capable
models is told nothing can see.

**Local vision is believed to work and has not been run.** The chain above was
traced, not executed. Three "the plumbing exists" claims turned out to have a
dead link in the middle during the 28 August session, including a fix that
shipped with its own resolver stubbed out. Convert it to a measurement before
relying on it — `gemma4:26b-a4b` is installed and vision-capable, and it will
be slow because it does not fit.

`output_modalities` rides in the same field, so this one change is also the
prerequisite for image *generation* routing. That still needs the second half:
`orchestrator/capabilities.py:40-44` maps `ModelCategory.VISION`, `IMAGE` and
`VIDEO` all to `Capability.VISION: 1.0`, so **"reads images", "makes images"
and "makes video" are one number** — ask for a model that can draw and you can
get one that can only look. Confirmed in code, 28 August.

### Not yet scoped: generated documents look subpar

Reported 28 August, against templates available online. Not diagnosed — it
needs a specific example and a statement of what is wrong: layout, typography,
structure, or the content itself. Ask before starting.

---

## Still open: vision — but not the job the last handoff described

**Read this before starting it. The previous two handoffs said "build the
modality gate", and checking the code found the gate already built.** Same
mistake as roadmap 1.4, caught this time before it cost a session.

What exists: `ProviderManager.select_model_for_task(requires_vision=True)` is
the gate, it has live callers at `main.py:372` and `main.py:682`, and
`tests/test_vision_gate.py` exercises it against a catalogue shaped like a real
machine's. The ordinary path is right too — `OllamaEngine.stream_response`
carries images on **whichever model was routed**, and refuses an image pasted
into prompt text rather than pretending to read it.

**What is left is a side door, and it is worse than a gap.**
`OllamaEngine.stream_vision_response` still hardcodes
`"model": "qwen2.5vl:7b"` — not installed here — and its own docstring at
`ollama_engine.py:277` says it bypasses **routing and the egress gate**. It is
reachable: `POST /vision/analyze` (`main.py:1393`) and `models_service.py:73`,
forwarded through both `RoutedEngine` and `LocalDispatchEngine`.

So the question is not *how do we gate modality* but **why does a second
entrance to inference exist that skips the gate and the egress log**. An
egress path the log cannot see is rule 3, and it is a data file's-worth of
precedent away from the `.vrm` remote-asset problem: the guard is real, and
something reaches past it.

The likely answer is deletion, not repair — route `/vision/analyze` through
the gated path and drop the method — but confirm what the frontend calls
before removing an endpoint.

Do not paper over any of it by pulling `qwen2.5vl:7b`.

Still true and worth keeping from the older note: `capabilities.py` maps
`ModelCategory.IMAGE` to `Capability.VISION: 1.0`, the same value a model that
*reads* images gets, so **"can see" and "can draw" are still one number** —
that half is genuinely unbuilt. And the `orchestrator/` package still has zero
importers and ranks a candidate that is missing a required capability, logging
a warning. Do not build on it; delete it.

---

## Running it for a visual check

`docs/RUNNING.md` is the authority, and it has gained the leftover-process trap
that cost the previous session its screenshot — read it before concluding a
port is held by something external.

One thing not in it, because it is about the agent's tools rather than the
product: **the Browser pane may not be displayed**, and then screenshots fail
outright and synthetic clicks silently do not reach the page. `read_page`,
`get_page_text` and `javascript_tool` all work; dispatching a pointer sequence
through `javascript_tool` is what actually opens the orb. Typing via
`computer` works once JS has focused the field. Say which of these you used —
a JS-dispatched click is weaker evidence than a real one.

---

## Roadmap

<https://claude.ai/code/artifact/b5c802a5-0701-43c1-aff1-5f9835ffbc65>

Phase 1 is **done**, including 1.4, which the previous handoff listed as
outstanding. Phase 0 — free-tier first run, import ChatGPT/Claude history — is
the gate everything else waits behind.

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
  "LM Studio", routed by `LocalDispatchEngine`, and — since this session —
  reachable by either of its two names. ~2.2 s to first token.
* **`gemma4:26b-a4b` can see**, and local vision through it works end to end as
  of 28 August. It does not fit — 165.8 s to first token, with the `oversized`
  warning shown, which is the designed behaviour rather than a fault.
* **Qwen3.8-27B can see too**, confirmed from its own config: 987 vision
  tensors, `language_model_only: False`. Zaram reports otherwise because
  discovery never asks. See queue item 4.
* **Say which environment you measured in, and it moves more than you expect.**
  The backend suite ran **4 m 16 s** with Ollama up and idle, and **6 m 46 s**
  on the same code with `gemma4` resident and contending — +58%. With Ollama
  *down* it is far longer again *and executes different code*.
* **The residency gate is inert under pytest.** `vram_known` is `False` in a
  bare test process, so `model_fits_resident` returns `None` for everything and
  the filter never fires. Any test about residency must stub
  `resident_budget_bytes` or it asserts nothing — that is how a live bug
  survived a green suite this session.
