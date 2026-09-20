# The plan to the vision — 19 September 2026

Written at the maintainer's request, after a session that measured where the
time goes per prompt, inventoried what the product actually ships against what
OpenWorker, Manus and Grok present, and walked the path a person takes today to
code a project. Read with `CLAUDE.md` (the rules every item below must survive),
`docs/AGENT-UX.md` (the study this extends) and `docs/MILESTONES.md` (status;
where this file and that one disagree about *status*, that one is newer).

This file holds the **diagnosis, the design, the order and the acceptance
criteria**, so each piece is argued once and a session can pick up any item
without re-deriving it. Every claim about the code below was read from the code
on 19 September, with the file named; nothing here is from memory of the docs.

---

## The vision, as seven claims that can be checked

In the maintainer's words, reordered into things a person can see:

1. **Fast, and consistently fast.** Memory never costs the reply. A second
   turn answers as quickly as a first.
2. **The work is visible while it happens.** A person watches Zaram search,
   read, write and run — one row per action, live, folding to a line when the
   reply lands. Claude's rows are the reference.
3. **A task is a list.** Multi-step work shows as a checklist that ticks itself
   off. Click a step, or a task, and a working pane cascades open with what
   that step did. Nothing opens on its own.
4. **Starting is one sentence.** "Add dark mode to the app in `C:\foo`" starts
   a coding task; setup is asked for inline, never required in advance.
5. **The model is used to its extent.** Qwen3.8-27B inside Zaram does what
   Qwen3.8-27B can do; a cloud model likewise. The product must not be the
   ceiling.
6. **Thinking is calm.** No back-and-forth about what it is; collapsed to one
   line of the model's own words; the full text one click away.
7. **Competitive on use cases, not on weights.** Code, research, documents,
   email and GitHub, images, voice, scheduled work — each *offered*, each lit
   only where it works — plus the two things none of the three can tick:
   memory that is yours across models, and an egress log.

Each workstream below names which claims it serves.

---

## Diagnosis — what is true today, read from the code

### Per prompt, where the time goes

The memory layer is not the cost and never was. Per turn: one embedding on the
CPU (89 ms, measured 12 Sept), a gate that skips retrieval on conversational
turns (`core/recall_gate.py`), a vector search cut to five
(`ExecutionEngine._recall`, `core/execution_engine.py:2496`), a heuristic
post-reply write with no model call (`_remember`, `:3349`). Whole layer: 100–200
ms, independent of Spine size.

Four things remain after the 12 September pass (which fixed the 10 GB swap and
the cache-busting prefix order):

| # | cause | where | evidence |
|---|---|---|---|
| L1 | **A turn that offers tools does not stream.** The engine buffers any generation that may call a tool, because `[TOOL_CALL]` arrives split across tokens. In a coding project tools are offered on *every* turn. | `execution_engine.py:756` (`buffering = bool(offered_tools) and …`), `ollama_engine.py:301` (`"stream": False`) | The comment at `:757` says it costs the typewriter and scopes it "as narrowly as it can be" — that scope is every coding turn. |
| L2 | **The model's narration between tool calls is dropped.** Each round's `text` is replaced by the next round's; only the last round's prose is spoken. "Let me check that file first" never reaches the screen. | `_run_tool_loop`, `:1359`, `:1419`, `:1628`, `:1659` — five `"".join(execute_step(...))` sites | By construction. |
| L3 | **The per-turn tail grew.** Tool rules, the repo-map briefing and up to 8 ranked stranger tools are appended *after* the conversation (`:902–904`), and the stranger shortlist is re-ranked per query, so it can differ every turn. The prefix still caches; the tail is a few thousand tokens re-read per coding turn. | `:902`, `runtimes/mcp/runtime.py:269` | Not yet measured in tokens; measure in A1. |
| L4 | **Reload from SATA, and the window's leading edge.** `keep_alive` 30 min then a 10 GB reload at ~500 MB/s (both of the maintainer's SSDs are SATA, measured 19 Sept). And once history fills the window, `transcript.fit` drops the oldest turn each turn, so the prefix start moves every turn and the cache misses again. | `ollama_engine.py:16`, `core/transcript.py` | Reload time not measured; the cache miss on a full window is the 12 Sept measurement (21.5 s → 3.9 s) in reverse. |

### The work is mostly invisible, and the machinery is mostly built

- `ToolCalls.tsx` renders one row per call with verdict, target and an output
  pane, and folds Claude-style when done (`docs/AGENT-UX.md` pattern 1) —
  **only inside the tool loop**, i.e. only on a buffered coding turn.
- A web search or a page read on an ordinary turn runs as a *plan step before
  generation* (`planner.py:1353`, `:1366`, `:1431`) and reaches the screen, at
  best, as a notice afterwards. `StreamEvent.step_start` / `step_complete`
  exist (`core/streaming_events.py:545`) and **nothing yields them into the
  stream** — the engine `_publish`es to the event bus (`:626`, `:925`) and
  `chatClient.parseEvent` has no case for them. Built, unreached: this
  repository's base-rate failure, instance eighteen.
