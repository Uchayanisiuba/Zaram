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
> **Items 1, 2, 3, 4, 5 and 7 are done.** **Item 6 is the only one left**, and
> it is a design that was agreed in principle with nothing built.
>
> **The vision side door is gone too** — the longer-horizon item that used to
> sit under this list. `POST /vision/analyze` is deleted rather than repaired,
> along with `stream_vision_response`, both wrapper forwarders,
> `ModelsService.analyze_image`, the desktop capability pack that was its only
> caller, and the `/vision` prefix from both proxy lists.
>
> **What is left across the whole queue is item 6 and Phase 0**, and item 6 is
> the design for half of Phase 0. A stranger with no GPU and no key still gets
> nothing, and `CLAUDE.md` says packaging is the actual blocker, not
> capability — so that is the work, and it is now the only thing standing
> between here and a retention test.
>
> **Before starting any item, read its section and then read the code.** Two
> handoff claims were stale before this session and one of them sent a whole
> job at work that had shipped eleven days earlier. The queue entries name
> files and line numbers so you can check in a minute.
>
> **`backend/orchestrator/` is deleted** — 1,261 lines, zero importers, the
> merged "can see = can draw" scorer and the ranker that treated a missing
> *required* capability as a warning. `CLAUDE.md` had said to delete it; three
> files carried prose warning about it instead. It is gone and they now say so
> in the past tense.
>
> > **Rule 7j's second dimension shipped.** `EgressPolicy` is keyed on
> `(host, DataClass)`, so "you connected this provider for chat" no longer
> reads as permission to send it a photograph. That unblocked cloud vision,
> which had been finished and refused one question short of working.
>
> **First run can store a cloud key.** `CloudKeyForm` is the executor for the
> offer `FirstRunPanel` had been greying out since it was built. **It has not
> been seen in the running app** — reaching that screen needs `can_chat:
> false`, and this machine has models. Verify with an empty `ZARAM_DATA_DIR`
> and Ollama stopped before trusting it.
>
**The `desktop/` audit is half done, and finishing it needs a decision
> rather than a cleanup — see the section below.** Knowledge and Speech went
> the way Vision did: uncredentialed, unreachable, duplicating a path that
> works. `conversation.runtime`, `reasoning.generate` and the `speech.tts`
> call in `VoiceRuntime` are in the same position and were left, because
> removing them decides whether the desktop execution pipeline keeps a
> backend-facing half at all.
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

### 3. Paste an image into the chat box — **DONE**

`frontend/src/lib/pastedFiles.ts`, wired as `onPaste` on the composer input.
**On the input rather than on the window**, the opposite of
`KnowledgeWorkspace.tsx:305` and deliberately so: that one skips fields because
a paste into its search box is a search, and here the caret is in the message
box by definition. Sharing the code would have meant a flag deciding which
product it was.

Two things that are not obvious. `items` and `files` are **both** read, because
an OS screenshot arrives as a `DataTransferItem` while a file copied from a
folder populates `files`, and which one is empty varies by platform. And a
clipboard image is named `image.png` every time, so two pastes produce two
chips the user cannot tell apart — a file copied from a folder keeps its real
name, a clipboard image gets the time it was pasted.

It reaches the same `takeFiles` the paperclip does, so the same parse, cap,
refusals and vision gate apply. Text pastes are untouched.
`frontend/src/lib/pastedFiles.test.ts`, 10 cases.

### 4. Images on the OpenAI-compatible path — **DONE (the bug), open (the discovery)**

**Local vision through Ollama works and was measured** — a PNG of a red circle
and a blue rectangle, answered correctly by `gemma4:26b-a4b` at 165.8 s to
first token with the `oversized` warning shown. Full account in
`docs/MILESTONES.md`; do not re-derive it.

**`_body()` now carries images.** It took no `images` parameter while
`stream_response` accepted one, so an image attached with a TabbyAPI or cloud
model selected was discarded and the model answered about a picture it had
never seen. The content-parts form appears only when there are images, because
several older servers accept a plain string only. The media type is read from
the picture's own **signature** — the filename is gone by the time an image
reaches an engine — and an image whose format cannot be established is refused
rather than labelled `image/png`.
`tests/test_images_on_the_openai_path.py`, 15 cases, 14 confirmed failing
before.

**Still open: TabbyAPI's modality is a default, not a measurement.**
`OpenAICompatibleAdapter._to_model` never sets `supports_vision`, so Zaram
reports `false` for a model that can plainly see —
`C:/Users/user/models/Qwen3.8-27B-exl3-2.20bpw/config.json` has a
`vision_config`, an `image_token_id`, `language_model_only: False`, and **987
vision tensors** out of 3,080.

Fixing that needs a decision, not a line, and there is now a **measurement that
sharpens it**: TabbyAPI's `/v1/model` reports `"use_vision": false` for the
loaded model on this machine. So the server itself says vision is off, whatever
the weights can do — which means the honest source is that field rather than
the chat template's `image_count` handling, and it also means an image sent
there today would not be read even with `_body` carrying it. `/v1/models`
still advertises no modality at all, so plain OpenAI keeps the base behaviour.
Queue item 7 did the equivalent for OpenRouter, where the field exists.

### 5. The VRAM budget cannot see a second local server — **DONE, measured**

Both defects were real and there was a third underneath them: merging the
adapters would have changed nothing, because `OpenAICompatibleAdapter` had no
`resident_models` to merge. Measured here with both servers up —

    nvidia-smi          -> 12288 MiB total, 9493 MiB used, 2623 MiB free
    Ollama /api/ps      -> {"models": []}        <- answered first, so this won
    TabbyAPI /v1/model  -> Qwen3.8-27B-exl3-2.20bpw

— a 3.3 GB cold start onto 2.6 GB of real headroom graded as `load`, "a cold
start with room to spare".

Now: the map merges across every local server and a provider that cannot answer
makes it unknown rather than empty; `/v1/model` reports the loaded model with
its size as `None` (never `0` — no OpenAI-compatible route carries a memory
figure); `HardwareProfiler.vram_used_bytes` supplies occupancy when an
unsizeable tenant makes the sum unanswerable; and `evicts` names only what the
model's own server would unload. Full account in `docs/MILESTONES.md`.

`tests/test_residency_sees_every_server.py`, 19 cases — twelve confirmed
failing against the unfixed code, three run against the real servers and skip
when they are not up. The fourteen existing `test_swap_preflight.py` cases pass
unchanged.

**What was deliberately not built, with its re-entry point.** When a model does
not fit and nothing evictable is in the way — a second server holding the card,
or a program Zaram knows nothing about — `swap_preflight` returns `None`. There
is no honest word for that among its four kinds, and a fifth is a cross-stack
change: `chatClient.ts:403` drops any kind it does not recognise, which it has
already been bitten by once. Worth doing when someone can write the sentence
the user should read. Re-entry: the empty-`evicts` branch in `swap_preflight`.

**And the asymmetry that makes local↔local routing expensive here is unchanged.**
Ollama unloads after `keep_alive` (observed — `bge-m3` dropped out mid-session);
**TabbyAPI holds for the process lifetime**. TabbyAPI does expose
`/v1/model/unload` and `/v1/model/load`, so a driven handoff is possible — but
it is a ~100 s round trip, so it belongs behind an offer, never a silent route.

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

### 7. Cloud discovery throws modality away — **DONE**

`OpenRouterAdapter._to_model` now reads `architecture.input_modalities` and
`architecture.output_modalities` — the same object `_is_free_tier` already
opened for pricing. Accepting images sets `supports_vision` and the model stays
an `LLM`; emitting images *and not text* makes it a `ModelCategory.IMAGE`, so
`select_model_for_task` stops offering a model that can only draw as an answer
to a question. Absent or malformed `architecture` leaves the base behaviour
alone — absent is "we do not know", never "text only".

The gate it feeds was already built and reachable —
`select_model_for_task(requires_vision=True)`, callers at `main.py:372` and
`main.py:682`, and the refusal at 682 is correct. It was reading a flag nothing
ever set, which is why a user with a dozen vision-capable cloud models was told
nothing could see. `tests/test_cloud_modality_survives_discovery.py`, 11 cases,
two of which pin that `test_openrouter_policy.py`'s rules are unloosened.