- The checklist (`PlanCard.tsx`, `plan` tool in `packs/code/tools.py`) exists
  and is the Claude-style task list — it appears only when the model calls
  `plan`, which it is told to do only in a coding project.
- `chatStore` holds a message as `content` plus a separate `toolCalls[]`
  (`stores/chatStore.ts:72`), so rows cannot sit *between* paragraphs. Claude's
  interleaving needs an ordered segment list.

### The model is gated by the planner, not by itself

`IntentPlanner.create_plan` decides, from an embedding classification, whether
a turn gets tools at all: `mcp.list_tools` is added when a coding project is
open, when the intent is TOOL, or when the message names a page
(`planner.py:1225`, `:1340`, `:1420`). On every other turn the model is handed a
fixed plan and a prompt and **cannot decide to search, read a page, or look
something up**. That is the structural reason a 27B feels limited inside Zaram
and unlimited outside it: outside, it chooses; inside, a classifier chose.

`ModelInfo.supports_tools` is populated from Ollama's `/api/show` and is `True`
for every OpenAI-compatible server (`openai_compat.py:382`). The native
tool-call channel exists on both engines (12 Sept): Ollama via `/api/chat`,
OpenAI-compatible via `delta.tool_calls`. `CLAUDE.md`'s rule *"do not classify
with a model call before every reply"* is about **routing between models** and
is untouched by letting the model choose a tool inside its own reply.

### Thinking

`ReasoningPanel.tsx` shows the raw stream, open while streaming, collapsed
after. `identity_preamble` (`core/identity.py:411`) states what Zaram is, which
model answers and where — and says nothing about *reasoning*, so a Qwen with
thinking on deliberates "I am Qwen… but the system says Zaram… we should…"
before every answer. Two separate defects: the deliberation, and the display.

### What ships, versus what the three present

Verified in `backend/packs` and `runtimes` (19 Sept): code — `plan`,
`list_files`, `read_lines`, `search_code`, `find_symbol`, `read_library_docs`,
`write_file`, `edit_file`, `run_command` (+ `check`), `start_app`, `stop_app`,
`get_app_status`, `read_app_log`, `look_at_app`; web — `read_page`; draw —
`draw_image`; any MCP server (GitHub 26 tools, email 40, attached now);
documents (.docx/.pdf/.xlsx/.md/charts); image reading; search connectors
(DuckDuckGo, DuckDuckGo News, Wikipedia, GitHub, RSS —
`runtimes/internet/runtime.py`); voice both ways; avatar; knowledge domains
and ingest; obligations; invoice drafts; command palette; ambient panel; egress
log; memory with provenance and correction.

Architecturally ~70% of the use-case surface the three present; *presented* as
perhaps 30%, because nothing shows the work and every capability is reached by
knowing the incantation. The genuinely missing capabilities are four: browser
action, scheduled tasks, slides, an inbox of held asks. Out on principle and
said so: phone access (the paid sync rung), video, hosted deploys, unattended
browsing of accounts.

---

## Rules that bound every item below

Restated so a reviewer can check each item against them without opening
`CLAUDE.md`:

- Rule 3, 5, 7j: every byte out is logged; consent per destination and data
  class, once, then remembered; nothing here adds a dialog per call.
- Rule 6 and the tier table: the gate runs on the tool actually chosen,
  after any ranking; **a retrieval score authorises nothing.**
- Rule 9: generation fails rather than invents; documents keep their refusal
  path whatever else changes.
- Six nodes. Nothing below adds a surface. The working pane is a layer of the
  conversation; the inbox is Activity; tasks are Project's.
- "Never render invented values." A summary line is the model's own words or
  the checklist's, never a generated paraphrase.
- "Assume unreachable until the caller is seen." Every item's acceptance
  criterion is something *seen on screen*, not a green test.
- No engagement mechanics. Scheduled work runs because the person scheduled
  it; Zaram speaks first only with something real.

---

## Workstream A — speed (claims 1, 2)

### A1. Instrument the reply. *Built 19 Sept, not yet seen.*

One `StreamEvent.usage`-style event per reply carrying phase timings: gate,
recall, plan, `list_tools`, prefill (request sent → first byte), generation
(first byte → done), and the token counts sent and received. Rendered in the
Activity panel's per-reply detail, not in the transcript. Logged at INFO.

*Why first:* every number in L3 and L4 is a reading from this. Without it,
"slow" is a feeling and every later item is argued rather than measured.

*Acceptance:* open Activity after a reply, read the six numbers.
*Files:* `core/execution_engine.py` (around `execute_step`'s token loop,
`:770`), `core/streaming_events.py`, `frontend/.../ActivityPanel.tsx`.

### A2. Stream through tool turns — the holdback. *Built 19 Sept, not yet seen.*

Replace the buffer with a **holdback**: show accumulated text up to the first
*complete* call opener (`[TOOL_CALL]` or `<tool_call>`); with no complete
opener, withhold only the tail that could be the start of one (a trailing `[`,
`[TOOL`, `<tool_`) and release it the moment the next token shows it was prose.
The marker still never reaches the screen; the prose no longer waits for it.

`visible_length(text) -> int` in `core/tool_loop.py`, beside `strip_calls`.
Checked 19 Sept against 11 cases including `a < b` (5), `a <t` (2), `a <th`
(5), `<think>x</think>ok` (18), `hello [TOOL_CALL] {}` (6) — the function was
written and verified, then reverted unwired pending this plan; it is ~30
lines.

Then one generator, `_stream_round(step, model, system_prompt, spoken)`, that
yields safe pieces as they arrive and *returns* the full text, replacing the
five `"".join(execute_step(...))` sites in `_run_tool_loop` and the buffering
branch at `:756`. At the "no more calls" exit, only `strip_calls(text[shown:])`
is spoken, so nothing is said twice. This also fixes **L2**: the narration
before each call is now shown and appended to `spoken`.

Engine side: `OllamaEngine._chat_with_tools` (`:280`) moves to `"stream":
True` and re-tags `message.thinking` deltas exactly as `stream_response` does
(`:566`); `tool_calls` may arrive in any chunk and are re-emitted as markers at
the end. `OpenAICompatibleEngine` already assembles `delta.tool_calls` across
frames.

*Rule check:* the text shown is what the model wrote; the call is still parsed
off accumulated text; the gate is unchanged.
*Acceptance:* in a coding project, ask for a two-file change; watch prose
stream, a row appear, more prose stream, the next row. Measured: time to first
visible character on a tool turn drops from "whole reply" to the model's TTFT.
*Tests:* `test_native_tool_calls_reach_the_loop.py` fakes a non-streamed
response and must move to `iter_lines`; add `test_tool_turns_stream.py`
asserting (a) prose before a call is yielded before the call's row, (b) a
marker never appears in any yielded text, (c) nothing is spoken twice.

### A3. The stable prefix, second pass. *Built 19-20 Sept, not yet seen.*

Everything constant for a session goes **before** the conversation; only what
changes per turn goes after. Constant: identity, the core tool set and its
rules (D1), the project briefing. Per turn: recall, the ranked stranger
shortlist if any, the question. `test_prompt_prefix_is_stable_between_turns.py`
extends to a tool turn.

And the window's leading edge: `transcript.fit` drops turns in **blocks**
(a quarter of the budget at a time) rather than one per turn, so a long
session re-prefills once per block instead of every turn.

*Acceptance:* re-run the 12 Sept measurement (14B, ~2,900-token history,
one new turn) with tools offered; second-turn TTFT within 1 s of the no-tools
figure (3.9 s). On Tabby, same history: within 1 s of 2.8 s.

### A4. Reload policy. *Built 19 Sept, not yet seen.*

`keep_alive` follows the window: 30 min while Zaram is focused, extended by
activity; `warm()` on focus after idle so the reload happens while the person
is typing, not after they press Enter. Does not fix SATA; hides it where it can
be hidden. Settings › Models already shows what is resident.

*Acceptance:* return after 40 min idle, type, send — first token within the
warm TTFT.

---

## Workstream B — the work is visible (claim 2)

### B1. A row for every step, on every turn. *Built 19 Sept, not yet seen.*

Yield `StreamEvent.step_start` / `step_complete` from `execute_step` for every
plan step, carrying a **plain-language verb and target** the row can print
without knowing the capability id: *Searching the web for "…"* · *Reading
bbc.com* · *Recalled 3 facts* · *Reading receipt.jpg* · *Writing invoice.pdf*
· *Drawing* · *Listing tools on github*. The verb table lives in one place
(`core/step_labels.py`) beside the existing `ToolCalls` verb table in the
frontend, and the two are one test away from drifting — pin them.

`chatClient.parseEvent` gains the two cases; `chatStore` records them in the
same list as tool calls, with `status: running | done | failed` and the
duration. `ToolCalls.tsx` renders them with the same row; a running row shows
a quiet spinner; a failed one keeps the amber mark and never folds — the same
rule `ToolCalls` already applies to refusals.

Recall gets a row too (*Recalled 3 facts*, opening to the citations) — it is
the one step every competitor hides and the one this product exists to show.

*Acceptance:* "what's the latest on the Fable outage" shows *Searching the web
for …* appearing before any prose, resolving to *Searched the web · 4 results*,
then *Reading …* for each page, then the reply — and after the reply, one
folded line: *Searched the web, read 2 pages ›*.

### B2. Rows between paragraphs. *Built 20 Sept, not yet seen.*

`chatStore` moves from `content` + `toolCalls[]` to an ordered `segments`
list: `{kind: 'text' | 'step' | 'notice' | 'plan', …}`. `MessageBody` renders
segments in order; the fold groups consecutive `step` segments into one line
when the reply is done. Transcript persistence keeps `content` as the joined
text (rule 7d: rows are working state and are not restored — same as
`reasoning` today, `chatStore.ts:243`).