**The other half is still genuinely unbuilt, and it stays that way on purpose.**
`orchestrator/capabilities.py` used to map `ModelCategory.VISION`, `IMAGE` and
`VIDEO` all to `Capability.VISION: 1.0` — "reads images", "makes images" and
"makes video" as one number. **The package was deleted on 28 August** (1,261
lines, zero importers, exactly as `CLAUDE.md` instructed), so the wrong version
is gone rather than merely unused; nothing was salvaged from it. Routing an
image *request* still needs a way to say "this reply should be a picture",
which does not exist — building the gate before the request would be scoring a
decision nobody can make yet.

### Not yet scoped: generated documents look subpar

Reported 28 August, against templates available online. Not diagnosed — it
needs a specific example and a statement of what is wrong: layout, typography,
structure, or the content itself. Ask before starting.

---

## Vision: what is settled and what is not

**The side door is gone.** `POST /vision/analyze`,
`OllamaEngine.stream_vision_response`, both wrapper forwarders,
`ModelsService.analyze_image` and the desktop capability pack that was its only
caller were all deleted on 28 August. Three facts settled the deletion, and
none of them was visible from the route table: the desktop caller sent no
credential and `RequireApiSecret` exempts nothing, so it had returned 401 for
eleven days; the endpoint called `_parse_legacy_sse`, which is defined nowhere;
and the suite's pass count was identical before and after, so nothing tested
it. `tests/test_no_second_entrance_to_inference.py` asserts the quarantine
rather than describing it.

**The trap in that deletion is recorded because it nearly worked.**
`IntentPlanner` still emits a `vision.*` step on keywords when nothing is
attached, and the dispatcher's vision branch was the only thing catching it —
remove the branch and such a step falls through to `generate_response`, where a
model describes a picture nobody supplied. The branch stays and refuses,
reaching no engine.

**What is settled:** `select_model_for_task(requires_vision=True)` is the gate,
`OllamaEngine.stream_response` carries images on whichever model was routed,
`OpenAICompatibleEngine._body` now does too, and OpenRouter discovery reports
which cloud models can see.

**What is not:** there is still no way to ask for an image as an *answer*.
("Can see" versus "can draw" as one number went with `orchestrator/`, deleted
28 August — there is nothing left to fix there, only something to build.) TabbyAPI's own `/v1/model` says `"use_vision": false` for the
model loaded here, which is the measurement the discovery question needs; see
queue item 4.

## Open: does the desktop runtime keep a backend-facing half?

**A decision, not a task**, and the audit that produced it is finished to the
point where the rest is one call.

`desktop/` is a second, parallel runtime with its own keyword planner, its own
capability registry and its own HTTP calls to 8420. **Every one of those calls
sends `Content-Type` and nothing else**, and `RequireApiSecret` wants
`X-Zaram-Auth` and exempts nothing — so all of them have returned 401 since the
per-launch secret shipped. Three are now deleted (Vision, Knowledge, Speech);
these remain:

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
backend-facing half of the desktop pipeline should not exist, and what stays is
the native work — filesystem, VS Code, workspace, presence, world. The counter
is that `ExecutiveRuntime` also feeds the orb's presence snapshot through
`main.js`, so it cannot simply be deleted wholesale; the planning half and the
presence half have to be separated first.

**Do not do this piecemeal.** Removing one more handler leaves the executive
planning steps nothing can execute, which is how this audit kept widening. Take
the decision, then make one change.

**One consequence to fold into that decision.** `npm run check:reachability`
now lists `POST /knowledge/search` as a backend route no frontend file
mentions, and that is this deletion's doing: the desktop Knowledge pack was its
only HTTP caller. The *capability* is very much alive — `ExecutionDispatcher`
calls `service.search_knowledge()` in process — so the route, not the feature,
is what has lost its caller. Check whether the frontend reaches search by some
other prefix before removing it; `/memory/maintenance` and `/memory/traffic`
were already on that list and are not related.

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