*Acceptance:* a coding reply reads *"I'll look at the store first."* → row →
*"The reducer is in …"* → row → answer, in that order, and folds to prose plus
one line.

---

## Workstream C — the task list and the working pane (claim 3)

### C1. The checklist on every multi-step turn. *Built 19 Sept, not yet seen.*

The planner's own steps are a checklist too. When a plan has more than one
step, `StreamEvent.plan` is emitted with the steps as items (`todo`), and each
`step_start`/`step_complete` moves its item. `PlanCard` needs no change beyond
accepting items whose source is the planner rather than the model. A single
step never shows a list (a list of one is noise — `AGENT-UX.md`).

*Acceptance:* a research question shows *Search → Read → Answer* ticking.

### C2. The working pane, on click. *Built 20 Sept, not yet seen.*

A layer of the conversation, opened from a row, a checklist item, or a task in
Activity or Project; closed by the same click, Escape, or the orb. It reuses
`SourcePanelLayer`'s mounting and motion. **Never opens on its own** — the
maintainer's decision, 19 Sept, against the always-open bench that Manus uses.

Contents, by what was clicked:

| clicked | pane shows |
|---|---|
| a step row | the step's output (`StepOutput`), its diff and Revert if it wrote (`ChangeCard`), the app card if it started something (`AppCard`), and the egress entries this step caused |
| a checklist item | the rows that ran under it, in order, each expandable |
| a task (Activity, Project) | the whole checklist with status, every row, the final answer, *what remains* |

The egress rows need a correlation: `EgressGate` entries carry the request's
`correlation_id` today only where the tool loop passes it — verify in
`core/egress.py` and thread it where it is missing. If an entry cannot be
attributed to a step it is shown under the task, never guessed onto a row.

*Acceptance:* click *Wrote `src/theme.ts`* → pane with the diff, Revert, and
one egress line reading *nothing left this device*. Click a GitHub row → the
egress line names `client:github` and the bytes.

### C3. Tasks outlive the thread. *Built 20 Sept, not yet seen.*

`PlanRecords` already keeps a task per project for seven days. Activity lists
running and finished tasks (it is the log; this is the log of tasks), Project
lists its own; either opens the pane. A running task keeps running when the
conversation is left; returning shows it where it is.

---

## Workstream D — the model to its extent (claim 5)

### D1. For a tool-capable model, the model chooses. *Built 20 Sept, not yet seen; the size floor is provisional until D2.*

The single largest change in this plan, and the one recorded here because it
revises how tools are offered.

**Today:** the planner decides before the model reads the question.
**After:** for a model with `supports_tools`, a **core set** is offered on
every ordinary turn and the model decides whether to use any of it:

| tool | exists? | tier |
|---|---|---|
| `web.search` | **new** — a tool over the internet runtime's connectors, which today run only as a plan step | egressive; the runtime already passes `EgressGate` |
| `web.read_page` | exists | egressive |
| `knowledge.search` | exists as a step; expose as a tool | local |
| `memory.search` | **new** — deeper recall than the automatic five, by query, scoped like `_recall` | local |
| the code pack | exists | as today, only with a coding project open |
| `draw.draw_image` | exists | generative |
| ranked stranger tools | exists, budget 8 | as today |

The core set is **constant for a session**, so its rules are read once (A3).
The stranger shortlist is ranked once per session on the project's description
and first question, and re-ranked only on a TOOL-intent turn.

What the planner keeps: routing *between models* (unchanged — rule: embeddings,
not a generative call); the document path and its rule-9 refusal; the image,
translate and speech paths; and **everything for a model without
`supports_tools`**, which is the marker path exactly as today. Per model, a
flag `chooses_tools` (default on when `supports_tools` and the model is ≥ 14B
by the catalogue's size; off below, because small weights over-call — measured
in D2 before the default is set).

**The gate is untouched.** `McpRuntime.execute` calls `policy.decide` on the
tool actually chosen; the egress log logs every byte; a search still needs its
destination allowed in Settings › Privacy. A retrieval score still authorises
nothing — ranking chooses what the model *sees*, the gate what it may *do*.

*Acceptance:* on Qwen3.8-27B (Tabby) and qwen3-14b (Ollama), with no coding
project open: "hello" calls nothing; "what did the court say about AI chat
logs this month" calls `web.search` then `read_page` unprompted; "what's my
rate for Northwind" calls `memory.search` or answers from recall; "read
bbc.com" calls `read_page`. Each with rows (B1) and the checklist (C1).

### D2. The tool-choice eval. *1 day, before D1's default is set.*

Twenty questions, three models (14B, 27B, one cloud), the expected first tool
or *none*. Cheap, no scoring model, run by hand and recorded in `CODE-PACK.md`
slice 9's table. **Sets the size floor for `chooses_tools`** from a number
rather than a belief.

### D3. The window, used. *Verified 19 Sept — not a build item.*

The suspicion was that a Tabby model was being budgeted as a 4,096-token one.
It is not: `local_server_context_length` (`core/context_budget.py:312`) reads
the loaded window from a non-Ollama local server by name, fixed 7 September
after exactly that 32x error was measured. Settings › Models already shows
it. What remains is only to *confirm on screen* after D1 that a tool turn's
handoff (`_run_tool_loop`'s `budget.handoff_tokens`) is measured against the
65,536 and not a fallback — one reading in A1's timings.

### D4. Native calls on the cloud fan-out. *(coworker step 5, unchanged.)*

---

## Workstream E — thinking (claim 6)

### E1. The preamble tells the model not to reason about itself. *Built 19 Sept; measurement not taken.*

One line in `identity_preamble`, placed with the rules about self-description
(after the manner, so the true instruction is the last read — the ordering
`test_identity_stays_truthful.py` already pins): *"You already know what you
are; do not deliberate about it in your reasoning. Reason about the question."*

*Measurement, not assertion:* ten prompts on qwen3-14b with thinking on,
count occurrences of "Qwen" and "as an AI" in the reasoning before and after.
Recorded in `MILESTONES.md`; the pinned test is structural (the line exists,
in that position).

### E2. Collapsed by default, one line of the model's own words. *Seen 20 Sept; the on/off control built and measured the same day — 27B 4.3 s → 0.8 s, 14B 19.4 s → 0.3 s.*

`ReasoningPanel` collapsed while streaming and after. The line, in priority:

1. the checklist's current `doing` item, if there is one;
2. else the first sentence of the **latest paragraph** of the reasoning so far,
   at most 80 characters, ellipsised at a word boundary;
3. when done: *Thought for 12 s*, with (2)'s last value beside it.

Never a generated paraphrase — no second model call, and "never render
invented values" applies to a summary of the model's mind as much as to a
number. The full text stays one click away and is never deleted.

A per-conversation **Thinking: on / off** control beside the routing control,
because on a 27B thinking costs 10–40 s per reply and a person writing an email
does not want it. Verify whether `payload["think"]` already has a setting
behind it (`user_settings`) before adding one.

*Acceptance:* a reply with thinking shows one muted line updating as
paragraphs arrive, then *Thought for 14 s · "…checking the reducer first"*;
expanding shows the full text. No "I am Qwen" in the line on the E1 sample.

---

## Workstream F — starting, and what is offered (claims 4, 7)

### F1. A project from the composer. *Built 19 Sept, not yet seen.*

A message that names a folder that exists on this machine, with no coding
project open, gets an offer under the composer: *"That's a folder. Open it as
a coding project?"* — name prefilled from the folder, one button, created in
place and selected. Rule 7h exactly; Project remains where projects are
managed. The offer is a `notice` with an action, the same shape as the plan
card's Go; the model is not asked.

*Acceptance:* type "add dark mode to the app in C:\Zaram\frontend", press
Enter, see the offer, press it, watch the task start with tools offered.

### F2. Use-case tiles on the empty conversation. *Built 20 Sept, not yet seen.*

`starterTasks.ts` grows from three rows to the use cases the product ships —
*Code a project · Research something · Write a document · Handle email · Work
with GitHub · Draw* — each lit only by what the interface measured (the rule
already in that file), each putting a real prompt in the composer. Still
exactly three shown at once on a fresh install; the rest behind *More*, so the
screen stays calm. **Never a tile for something not seen end to end.**

### F3. Held asks and unattended runs land in Activity. *(coworker step 4.)*

The inbox. Activity already lists what happened; it gains *what is waiting on
you* at the top, each opening the working pane (C2). No badge, no count in the
sidebar, no re-engagement — a held ask waits.

### F4. Triggers. *(coworker step 4.)*

Time, a watched folder, an obligation coming due. Unattended runs never
self-approve. The Monday month's-picture is the acceptance.

### F5. The four missing capabilities. *October, after the above.*

- **Slides** — `python-pptx` (MIT), the same HTML-first pipeline; a week.
- **A browser** — attach a Playwright MCP server rather than build one;
  per-site consent, every navigation an egress entry; `read_page` stays the
  local, silent path. A week, mostly the consent surface.
- **Scheduled tasks** — F4.
- **The inbox** — F3.

---

## Workstream G — the daily driver (every claim, and the one `CLAUDE.md` puts first)

Added 20 September 2026, at the maintainer's request, wearing two hats: the
product designer asking *why would someone open this on a Tuesday in month
three*, and the architect asking *what has to be true underneath for that to
keep being the answer*. `CLAUDE.md` already gives the order — **usable daily →
useful because it remembers → indispensable because it acts** — and A–F build
the first step. G is the second and third, designed from a day rather than
from a feature list.

### The day it is designed for

Three people, one product, no seventh node. The freelancer with invoices, the
developer with a repository, and anyone who types for a living — the same
person on different afternoons.

| moment | what happens | what it rests on |
|---|---|---|
| **08:30, opening the laptop** | Activity, once: what ran overnight, what is waiting on a *Go*, which obligations fall due this week. Empty when nothing is — Zaram speaks first only with something real. | F3, F4, G6 |
| **10:15, in Outlook, a client's mail selected** | **Alt+C.** "Reply — we agreed 30 days, they are asking for 45." The draft knows the client, the terms and the last three exchanges, says which of that it recalled, and goes back where the selection came from. Under a second to the first word. | the ambient surface (built), A1–A4, G2 |
| **11:40, a paragraph selected anywhere** | Alt+C: *rewrite · shorter · translate · summarise · explain*. Five verbs, no chat, no window to find. Local, nothing leaves. | G3 |
| **14:00, at the desk** | "Add the export button to the app in `C:\foo`" — a list that ticks, rows between the prose, a pause before the write with the diff, one *Go*. The second time the same shape of task comes, Zaram already has the procedure. | A–F, G5, G7 |
| **16:30** | "Chase Northwind for the March invoice." Plan, the draft, the send held — *once · this session · always for this address · deny*. Chosen once; never asked again for the same class. | G4, G6 |
| **Monday 09:00** | The month's picture, run while the window was closed, with what it read and what left the machine. | F4, G6 |
| **Any time** | "What did we decide about the rate?" — the actual line, dated, from the transcript, with the fact beside it from memory. | G2 |

Five design rules, each derived from one of those rows and each checkable:

1. **The first word within a second, or a row within 300 ms.** A person waits
   for progress, not for silence. (A1–A4; measured in `timing`.)
2. **Never the same question twice.** Consent once per destination and data
   class, remembered, visible in Settings, revocable. Forty dialogs a day is a
   product nobody opens on day two. (Rule 7j, G4.)
3. **Every reply says why it knew.** One line: what was recalled and from
   where, what answered and where it runs. The *"it remembered"* moment is the
   retention mechanism, and it only lands when it is visible. (Rule 2, G2.)
4. **The app is not the destination.** For the five daily jobs the person
   stays in Outlook, Word, the browser; Zaram comes to the selection and
   leaves. The main window is for tasks, memory and the record. (G3.)
5. **Nothing nags.** No streaks, no "you haven't asked me anything", no
   re-engagement. Activity fills only with things the person caused. (Rule
   against engagement mechanics; F3.)

### The items, in the order daily use ranks them

**G1. A tool server sees only what it was given.** *Built 20 Sept, tested
at the process boundary; not yet re-run against the real server list.* Read from
`runtimes/mcp/client.py:214` on 20 September: `_child_env` starts from
`dict(os.environ)`, so every attached server inherits **`ZARAM_API_SECRET`** —
the credential that authenticates `GET /memory`. A third-party MCP server can
read the whole Spine. The 15 September fix was right about `PATH` and
`SYSTEMROOT` and did not subtract. The base becomes what a process needs to
start (`PATH`, `SYSTEMROOT`, `TEMP`/`TMP`, `USERPROFILE`/`HOME`, `COMSPEC`,
`LANG`/locale, `APPDATA`/`LOCALAPPDATA` for Node) plus the server's own `env`
block; nothing whose name contains `SECRET`, `TOKEN`, `KEY` or `PASSWORD`
crosses unless the block names it. *Seen:* a server that prints its
environment shows no `ZARAM_API_SECRET`; Blender and GitHub still start.

**G2. Memory that answers the daily question.** *Three days; build without
GPU, measure with.* Two halves, one item, because they are the same promise —
*it remembered*:

* *Lexical retrieval beside the vectors.* `bm25s` (MIT, numpy/scipy) over the
  same facts and chunks the Spine embeds, fused with the dense list by RRF —
  `Σ 1/(k + rank)` — for **ordering only**. Membership and citation stay on
  the cosine; a test asserts the fused score never meets the citation floor.
  The acceptance is rule 9's own case: "write that up as a proposal" after
  the Northwind conversation retrieves Northwind. Client names, invoice
  numbers and reference codes are what a person says every day and what an
  embedding is worst at.
* *The transcript as a tool.* `history.search` over what Activity already
  keeps: FTS5 in the standard-library `sqlite3`, verbatim results, dated,
  retention honoured (a pruned turn is not searchable). A read tool — nothing
  it returns enters the Spine, so 7d holds and no new store is added.

*Seen:* "what did we decide about the rate" answered with the line and the
date; the recall eval's before/after on the rule 9 question.

**G3. The five verbs on the selection.** *Two days, no GPU for the build.*
The ambient surface already reads the selection on **Alt+C**. What it lacks is
the five jobs a local 8–14B does well as *verbs* rather than as a chat:
rewrite, shorter, translate, summarise, reply — plus explain. Each is a
one-keystroke choice on the panel, answers from the resident model, and puts
the result on the clipboard (insertion into the host app stays out: pasting
is the person's act, and it is the one Superhuman Go gets wrong by doing it
for them). Memory is carried — *reply* knows the sender if the Spine does —
and the panel's own egress line says whether anything left. *Seen:* a
paragraph in Word, Alt+C, *shorter*, paste; the sender's name recalled on
*reply* with the source named.

**G4. Once · session · always · deny, and a floor.** *The conversation rung
and the floor built 20 Sept (coworker steps 2–3); the standing-rules page
under Settings and the circuit breaker are still to build.* The held-tool card offers the four;
*always* writes a standing rule under Settings beside Tools, revocable, keyed
by destination and data class (an address, a repository, a folder) so the
grant is legible; an allowlist entry may name a danger rule rather than a
command. The floor is a written list no mode lowers — money, deletion outside
the trash, mass-send, privacy-rule changes — tested by attempting each under
every mode. Three denials pause the run and say so in Activity. *Seen:*
approve a send to one address once, watch the second not ask; try a mass-send
under *always*, watch it refuse.

**G5. The tool-choice eval, on BFCL's scorer.** *Run 20 Sept: 27B 20/20,
14B 19/20, no over-calls; `CODE-PACK.md` 9b.* Twenty Zaram questions in BFCL's format plus its *relevance
detection* slice — the right answer is *no tool* — scored by its AST matcher
(`bfcl-eval`, Apache-2.0), run on the 14B, the 27B and one cloud model.
Sets `CHOOSES_TOOLS_MIN_BYTES` from a number; recorded in `CODE-PACK.md`
slice 9. The go/no-go stands: over-calling on more than one question in five
keeps the planner primary on that model. *Seen:* the table.

**G6. Two official servers, one real task, then the triggers.** *The
triggers half built 20 Sept (coworker step 4: `core/triggers.py`, seen
live once); the real GitHub/mail task still needs the maintainer's tokens.
Social media and YouTube fit the same shape — an attached API-backed
server, a scheduled post as a trigger the gate holds, replies to strangers
draft-only unless granted by name — and want a catalogue of known servers
under Settings → Tools, not a build.* `github/github-mcp-server` (MIT) and
`microsoft/playwright-mcp` (Apache-2.0), and a mail server, attached rather
than built. One task end to end — the plan, the pause, the Go, the egress
entries addressed to each. Then the scheduler runs the month's picture and
the seven-days-out reminder draft, held in Activity, never self-approved.
The Playwright half is F5's browser with per-site consent as the only new
surface. *Seen:* the Monday picture that ran with the window closed.

**G7. Procedural memory — skills the system writes.** *A week, after G6,
because a skill is written from a real task.* Zaram remembers facts; it does
not remember *how it did something*, and for a local 14B — whose weakness is
planning, not execution — that is the larger half. After a multi-step task
finishes, after a dead end is resolved, or after a correction, Zaram drafts a
skill: *When to use / Procedure / Pitfalls / Verification*, lessons not logs,
a pitfall as a rule plus one clause of why. It lands as a card, origin
`zaram-generated`, provenance to the session and the correction, correctable
and deletable like any fact (rules 4, 7b, 7d, 7e, 7f all apply unchanged).
Listed to the model by name and description, loaded whole only when it asks —
progressive disclosure, so a hundred skills cost ~3k tokens, not the window.
A skill is prompt text and therefore third-party text: never silently
installed, never widening a permission. *Seen:* the second "chase an invoice"
runs on the procedure the first one wrote, and the card that says so.

**G8. TabbyAPI's native calls.** *Done 20 Sept — two keys, the second being
`use_as_default`; measured 3.4 s with a parsed call.* `tool_calls` are
null unless `tool_format` is set in Tabby's config — the call comes back as
text in `content`, silently. Check, set, pin with a live test skipped when
Tabby is down. Without it D4's native path on the maintainer's own server is
the marker path wearing a different name.

**G9. The memory number.** *One day, needs a model.* LongMemEval's 500
questions through recall, reported with the model and the environment
stated. LoCoMo stays internal (CC-BY-NC). `CLAUDE.md` says benchmark memory
"not by feel"; this is the first time it is.

### The order, revised

GPU-free first, in the order the day ranks them; the rest the moment the GPU
is free, after the *Look* list.

| when | build | what a person sees |
|---|---|---|
| **Now, GPU held** | G1, G2 build, G3 build, G4, G5 scaffold | Nothing yet — the environment test, the fused-ranking test, the five verbs and the four-option card all pinned by tests that assert the contract. |
| **GPU free, day 1** | the *Look* list; G8 | Everything built since 19 September, seen; Tabby's native calls confirmed or fixed. |
| **GPU free, days 2–3** | G2 measured, G3 seen, G5 run | Alt+C → *shorter* → paste; the rule 9 question retrieving Northwind; the tool-choice table and the floor it sets. |
| **Week after** | G6 | The GitHub task at the pause; the Monday picture that ran while closed. |
| **Week after that** | G7, G9 | The second task on the first task's procedure; the LongMemEval number. |

### What this does not do, said so nobody expects it

* **It does not make the local half smarter.** A 14B answers the five jobs
  fast and well and hands hard reasoning to a key the person added. The
  reply says which happened. A person expecting frontier reasoning from the
  local model will feel the difference, and the product says so rather than
  hides it.
* **It does not put the result into the host application.** Clipboard, then
  the person's paste. The one interaction Superhuman Go automates is the one
  that reads as the product acting in your document.
* **It adds no surface.** Verbs live on the ambient panel; rules under
  Settings beside Tools; the inbox is Activity; skills are memory.
* **It adds no store without a retention answer.** The transcript index is a
  view over Activity's retention; skills are facts and prune with them.

### How daily use is measured, before the fifteen-person test

Counted locally, sent nowhere, and **not shown as a running score** — a
count of days opened is a streak, and streaks are the engagement mechanic
`CLAUDE.md` forbids. It sits under Settings as a plain table the person can
read and a tester can choose to copy into a reply. Days opened per week;
ambient summons per day; tasks that reached *Go*; replies whose recall line
named a source. The number that decides whether G worked is the second: **a
person who summons the panel three times a day has a habit; one who opens
the window once a week has a tool.** Everything in G is aimed at the first.

---

## The order, with what is seen at each checkpoint

Working days, one maintainer plus sessions. Dates assume the alpha page flips
on 21 September and the tester email is settled first; none of this lands on
`main` before the tag.

| when | build | checkpoint — what a person sees |
|---|---|---|
| **Week 1** (built 19 Sep, to be *seen* 22–26 Sep) | A1, A2, B1, E1, E2 | A research question shows *Searching…* and *Reading…* rows before any prose; a coding turn streams prose between rows; thinking is one muted line. Six timings per reply in Activity. |
| **Week 2** (29 Sep–3 Oct) | D2, D1, A3 | On the 27B with no project open, a current-events question searches on its own; second-turn TTFT on a tool turn within 1 s of a plain turn; the handoff budget reads 65,536 on Tabby. |
| **Week 3** (6–10 Oct) | B2, C1, C2, F1 | Rows sit between paragraphs; a task is a ticking list; click a row → the pane with diff, Revert and egress; a folder in a sentence becomes a project. |
| **Week 4** (13–17 Oct) | C3, F2, A4, coworker step 1 (the real GitHub task, end to end) | Tasks in Activity and Project, resumable; six tiles; one real task through GitHub watched at the pause. |
| **Weeks 5–7** | coworker steps 2–4 (OpenWorker modules, standing rules, triggers + inbox), slides | A Monday month's-picture that ran while the window was closed. |
| **Week 8** | browser MCP with per-site consent | "Book nothing, read everything": a page-by-page task through an attached browser, every navigation logged. |

The go/no-go after Week 2 is D2's table. If the 14B over-calls at more than
one question in five, `chooses_tools` defaults off below the 27B and the
planner path stays primary there — the product does not get worse on small
weights to get better on large ones.

---

## Estimates, stated with their uncertainty

Weeks 1–3 are engineering against code that was read line by line for this
plan; the estimates there are within a day each. Week 4 onward depends on
things not yet measured — the eval, the real GitHub task — and the coworker
milestone's own estimate ("four to six weeks after the 21st for steps 1–4")
stands. Slides and the browser are a week each *if* nothing about the consent
surface surprises, and the consent surface is where surprises live.

---

## What is not in this plan, and why

- **A second model call to summarise thinking.** Costs a call per reply on a
  product whose thesis is speed, and renders a paraphrase as if it were the
  model's mind.
- **An always-open bench.** Declined 19 Sept; the pane opens on click.
- **A seventh node.** Tasks are Project's, the inbox is Activity's, the pane
  is the conversation's.
- **A reviewer model that approves.** OpenWorker's; a model's judgement is
  never the permission here.
- **Video, phone, hosted deploys, unattended browsing of accounts.** Their
  cost of goods and their liability.
- **Hiding the model.** The line under a reply still names what answered and
  why; a model switch is the demonstration, not a leak.

---

## Risks, named

1. **Small models with five tools over-call or call badly.** D2 measures it
   before D1's default is set; the marker path stays as the fallback per model.
2. **The holdback withholds too long inside code.** A reply full of `<` and
   `[` releases each within a token; the worst case is one token of delay per
   bracket. A reasoning stream that *mentions* `[TOOL_CALL]` stops the visible
   text at that point — the rest arrives when the round ends, which is today's
   behaviour, not a regression.
3. **Prefix caching differs by server.** Ollama and ExLlamaV3 both cache by
   prefix (measured 12 Sept); llama.cpp's server does with `cache_prompt`.
   A3's acceptance is measured on both of the maintainer's servers.
4. **The summary line reads as the model speaking.** It is muted, labelled
   *thinking*, and is the model's own words — the same posture `NoticeCard`
   takes to keep Zaram's bookkeeping out of the model's voice.
5. **Tests that assert the scaffolding.** Every acceptance above is a thing
   seen on screen; the suite pins the contract afterwards, never instead.
