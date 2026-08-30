# Zaram — Milestones

Ordered. Each has an acceptance criterion phrased as something you can *see*, not
something that passes. "Tests green" is not done; "I ran it and watched X happen" is.

Read with `CLAUDE.md` (the contract) and `docs/UI-SPEC.md` (the interface).

**This file is the handoff.** A new session should be able to read it and know
where the work stands without being told. Keep the Current state block below
accurate — it is the first thing anyone reads.

---

## Current state — 30 August 2026

*The latest work is first. Earlier sessions follow below.*

### The session's work is committed, and a skip was not what it said — 30 August

Committed on `Zaram-V0.1`, grouped along file boundaries, each message
written against the diff it describes rather than from the handoff, none
pushed. Where one file carried two changes — `execution_engine.py` has both
the conversation carry-forward and the search-notice fix, `html.py` both the
CV renderer and the theme wiring — the commit names both rather than claiming
an atomicity it does not have. The session that produced the work left 38 files
uncommitted; this is that surface read and landed rather than built on.

Re-measured rather than carried over: backend **2954 passing, 21 skipped,
2m32s**; frontend **362 passing across 41 files**, `tsc` clean. The condition,
because a number without one is not a measurement: Ollama up holding `bge-m3`
and `gemma4:26b-a4b`, TabbyAPI serving on 127.0.0.1:1234, so the discovery
branches executed.

**Reconciling the skip count found a test that had never run.**

`test_vision_gate.py` reported *"no Ollama models installed"* on a machine
holding two of them. Two causes, and both land in the same place:
`ProviderManager.refresh` is a coroutine and was called bare, so discovery
never happened — the only trace anywhere was a `RuntimeWarning` in the tail of
the suite output; and `ProviderManager()` constructs an **empty**
`ProviderRegistry`, so even correctly awaited there was nothing registered to
scan, the real path registering `OllamaAdapter` in `providers/runtime.py`.
Both produce an empty model list, and `if not local: pytest.skip(...)` read
that as a statement about the hardware.

So a check whose docstring says it exists precisely because *"`supports_vision`
could be correct in every fixture and still be `False` for every real model"*
had never executed one assertion, and its claim to have caught that failure on
its first run cannot be true. It is the `docs/KNOWN-FAILURES.md` shape again —
*"the suite was skipping, not passing"* — arrived at from the other direction,
by a count that would not add up.

The assertions were empty in any case: `any(x) or all(not x)` is a tautology
over booleans and passed whatever discovery returned. The replacement is the
real contract — each discovered model's `supports_vision` compared against
Ollama's own `/api/show` capabilities, which is the enrichment step that does
the work, since `/api/tags` omits vision entirely. Both polarities are
exercised on this machine: gemma4 reports vision, bge-m3 does not. Checked by
inverting the assertion and watching it fail, then pass again on revert.

The capability was never broken. The instrument was, quietly, for its whole
life.

> **Five skips still do not reconcile, and they are left named rather than
> guessed at.** The previous handoff recorded 2959 / 16 against this run's
> 2954 / 21 — identical totals, so five tests that ran then skip now, beyond
> the one fixed above. Every skip is environment-gated: `test_recall_at_scale`
> (9, `ZARAM_SCALE_EVAL=1`), `voice/test_kokoro_onnx_backend` (7, wants
> `onnxruntime`, `onnx` and `misaki`, of which `onnx` is missing here),
> `test_identity_holds_across_models` plus `test_extraction_across_models` (3,
> `ZARAM_LIVE_MODELS=1`), and `test_memory_traffic_review` (2, no memory
> runtime in-process). None of those families is five, which is why this is
> recorded as unexplained rather than attributed. One run with the gates named
> settles it.

> **`providers/model_manifest.py` and `models.manifest.json` are committed and
> have no caller and no tests.** Half of the model-pull executor; the endpoint,
> the progress UI and the offer beside Settings' oversized-model warning are
> not built. Committed as work in progress rather than left loose, and said
> plainly here because this codebase's base rate for complete, tested,
> unreachable subsystems is fifteen and counting. It is dead code today.

### A citation now says which site it came from — 30 August

A cited page rendered as a globe and a number, so four web sources were four
identical glyphs and the one fact that separates them — who published the
page — was reachable only by opening the panel on each in turn. A source row is
scanned, not read.

`sourceHost` / `hostOf` in `chatClient`, and `SourcePanel`'s own inline parse
now calls the shared one: two implementations of *"which site is this"* is how
a panel and the chip beside it come to name different things about one page.
`www.` is dropped, subdomains are kept — `docs.example.com` and
`blog.example.com` are not the same publisher — and a malformed URL yields no
name rather than a guessed one.

> **Favicons were asked for and declined, and the reasoning is the useful
> part.** Claude and Gemini show them; here the same feature is banned twice
> over. An `<img src="https://site/favicon.ico">` is a request the *renderer*
> makes, which `EgressGate` structurally cannot see — precisely what
> `check-no-remote-assets.mjs` exists to forbid — and the common shortcut
> (`google.com/s2/favicons`) hands Google the domain of every page the user
> cited. Worse, it fires on **render**: reopening a conversation next week
> pings the publisher again, so it reports not that the page was read once but
> every time the citation was looked at.
>
> It is buildable honestly — fetch at search time, backend-side, through the
> gate, to a host the user has already permitted, cache as a data URI, serve
> locally — and that is the route if it is ever wanted. It was not taken now
> because the domain is the better signal anyway: legible where a 16px mark is
> a guess, and it does not lend a content farm the authority of a good logo.
>
> `CitationChips.test.tsx`, 9 cases, three of which guard what naming the site
> must *not* change — the colour still encodes egress rather than category, the
> summary still leads with the split, and **rendering a chip touches the
> network zero times**, asserted by spying on `fetch`. That last one is the
> property a favicon would break, written down so the next person to want one
> argues with a test rather than with a comment.

### A refused search is not an empty web — 30 August

Two defects, both found by the maintainer pressing the button built earlier the
same day, and the second was mine twice over.

**The offer was a refusal with no remedy.** `setWebSearch(true)` turns the
planner on and grants nothing. The search then went to `duckduckgo.com`, which
had no egress rule, default-deny refused it, and the reply said *"web search
ran but returned no results"*. Nothing had failed except that Zaram asked the
same question twice and answered it "no" the second time — which is the exact
shape the 29 August handoff recorded about the image consent, one day later.

Rule 7j settles it almost verbatim: *"Requiring a second, separate host rule
afterwards asks the same question twice and reads as the product being
broken."* Pressing a button that says the question goes to a search engine
**is** the decision about that destination, so `enableSearchAndRetry` now sets
the host rule too — reading the host off `/search/web` rather than deriving it,
because that endpoint already answers the question. Still per-host, still
visible in Settings, still revocable, and the kill switch still beats it. The
card's disclosure names both halves rather than one.

**And the sentence itself was false.** `result_count` cannot tell a refusal
from an empty web: both arrive as an empty list. `reached_the_web` in
`search_context.py` reads `provider_status` and answers the other question —
did anything leave this machine — with three states, because an unreadable
payload is evidence for neither claim. The engine now says *"could not reach
the web — the search engine is not a permitted destination yet"*, or *"ran but
returned no results"*, or, when it cannot tell, only that no live sources were
used. The local connector set is the closed one deliberately: a new web
connector nobody adds to a list counts as web, so forgetting produces the
cautious error rather than telling a user their question stayed home when it
did not.

`test_a_refused_search_is_not_an_empty_web.py`, 9 cases. `EMPTY` in
`test_search_reaches_the_model.py` was rewritten to carry `provider_status`,
which is what the runtime actually emits — the old fixture could not have
distinguished the two states it was asserting about.

> **Verified by repeating the failure.** Search off, `duckduckgo.com` reset to
> deny, backend restarted, the same question asked and the button pressed:
> `search/web` returned `on: true, host_policy: "allow"`, the egress policy
> gained `duckduckgo.com: allow`, `hosts_seen` grew by freightwaves,
> logupdateafrica and nytimes, and the reply came back `4 sources · 4 sent to
> the web` citing DP World's $1b Lagos port talks. A third defect went with it:
> the card sat on "Turning it on…" forever because its phase was never reset —
> notices are not persisted, so the stale card was a live component, and a
> reload was the user's only escape.

### The reply can be stopped — 30 August

`chatStore.cancel()` aborted the in-flight request on clear, on resume and on
the next send, and **nothing in the interface called it**. The one case it was
never wired to was a person deciding, mid-answer, that this one is going wrong.
On a machine where an oversized model takes minutes per reply that is not a
convenience; it is the difference between watching three minutes of a wrong
answer and asking a better question.

Send becomes stop while streaming — one control, because they are the same
decision at two moments. Verified with a real click against gemma4: the
button's accessible name changed to *Stop answering*, pressing it returned the
composer, and the network log recorded `POST /chat → net::ERR_ABORTED`. The
abandoned question stays in the transcript rather than vanishing.

**Not verified, and not claimed: whether the backend stops generating.** The
client abort closes the stream; whether Ollama halts is a separate question,
and the evidence points at no — the next reply was unusually slow, consistent
with the abandoned generation still holding the card.

> **A live defect found while looking at the ambient panel.** It read
> *"Thinking. Working remotely."* while a local model on 127.0.0.1 was
> answering. `describeSystem` consulted `routing.mode` — the machine's overall
> *posture*, which is non-local as soon as any cloud provider is configured —
> rather than the locality of the thing actually answering. A false egress
> claim, on the surface `CLAUDE.md` singles out as the one where the disclosure
> matters most. The correction was already written twenty lines above in the
> same file, for the persistent bar: *"mode describes the machine's overall
> posture and this must describe the thing that actually answers."* Half of it
> had landed. Unknown locality now claims neither direction, following
> `locality_of`.

### Documents stopped looking generated — 30 August

Reported as *"generated documents look subpar"* since 28 August and undiagnosed
because nobody had looked at the file. The composer was never at fault.

**The design existed and stopped at the HTML boundary.** Measured by unzipping
a generated proposal: body Calibri 11pt, headings in `#365F91` and `#4F81BD` —
Word 2007's blues — page US Letter with 1 inch top and **1.25 inch** sides,
which is the Word 2003 default, and every table drawn with "Table Grid", a
border on all four sides of every cell. Meanwhile the HTML carried A4 with
print margins, a serif face, uppercase letterspaced section labels, hairline
rules and one accent deliberately not blue. A `.docx` is not rendered from that
CSS; it is rebuilt block by block, and every block took the stock style.

`artifacts/theme.py` holds the tokens once and both renderers read them.
`artifacts/export/word_theme.py` applies them: A4 at the stylesheet's margins,
Georgia at the shared body size, section labels in the sans face with real
letterspacing, a footer with `PAGE`/`NUMPAGES` fields, and table borders that
rule between rows instead of boxing every cell. Styles rather than direct
formatting, so the file stays editable and the user's next paragraph inherits
the design. `_reader` now carries `numeric_columns` back off the `class="num"`
the stylesheet already emits, so money right-aligns in Word as it does in the
PDF. `test_word_carries_the_design.py`, 14 cases reading the XML rather than
trusting the API; 9 fail with the theme removed.

**A CV is a kind now, not a longer document.** `ArtifactKind.CV` with its own
extractor, renderer and stylesheet: no masthead — a CV's letterhead is the
person's name — no metadata grid, dates in their own column in tabular figures,
entries that never split across a page, skills as a separated line, and empty
sections omitted because a bare "Education" heading says something untrue about
the person. It refuses rather than invents: no name, or nothing to put on it,
and it stops. `_kind_from` now matches on word boundaries for every keyword,
because `"cv"` is two letters and `test_intent_word_boundaries.py` already
records what `in`-matching cost when "invoice" contained "voice".
`test_a_cv_looks_like_a_cv.py`, 20 cases.

**An attached document can be a shape to follow.** `attachments/exemplar.py`
reads a reference's outline and puts it under that file in the prompt with one
instruction: follow its sections, write the content from what the user said,
**never copy its sentences or carry over its names, figures or dates** — without
which a model asked to write one "like this" returns the reference with the
names changed. The outline is read from the whole file, never the excerpt,
because selection ranks passages against the question and will drop the very
headings it is made of. Heading detection fails towards *fewer* headings: a
missed one makes a thinner exemplar, an invented one becomes a section the
author never had. `test_a_reference_document_shapes_the_new_one.py`, 13 cases.

> **A test of mine passed against broken code, again.** The long-document case
> went green with the outline read from the *excerpt*, because the excerpt
> happened to contain the headings. The fixture was rewritten — the question's
> rare terms now appear once, deep in filler, nowhere near a heading — not the
> assertion. It fails correctly now.

Two smaller things went with it. The preview sheet was `content-box`, so it
rendered 945px wide where A4 is 794 — the margins added *outside* the paper, on
the one surface whose job is to show what will print; measured in the browser,
now exactly 794. And the frontend's `ArtifactKind` union was missing `deck`,
which had shipped on the backend weeks earlier, so a deck's card had no icon
and no colour: adding `cv` broke both copies of the map at compile time, which
is how it was found.

**PDF is still unavailable on this machine and the reason is unchanged.**
`pip install weasyprint` now succeeds in the backend venv; the native GTK
libraries are what is missing, which on Windows means an MSYS2 installation.
Whether the installer bundles it is a Phase 0 decision, not a bug, and it was
left for the maintainer.

### A follow-up knows what it follows — 30 August

**Measured before it was fixed**, one model, one session, seconds apart:

    "What is the capital of Portugal?"        -> "Lisbon."
    "And roughly how many people live there?" -> "I don't have the place you're
                                                 referring to in this
                                                 conversation."

Everything needed was already built. `_session_turns` recorded the exchange,
`seed_session_turns` rehydrated it across a restart, `core/transcript.fit`
trimmed it by whole turns and `as_prompt` rendered it — and the only caller was
the *document* branch, so none of it reached an ordinary reply.
`core/transcript.as_prompt` and `as_messages` had tests and no production
caller at all: the repository's signature failure, on the daily-driver path.

`_augment_with_conversation` puts the recent exchange in the same system-prompt
slot recall already uses, so no engine changed. Bounded twice —
`CONVERSATION_TURNS` caps how many exchanges are eligible,
`CONVERSATION_SHARE` caps what they may spend against the smallest window Zaram
assumes, and `fit` drops oldest-first and whole turns only. The document branch
keeps its own framing because rule 9's refusal hangs off `context_resolved`,
which only that path produces; never both, or the same exchange arrives twice
under two headings.

`test_a_follow_up_knows_what_it_follows.py`, 12 cases; removing the one new
line fails 6 of them.

> **Verified live, and across a provider switch.** Asked TabbyAPI/Qwen *"What
> is the capital of Portugal?"*, then asked Ollama/gemma4 in the same session
> *"And roughly how many people live there?"* — which answered with Lisbon's
> city and metropolitan populations. The buffer is keyed on the session and
> carries no model, so this is the same measurement the handoff had offered to
> run for document requests, done for every reply instead.
>
> **What it does not guard**, checked by breaking it: changing `_recall`'s
> `session_id=None` to pass the session through leaves every test green,
> because session membership is a *ranking* signal in `MemoryRankerImpl` and
> never a filter.

### The claim at the centre of the product was never measured — 29 August

**"One memory, whichever model answers" is what Zaram is for, and nothing in
the repository asserted it.** The pieces each had cover —
`test_provenance_invariant.py` proves recall reaches *the* model,
`test_memory_supersession.py` proves a corrected fact stops being recalled,
`test_engine_routing.py` proves a model name reaches the right engine — and the
property that joins them, which is the one a user would call memory, had no
test and had never been run end to end on two real models.

It has now been both. **Run first, on this machine, with two live providers:**

| | |
|---|---|
| Fact stated to **TabbyAPI / Qwen3.8-27B**, session `turn-one` | stored, one record |
| Asked of **Ollama / gemma4:26b-a4b**, session `turn-two` | recalled, **cited**, relevance **0.821**, answered *"You mentioned earlier that your day rate for Harbour Lane is 425,000 naira…"* |
| Second fact stated to **gemma4**, session `turn-three` | stored |
| Asked of **Qwen**, session `turn-four-b` | recalled, cited, relevance **0.779**, answered from it |
| `DELETE /memory/{id}`, then re-asked of Qwen | **0 sources**, and the reply says it does not have it |

Four different session ids, two different engines — `OllamaEngine` and
`OpenAICompatibleEngine` through `LocalDispatchEngine` — one Spine. Measured
with the real `bge-m3` embedder against a scratch `ZARAM_DATA_DIR`, so no
number here is a fixture's. gemma4 took **2 m 55 s** to answer, which is the
`oversized` warning behaving as designed rather than a fault.

`tests/test_memory_holds_across_providers.py`, 10 cases, is the durable half:
capture under one provider, recall under the other, in both directions, plus
correction and deletion crossing the same boundary. Two things in it worth not
re-deriving:

* **The floors are the fixture's, not the product's.** It embeds with the
  `hash` backend so the suite needs no Ollama, and 0.42 is a bge-m3 number that
  means nothing there. The fixture runs at 0.35, and
  `test_an_unrelated_question_recalls_nothing` is what stops the file measuring
  its own permissiveness.

  **The first version of that number was measured on the wrong quantity**, and
  it is this codebase's recurring error in miniature: it quoted the embedding
  cosine (+0.064 for the matching question), when what the floor is compared
  against is `MemoryResult.relevance` out of the hybrid retriever — **0.40**,
  because under the hash backend `_keyword_match` carries the retrieval and the
  cosine carries nothing. Same fixture, same run, two numbers an order of
  magnitude apart, and only one of them is the one being thresholded.
* **Falsified before it was kept.** Dropping `system_prompt` on the cloud route
  fails two cases. Making `_recall` session-scoped fails **none**, and that is
  recorded in the test rather than glossed: session membership is a *ranking*
  signal in `MemoryRankerImpl` and never a filter, so the test asserts the
  outcome and not the argument that currently produces it.

> **What the claim does not cover, found while measuring it.** Recall carries
> **facts**; it does not carry **the conversation**. `_augment_with_recent_turns`
> is called from exactly one place — behind `if self._is_document_request(prompt)`
> — and `OpenAICompatibleEngine._body` sends one system message and one user
> message with no history. Observed, same model, same session: *"What is the
> capital of Portugal?"* → "Lisbon", then *"And roughly how many people live
> there?"* → **"I don't have the place you're referring to in this
> conversation."**
>
> That is not a cross-model gap; it is a single-model one, and switching models
> mid-thread only makes it visible. It sits directly under the daily-driver
> argument — an assistant that cannot follow up is not one somebody opens on a
> Tuesday — and the machinery already exists: the buffer is bounded, seeded
> from stored transcripts, and fitted to the answering model's window by
> `core/transcript.fit`. What is missing is the decision to put it in front of
> an ordinary reply, which is a design call and is **not** made here.
>
> A second finding from the same probe: *"Now add ten to that number."* was
> classified as a **document** request, so it took the recent-turns path — and
> silently wrote a `.docx`. It answered correctly, for the wrong reason, and
> produced a file nobody asked for.

### The Advanced type-in model field — queue item 6 is finished — 29 August

The last third of the model picker. Its hard condition shipped last session:
`_unplaceable_model_refusal` refuses a name the catalogue cannot place before
dispatch, so a typed string can no longer fall through to Ollama and return
`model 'anthropic/claude-sonnet-4.5' not found` from a server the user never
named. What was left was the field and the sentence beside it.

`frontend/src/components/settings/AdvancedModelField.tsx`, inside *Which model
answers*, behind a `<details>` — the third of `CLAUDE.md`'s three tiers, "so a
non-technical user never sees the third".

Three rules, each one a friendlier version of this field would break:

* **The terms are stated while the user is choosing**, from the discovered
  model's own `data_policy`, in `CloudKeyForm`'s shape rather than behind a
  disclosure. A `:free` name typed here says outright that prompts are logged
  and may be trained on.
* **`selectableByDefault` is not this field's business.** It stops *Zaram*
  routing to a provider whose terms are unknown; it must never stop a person
  choosing one knowingly.
* **A typed name widens nothing** — no host rule, no connection, no egress —
  and the field says so under the button rather than leaving a saved name to
  imply it.

**And it never calls a name imaginary on the strength of not having looked.**
Three states, three different sentences: a name that resolves gets its terms; a
name that does not, *with discovery run and non-empty*, gets "Zaram cannot
place… it will refuse to send rather than guess"; and with no discovery it gets
"Zaram has not looked for models yet". That mirrors the backend guard, whose
own rule is that every uncertainty resolves to no refusal. Falsified: removing
the `models !== null && models.length > 0` condition fails two cases.

`AdvancedModelField.test.tsx`, 14 cases.

> **Seen on screen, which the handoff asked for.** Vite on 5173 against a
> backend on a scratch `ZARAM_DATA_DIR` with a known secret — the browser-tab
> route `docs/RUNNING.md` documents — in the Browser pane, screenshotted at
> each step: the disclosure open with the field and its permits-nothing line;
> `anthropic/claude-sonnet-4.5` typed **before** discovery showing the
> not-looked sentence; the same name **after** *Look for models* showing the
> amber cannot-place sentence; `gemma4:26b-a4b-it-q4_K_M` showing "Runs on this
> machine. Nothing is sent."; and *Use this model* pressed, after which
> `GET /routing/preference` returns `"default_model":"gemma4:26b-a4b-it-q4_K_M"`.
> The typing and the Settings navigation were real pointer and keyboard events;
> two clicks on orbiting nav nodes and on the buttons had to be dispatched
> through `javascript_tool`, because the landing nodes move under the cursor
> between the screenshot and the click.

### The third door, and it was the one that had been measured — 29 August

The 28 August handoff predicted it in one sentence: *"anywhere that treats 'no
model named' or 'cannot place this name' as **therefore Ollama** is the same
bug waiting."* Two had been found. This was the third, and unlike the others it
had already been observed — asking for `anthropic/claude-sonnet-4.5` produced

    [ERROR] Ollama refused the request for anthropic/claude-sonnet-4.5:
    model 'anthropic/claude-sonnet-4.5' not found

**The safety was never the problem and has not changed.** Nothing was sent
anywhere: `_is_remote_model` answers `False` for a name it cannot resolve,
which is the fail-safe direction, so the request went to a local server and
stopped. What was wrong was the *sentence*. It names a server the user never
mentioned, for a model they did not associate with it, and offers no idea what
to do — and it mattered more the moment queue item 6's type-in field made "any
string at all" something a person can enter.

`_unplaceable_model_refusal` refuses before dispatch. Two disciplines shape it,
both borrowed rather than invented:

**Every uncertainty resolves to no refusal.** No provider layer, a discovery
that has not run, an empty catalogue, a lookup that raised — all proceed
exactly as before. `_vision_refusal` states the reason in its own docstring and
learned it the hard way: that function's first version fired on the first
request after a boot, before anything had scanned, on a machine with two
vision-capable models installed. A guard built on our own missing bookkeeping
reports "that model does not exist" about a machine nobody had looked at.

**It blames nobody for Zaram's own pick.** Only `request` and `settings` are
checked. `task` and `zaram` are the provider layer's selections, drawn from the
catalogue, so they cannot fail to be in it — and if one ever did, refusing
would report our bookkeeping error as the user's mistake.

**Ollama's fallback for a bare id is untouched.** `_local_endpoint_for`'s own
reasoning still holds — *"an id this cannot place is far more often one Ollama
serves than one it does not"* — because those ids arrive from a picker built
out of the catalogue. It stops holding only where a person can type anything,
which is the case this now covers.

`tests/test_a_model_nobody_can_place.py`, 14 cases. **Two of them post to
`/chat`**, because the rest could all pass against a function nothing calls —
this directory already holds `test_chat_endpoint_writes_a_transcript.py`, which
exists because sixteen tests of the persistence helpers missed a live
`NameError` in the endpoint that used them.

### The consent has a way to be given — 29 August

**Shipping the refusal without the remedy was half a feature, and the half
that reads as a broken product.** The policy started refusing an image bound
for a chat-approved host, correctly and with a message naming the missing
decision — while `PUT /egress/policy` took a host and a mode and nothing else.
The user would be told a choice had not been made and given nothing to make it
with.

`data_class` now travels the whole way: an optional field on `PUT`, an optional
query parameter on `DELETE`, and a `class_rules` key on `GET` beside the
existing `rules` rather than nested into it — that shape is already parsed and
rendered, and changing it quietly is how a privacy pane comes to show nothing
at all. An unknown class is **refused with its name**, never defaulted to
`prompt`, since silently downgrading it would grant chat permission to a caller
that asked for something else.

Activity gains an `images` row under each destination's mode buttons, shown
only once that destination has a rule at all — before then the question does
not arise, and offering to permit pictures to somewhere nothing may be sent is
a control that governs nothing. **`spine` deliberately has no row.** It exists
in the policy and nothing sends it yet, so a switch for it would be an invented
value on the one surface whose whole job is to be trusted.

> **A hole in the day's own work, found by wiring it up.** The privacy pane's
> "cut everything" control sets every known host to deny — and `decide`
> consulted the class rules *first*, so a standing image grant survived it. The
> one control whose meaning has to be unambiguous would have left a destination
> able to receive photographs, and the same hole was open to anyone who blocked
> a host by hand and reasonably expected it to mean what it says.
>
> A host `DENY` is now checked ahead of the class rules. The asymmetry still
> points one way: a class rule may **widen** what a permitted destination
> receives, because the user granted it deliberately, and may never rescue one
> they shut. Two cases pin both directions.
>
> The lesson is the one this file keeps recording: the defect was not in the
> policy, it was at the seam, and it appeared the moment something real was
> connected to it. Tracing would not have found it.

`tests/test_an_image_needs_its_own_consent.py` is now 29 cases, five of them
against the real application rather than a router mounted in the test — a
complete router that nothing includes is a defect this repository has shipped
once already.

### Rule 7j's second dimension, and the first-run key — 29 August

Two items, and the first unblocked work that had already shipped.

#### The egress policy now knows *what* is leaving, not only where

Rule 7j grants consent "per destination **and data class**". `EgressPolicy` was
keyed on host alone, so the second half of that sentence had nowhere to live —
and the cost had just become concrete: OpenRouter discovery had started
reporting which cloud models can see, `select_model_for_task(requires_vision=True)`
could pick one, and then `RoutedEngine` refused to send the picture. **A
finished feature dead-ending one consent question short of working.**

`DataClass` is three members, each named in `CLAUDE.md` rather than invented:
`PROMPT`, `IMAGE`, `SPINE`. Rules are keyed `(host, class)`, and the whole
design is one asymmetry:

> **Inheritance runs one way.** A plain host rule covers `PROMPT` and nothing
> else. Every other class must be granted for that host in its own right, so a
> broader consent never implies a narrower and more sensitive one.

That is `_INHERITS_HOST_RULE`, a frozenset of one — a set rather than an `if`
so that widening what "I connected this provider" means is a visible,
reviewable diff.

Four details worth not re-deriving:

* **Existing policy files keep meaning what they meant.** Every one on every
  machine predates this. `{"hosts": {...}}` reads as permission for chat, which
  is what the user was actually asked; read as "permission for everything" it
  would have silently granted image egress nobody agreed to.
* **The refusal names the missing decision** rather than falling back to
  default-deny wording. The user *has* decided about this destination, and
  "refused, no reason given" sends them looking for a rule that does not exist.
* **`has_rule` is per class too**, because `SearchReadGrant` leans on it: a
  grant written for reading a web page must not start reasoning about a class
  it was never meant to touch.
* **`forget(host)` takes the class grants with it.** A permission outliving the
  decision that created it would also be invisible — the privacy pane lists
  host rules.

The class is decided at the chokepoint, by `OpenAICompatibleEngine`, and **read
off the body rather than off the caller's argument**. That distinction is the
one `SearchReadGrant` already had to learn: `source` is a label a call site
supplies about itself, and `_body` is the only thing that knows whether an
image actually survived into the payload. `RoutedEngine`'s blanket refusal is
gone, and deliberately not replaced with a second copy of the rule — one
chokepoint, asked once, which is the lesson `_local_endpoint_for` cost.

> **A weak assertion of my own, caught by falsifying it.** The new tests were
> run against deliberately broken code, and
> `test_an_image_to_a_chat_approved_host_is_refused` **passed anyway**: the
> `no_socket` fixture raised, the engine caught it in its "could not reach the
> provider" handler, and the resulting `[ERROR]` line named the host — which
> was exactly what the test checked for. A network failure and a refusal had
> become indistinguishable to the test. The fixture now records attempts
> instead of raising, and the test asserts the transport was never reached.
> Both then failed against the broken code, which is the only reason either is
> worth keeping.

`tests/test_an_image_needs_its_own_consent.py`, 22 cases.
`test_engine_routing.py`'s image class was rewritten rather than deleted, with
its old contract and the reason it changed recorded in the docstring. Backend
suite: **2852 passed, 24 skipped**, 4 m 21 s with Ollama up.

#### First run can now store a cloud key

`FirstRunPanel` has rendered a "use a cloud key" offer since it was built,
greyed out, with its own docstring naming why: *"Installing an engine, pulling
a model and storing a cloud key each need an executor that does not exist
yet."* This is that executor, and the cloud key went first because **its
backend already existed** — `POST /providers/cloud` writes the configuration
and is effective without a restart, so the offer can be honoured now rather
than promising something about the next launch.

`CloudKeyForm` holds four rules, and each is one a friendlier version of the
screen would break by accident:

* **It never claims the key works.** The backend makes no network call, so a
  200 means *configured* and nothing else. The success line reads "Zaram has
  not contacted them — nothing has left this device," and a test asserts the
  words *connected*, *verified*, *valid* and *working* do not appear.
* **The data policy is shown while choosing**, under the picker, before the key
  field — not behind a disclosure. `CLAUDE.md`: *"add a free key — your prompts
  train Google, and Zaram will tell you every time one goes."*
* **`selectable_by_default` is not this screen's business.** It stops *Zaram*
  routing to a provider whose terms are unknown; it must never stop a person
  choosing one knowingly. Every available entry is offered.
* **The button says "Save key", not "Connect".** What happens is that a value
  is written to disk, and the label says so.

`useReadiness` gained a `recheck`, because saving a key takes effect
immediately and the setup screen would otherwise keep standing over a product
that had just become able to answer. It re-runs the same probe — no cache, no
inference, so it cannot drift from `/readiness`.

`onConnected` is a **required** prop, following `ChatSurface`'s `navigate`: the
eight call sites that broke were eight compile errors rather than one silent
button. `CloudKeyForm.test.tsx` (11 cases) and the extended
`FirstRunPanel.test.tsx` (10) both pass; frontend **325 passing, `tsc` clean**.

> **Not seen in the running app, and the reason is worth stating.** Reaching
> this screen requires `can_chat: false`, and this machine has Ollama with
> models — so it cannot be reached here without breaking the local setup. The
> tests drive a real `userEvent` against a stubbed client, which is not the
> same as watching it. `docs/MILESTONES.md` already records what that
> distinction cost once, on the VRM gaze. **To verify: run with an empty
> `ZARAM_DATA_DIR` and Ollama stopped**, open the conversation, and the panel
> should stand where the composer does with a live key offer under it.

### The framing caught up with the product — 29 August

**Nothing in the code changed. Four documents did**, because they still sold a
product `CLAUDE.md` stopped describing on 16 August 2026.

That was the day the wedge stopped being a segment: *"a universal base, with
verticals as packs"*, the freelance business layer demoted from **the wedge** to
**the first pack**. `CLAUDE.md` was rewritten then. `README.md`, `docs/PITCH.md`
and `docs/VISION.md` were not, and for thirteen days the three documents a
stranger reads first opened on invoices and one-person businesses while the file
that governs them opened on "what earns the daily open is universal".

* **`README.md`** — "Who this is for" led with three professions and buried the
  horizontal base in a trailing sentence. It now leads with *anyone who types on
  a computer*, states the daily-driver order, and the professions follow under
  **where it stops being a preference and becomes a requirement** — which is the
  honest thing they are.
* **`docs/PITCH.md`** — the opening quote said *"Zaram replaces the admin half of
  a small business."* It now opens on the memory that stays put while the model
  changes, with obligations named as the first pack rather than the boundary.
  The 16 August sharpening note underneath it had already said this; the pitch
  above it had not been changed to match, which is how a document argues with
  itself.
* **`docs/VISION.md`** — the worst of the three, opening on the freelancer's
  unpaid hours for its whole first section. A new opening carries the universal
  argument and the routing claim; the old section is retitled **"The first
  pack"** and kept intact, because its argument is good and only its billing was
  wrong.

**And one thing that was true in code and stated nowhere: Zaram routes between
local and cloud per request.** `CLAUDE.md`'s "Models and routing" described
classification and the three tiers of control, but never the decision itself. It
now does, read off `ProviderManager.select_model_for_task` rather than
remembered — **and the first draft of it got the order wrong**, listing
capability before residency. The code applies consent and residency together in
`_auto_candidates`, *then* the capability gate, and relaxes residency only when
that gate empties the field. Corrected before it landed, which is the only
reason it is worth recording: a wrong order in the file that governs the order
is worse than no description at all.

The honest boundaries went in beside the claim: **difficulty is not routed**
("too hard for the local model" is not decidable in advance — react with an
offer, never predict), and **images do not go to cloud yet**, which
`RoutedEngine` refuses explicitly rather than by stripping the picture.

### Two dead subsystems removed, and one line of the audit left open — 28 August

Follow-on from the side door below, and the same defect three more times.

**`backend/orchestrator/` is gone — 1,261 lines across 7 modules, zero
importers.** Not one `import` statement anywhere in `backend/`, `frontend/`,
`desktop/` or `electron/` named it; every surviving mention was a comment
calling it dead. `CLAUDE.md` had said *"Do not build on it; delete it"* for
weeks while three separate files carried prose explaining why it was dangerous.

It was dangerous. `scoring.py` recorded a **missing required capability** as a
warning and ranked the candidate anyway, and `capabilities.py` scored
`ModelCategory.VISION`, `IMAGE` and `VIDEO` all as `Capability.VISION: 1.0` —
"can see", "can draw" and "can make video" as one number. That is this
codebase's most expensive recurring bug, in working form, one import away.
**A warning about a loaded gun is worth less than removing it**, so the four
places that cited it as a cautionary example now cite it in the past tense and
the code is gone. Backend suite after: **2832 passed, 22 skipped**.

**Two more desktop capability packs could not authenticate.** The vision pack
deleted below was not the only one. Every backend-calling handler in
`desktop/` sends `Content-Type` and nothing else, and `RequireApiSecret` wants
`X-Zaram-Auth` and exempts nothing:

| Handler | Calls | Since the secret shipped |
|---|---|---|
| `knowledge-handler.ts:27` | `/knowledge/search` | 401 |
| `speech-handler.ts:38` | `/voice/stream` | 401 |
| `bootstrap.ts:414` — inline `speech.tts` | `/voice/stream` | 401 |
| `callBackendChat`, `bootstrap.ts:585` | `/chat` | 401 |

**And nothing invokes any of them.** `executeCapability` is exposed on the
preload bridge at `electron/preload.js:111` and has **no caller in the live
frontend**; `executive.plan` likewise. `desktop-bridge.ts` is imported by
exactly two modules, `PresenceContext` and `OrbEngine`, and both use it for
presence and orb state.

They were also duplicates of paths that work. `knowledge.search` is a live
backend capability with its own dispatcher branch; speech reaches
`POST /voice/synthesize` from `speechStore.ts`, which is what `docs/SPEECH.md`
documents as the path that speaks. `CLAUDE.md` settles which of the two is
right — *"Frontend calls the backend directly over HTTP, not through Electron
IPC"* — so the Knowledge and Speech packs are gone, with the `speech.tts`
descriptor and the executive's `knowledge.search` planning step that reached
for them. `tsc --noEmit` clean; desktop tests unchanged at 617/620, the three
failures confirmed pre-existing against stashed changes (one incomplete
Electron mock, two timing benchmarks).

> **What was deliberately left, with its reason.** `VoiceRuntime` (full) still
> executes `speech.tts`, which now has no handler — the one internal caller,
> found by grepping after the deletion rather than before it, which is the
> right order to be embarrassed in. It is commented at
> `voice/voice-runtime.ts:120` rather than removed, because removing it takes
> `VoiceRuntime` with it and that raises the wider question this audit does not
> settle: **whether the desktop execution pipeline keeps a backend-facing half
> at all.** `conversation.runtime` and `reasoning.generate` are in the same
> position — uncredentialed, unreachable, duplicating `/chat`. Four handlers,
> one decision, and it is an architecture call rather than a cleanup.

### The second entrance to inference is gone — 28 August

`POST /vision/analyze` reached `OllamaEngine.stream_vision_response`, whose own
docstring said it bypassed **routing and the egress gate**, against a hardcoded
`qwen2.5vl:7b` that was never installed here. Three things were true of it that
the route table could not show, and each was checked rather than assumed:

* **Its only caller could not authenticate.** `desktop/src/capabilities/vision/`
  posted to `127.0.0.1:8420/vision/analyze` with `Content-Type` and
  `Content-Length` and nothing else. `RequireApiSecret` exempts nothing, so
  every call had returned **401** since the per-launch secret shipped eleven
  days earlier. The live React frontend never referenced the route at all.
* **It could not have run even so.** The endpoint called `_parse_legacy_sse`,
  which is defined **nowhere in the repository**. The first streamed chunk
  would have raised `NameError`.
* **Nothing tested it.** The suite's pass count was identical before and after
  the deletion — an ungated path into inference with zero coverage.

So it was deleted rather than repaired, which is what the handoff expected:
endpoint, engine method, both wrapper forwarders, `ModelsService.analyze_image`
and its private SSE parser, the `/vision` prefix from both proxy lists, and the
desktop capability pack with the keyword planner that reached for it.

> **The deletion had a trap in it, and it is the part worth reading.**
> `IntentPlanner` still emits a `vision.*` step when the *words* suggest a
> picture and nothing is attached — `has_images` fixed the case where an image
> *is* attached and deliberately left the other alone. The dispatcher's vision
> branch was the only thing catching it.
>
> Removing that branch would have let such a step fall through to
> `generate_response`, and a model asked to describe a picture nobody supplied
> writes a confident description of nothing. **Deleting a side door into a rule
> 9 failure would have been a poor trade.** The branch stays and refuses,
> reaching no engine at all — which is also the honest shape, since there is no
> gated capability route for vision and the real path is `/chat` with an
> attachment.

`tests/test_no_second_entrance_to_inference.py`, 12 cases, **10 confirmed
failing against the undeleted code** — including all five vision capabilities,
which is the fall-through proved rather than argued.

It also found a live defect on its first run, which is the only reason to trust
a guard like it. `implementations/ollama_llm.py` had its *"switch to a
vision-capable model (qwen2.5vl:7b)"* advice fixed on 19 August — *"names no
model deliberately"* — and `OllamaEngine` carried a **second copy of the same
sentence** that was missed, still recommending a model nobody had. The guard
reads string constants through the AST rather than raw text, so prose
explaining the removal is allowed and a live string is not.

### Images travel on the OpenAI-compatible path — 28 August

Queue item 4's remaining half. `stream_response` took an `images` argument;
`_body` had no such parameter; nothing joined them. An image attached while a
TabbyAPI or cloud model was selected was **discarded, and the model answered
about a picture it had never seen** — rule 9 again, in the silent version,
where the reply is fluent and nothing on screen suggests the picture went
nowhere.

The content-parts form is used **only when there are images**: a plain string
is what every server has always accepted and several older ones accept only, so
sending a one-element array for an ordinary message would trade a fixed bug for
a new one on endpoints nobody here can test.

**The media type is read from the picture's own signature.** By the time an
image reaches an engine the filename is gone — `main.py` passes
`[a.data for a in attached ...]`, base64 and nothing else, and
`Attachment.suffix` stays behind — while `image_url` needs a type. Defaulting
to `image/png` because most screenshots are PNGs would be a guess; the first
bytes are a measurement. **An image whose format cannot be established is
refused rather than labelled**, and the refusal is reported in band rather than
falling into the general handler, which would have called it *"could not
reach"* and sent the user to look at their connection.

`tests/test_images_on_the_openai_path.py`, 15 cases, **14 confirmed failing
against the unfixed engine**.

### Cloud discovery keeps what a model can see — 28 August

Queue item 7, and it was as small as the handoff said. OpenRouter's
`/api/v1/models` returns `architecture` with `input_modalities` and
`output_modalities`, in the same object `_is_free_tier` already opens for
pricing, and `_to_model` threw it away.

The consequence was a refusal built on missing data, which is the hardest kind
to notice because it looks like the safety working: a user with a connected
account and a dozen vision-capable models attaches a screenshot and is told
*"No model on this machine can read images."* That sentence is correct and the
gate behind it — `select_model_for_task(requires_vision=True)`, live callers at
`main.py:372` and `main.py:682` — was already built. It was reading a flag
nothing ever set.

**Input and output stay two questions**, because `CLAUDE.md` names the merged
version as a failure with a worked example. Accepting images sets
`supports_vision` and leaves the model an `LLM` — a chat model that can also
see is still a chat model, and that is the shape Ollama discovery already
produces from `/api/show`. Emitting images *and not text* makes it a
`ModelCategory.IMAGE`, which is not decoration: `select_model_for_task` filters
by category, so without it a model that can only draw is a candidate for
answering a question, and it answers by not answering.

Nothing here routes an image *request* anywhere. That needs a way to say "this
reply should be a picture", which does not exist, and building the gate before
the request would be scoring a decision nobody can make yet.

`tests/test_cloud_modality_survives_discovery.py`, 11 cases, including two that
pin the policy rules this must not have loosened — a vision-capable `:free`
model is still the logged tier and still not `selectable_by_default`.

### Pasting a screenshot into the chat box — 28 August

Queue item 3. The paperclip and a drag both reached `takeFiles`; Ctrl+V did
nothing, so the gesture a person uses immediately after taking a screenshot was
the one that was not wired — and there is no keyboard route to the file picker
either.

`frontend/src/lib/pastedFiles.ts`, wired as `onPaste` on the composer input.
**On the input rather than on the window**, which is the opposite of
`KnowledgeWorkspace`'s handler and deliberately so: that one skips fields
because a paste into its search box is a search, and here the caret is in the
message box by definition. Sharing the code would have meant a flag deciding
which product it was.

Two details that are not obvious and are the whole reason this is a module with
tests rather than four lines in a component. `items` and `files` are **both**
read, because an OS screenshot arrives as a `DataTransferItem` while a file
copied from a folder populates `files`, and which one is empty varies by
platform — so reading one loses one of the two ways a person puts a picture on
the clipboard. And a clipboard image is named `image.png` by Chromium every
time, so two pastes produce two chips the user cannot tell apart; the time it
was pasted is the only thing that distinguishes them, and a file copied from a
folder keeps its real name because that is what the user recognises.

Nothing here is a new route to a model: it reaches the same `takeFiles` the
paperclip does, so the same parse, the same eight-file cap, the same refusals
and the same vision gate apply. Text pastes are untouched — `preventDefault` is
called only once files are known to be present.

`frontend/src/lib/pastedFiles.test.ts`, 10 cases.

**Verified by driving it**, against a matched backend and Vite on a scratch
`ZARAM_DATA_DIR`. A real 1×1 PNG named `image.png` — Chromium's own name for a
clipboard screenshot, so the rename was exercised too — pasted into the
composer produced `POST /chat/attachments -> 200` and the chip
**`pasted-2026-08-28-155933.png · image`** above the input. A text paste
straight after left `defaultPrevented` false, so typing is untouched.

Say which instrument, because it changes the weight: the orb was opened with a
real synthetic pointer click through the browser tool, and the paste was a
`ClipboardEvent` carrying a real `DataTransfer` and a real `File`, dispatched
from the page rather than from a physical Ctrl+V. Screenshots worked in this
session, unlike the last.

**Both ports were held by leftovers when this started**, which is the trap
`docs/RUNNING.md` names, and the evidence that they were dead is worth keeping:
the Vite was fourteen hours old, the backend was a bare `python main.py` that
returned **401 to every request including `/health`** with the twelve-day-old
`backend/api-secret`, and no Electron process existed to hold a secret it would
accept. It could serve nobody.

### The card had a second tenant and nothing could see it — 28 August

Queue item 5, and it was the one blocking rather than the one recommended.
`ProviderManager._resident_models` asked each registered adapter in turn and
**returned on the first non-`None` answer**. On a one-server machine that is
indistinguishable from correct. Measured here, with both servers up:

    nvidia-smi          -> 12288 MiB total, 9493 MiB used, 2623 MiB free
    Ollama /api/ps      -> {"models": []}        <- answered first, so this won
    TabbyAPI /v1/model  -> Qwen3.8-27B-exl3-2.20bpw

So the residency map was an empty Ollama, `swap_preflight` planned against a
card it believed was clear, and a 3.3 GB cold start onto 2.6 GB of real
headroom graded as **`load` — "a cold start with room to spare"**. Every
residency verdict on this machine was taken on an input wrong by most of the
card.

**Merging alone would have changed nothing, and that is the half worth
remembering.** `OpenAICompatibleAdapter` had no `resident_models` at all, so
the second server could not have contributed to the map however the map was
built. The defect looked like one bad `return` and was two things, one of them
an absence — the same shape as the vision chain, where each defect hid the next.

Four pieces:

* **The map is merged across every local server**, and a provider that cannot
  answer makes the whole map unknown rather than contributing nothing. Partial
  knowledge is not knowledge here, and the error runs one way: an unseen tenant
  always makes the card look emptier than it is. Cloud providers are skipped;
  a provider that does not declare its kind is treated as local, which is the
  assumption that fails safe.
* **`OpenAICompatibleAdapter.resident_models`**, reading `/v1/model`. Three
  outcomes rather than one `except`: a cloud provider answers `{}` with no
  request; a **refused connection on a local port is a fact** — nothing is
  listening, so that server holds nothing, which is what keeps the indicator
  alive on the Ollama-only machines where the LM Studio adapter is registered
  and idle; anything else is unknown.
* **The size is `None`, never `0`.** `/v1/model` carries the id, the context
  and cache settings and the chat template, and no memory figure anywhere — the
  OpenAI contract has no field for one. A zero would be a measurement meaning
  "holds nothing", which is the false zero `vram_bytes` already cost this
  codebase once, pointing the same way.
* **`HardwareProfiler.vram_used_bytes`**, because an unsizeable tenant leaves
  the sum unanswerable and the driver can answer regardless — it measures the
  card rather than asking its tenants. Outside `profile()` and uncached, on a
  one-second budget: capacity is a property of the machine, occupancy changes
  between one reply and the next.

**Two sources for occupancy, and they are alternatives rather than a blend.**
The attributable sum is preferred and is counted against `resident_budget_bytes`;
the driver is the fallback and is counted against capacity-less-reserve, because
the measured figure already contains the embedder and deducting it from the
budget as well would charge it twice. Each measured against its own baseline —
`_headroom_bytes` — which is the same discipline the ranking-versus-selection
rule states, applied to a quantity rather than to a score.

**Two things it deliberately does not do.**

`evicts` now names only models **this model's own server** would unload. Ollama
cannot touch what TabbyAPI holds and does not try; it loads anyway and spills to
system RAM. Naming a cross-server model would be the indicator claiming a
displacement that never happens.

And when a model does not fit while nothing evictable is in the way — a second
server holding the card, or a program Zaram knows nothing about — `swap_preflight`
returns **`None`**. There is no honest word for it in the four-kind vocabulary:
not `oversized`, the model is far smaller than the card; not `swap`, nothing is
displaced. Adding a fifth kind is a cross-stack change (`chatClient.ts` drops
any kind it does not know, which it has been bitten by once), and it should be
argued for with a user-visible sentence in hand rather than added in passing.
**Re-entry point: `_evictable_by` returning empty in `swap_preflight`.**

`tests/test_residency_sees_every_server.py` — 19 cases. Twelve were confirmed
failing against the unfixed code, including the replay of the measurement
above; four are guards that would have passed; and three run against **whatever
is actually listening on this machine**, skipping when nothing is. Those last
three are the point: this defect survived because `test_swap_preflight.py`
registers exactly one adapter and `test_local_dispatch.py` stubbed the resolver
it was testing, so neither fake could hold two servers. The existing fourteen
`test_swap_preflight.py` cases still pass unchanged.

**Still true and untouched:** TabbyAPI holds for the process lifetime while
Ollama unloads after `keep_alive`, so a driven local↔local handoff via
`/v1/model/unload` remains a ~100 s round trip and belongs behind an offer.

### The history panel, seen — and a routing defect it uncovered — 28 August

**The panel works.** Rendered in a real browser against a real backend, with a
scratch `ZARAM_DATA_DIR` so nothing touched the maintainer's Spine. Verified by
watching it, not by reading a test: the lip carries a real count (7), it pins
on click, groups under **Today**, lists by recency, **resume restores the whole
transcript** with its model attribution line, and **delete removes exactly one
conversation** (7 → 6) while the rest stand.

The port that blocked this last session was held by that session's own leftover
Vite and Electron — eleven hours old. Nothing was wrong with the config.

> **A live routing defect, found by running it and not on any list.**
>
> The first real message came back as
>
>     [ERROR] Ollama refused the request for Qwen3.8-27B-exl3-2.20bpw:
>     model 'Qwen3.8-27B-exl3-2.20bpw' not found
>
> which is the *exact* error last session's `LocalDispatchEngine` was written to
> stop. Isolated with two requests differing only in the name:
>
> | `model` sent | Result |
> |---|---|
> | `lm_studio:Qwen3.8-27B-exl3-2.20bpw` | TabbyAPI, generated |
> | `Qwen3.8-27B-exl3-2.20bpw` | **Ollama**, `model not found` |
>
> Same model. The second is `display_name` — what TabbyAPI itself reports and
> what `wire_name` converts *to*. `provider_of`, `locality_of`, `_is_remote_model`
> and `wire_name` all resolve a model through `_catalogued`, which normalises a
> bare provider-native name. **`_local_endpoint_for` alone did a
> `split(":", 1)`** and could not. One question, two implementations, and they
> disagreed.
>
> The user-facing half is worse than the failure: the `answering` event said
> `provider: lm_studio, locality: local` **while the dispatcher posted to
> Ollama**. The product naming one server and using another is the routing
> legibility claim inverted, on the surface whose whole job is to be trusted.
>
> **Why it was green.** `test_local_dispatch.py` passes
> `resolve_endpoint=lambda mid: endpoints.get(mid)` — it tests the dispatcher
> and *stubs the resolver*, and the resolver was the bug.
> `_local_endpoint_for`, the function actually wired in at
> `models_runtime.py:143`, had **zero tests**. The regression suite for a fix
> mocked out the one part of it that was wrong.
>
> Fixed by asking the catalogue first, exactly as its four siblings do; the
> prefix split stays underneath it for an id the catalogue does not hold. New
> `tests/test_local_endpoint_resolution.py` — nine cases, and the two that
> matter were **confirmed to fail against the unfixed code** before being kept.
> Verified against the running product: the same request now answers `pong`
> from TabbyAPI, ~2.2 s to first token.
>
> **And there was a second door, which is the one that was actually biting.**
> The fix above only helps a request that *names* a model.
> `_resolve_model` returns `_ModelChoice(None, "zaram")` whenever nobody named
> one — **every ordinary message** — and `LocalDispatchEngine` resolved only
> when `model` was truthy, so an unspecified message went to Ollama however the
> default was served. Underneath, the `default_model` setter stored the
> runtime's pick on `self._ollama` **and nowhere else**: the default was
> recorded on the one engine that could not reach it.
>
> Measured after the first fix, asking *"What are you, and who made you?"*
> with no model named:
>
>     answering -> {"model": "Qwen3.8-27B-exl3-2.20bpw", "provider": "lm_studio"}
>     answer    -> [ERROR] Ollama refused the request ... model not found
>
> The interface named one server and the dispatcher used another — again. The
> engine now holds its own `_default_model` and resolves `model or default`;
> Ollama keeps its copy so the Ollama-served path is untouched. Five cases in
> `test_local_dispatch.py::TestTheDefaultIsAChoiceToo`, one confirmed failing
> without the fix. Verified live: the same question now answers from TabbyAPI.
>
> **Two doors, one assumption.** Worth stating plainly because a third is
> possible: anywhere that treats "no model named" or "cannot place this name"
> as *therefore Ollama* is the same bug waiting.

> ### Replies opened with a blank gap, on every message
>
> Reported as *"talking weird"*. The first content delta after `</think>`
> arrives as `"\n\nI’m"` — the chat template's own newlines — so every reply
> began with two blank lines. Invisible in a raw stream, and on screen it
> reads as the answer starting late.
>
> `OpenAICompatibleEngine._tokens` now trims the leading edge once, and only
> once: a blank line *inside* an answer is a paragraph break and stripping
> those would run the prose together. Thinking is left verbatim, because it is
> shown in a panel of its own and reshaping it would misrepresent what the
> model did.
>
> **The `reasoning_content` re-tagging this sits inside had no tests at all** —
> it shipped last session and nothing asserted that a provider splitting the
> monologue into its own field was read rather than dropped in silence.
> `tests/test_reasoning_content_retag.py`, eighteen cases; the eight covering
> re-tagging pin behaviour that already worked, and the four covering the trim
> were confirmed failing without it.

> ### Two decisions the maintainer took, 28 August
>
> Both came out of the "talking weird" report and both were put to them rather
> than assumed.
>
> **Sending no sampling parameters is not neutral.** The OpenAI-compatible body
> carried `model`, `messages` and `stream` and nothing else, so the server's own
> factory default applied — and TabbyAPI's is temperature 1.0 with top-p 1.0,
> unconstrained sampling from the raw distribution. Ollama does not have this
> problem: a Modelfile ships per-model settings and Ollama applies them. **So
> the two local engines generated differently, nobody chose that, and nothing
> anywhere said so** — visible as wandering answers and headings nobody asked
> for, on a 27B quantised to 2.20bpw.
>
> `LOCAL_SAMPLING` is temperature 0.6 / top-p 0.95, Qwen3's own published
> recommendation for thinking mode and conservative enough for any model. It is
> a **default, not a setting** — never surfaced in the interface, which
> `CLAUDE.md` forbids — and it is supplied by `LocalDispatchEngine` alone.
> **Cloud engines deliberately do not get it**: a provider's default is part of
> what the user chose when they connected it. `temperature` and `top_p` only,
> because both are standard OpenAI fields; `top_k` is a local dialect extension
> and one dialect-specific key would make the constant unsafe to reuse.
>
> **The maker is now a supplied fact: "Zaram was made by Uche Anisiuba."**
> The preamble forbade crediting the training lab and named no alternative,
> and `_HONESTY` says "where you were not told, say you do not know" — so
> asked who made it, Zaram answered *"I wasn't given a maker for Zaram
> specifically, so I don't know."* The product did not know what it was on the
> question people ask first.
>
> The second half is the more instructive one. Having no answer, the model
> **narrated its own instruction** to fill the gap: *"I also shouldn't treat
> the lab or company that trained the underlying answering model as the maker
> of me."* That is the recital failure `identity.py` already records happening
> once on `qwen2.5-coder:1.5b`, returning as **paraphrase rather than
> quotation**, which is exactly why the line against quoting did not catch it.
> The line now says "quoted, listed, paraphrased or repeated back — not even to
> explain why you cannot say something".
>
> **The durable lesson:** a rule that removes a wrong answer without supplying
> the right one does not leave silence. It leaves the model improvising, and
> what it reaches for is the prompt itself. `CLAUDE.md` already says identity
> is a fact the system supplies; the maker was a fact nobody had supplied.

> ### Two things the interface was saying that were not true
>
> Both reported by the maintainer from ordinary use, both fixed and **verified
> by driving the running product**, not by tests alone.
>
> **"Open Settings →" did nothing.** `NoticeCard` called `openWorkspace`, which
> was `useConversationStore.setActiveNode` — and `activeNode` has no reader
> outside `src/legacy/`, which is not mounted. Two dead routes: the notice
> action and the citation panel's "open Activity". `ChatSurface` now takes
> `navigate` as a **required prop** from `App`. Not a store, because `App`'s
> `navigate` also closes the chat, closes the command palette and sets the
> conversation context — a second implementation would drift, and drifting
> navigation is how this broke. Required rather than optional so `tsc` fails at
> the call site instead of a button failing silently.
>
> **`check:reachability` cannot see this class of defect**, and the reason is
> worth keeping: the export *was* used and the call *did* go somewhere. It had
> no effect. No import graph tells that apart from working code.
>
> The four new tests in `NoticeCard.test.tsx` say in their own docstring that
> **all of them would have passed on the day the bug was reported** — the card
> was never the broken part. They pin which node each action resolves to; the
> wiring is guarded by the required prop, which is a compile error rather than
> a test, and that is the better guard when the defect was a call that went
> nowhere rather than a wrong value.
>
> **The "web search is off" warning fired on a question Zaram had already
> answered from a supplied fact.** Asked *"What is today's date?"*, Zaram
> answered **"Today's date is 28 August 2026"** — correct, from
> `identity._today_line` — and rendered the amber *"this answer comes only from
> what the model already knows"* card underneath it. The reply and the warning
> about the reply contradicted each other on screen, and the warning was the
> wrong one: the answer came from Zaram, not from the weights. Two patterns
> matched — `_TIME_RE` on the bare word "today", `_FACTUAL_RE` on "what is the".
>
> `_ANSWERED_BY_SUPPLIED_DATE` exempts it, checked before every other pattern.
> Measured after: the date question answers with no notice, *"What happened in
> the news today?"* still warns.
>
> **Three constraints keep it from becoming another keyword list.** Anchored to
> the whole question — `_TIME_RE` matching "today" anywhere is how the bug
> happened, and an unanchored exemption is the same defect with the sign
> reversed, which is the worse direction because a missing warning is quieter
> than a false one. Scoped to the *date*, since `_today_line` supplies nothing
> finer, so "what time is it" is deliberately not exempt. And **coupled to the
> fact by test**, so if `identity.py` ever stops supplying the date the
> exemption fails rather than silently suppressing a warning that has become
> true. No general "answerable from supplied facts" mechanism was built: there
> is one supplied fact, and building the abstraction from one example is what
> the pack-system rule forbids.
>
> ### Local vision works, and three defects were stacked in front of it
>
> **Measured end to end, 28 August 2026.** A PNG of a red circle and a blue
> rectangle, attached to a chat message, asked *"What shapes and colours are in
> this image?"*:
>
> > "The image contains a red circle and a blue rectangle. The two shapes are a
> > circle and a rectangle."
>
> `gemma4:26b-a4b-it-q4_K_M`, `chosen_by: "task"`, **165.8 s to first token**
> because it spills — and the `oversized` warning fired, which is the designed
> behaviour rather than a fault. Slow, honest, working.
>
> Three defects, each hiding the next, and each a different shape of the same
> mistake — **a guess overriding a fact**.
>
> **1. Residency answered a capability question.** `_auto_candidates` drops
> anything that positively does not fit VRAM, *before* the vision gate runs. So
> on a machine whose only sighted model is oversized the field emptied for the
> wrong reason and the user was told **"No model on this machine can read
> images."** `gemma4:26b-a4b` is catalogued `supports_vision: True`,
> `fits_resident: False` — 18.2 GB against a 12 GB card. It sees perfectly
> well; it is *slow*, which is a different sentence, and `CLAUDE.md` settles
> which wins: *"VRAM limits route a task; they do not reject a vertical."*
> A required capability now relaxes residency before answering `None`. Consent
> filters are re-applied, never skipped.
>
> **2. The planner is built from words alone.** `create_plan(prompt)` matched
> the *word* "image" and emitted a `vision.analyze` step. It had no idea an
> image was actually attached — while `main.py` had already got this right for
> model selection (`requires_vision or has_images`, an attachment outranking
> wording) and the planner never learned the same lesson.
>
> **3. Two names for one thing.** The dispatcher's vision branch reads
> `input_data["image"]` — singular. `ExecutionEngine` writes
> `input_data["images"]` — plural, and onto the **generation** step only. So
> the picture sat three layers up, intact, on a step nobody ran, and the reply
> was *"[ERROR] No valid image provided for vision analysis."*
>
> `create_plan` now takes `has_images`, and an attached image keeps the plan an
> ordinary generation — which carries images to whichever model was routed,
> passes the residency and consent gates, and is logged. `vision.analyze` stays
> for the capability route, `/vision/analyze`, screen and camera, which supply
> their own singular `image` and do not go through the planner.
>
> **The residency gate is inert in the entire test suite**, and that is why
> defect 1 lived only on the machine where it mattered. `vram_known` is `False`
> in a bare pytest process, so `model_fits_resident` returns `None` for
> everything and the filter never fires — every pre-existing test in
> `test_vision_gate.py` passed without it running once. The new cases stub
> `resident_budget_bytes` explicitly and carry a `test_the_stub_actually_gates`
> case so they cannot pass vacuously. The regression case was confirmed failing
> against the unfixed code.
>
> **Qwen can see too, and Zaram says it cannot.** The EXL3 quant reports
> `architectures: ['Qwen3_5ForConditionalGeneration']`, `vision_config`,
> `image_token_id`, and **987 vision tensors** with `language_model_only:
> False`. Zaram catalogues it `supports_vision: False` because
> `OpenAICompatibleAdapter._to_model` never sets the flag — the same discovery
> gap as queue item 7, on the local side. Not fixed; TabbyAPI advertises no
> modality field, so the fix needs a decision rather than a line.
>
> ### The 1800 s lock bug had a sibling with 3600 s, and it was still live
>
> **`BackgroundReindexer._run` slept `_interval_seconds` — 3600 — while
> holding `_lock`.** `stop()` takes that lock to clear `_running` and
> `enqueue()` takes it to append a task, so both blocked for **up to an hour**.
> The `join(timeout=5)` in `stop()` never mattered; `stop()` was already
> blocked before reaching it.
>
> This is the defect the 27 August session found in
> `ContinuousLearningPipeline` and fixed there — 1800 s, 9,000.04 s in one
> test, 97% of a 2h35m run. **The sibling class was never looked at**, and its
> interval is twice as long.
>
> **Why it survived: it is a race, not a certainty.** The test starts the
> worker and stops it immediately, so whichever thread reaches the lock first
> decides. It passes most runs. Measured 28 August: one full suite at 4:18,
> then the next blocked at 51% with the pytest process flat on CPU over a
> 20-second sample and one socket open going nowhere — which is how it got
> misread as a network problem for twenty minutes before `--collect-only`
> named the test.
>
> Fixed the same way: an interruptible `threading.Event` instead of `sleep`,
> and the lock held only to read state. `TestStoppingIsPrompt` gains two cases
> — `stop()` and `enqueue()` both bounded at 5 s. Against the unfixed code they
> **time out on every run** (exit 124, three consecutive tries at 25 s);
> with the fix the whole 65-test file runs in **0.87 s**.
>
> **The lesson is about the first fix, not the second.** A defect found in one
> class is a defect to look for in every class with the same shape, and nobody
> grepped. `enqueue()` is also the half that was never only a slow test: a task
> submitted while the worker idled blocked the caller for up to an hour **in
> the running product**.
>
> Separately and still open: the suite makes **live outbound internet calls** —
> five simultaneous HTTPS connections to Wikimedia, Cloudflare, Yahoo and
> CloudFront observed from the pytest process. Not the cause of this hang, but
> it makes the suite's duration depend on the network, and
> `test_egress_chokepoint.py` cannot see it because that scans source rather
> than runtime.

**Roadmap 1.4 was already done, and the handoff was wrong to list it.** The
per-launch API secret ships: `electron/main.js` mints 32 bytes at boot,
`RequireApiSecret` enforces on every route including `/health`,
`core/api_secret.py` documents the dev file fallback as the weaker path.
`GET /health` with no credential returns **401**, measured. A comment block in
`main.py` still said *"there is no authentication anywhere ... until that
exists"* four lines above the import that provides it, and `CLAUDE.md`'s
custody section said the same — both corrected. This is the README defect this
repository already recorded once: **the product understating itself**, in the
one direction where a reader acts on it and rebuilds what exists.

**Suite: 2781 passing, 0 failing, 16 skipped.** Frontend **302 passing** (35
files). Started the session at 2716 backend / 298 frontend, so **65 new backend
tests and 4 new frontend tests** — every one written against a defect that was
reproduced first, and for each fix the decisive cases were confirmed to **fail
against the unfixed code** before being kept.

**Say the condition, because it moved a lot.** 3 m 25 s and 4 m 16 s with
Ollama up and idle; **6 m 46 s** on one run with `gemma4:26b-a4b` resident from
the vision test and contending for the card. Same suite, same code, +98%
between the extremes.

One of those 39 replaced an assertion rather than adding coverage.
`test_identity.py` pinned the string `"never quoted, listed or repeated back"`
verbatim, so **strengthening that rule to cover paraphrase turned the suite
red** — a test that fails when its own contract is reinforced is pinning the
wording, and it would have argued against the fix. It now asserts the contract.

**Vision was re-read rather than carried forward, and the job is not what the
handoff said.** The modality gate exists — `select_model_for_task`, live
callers at `main.py:372` and `682`, `tests/test_vision_gate.py` — and the
ordinary path already carries images on whichever model was routed. What
remains is `OllamaEngine.stream_vision_response`: a hardcoded, uninstalled
`qwen2.5vl:7b`, reachable through `POST /vision/analyze`, and by its own
docstring bypassing **routing and the egress gate**. A second entrance to
inference that the log cannot see is rule 3, and it is a deletion question
rather than a gating one. Detail in `docs/NEXT-SESSION.md`.

That is the second stale handoff claim caught in one session, and the pattern
is the same both times: the note described work as unbuilt, and the code had
it. **Re-read before starting; the base rate here is high enough that it is
not optional.**

---

### Conversation history, context budget, transcript projection — 28 August

**Suite: 2716 passing, 0 failing, 194 s with Ollama up.** Frontend 298 passing.
Everything committed and pushed on `Zaram-V0.1` through `08788f6`.

Roadmap 0.2, 1.1, 1.2, 1.3 and U.3 done. ~~1.4 — the per-launch API secret — is
the one Phase 1 item left~~ — **wrong, see above: 1.4 had already shipped.**

* **Conversation history exists.** Before this, no table in any of the seven
  databases held a message; closing the window lost the conversation.
  `conversations.db` implements rule 7d's *"session state and long-term memory
  are separate stores"* — the half that was never built. Deleting a transcript
  does not touch Spine facts, and the response says so.
* **The context window is measured**, from `/api/ps`, not assumed. Ollama
  serves a default `num_ctx` whatever a model advertises — `gemma4:12b` reports
  262,144 and loads with 4,096. Unknown returns `None`, never a guess.
* **One transcript, projected per provider**, fitted to the answering model's
  real window. Whole turns only. A resumed conversation now gets its recent
  turns back, which `_session_turns` could not do because it dies with the
  process.
* **Two live defects fixed, neither on any list.** An engine failure could
  reach the user as a truncated reply with no error, because
  `ConversationManager` raced its own error flag against the queue carrying it.
  And `ContinuousLearningPipeline.stop()` could hang for half an hour, because
  `_run` slept 1800 s holding the lock `stop()` needs — that one was 97% of a
  2h35m suite run and had been read as "the suite is slow".
* **Not verified:** the conversation history panel has never been rendered.
  Port 5173 was held for the whole session and `strictPort` plus the backend's
  CORS allow-list make it unmovable. See `docs/NEXT-SESSION.md`.
* **Still open, carried forward:** the vision modality gate. Untouched this
  session.

> ### A second local server, and three defects it exposed
>
> **Qwen3.8-27B now runs on this machine at 2.20bpw through TabbyAPI**, served
> on `127.0.0.1:1234` where Zaram discovers it as `lm_studio`. Getting there
> found three defects in Zaram rather than in the setup, and the first is the
> one worth carrying forward.
>
> **"Local" was a synonym for "Ollama".** `RoutedEngine` splits local from
> cloud and gave everything local to `OllamaEngine`. True while Ollama was the
> only local server; false since the catalogue gained an OpenAI-compatible
> entry on loopback. A model served there was discovered, catalogued, listed
> with a correct `NEVER_LEAVES_DEVICE` policy, chosen — and posted to Ollama,
> which had never heard of it. Underneath, `OpenAICompatibleEngine` refused an
> empty key with *"A cloud model needs your own API key"*, written assuming
> OpenAI-compatible implies cloud. Both LM Studio and TabbyAPI ship auth-free
> on loopback, so **the `lm_studio` entry could never have executed a single
> request** — discoverable, never runnable, in the routing layer.
>
> `engines/local_dispatch_engine.py` dispatches by **provider id**, never by
> model name, and the keyless exemption is gated on the address rather than on
> the key being blank — `https://localhost.attacker.example` is still refused,
> and asserted.
>
> **Two existing tests were asserting the wrong contract.** They read
> `isinstance(engine, OllamaEngine)` for the no-key case, pinning *which local
> server answers* when the rule they protect is *nothing capable of leaving the
> device is built without a key*. Green the whole time they were wrong.
>
> **Reasoning was being rendered as the answer.** The model's chat template
> ends the prompt with a bare `<think>`, so generation starts inside the block
> and only the closing tag is emitted; `ReasoningSplitter` waited for an
> opening tag that never came — and Kokoro read the monologue aloud, the exact
> failure that module exists to prevent. Fixed at both ends: TabbyAPI splits it
> server-side, and the engine now reads `reasoning_content`, which also fixes
> DeepSeek and every other provider using that extension.
>
> **Knowledge gained per-file removal.** Rule 4 says the user can delete any
> stored thing; the only unit was a whole source, and every pasted file shares
> one uploads source — so removing one image meant discarding everything ever
> pasted.
>
> **Vision is half fixed and is the next job.** Both engine wrappers now
> forward `stream_vision_response`, but `OllamaEngine` hardcodes
> `qwen2.5vl:7b`, which is not installed and ignores the chosen model. The
> real fix is the modality gate: `supports_vision` exists but only as a 0..1
> *ranking* score, and modality is a precondition, never a ranking.
>
> Measured, same ~2,500-token prompt: the old `qwen3.8:27b` managed 19.5 s to
> first token and 1.96 tok/s; the EXL3 does **0.72 s and 8.0 tok/s**; and
> `gemma4:26b-a4b` does 4.5 s and **23.75 tok/s**. Two 18 GB models spilling
> by the same ~50%, and **the MoE generates 9.4× faster** — only ~4B params
> read per token, so the exiled experts sit untouched.
>
> Full detail, uncommitted-work breakdown and open threads:
> `docs/NEXT-SESSION.md`.

---

## Earlier — 26 August 2026

*Several sessions ran on this date. The latest work is first.*

> ### A file dropped into a message, and an honest account of what was read
>
> Zaram could ingest a document into Knowledge and had no way to ask a
> question about one. Every other assistant has a paperclip and this had none.
>
> `backend/attachments/` is **working state, never the Spine**, and rule 7d is
> the reason rather than tidiness. Someone asking one question about a contract
> has not decided to add it to their knowledge base, and indexing it because
> they asked would fill the Spine with things they looked at once — which is
> the store that stops being worth searching.
> `POST /chat/attachments/{id}/keep` is the only place the two meet, and only
> because the user said so.
>
> **`compose.py` is the part worth having.** LM Studio does the same job —
> whole document into context when it fits, retrieval when it does not — and
> its own documentation declines to say which happened or where the threshold
> sits. A silently-summarised document is worse than a refused one, because the
> answer looks complete. So the block the model sees and the sentence the user
> reads are built together from one decision, and **the notice is emitted even
> when nothing was left out**: a disclosure that appears only on the lossy path
> teaches the reader that silence means "all of it", which makes the one time
> it fails to fire unreadable.
>
> The budget is measured. `/api/ps` reports `gemma4:12b` loaded at
> `context_length: 4096` while `/api/show` declares 262144, so the declared
> maximum is the wrong number and using it would overflow the context on almost
> every real document. About 5,400 characters — two pages — go in whole.
>
> Selection keeps **membership, ordering and presentation** apart, which this
> repository has paid three times for merging. Every passage is a candidate;
> ranking is by rare-term overlap *within the document*, so a term appearing in
> every passage scores zero and no stopword list has to be guessed at; and
> whatever survives is restored to **document order**, because a contract read
> out of order is a different contract.
>
> Measured against a live model rather than a fixture. A 601-character
> statement of work: *"Read sow.txt in full"*, and `gemma4:12b` answered
> "30 days from the invoice date" and "2 October 2026", both correct. A
> 23,315-character agreement of 120 clauses: *"too long to read at once, so
> Zaram searched it and used 28 of its 120 sections"* — and it found clause 90,
> the one passage that answers, where the other 119 share most of the
> question's words.
>
> ### A photograph Zaram reads on this machine, and refuses to send anywhere
>
> Attach an image and ask about it. A 7 KB PNG of an invoice, `gemma4:12b`,
> *"The amount due is 8,400 GBP and the due date is 14 September 2026"* — both
> correct, nothing uploaded. That is the product's thesis in one exchange, and
> every competitor has to upload the picture to answer it.
>
> **`/vision/analyze` was the only image path and could not have done it — the
> nineteenth.** It builds its own `OllamaEngine`, hardcodes `qwen2.5vl:7b`
> (not installed here), and bypasses routing, `EgressGate`, the identity
> preamble and memory. Its own error string says *"attach an image first"*,
> naming a control nobody had built. Images now travel the ordinary chain:
> `/chat` → `ChatRouter` → `ExecutionEngine` → `Dispatcher` → `ModelsService` →
> engine, one optional argument beside `model` at every layer.
>
> **The gate already existed, and `CLAUDE.md` is stale about it.** That file
> says modality "exists only as a 0..1 score built for ranking" and that
> "nothing gates". `ProviderManager.select_model_for_task` has filtered on
> `supports_vision` *before* ranking for some time, with a docstring explaining
> why merging it into the ranking would be wrong. What was missing was a
> **caller**: `requires_vision` was inferred from wording, so the gate was
> never asked in earnest. An attached image is now a fact rather than a guess.
>
> Three refusals, each a different sentence because each has a different fix:
> this model cannot see; nothing here can see; this is a cloud model and Zaram
> does not send pictures off the device. The last is **rule 7j** rather than a
> missing feature — a chat message is ~2 KB and a photograph is megabytes of
> something far more personal, and connecting a provider for text is not
> consent to send it one. Refused rather than stripped: an answer built with
> the picture quietly removed is the same failure the local gate exists to
> stop, arriving by the cloud route.
>
> **Two defects found by wiring it up.** The vision check read an *unscanned*
> catalogue and reported "no model on this machine can read images" on the
> first request after a boot, on a machine with two vision-capable models
> installed — a check failing closed on missing information and announcing it
> as a fact about the user's hardware. Every uncertainty now proceeds; only
> "models were found and none can see" refuses. And the read timeout was 120 s
> against a **measured 158.9 s** for a cold vision projector, so Ollama
> answered correctly and Zaram threw the answer away.
>
> ### Four reasons the desktop window opened black, three of them silent
>
> Reported as "electron launched and a black screen". It was `error.html`:
> dark, nearly empty, and correct that something was wrong.
>
> **`broadcastViewport` was declared inside a conditional block and called
> outside it.** A `function` declaration in a block is scoped to that block, so
> every backend state change threw `ReferenceError` — into a bare
> `catch (_) {}` in the subscriber loop. The renderer loaded and was never told
> its own size. The comment directly above that function already describes the
> previous incarnation of the same shape, one scope out.
>
> **`startupTimeoutMs` was 30,000 against a cold boot measured at 148 s** — 13 s
> to reindex the Spine, then **131 s in semantic intent routing, which logs
> nothing while it runs**. Now 240,000, with the measurement recorded beside it.
>
> **One aborted 3 s health probe tore down the loaded app.** A single failure
> moved the launcher to `unavailable`, which reloads the error page over a
> working renderer. Not hypothetical: a cold model load takes 95 s here, so
> testing a large model would have destroyed the window it was being tested in.
> The fix is not a longer probe — **the probe answers readiness and the child
> process answers liveness**, and only the second is evidence the backend has
> gone.
>
> The fourth is why the other three took so long to find: the launcher logged
> no state transitions and swallowed subscriber errors. Both now report.
>
> ### The desktop holds most of the GPU, and it may explain the suite mystery
>
> Measured with `nvidia-smi --query-compute-apps`, **no model loaded**:
> Explorer, Edge, WebView2, WhatsApp, PhoneExperienceHost, SearchHost and the
> start menu together hold **~8.8 GB of this 12 GB card**.
>
> That leaves ~3.4 GB. `gemma4:12b` needs 7.5 GB, so it **spills to CPU** —
> measured at 1.8 GB of 8.95 GB resident. Any test performing a real inference
> then runs at processor speed. The backend suite hung at 51% twice in that
> state and completed in **4:51** once the card was quieter.
>
> This file records an unexplained 2:53-versus-20:46 split and blames
> provider-probe timeouts. **This is a better candidate**, and checking it is
> cheap. Two consequences: the **30.3 tok/s "fully resident"** figure was taken
> on a quiet machine and does not hold on a working desktop; and
> `resident_budget_bytes` subtracts the embedder and a KV reserve from *total*
> VRAM without subtracting the desktop, so the residency gate is optimistic by
> several gigabytes in exactly the case that matters.
>
> ### A module that deleted its own source
>
> `AttachmentStore` swept its scratch directory with `shutil.rmtree`.
> `data_dir()` resolves to `C:\Zaram\backend` in a checkout that already holds
> databases — correct and deliberate — and the directory was called
> `attachments`. So the root came out as `backend/attachments`, the package's
> own directory, and importing `main.py` removed it.
>
> The rename to `chat-attachments` closes that route, since a hyphen cannot be
> a module name. **The rename is the smaller half.** A recursive delete rooted
> at a path derived from configuration has a blast radius somebody else
> chooses, and `ZARAM_DATA_DIR` is a value somebody can set. The sweep now
> unlinks only files matching its own prefix and never removes a directory.
>
> ### What was measured, and in what condition
>
> Backend **2554 passed, 22 skipped, 0 failed**, Ollama up, 4:51. Frontend 268
> passed. Electron 56/56 with nothing running. Twenty mutations run across two
> passes; **five came back green and were fixed** — a fixture that ranked in
> document order anyway, filler sharing no words with the question, a budget
> assertion measuring the block header, a gap marker the header explains by
> using, and a detach test whose single file made the id under test also
> `attachments[0]`.
>
> One flake, not from this work:
> `test_an_engine_failure_becomes_an_error_event_and_still_terminates` fails
> under load and passes alone. The log shows the error *was* caught and
> printed, so the event races the consumer's completion — a real defect in the
> legacy `ConversationManager` path.

> ### Obligations reach the screen, and the proxy never carried them
>
> `GET /obligations` had been live since earlier today and **no frontend file
> contained the word**. `check:reachability` said so — eight backend routes
> unreached at the start of this session, six of them obligations — and so did
> a second guard nobody had run: `check:proxy` was **already failing**, because
> `/obligations` was in neither `frontend/vite.config.js` nor
> `electron/config.js`. A missing prefix does not 404. Vite answers with its
> own `index.html` and a 200, so the first thing the new client reported was
> `Unexpected token '<', "<!doctype "... is not valid JSON` — a sentence naming
> neither the route nor the proxy. The packaged list was missing it too, and
> that half breaks only in a build.
>
> **Commitments is a view inside Memory, not a seventh node.** `CLAUDE.md`
> fixes the count at six and says a pack *"adds no screens"*; obligations are
> the first pack. The division it does draw is that Memory holds derived facts
> about the user and Knowledge holds the documents those came from — and an
> obligation is a derived, correctable claim carrying provenance back to a
> source. Same store of belief, same correction loop, a different shape of
> record. `Facts | Commitments`, with the live count on the tab.
>
> **It is not a calendar, and the shape is where that is enforced.** No grid,
> no month, no week. A list in the order things fall due, and every action on
> it is *report* or *correct*: nothing schedules, notifies or writes anywhere
> but the obligations store.
>
> **The clause is in the collapsed row, never behind a disclosure.** A clause
> one click away is a clause nobody opens, and a date somebody reorganises
> their week around with the evidence hidden is a date they will trust without
> checking — which is what the rule exists to prevent. **The questions are
> above the commitments** for the same reason: a document read incompletely
> must not look cleanly read.
>
> **Who owes it is one click**, because it is the field the extractor
> deliberately refuses to guess and therefore the one the user most often sets.
>
> Verified against a live backend on a scratch `ZARAM_DATA_DIR`, driving the
> real routes: ingest a statement of work, answer *"when was it issued?"* with
> 15 August and watch `net 30` become **14 September**; correct the deliverable
> from 2 October to 9 October and watch the original appear under *Settled and
> corrected*, struck through, dated, pointing at its replacement; mark one met,
> dismiss one, and see the counts move 5 → 4 → 3.
>
> **What is deliberately not built: a way to dismiss a question.** There is no
> backend route for it. A clause the user cannot date — because they do not
> know the issue date, or because it is not really a commitment — sits in
> *Needs a date* forever, and a permanent item nobody can clear is the shape of
> an engagement mechanic the product forbids. It wants `POST
> /obligations/questions/{id}/dismiss`, stored rather than deleted, exactly as
> a dismissed obligation is.
>
> ### Two defects the interface exposed, both in extraction, both unfixed
>
> Measured directly against `extract_obligations`, not inferred from the
> screen:
>
> **A real deadline is dropped with no obligation and no question.**
>
>     The first round of concepts is due by 14 September 2026.   ->  nothing
>
> It clears `_COMMITMENT` — *due*, *by* — and carries an unambiguous date, and
> `_classify` returns `None` because no word in it names a payment, a
> deliverable, an expiry or a renewal. This is the same failure that was fixed
> this morning for *"Payment terms: 30 days from the invoice date"*, arriving
> by the other gate: there the kind was known and the commitment gate dropped
> it; here the commitment is known and the kind gate drops it. Both discard
> silently, which is the part that matters.
>
> **A newline shreds a sentence, and the fragment is shown as the evidence.**
> `_TERMINATOR` is `[.!?;](?!\d)|[\r\n]+`, so a soft wrap ends a clause:
>
>     Final artwork must be
>     delivered by 2 October 2026.        ->  clause: "delivered by 2 October 2026."
>
>     The image licence renews on 5 January 2027 and will continue at the then
>     current rate unless cancelled beforehand.
>                                        ->  clause: cut at "at the then"
>
> Both are on screen now, and wrapped text is the *normal* case for plaintext
> and for PDF extraction — so this weakens the one guarantee the package makes
> on most real documents. The date is still right; the citation is a fragment.
>
> Breaking on a newline cannot simply be removed: a headed list
> (`Due: 1 September 2026`) has no punctuation and the newline is its only
> boundary. The rule that separates the two is whether the wrap lands
> mid-sentence — lowercase before it and lowercase after — and that is a
> heuristic with real failure modes, which is why it belongs in its own pass
> with its own tests rather than at the end of a session about the interface.
> **Extraction accuracy is "the whole thing"; it should not be amended in
> passing.**
>
> ### What the tests were made to prove, by breaking the code
>
> 31 new tests, and each of the nine things they claim to cover was disabled in
> turn and the *named* survivors read — not the failure count. All nine went
> red, in the tests that claim them: the clause hidden behind the disclosure
> fails *"is on the row before anything is expanded"*; the questions dropped
> from the view fails four, including the ordering test; `daysUntil` switched
> from calendar days to instants fails *"is zero all day on the due date"* and
> nothing else, which is the one that guards the evening.
>
> The harness itself was wrong first and said so loudly: passing two test paths
> as one argv string ran **zero** tests and printed nine confident
> `GREEN — NOTHING CAUGHT IT` lines. *Check the instrument before reading its
> output.*
>
> **One live defect was found by a test asserting a property rather than a
> type.** `correctObligation` spread the caller's object into the request body,
> so a plain object carrying `source_clause` would have posted a rewritten
> clause to the one endpoint whose whole design is that the clause is not
> editable. The backend ignores the field today, which is exactly what makes it
> quiet — it would start mattering the day someone widens
> `ObligationCorrection` there. The body is now assembled field by field.
>
> Also fixed while looking at it: the row printed *"Payment of GBP 1,200.00 due
> · GBP 1200"*, one figure twice in two spellings, because the backend's
> `_summarise` already writes the money into the summary; and a settled row
> printed a countdown — *"September 20, 2026 · in 25 days · done"* — to a
> deadline that had stopped mattering when the user said so.
>
> **Not called, and the reachability guard now says otherwise.**
> `GET /obligations/{obligation_id}` has no client function; the listing
> carries everything the surface needs. The guard stopped reporting it because
> its path matching is loose enough to be satisfied by the identifiers around
> it — worth knowing before trusting a shrinking count from that instrument.


> ### Obligations reach the product — the eighteenth, wired
>
> `backend/obligations/` had `contracts.py`, `extract.py` and 28 green tests,
> and was imported by nothing but that test file. CLAUDE.md calls it the
> freelance pack's entry point and the reason someone opens Zaram in week one.
> Three things were missing: somewhere to put a commitment, a caller, and a way
> to correct one.
>
> **`obligations/records.py`** is append-and-supersede only. A correction
> writes a new row and points the old one at it, the same shape
> `MemoryRecord.superseded_by` uses for facts — rule 4 says the affected
> answers must change, not that the previous belief should vanish. A dismissal
> is stored rather than deleted, because deleting means the next ingest of the
> same document extracts the clause and asks again, which teaches the user that
> correcting Zaram does not stick. Identity is a hash of document, clause, kind
> and date, so re-ingesting a file is a no-op.
>
> **The seam is `_ingest_one`**, injected the way `store_fact` already is, so
> `ingest/service.py` stays testable without a Spine or an obligations
> database. Obligations are read from the **whole parsed document**, never the
> chunks: `chunk()` splits on size and a clause is a sentence, so half of
> "payment is due within 30 days of the invoice date" is a fragment rather than
> a commitment. Extraction failure is caught and logged — a commitment Zaram
> could not read is bad, a document that failed to ingest because of one is
> worse.
>
> **Two refusals, both deliberate.** No anchor date is supplied at the ingest
> layer, because the parsers return text and not fields, so "30 days from the
> invoice date" is stored *unresolved with the question that would settle it*.
> Passing today's date would turn "I do not know when this was issued" into a
> confident wrong deadline the user plans their week around. `direction` stays
> UNKNOWN for the same reason: the sentence reads identically on an invoice
> sent and one received, and guessing tells a freelancer they owe money they
> are in fact owed.
>
> **A defect found by wiring it up, on the canonical case.** `_COMMITMENT`
> gates every sentence before a date in it is read as a deadline, and
>
>     Payment terms: 30 days from the invoice date.
>
> carries none of `due`, `by`, `within` or `net` — so it was dropped at that
> gate with **no obligation and no unresolved question**. Classified as a
> payment, its thirty days parsed, then discarded silently. That is the
> commonest clause on a real invoice and the exact sentence
> `test_recall_eval.py` uses as its sample invoice: the repository's own
> canonical example was the one the extractor could not read. Fixed by treating
> a parsed relative term as commitment evidence rather than by widening the
> regex, which keeps "we met on 3 March" out — asserted directly.
>
> Routes: `GET /obligations` (with the open questions beside them), read one,
> correct, dismiss, mark met, and `POST /obligations/questions/{id}/answer`.
> The source clause is not on the correction model at all — a correction says
> Zaram read the sentence wrongly, not that the sentence was different.
> Answering with a date that still does not resolve the clause returns 409 and
> leaves the question open rather than closing it on a guess.
>
> **What is not built**: any interface. The obligations exist, are correctable
> and are reachable over HTTP, and nothing on screen shows them. That is the
> next piece and it is where CLAUDE.md's constraint bites — *Zaram surfaces
> obligations in context and drafts the response; it is not a calendar and must
> not become one.*
>
> ### Two user databases that should never have been in the repository
>
> `backend/domains.db` was committed in `c07177b` and tracked since. Empty, so
> nothing leaked and the history is clean — but tracked means the first
> knowledge domain the user creates turns it into a modified file in
> `git status`, ready to be committed with real content. `backend/obligations.db`
> is new and holds the deadlines and payment terms read out of the user's own
> contracts, which is the most sensitive store in the product after the Spine.
> Neither was ignored. Both are now.

> ### Documents stopped being a text dump, and an invoice stopped losing its money
>
> The complaint was that generated documents "do not meet the standard of
> templates you can get online". The page design was never the problem — the A4
> page box, the serif measure, the masthead, the tabular figures and the row
> hairlines were all already written and tested. **The vocabulary to reach them
> was missing at the one end that writes.**
>
> `render_document` took `Sequence[str | Claim]` and wrapped every member in
> `<p>`, escaping it on the way, so a model asked for a proposal produced
> markdown that came out as literal text: a paragraph reading `## Scope of
> Work`, another reading `- Discovery`, a fee table as one mangled block of
> pipes. There was no way to express a heading, a list or a table.
>
> It was missing only at that end. `export/_reader.py` has always parsed
> `h1, h2, h3, p, li` plus `table/caption/tr/td/th`, and `export/docx.py` has
> always mapped headings to Word heading styles and `li` to "List Bullet". The
> readers were built for a document the writer could not produce — this
> repository's signature shape, arriving from the far side.
>
> So: `Heading`, `BulletList`, `TableBlock`, `PageBreak` and `RichText` in
> `artifacts/contracts.py`, dispatched by `render_block`. `str` and `Claim`
> are unchanged and first, so every caller that predates them takes exactly the
> route it always did.
>
> **`create_document` also passed none of the masthead arguments it had.**
> `letterhead`, `meta` and `kind_label` had been accepted by `render_document`
> since the letterhead work landed, and the only caller that makes a prose
> document passed none of them — so every proposal and report rendered
> `<header class="masthead"><div></div></header>`: present, correctly styled,
> and empty, while the invoice path three methods down looked like a real
> document. Reachable from one caller out of two is why it read as a design gap
> rather than as a bug, and it is the shape `npm run check:reachability` is
> explicit about missing.
>
> ### The model writes markdown, so Zaram now reads markdown
>
> The block types are an API, and a language model does not assemble JSON.
> `markdown-it-py` (CommonMark + GFM tables, MIT, already installed) parses;
> `artifacts/markdown_blocks.py` maps its tokens onto the block types and
> enforces two bounds a general-purpose renderer has no reason to enforce.
>
> **Raw HTML is disabled, and that is not the default.**
> `MarkdownIt("commonmark")` sets `html: True` — measured, not assumed — so the
> naive construction passes a `<script>` tag from a model's reply into a file
> the user sends to a client.
>
> **The inline tag set is exactly what `_reader.py` parses**: strong, em, code,
> br. Narrower than "safe HTML", and the reason is not security — a tag the
> readers do not know survives into the preview looking correct and vanishes on
> export with nothing reporting it. `img` is dropped to its alt text, because a
> markdown image names a URL and a document that fetches one is a remote asset
> arriving inside a data file, where `check-no-remote-assets.mjs` cannot see it.
>
> ### Not all local models produce the same document, and the adapter absorbs it
>
> Measured, same prompt, same task:
>
> | | fenced? | parsed |
> |---|---|---|
> | `gemma4:12b`, plain prompt | no | 7 headings, 8 paragraphs, 4 lists, 1 table |
> | `qwen2.5-coder:14b`, plain prompt | **yes** | **1 block** — a monospace blob |
> | `qwen2.5-coder:14b`, format rules | no | 9 headings, 5 paragraphs, 4 lists, 3 tables |
>
> The coder model wraps its whole answer in a fenced markdown block every time;
> gemma4 never does. No hand-written test markdown would have produced that.
> **The answer is two layers**: a format contract in the prompt removes most
> variance, and the adapter absorbs the rest. Neither is sufficient alone — a
> prompt is a request, not a guarantee.
>
> Three classes are handled: relative heading depth (the shallowest heading
> becomes h2, so a `#` opener and a `##` opener produce the same document),
> title restatement, and whole-document fencing. **One known and unhandled**: a
> model that opens with "Sure! Here's the statement of work:" leaves a stray
> paragraph. Untested, flagged rather than claimed.
>
> This is also why the answer to "should we just tell users to use cloud" is
> no. It was never a capability failure — qwen wrote a perfectly good statement
> of work and then wrapped it in backticks.
>
> ### An invoice exported to Word had no line items, no amounts, no total
>
> `docx.py` had **no table handling at all**. `_reader` parsed tables and
> `csv`, `pptx`, `text` and `xlsx` all consumed them; the Word exporter never
> mentioned them. Not a latent gap waiting for structured documents — live, on
> the flagship document. Measured that way before the fix: title, "Billed to",
> the client's name, and nothing else. A missing citation is embarrassing; a
> missing charge is unpaid work.
>
> Then, one layer in: `colspan` was ignored, which does not lose a cell but
> shifts every later cell leftwards. The totals block spans three columns, so
> the amount owed printed **under a heading reading Qty**. Worse than missing,
> because nobody doubts it.
>
> Position is carried on `Table.after_block` rather than by interleaving a
> placeholder into `blocks`, because every existing consumer iterates
> `body_blocks()` and expects only `h1, h2, h3, p, li`. `h3` also stopped
> collapsing into Word Heading 2, which had been flattening the outline that
> Word's navigation pane and the PDF bookmark tree are both built from.
>
> ### The user's own records were being handed to the model as web results
>
> `knowledge.search` fans out across providers and returns web results and
> Spine records in **one list**, each carrying `provider` and `type`.
> `format_search_results` read only `title`, `url`, `snippet` and `published`,
> dropping the field that tells them apart, and printed the lot under the
> INTERNET SEARCH RESULTS marker with "ALWAYS trust the live sources."
>
> Measured on a live question about the day's news: **five of six "internet
> search results" were the user's own Spine records** — one a stored
> conversation turn, three near-duplicates of the same old prompt — and the
> single genuine web result ranked last of six.
>
> Rule 2 broken (a `memory:` id printed on a `URL:` line is a web address that
> does not exist and cannot be checked), rule 7d broken (a conversation turn
> presented as research, alongside copies of itself), and the instruction
> simply wrong for most of the block.
>
> `Origin` now classifies each result and the label prints beside the source
> number; a non-web source gets `Reference:` and never `URL:`; the instructions
> are assembled from what is actually in the block. `origin_of` defaults to
> *local record* for anything unrecognised — calling a web page a local record
> understates a source, while the reverse is the rule 2 failure. When in doubt,
> claim less.
>
> `SEARCH_MARKER` is unchanged and asserted to be: `needs_search` suppresses a
> second search on it and `planner` splits the user's question out of it, so
> rewording the header would have broken both. The honesty sits beside the
> sentinel.
>
> **Left for the maintainer**: whether `conversation`-type memories belong in
> `knowledge.search` results at all is a rule 7d question. Labelling them
> correctly is not the same as deciding they should be there.
>
> ### The recall eval was grading its most important question against nothing
>
> Step zero before touching retrieval: check the instrument.
> `TestTheCorpusIsFitToMeasureWith` already asserted filler does not *answer*
> the eval questions — the title-sequence lesson. **Nothing asserted the filler
> was near them**, and CLAUDE.md's rule is *near the target without answering
> it*. Only the second clause was enforced.
>
>     note               nearest filler shares  0% of its content words
>     harbour-brief      nearest filler shares 75%
>     nda                nearest filler shares 75%
>     century-invoice    nearest filler shares 77%
>     harbour-invoice    nearest filler shares 80%
>
> `note` is the preference document — the global-vs-project case from rule 7i,
> the most product-specific question in the eval. It was graded against a
> thousand invoices, briefs and NDAs and won on vocabulary alone. **Recalling
> it proved nothing, and the eval had been counting it as a pass.** The
> title-sequence failure with the sign reversed: there, filler answered and
> correct retrieval read as a miss; here nothing came near and weak retrieval
> read as a success.
>
> Fixed with preference-shaped filler. `note` now sits at 58%, and the scale
> eval's target ranks moved from a trivial all-1 to **[1, 1, 1, 1, 2]**, the 2
> being "How should I write to clients?". Recall still holds at rank 2 of 100
> inside a shortlist of 6.
>
> ### Bitemporality is stored and never queried — the seventeenth
>
> Found on 26 August while answering whether Zaram's memory is comparable to
> the state of the art. `MemoryRecord` carries `valid_from` / `valid_until` —
> **valid time**, when the world changed — kept distinct from `superseded_at`,
> which is **recorded time**, when the user said so. That separation is
> genuinely strong and is precisely what Zep/Graphiti markets as its headline
> differentiator.
>
> `runtimes/memory/valid_time.py` implements the queries over it —
> `in_force_at`, `history_of`, `explain` — and **is imported by exactly one
> file: its own test.** The field is written, persisted and exported; nothing
> in recall filters by it. So the differentiator is not real yet: Zaram can
> store that the day rate was 500 until June and 600 after, and cannot answer
> "what was it in May" through any live path.
>
> This is the seventeenth complete, tested, unreachable subsystem, and it is
> the one that most directly undercuts a claim worth making. **Do not repeat
> the bitemporality claim until something calls `in_force_at`.**
>
> ### Whether the memory is state of the art: unanswerable, by our own standard
>
> CLAUDE.md says *"Benchmark against LoCoMo / LongMemEval, not by feel."* That
> has never been done. The only three places those names appear in the repo are
> CLAUDE.md, this file, and the first line of `test_recall_eval.py` — which
> says explicitly *"Not a benchmark against LoCoMo or LongMemEval."*
>
> What exists is 5 questions over a 5-document corpus, plus an opt-in scale
> test at 100. Those numbers are now trustworthy (see the corpus repair above)
> and they are not a benchmark. Mem0, Zep and Letta all publish figures; Zaram
> publishes none, so *comparable to state of the art* is unsupported in either
> direction and should not be claimed.
>
> **The architecture is the strong half.** `MemoryRecord` carries no provider
> and no model field, so it is cross-model by construction rather than by
> adapter, and one shared embedder means one index serves every provider.
> `superseded_by` keeps correction history instead of deleting. Provenance,
> origin tagging and `global`/`project:<id>` scope are all present.
>
> **Cross-vendor has never been observed on this machine.** `settings.json` has
> no cloud key, `default_model` is null, routing is `prefer_local`, and
> `/health` reports openrouter with `model: null`. Cross-*model* within Ollama
> (gemma4 and qwen2.5-coder) is demonstrable; cross-*vendor* is not. The
> current milestone — ask model A, ask model B later, get a cited answer —
> still has one working provider.
>
> ### What was measured, and in what condition
>
> Suite **2512 passed, 21 skipped, 0 failed**, Ollama up. The document and
> search work is covered by 20 new tests, each confirmed to fail without its
> fix by disabling the fix and watching them go red.
>
> `gemma4:12b` writes at **30.3 tok/s** fully resident (8.4 GB, 100% GPU).
> `qwen3.8:27b` is 18.7 GB against 12 GB of VRAM — 45% on GPU, 55% on CPU,
> **1.85 tok/s**, 95.6 s cold load. Nineteen times slower, and no Ollama flag
> fixes a 10 GB shortfall. On a 12 GB card the ceiling is a 14B fully resident.
>
> **Unexplained and worth instrumenting**: the suite ran in 2:53, 3:48, 4:50
> and **20:46** on the same machine with Ollama up in every case. No stale
> backend on 8420, Ollama answering 200. The mechanism CLAUDE.md already blames
> for the 4-vs-20 split is provider-probe timeouts, and that is where to look.
>
> ### Routing: the classifier is cheap, the swap is not
>
> `_rank_key` says fit is ordered first because *"a specialist that forces an
> eviction costs seconds on this exchange and on the next one that swaps
> back"*. What it ranks on is `model_fits_resident`, which is
> `size_bytes <= budget` — **a static capacity check with no reference to what
> Ollama currently has loaded.** Two different questions: *could this fit* and
> *is it loaded right now*. Only the first is asked.
>
> So a coding question routes to `qwen2.5-coder:14b` (9.0 GB) while
> `gemma4:12b` (7.6 GB) sits loaded, paying a full unload and reload. Both
> clear the ~9.1 GB budget, so both tie at tier 0 and specialisation breaks the
> tie. The docstring describes a protection the code does not implement.
>
> `INTENT_SPECIALISATION` maps exactly one intent — `CODE` to `"code"` — so
> that single entry is the only thing that can trigger a swap today. Measured,
> qwen2.5-coder ran at 10.8 tok/s against gemma4's 30.3. **Deleting that one
> mapping would remove every swap in the product**, and the open question of
> whether the coder model is even better at code is still open and needs three
> real coding questions judged by a human.

---

## Previous state — 19 August 2026

> ### Web search was running, leaving the machine, and being thrown away
>
> The symptom was reported repeatedly as *"web search does nothing with local
> models"*, and every previous attempt looked at the search layer. **The search
> layer was the one part working.** The egress log proves it: `duckduckgo.com`
> allowed, `en.wikipedia.org`, and `internet.deep_read` pulling real pages. The
> toggle was on, `duckduckgo.com` was `allow`, the kill switch off, and `ddgs
> 9.14.4` installed in both virtualenvs and preferred over the dead package.
>
> The break was one layer downstream, in the seam between two steps of a plan.
> `execution_engine` wrote the search step's output into `step_results` and
> **no line ever read it**. The only consumers were the `document.*` injection
> and `reasoning.generate`'s own result. So the reasoning step was dispatched
> with `input_data["prompt"]` still holding the bare question, and the model
> answered from its weights — having just been paid for a search.
>
> **`main._format_search_results` built exactly the block that was missing, and
> had no caller outside its own two tests.** Another complete, correct, tested,
> unreachable subsystem, in the documented shape: the tests asserted the
> *formatting* and nothing asserted that anything *used* it.
>
> Fixed by moving it to `core/search_context.py` — the engine is its only
> consumer and the kernel boundary runs one way — and injecting before the
> reasoning step, mirroring the document injection ten lines above. Three
> details that were not obvious: the search step yields a JSON **string** and
> the engine accumulates step output as text, so the original `(query, dict)`
> signature could never have been called with what the engine holds; `0` and
> `None` are kept apart by `result_count`, because `if not count` would
> announce "the web had nothing" about a search that errored; and the block
> still ends with the user's question, on the same ordering argument
> `identity.py` makes about a hostile manner.
>
> **The tests were verified to fail without the fix**, by disabling the
> injection and watching two of them go red. `_format_search_results` had two
> passing tests for the entire time it was reaching nothing, which is the whole
> reason that check is worth making.
>
> ### Routing now asks what the question is, and modality gates rather than ranks
>
> `_who_chose` said it outright — *"routing has no task classifier yet"* — and
> the models runtime chose one model at boot and used it for every capability,
> including `vision.analyze`. `ProviderManager.select_model_for_task` takes a
> **gate** and a **preference** and keeps them apart: `requires_vision` filters
> the candidate set before ranking, and returns `None` when it empties rather
> than the closest permitted thing; `specialisation` orders survivors in three
> tiers, since a maths fine-tune is a worse answer to a coding question than a
> general model is. The dead `orchestrator` still contains the merged version —
> `scoring.py` records a missing *required* capability as a warning and ranks
> the candidate anyway.
>
> `IntentType.CODE` with eight exemplars written to sit clear of `tool` and
> `conversation`; `_TOOL_KEYWORDS` loses `"code"`, which was sending "is there a
> cleaner way to write this code" to `tool.terminal` on exactly the machine
> where the embedder is down and nothing else would catch it. `_resolve_model`
> and `_who_chose` become one `_ModelChoice`, and `chosen_by: task` is reported
> **only when the routed pick differs from the untasked one** — on a
> single-model machine nothing was routed, and saying otherwise is a rendered
> value nobody measured.
>
> ### The model set, decided by measurement
>
> Six superseded models removed. **`gemma4:12b` is the daily driver** — 7.6 GB,
> fits the ~9.1 GB budget beside `bge-m3`, 262144 context, and `ollama show`
> reports `vision` and `audio`, so it covers images with no swap and no code
> change. The plan that came into the session had it marked for deletion in
> favour of `qwen3:14b`, which is 9.3 GB and therefore **fails the residency
> gate it was chosen to satisfy** — and is a generation behind, since Qwen's
> current line has no dense model under 27B.
>
> **`qwen3.8:27b` pulled and measured, not estimated: 1.45 tok/s.** Ollama
> reports 18.70 GB loaded, **8.59 GB on the GPU and 10.11 GB in system RAM** —
> more than half the model on the CPU. The 3–5 tok/s figure quoted from other
> people's numbers was roughly three times optimistic. It is correctly excluded
> from auto-selection by `model_fits_resident`, so it is reachable only by being
> named. A 3060 owner reported ~9.7 tok/s on this model with llama.cpp using
> Q4_K_S, a quantised KV cache, selective FFN offload and MTP speculative
> decoding — **6.7× what Ollama does**, and none of those flags are reachable
> through Ollama.
>
> ### Two disclosures that were missing, and one that was already there
>
> Search suppression is now visible. `search_suppressed` is a separate field
> from `not requires_search`, which is false for every ordinary question too;
> the only trace used to be a `logger.debug` line. A search that runs and
> returns nothing now says so as well, since otherwise it is indistinguishable
> from one that never ran.
>
> `core/untrusted.py` is wired at the recall boundary, where it was always
> needed: recall folds passages into the **system prompt**, and those passages
> are often written by whoever sent the user the file.
>
> **And the README was understating the product.** It said *"the local API has
> no authentication"*. `RequireApiSecret` is installed as middleware at
> `main.py:155`, a per-launch secret is minted at boot, and
> `test_api_requires_the_credential.py` asserts no-credential refused, wrong
> credential refused, health not exempt, and `X-Zaram-Client` explicitly *not* a
> credential. That gap closed and the status page did not notice — the same
> defect the file already records itself having had, in the same direction.
>
> ### Kokoro lost torch and kept its timings — 662 MB, measured
>
> The open question this file recorded — *"whether to move Kokoro off torch"* —
> is answered, built and tested. `KokoroConfig.backend` selects `torch` or
> `onnx`; both go through the `_default_pipeline_factory` seam that already
> existed, both yield `.audio` and `.tokens`, and `_run_synthesis` is unchanged
> and cannot tell which it got. `VoiceProvider` did the job it was written for.
>
> **The saving is 662 MB, not the ~590 estimated here**, because torch drags
> sympy (79 MB) and networkx (19 MB) behind it and nobody had counted them.
> Dropped: torch 528, transformers 109, sympy 79, networkx 19, and 20 more in
> tokenizers/safetensors/mpmath/kokoro/functorch/torchgen. Added: onnxruntime 45,
> onnx 48. `backend/requirements-voice-onnx.txt` is the install.
>
> **The blocker was real and it was word timings, exactly as this file said.**
> The community export emits `waveform` and nothing else — measured, not
> assumed — so a naive swap would have shipped a smaller installer and a shut
> mouth, one session after the shut mouth was fixed.
>
> **`pred_dur` is still computed inside the graph; the export just never wired
> it to an output.** Walking back from the encoder's `CumSum` recovers
> `KModel.forward` line for line, so `/encoder/Gather_output_0` *is* `pred_dur`.
> Adding an existing internal tensor to `graph.output` is local surgery on a file
> already on disk: no re-export from torch, no second set of weights, nothing to
> host. Cached after the first run, and **refused loudly** when absent — arriving
> at empty timings by accident is precisely how lip sync dies with everything
> green.
>
> **Against torch, five sentences, `am_michael`: word timings are bit-identical
> — 0.000000 s drift, same words, same order — and audio length matches to the
> sample.** Magnitude spectra correlate at 0.984. One difference is real: ONNX is
> ~3 dB louder (best-fit gain 1.4385, sd 0.0155), flat across the spectrum, which
> reads as an iSTFT normalisation convention in the export rather than lost
> precision. Not corrected by a constant in code — the number has no derivation,
> and an unexplained scalar on the audio path is the same class of error as a
> ranking blend used as a threshold. A full-scale guard is in code, because
> `soundfile` clips silently and clipping is the one difference a listener would
> hear as a fault rather than a level.
>
> **fp16 was measured and rejected.** Correlation against torch starts at 0.963
> and falls to **0.601** by the end of a five-second sentence, per-window gain
> swinging 1.43 to 0.86 — error accumulating through the decoder, and the
> sinusoidal source generator's `CumSum` is the obvious culprit. The worst
> available defect shape: invisible in a short test, audible at the end of a long
> reply. fp32 holds 0.960 over the same final second.
>
> **The default is still `torch`, and that is the one thing outstanding.** Every
> objective measure says equivalent; one says 3 dB; nobody has *heard* them side
> by side. CLAUDE.md's fifth integration test is that the maintainer judges
> whether output is good, and no measurement above is that judgement. Three WAVs
> were produced for exactly that A/B. A test asserts the default, so flipping it
> trips a named assertion rather than sliding through a diff.
>
> **Proven torch-free in a clean virtualenv**, not inferred from metadata: with
> torch, `kokoro` and `spacy-curated-transformers` absent, it synthesised 4.25 s
> with 11 timed words and `torch` never entered `sys.modules`.
>
> **Two guards caught real defects in this work, and both were right.**
> `test_installer_payload` found the patched 326 MB graph being written into
> `backend/` — `in_data_dir` resolves to the backend *source* directory in a
> checkout, correctly for the Spine and disastrously for a regenerable blob that
> would have gone into the installer. `test_egress_chokepoint` found
> `huggingface_hub` reached without the gate. Both fixed; every ONNX fetch now
> tries the cache offline first and asks the gate only when there is genuinely
> something to download.
>
> **A hole in the torch path is now named rather than fixed:**
> `KPipeline.load_voice` downloads a `.pt` on first use of a voice, at synthesis
> time, with nothing asked and nothing logged. The ONNX path routes its voice
> loads through the gate because they happen in the same place — inside
> `__call__`, outside the window `_ensure_pipeline` wraps.
>
> **One trap worth carrying forward.** spaCy loads plugin entry points from
> whatever is installed; `spacy-curated-transformers` is such a plugin and
> imports torch at module scope; spaCy raises rather than skipping a plugin it
> cannot import. One contaminated virtualenv therefore drags 494 MB back through
> a package nobody asked for, invisibly to any requirements file. Same shape as
> the misaki/spaCy lesson, with the edge running the other way.
>
> ### Three interface changes, asked for the same day
>
> **Text is typed rather than dumped.** It always streamed; what it did not do
> was *read* like it, because tokens arrive in clumps. `lib/typewriter.ts` holds
> the rule as a pure function — floor rate, plus a share of the backlog, so it
> types steadily on a trickle and catches up on a burst instead of queueing.
> Measured: a 1200-character lump is absorbed in ~0.93 s; a fixed 45 c/s reveal
> would have taken 26 s and still been typing after the answer, the speech and
> the next question. **Display only**: `streamingText` remains the truth and is
> what `pushSpeech` reads, so the voice never waits on an animation. Skipped
> entirely under `prefers-reduced-motion`.
>
> **The hook around it shipped broken and was caught by re-reading it, not by a
> test.** Keying the effect on `text` meant every token tore it down and reset
> `last = performance.now()`, so at the next paint `elapsed` was measured from
> the most recent token rather than the previous frame — the reveal ran about
> twelve times slow exactly while it was being watched. Measured with the fault
> reintroduced: **38 characters of 1800 after six frames, against 450+ fixed.**
> Every test of the reveal arithmetic passed throughout, because all of them
> call the pure function directly. Same shape as the visemes.
>
> **Two attempts at the regression test were themselves vacuous**, and that is
> the more useful lesson. The first stubbed `cancelAnimationFrame` as a no-op;
> the second rerendered with an identical string, so React skipped the effect
> and the defect could not occur. Both passed against the broken hook. **A test
> for a regression is not finished until it has been watched to fail** — and the
> first diagnosis written down here, that cancellation starved the loop, was
> also wrong: frames scheduled repeatedly within one paint interval still run.
>
> **The model's thinking is shown, and — more importantly — kept out of the
> answer.** `core/reasoning.py` splits `<think>` blocks into their own
> `reasoning` event. This is a defect fix before it is a feature: nothing looked
> for those tags, so on a reasoning model the working *was* the answer as far as
> this backend was concerned — rendered as the reply, committed to the
> transcript, and handed to `pushSpeech`, which means Kokoro read the model's
> internal monologue aloud in avatar mode. The splitter buffers, because a tag
> arrives split across tokens exactly as `[M1]` does, and a half-recognised tag
> does not merely render oddly — it files the rest of the reply under the wrong
> heading.
>
> **A sixteenth unreachable module.** `hooks/useStreamingText.ts` sits in the
> live hooks directory and is imported only by `src/legacy/`, which is
> quarantined. It is also the wrong shape: `startStreaming(fullText)` replays a
> string that already exists, so it can never consume a stream. Flagged, not
> deleted — that touches quarantine policy.
>
> ### What was not verified, and why
>
> **The app was not run.** Ports 5173 and 8420 were both held by a running
> instance, `LISTEN_PORT` is a hardcoded constant and the Host guard pins
> `127.0.0.1:8420`, so a parallel stack would have meant editing shipped code to
> test it — and stopping somebody's running app is not a call to make silently.
> The suites are green (backend, frontend 219, typecheck clean) and the changed
> speech path is display-only, but **that is not the same as having watched the
> mouth move**, and this file's own standard is the screenshot. It is the first
> thing to do next.


> ### Speech was installed into the wrong half of the machine.
>
> Continuing the voice session below. The maintainer asked for speech
> **installed and working** during development, to be removed before the
> installer ships. It is now installed and verified, and there is nothing to
> remove.
>
> **The listening half was dark because there are two virtualenvs.**
> `backend/venv` and `C:\Zaram\.venv` both exist and are both complete
> backends. Diffed, they were identical but for the mic extra — `av`,
> `ctranslate2`, `faster-whisper`, `onnxruntime` present in the root `.venv`,
> absent from `backend/venv`. And `docs/RUNNING.md` told you to launch with
> `ZARAM_PYTHON` pointing at `backend/venv`: the half that could not listen.
>
> **`docs/RUNNING.md` was wrong about why, and the correction is the useful
> part.** It said the launcher "finds nothing" because this repository has
> `venv` rather than `.venv`. It does not find nothing: `cwd` is the backend
> directory, so `../.venv` resolves to `C:\Zaram\.venv`, which **exists**. An
> unset `ZARAM_PYTHON` therefore does not fail — it silently starts a
> *different* interpreter, which is precisely the failure that file's own PATH
> argument warns about, arriving by the route nobody was watching. Corrected
> there; **reconciling the two venvs is a triage decision**, the same shape as
> the two Electron trees.
>
> **The suite was skipping, not passing.** `tests/test_speech_roundtrip.py`
> requires both extras and both weight caches, and 8 skipped reads much like 8
> passed in a summary line. That is how the listening half went a whole session
> unverified while the speaking half worked. With `backend/venv` completed:
> **45 passed** across roundtrip, voice-resolution and recogniser suites, and
> **59 passed** in `voice/tests/`. The roundtrip tests skip when the recogniser
> reports itself unavailable, so their *running* is the evidence the mic button
> is offered. **A guard that fails when these skip on a machine holding both
> extras is worth writing** — otherwise the next silent skip costs another
> session.
>
> **Nothing leaks into the installer**, checked rather than assumed:
> `scripts/build-python-runtime.mjs` downloads a fresh interpreter and installs
> **only** `backend/requirements.txt`, never consulting a dev venv, and
> `check-installer-payload.mjs` has `venv/` and `.venv/` in FORBIDDEN. Two
> independent guards, so "remove it before shipping" needs no action.
>
> ### Kokoro is light; its runtime is not
>
> Measured on disk, because the two get confused: the `kokoro` package is
> **~1 MB**, the weights 315 MB, and the 905 MB is **torch at 494 MB** plus
> transformers at 96 and the spaCy stack at 125. The 82M parameters really are
> small. `kokoro-onnx` would drop torch and transformers — ~590 MB — and
> onnxruntime is *already in the tree* at 43 MB because faster-whisper pulled
> it. The open question is G2P, and the constraint that decides any swap is not
> size but **word timings**: `SpeechTiming` is the lip-sync seam and an engine
> that cannot emit timings costs the viseme chain. Options and caveats in
> `docs/SPEECH.md`; none tested.
>
> ### One defect found and left for the maintainer
>
> `backend/requirements.txt:45` pins `en_core_web_sm` — a spaCy *model* — into
> the **base** install. Nothing in the repository imports spaCy (checked
> repo-wide); it is useless without spaCy, which is not in base; and it is
> pinned as a GitHub release URL, the exact pattern
> `requirements-voice.txt`'s own header says "fails the entire install when a
> connection drops". On the 22 kB/s link measured during this session that is a
> real installer-build failure mode. Not changed — it alters the shipping base.
>
> ### The voice nobody could choose, and the mouth that never opened.
>
> Suites: **2290 backend passed / 0 failed**, 43 skipped — measured with
> **Ollama up**, 3m09s · **206 frontend** · **56 Electron** · typecheck clean ·
> lint passes · guards pass · reachability 2 modules and 2 routes, each a named
> piece of work.
>
> **That backend number is not comparable to the 2207 below**, which was
> measured with Ollama *down*. Both are real and they run different code. Take
> the Ollama-down run before shipping anything, because that is the machine a
> stranger installs onto.
>
> ### The avatar's mouth never opened, and the cause was two writers to one state
>
> Asked for by the maintainer on 19 August: speech automatic in avatar mode,
> with lip sync and animation working. Two of the three were already built —
> `chatStore` gates speech on `renderer === 'avatar'`, and `VrmAvatar` drives
> visemes from Kokoro's own phoneme timings scrubbed against `audio.currentTime`.
> The mouth still never moved.
>
> **`ChatSurface` and `speechStore` both wrote `orbStore`, and only one of them
> guarded.** Speech sets `speaking`; the chat effect set `thinking` while the
> request was in flight and `idle` the moment it finished. Speech starts on the
> first sentence that will not change again and outlives the stream **by
> design**, so that `idle` landed on top of `speaking` on every reply, and the
> avatar — which opens its mouth only in `speaking` — sat shut through the whole
> answer.
>
> **Nothing looked broken, which is why it lasted.** The rim light is the same
> cyan for `thinking` and for `speaking`, so the only renderer that could show
> the difference was the mouth, and a still mouth reads as "lip sync is
> unfinished" rather than as a state bug. The viseme code, the mapping test and
> `check:visemes` were all green and all correct.
>
> `speaking` is now set where it is true — the moment a clip starts playing, not
> when the queue opens, which claimed sound seconds before any existed — and
> `preserveSpeaking` stops chat activity overwriting it. `lib/orbActivity.ts`,
> with the rule as a function so a test asserts it rather than a component
> having to be rendered to find out.
>
> **Measured in a browser, before and after, because this is a visual claim.**
> Driven with Playwright against the system Edge: avatar mode, a real reply from
> a local model, `am_michael` clip fetched and playing. Before: `currentTime`
> advancing 0 → 8.1s, `paused` false throughout, and the mouth shut in all 40
> frames. After: mouth wide open at frame 3, closed at frame 7, four clips
> playing in sequence as the reply streamed. That is the standard the pointer
> gaze failure set — *"if it returns, it returns with a screenshot"* — applied
> to the mouth.
>
> **What this says about the instrument, again.** `check:reachability` sees a
> module nothing imports. It cannot see two modules that both import the same
> store and disagree about who owns a field. That is now the second shape found
> this session that the report is blind to, after a settings control nothing
> downstream read.
>
> ### The speech behaviour is now written down, because it was only in the code
>
> The maintainer asked what the voice was, whether it was male, and whether
> speech was automatic in avatar mode with lip sync working. Every answer
> existed only as behaviour — no document held the contract, so each question
> had to be answered by reading source. That is now `docs/SPEECH.md`: the two
> modes and why there is no third, the voice resolution order, streaming
> granularity, barge-in, the viseme chain, and who owns `speaking`.
>
> **Confirmed rather than assumed**, since three of the four were already
> built: orb mode offers a **Speak** button per reply and is otherwise silent;
> avatar mode speaks automatically; barge-in works by **typing** (composer
> `onChange`) and by **microphone** (before `start()`, where it is a
> correctness requirement — the mic would otherwise transcribe Zaram's own
> voice back). Only lip sync was broken, and it was the state bug above.
>
> **Word-by-word speech was asked for and is not built.** `CLAUDE.md` rules it
> out in the same paragraph that requires the streaming — *"a clause is the
> smallest unit with prosody"* — and per-word synthesis would give every word
> the intonation of a complete sentence. What is built already speaks
> *alongside* the streaming text rather than after it, which is probably the
> real intent. Recorded as an open maintainer decision in
> `docs/NEXT-SESSION.md` rather than silently declined.
>
> **`docs/RUNNING.md` is new and is the other thing that only existed as
> folklore.** Launching the real app cost four separate failures in one
> session: `npm run dev:desktop` launches `desktop/src/main/index.ts` while the
> installer ships `electron/main.js`; `ELECTRON_RUN_AS_NODE` is set inside every
> VSCode terminal and makes Electron run the main as plain Node, with a
> `TypeError` naming a line in `main.js`; `backendLauncher` looks for
> `backend/.venv` while this repository has `backend/venv`; and a browser tab
> reports "engine not running" correctly, because it has no desktop host to ask
> for the per-launch secret.
>
> **Two Electron trees is now a triage item.** `electron/main.js` is what
> `electron-builder.yml` packages and what `test/*.test.js` covers.
> `desktop/src/main/index.ts` is a parallel TypeScript implementation with its
> own builder config and its own tests. Both are internally consistent, which
> is why no guard sees it. One is dead weight; deciding which is somebody's
> next job.
>
> ### The voice defect
>
> `user_settings.voice` was written by the character pane, read back by
> `GET /character`, rendered in Settings — and consulted by **nothing**.
> `/voice/synthesize` resolved `request.voice or PERSONAS[persona]["voice"] or`
> a literal, and both frontend callers speak with no voice argument at all. So
> a setting the interface offers, stores and renders back had no effect on any
> sound the user heard.
>
> This is the signature failure wearing a **settings control** rather than a
> module, and `check:reachability` cannot see it: the route *is* called, the
> setting *is* read. What was missing is the one hop between them — a shape the
> instrument does not claim. The answer is a test that asks what the user would
> ask, which is what `backend/tests/test_voice_resolution.py` does.
>
> `_resolve_voice` now orders it explicitly: this request, then the user's
> setting, then a deliberately-chosen preset, then `DEFAULT_VOICE`. Step three
> is narrow on purpose — every request carries `persona="zaram_prime"` whether
> or not anybody picked it, so taking the preset first would mean the preset
> nobody chose silently outranked the only voice the user did. Both voice
> request models take that default *by reference*, and a test asserts it,
> because the day they drift is the day the defect returns by a second route.
>
> **One spelling.** `"af_heart"` was written in six places, including a
> `ChatRequest.personality` field defaulting to a *voice id* that nothing read
> or sent. `voice/config.py` owns it now, and a scan test fails if a live module
> spells it again — the same disease as the two TTS text cleaners and the two
> rankers this repository has already paid for.
>
> **The default is `am_michael`**, male, asked for by the maintainer on
> 19 August. Asserted on the id's own convention (`<language><gender>_<name>`),
> so another male voice keeps it green and a female one does not.
>
> **Verified in the running product, not by the suite.** Backend on a scratch
> `ZARAM_DATA_DIR`. With nothing chosen, `POST /voice/synthesize` returned
> `voice: "am_michael"` and a 108 KB clip. Chose `bm_george` through
> `POST /character`; the *same* request, still naming no voice, returned
> `voice: "bm_george"` and a 122 KB clip. That is the hop that did not exist.
>
> **Speech-out failures also said the wrong thing.** The message was "Speech is
> not installed." sitting under a comment claiming it named "the fix and its
> size the way the OCR extra does". It named neither. Now:
> *"pip install -r backend/requirements-voice.txt (905 MB, one time)"* — the
> size is the half that decides on a metered connection. The test asserts the
> *properties*, a command and a number, so rephrasing stays free and hollowing
> it out does not.
>
> ### The backend could not start on a machine without Ollama, and a green suite had said otherwise for two weeks
>
> Measured then: **2207 backend passed / 0 failed**, 95 skipped, Ollama
> **down**, 21m43s, at HEAD `61d6e36`.
>
> **Say which condition you measured in.** With Ollama running the backend
> suite takes ~4 minutes; with it down, ~20, because every provider probe waits
> for a timeout. It also changes *which code paths execute*. The old
> "2184 passed / 0 failed" was measured with Ollama up and is not the number a
> clean machine produces — measured with it down on 18 August, before the fix
> below, it was 1 failed and 53 errors.
>
> ### The crash
>
> `models_runtime.py` read `m.id for m in rejected` while
> `rejected_default_candidates()` returns `list[tuple[ModelInfo, str]]`. The
> `AttributeError` escaped through kernel boot — **53 tests errored at app
> startup**, with a traceback naming a logging line rather than the model layer.
>
> This is an installer-class defect rather than a logging nit. The branch runs
> only when models are discovered and *every one* is unselectable: a machine
> with no Ollama, which is every machine a stranger installs this on.
>
> **Why it survived.** The *producer* is tested twice and both tests unpack the
> tuple correctly, so the type was never in doubt. The *consumer* had no test
> at all, and its branch does not execute with Ollama up. Nothing was hidden by
> cleverness — it was hidden by an environment condition no previous run
> happened to be in.
>
> The function had promised since 4 August that "every failure here returns
> None… must degrade rather than take chat down with it", and its `try` covered
> its first two statements only. The guarantee now wraps the whole body, split
> into `_choose_model_inner` so a later edit cannot append past it, and the test
> asserts *failure* — strings, bare objects, short tuples, nulls, an exploding
> manager — rather than one more correct shape.
>
> ### Why this codebase is the way it is
>
> **Zaram was partly built with Kilo Code and Trae**, which the maintainer
> confirmed on 18 August. It explains the dominant failure mode precisely:
> complete, well-commented, fully-tested subsystems that nothing calls.
> **Fifteen found so far.** Those tools produce a plausible whole and cannot
> check that anything reaches it, and the tests they write assert the
> scaffolding rather than the contract — which is why "tests green" has
> repeatedly meant nothing here. Assume unreachable until the caller is seen.
>
> `npm run check:reachability` now reports two of the shapes: Python modules
> nothing imports, and backend routes no frontend file calls. It is honest
> about what it misses — a dead branch inside a live function, an unused
> export, a component mounted that should not be. Three of this session's six
> finds were invisible to it.
>
> Report-only in `check:all`; 25 modules and 4 routes are outstanding and
> `--strict` would fail the build today. **Triaging that list is the next piece
> of work** — each is wire, allowlist with a reason, or delete.
>
> **The worst thing it found: `core/untrusted.py` is called by nothing.**
> `Provenance`, `may_instruct` and `scan` — the prompt-injection defence — are
> complete, tested and attached to no code path. Its own docstring names the
> exposure it was written for: *"a hostile invoice is a way to put a deadline in
> someone's week, or a different bank account on their letterhead."* Written
> for the features now being built, never wired to them. **Obligation
> extraction must not ship without it.**
>
> ### Verified in the running product, not by the suite
>
> Backend standalone, then the Vite dev server, driven in a browser. That order
> matters — Vite bakes the API secret in at boot, so starting it first is what
> produces the "engine not running" report about a healthy backend.
>
> - **The orb.** Against a backend reporting an OpenRouter provider and
>   `can_leave_device: true` — the exact state that used to paint amber — the
>   label read **"Local · cloud ready"** at computed `rgb(16,185,129)`, emerald,
>   against amber `#f59e0b`. Read off `getComputedStyle`, which is the check the
>   previous session's orb assessment skipped.
> - **The character pane.** Typed `"  Ada    Lovelace  "`; the backend stored
>   `"Ada Lovelace"`, `settings.json` agreed, and the input rendered the
>   *stored* value rather than the typed one.
> - **Domains in chat.** `POST /chat` with an empty domain emitted, before the
>   answer, *"Nothing is indexed in your Investing domain yet, so this answer
>   used no facts from your files."*
> - **The landing.** Six nodes and the orb, nothing else — a panel reading
>   "EMBODIMENT SPIKE — NOT SHIPPED UI" had been mounted there unconditionally.
>
> **Not verified, and why:** the domain picker's own rendering and the date in
> the system prompt. With no model installed the conversation shows the
> first-run gate instead of the composer, so no composer control renders at all.
> Both stay test-covered until a model exists.
>
> ### Two corrections of my own work, which are the useful part
>
> **A wrong claim reached CLAUDE.md.** The modality paragraph said
> "`ProviderEntry` carries no modality field today; that is the first piece of
> work". Both halves were wrong: `ProviderEntry` is a *provider* record holding
> no models, and modality belongs on `ModelInfo`, which already carries
> `supports_vision` and a `ModelCategory` including `VISION`, `IMAGE` and
> `VIDEO`. Written from a note instead of from the code.
>
> **The reachability guard's first run reported 183 dead modules that were all
> alive** — it resolved relative imports against the repo root. Fixed, then
> sampled five by hand: five true positives. Check the instrument before
> reading its output.
>
> ### Also decided
>
> **Image generation moved into v1** by the maintainer. Shape unchanged — Zaram
> ships no image weights, routes to a provider, logs the egress — and the
> recorded objection is spent, because the cloud engine it was waiting for has
> landed. An image is **its own consent class** under rule 7j.
>
> **Start here, in this order.**
>
> 1. **Wire `core/untrusted.py`.** Security, and a prerequisite for obligations.
>    It is one of the two modules the reachability report still names, and the
>    only one on that list that is a defence rather than a gap.
> 2. **Conversation persistence, as the session/memory split.** There is no
>    conversation history at all — close Zaram and yesterday is gone. Guardrail,
>    enforced by test: the store is readable by the user and invisible to recall.
> 3. **The maintainer's two decisions**, both blocking: delete or revive
>    `backend/orchestrator/` (1,261 lines, no importers, no tests), and rebuild
>    the installer before testing it on a clean machine.
>
> **Done since that list was written.** The reachability report is triaged —
> 25 modules and 4 routes down to 2 and 2, each of the four a named piece of
> work rather than an unknown. What the voice defect adds is the report's
> boundary: a *wired* module whose one useful hop is missing looks identical to
> a healthy one from the outside. `check:reachability` is honest about missing
> three shapes, and this is a fourth. The cheap counter is not another scanner —
> it is asking, of each control the interface offers, whether anything downstream
> reads what it stores.

## Superseded — 18 August 2026

> ### Documents go in three ways now, domains scope what comes back out, and one of this session's own written findings was wrong.
>
> Suites: **2184 backend passed / 0 failed**, 102 skipped · **178 frontend** ·
> **48 Electron** · typecheck clean · lint passes · guards pass. HEAD `3d9db72`,
> working tree clean, **16 commits ahead of `origin/Zaram-V0.1` and not pushed**.
>
> Run the Electron suite with **no Zaram running**: `electron/main.js` takes a
> single-instance lock, so the two bootstrap tests spawn an instance that quits
> instantly and asserts against an empty log. It looks like a regression and is
> not.
>
> **The ingestion service layer now has routes**, so drop, paste and upload are
> reachable rather than merely implemented — the twelfth instance of this
> repository's signature failure, and the first one closed by adding the route
> the code was already written for. `POST /ingest/upload` (multipart) and
> `POST /ingest/text` (JSON), both streaming the same NDJSON the folder scan
> emits, so the interface parses one stream shape rather than three.
>
> **Verified in the running product, not by the suite.** A file dropped onto
> Knowledge, a folder path, and a paste offer accepted, all through the
> interface at `localhost:5173` against a live backend: four documents indexed
> under one `uploads` source, each listed with its character count, the source
> reporting **Local only**. Then *Forget this folder* — the Spine went from 17
> records back to **13**, its state before the session, and the source row
> disappeared.
>
> That last number is the interesting one, because it is what a real defect
> looked like when it was fixed.
>
> **`record_outcomes` replaces a source's rows wholesale, and every drop lands
> in one shared uploads directory.** Correct for a folder scan, which saw every
> file in its source and is entitled to overwrite the lot; wrong for a drop,
> which saw only what was dropped. The second drop therefore deleted the first
> drop's outcome row — and `fact_ids` live on that row, so it also deleted the
> only route rule 4 has back to those facts. The user would have pressed
> *"Forget this folder and everything Zaram learned from it"* and been told it
> worked, while every fact from every earlier drop stayed in the Spine, still
> recallable, with nothing anywhere able to reach it.
>
> Found by the second assertion in a route test — two files kept, one file
> listed. `merge_outcomes` records per *path*, so re-reading one file still
> replaces its own row and the "what is wrong now" property holds per file,
> while every other row survives with its fact ids.
>
> **A refused drop is now all-or-none.** The tenth file being too large would
> otherwise leave the first nine on disk with nothing recording them: bytes in
> the uploads directory that no source row mentions, no answer can cite and no
> deletion can reach — the same orphaning as above, arriving by a second route.
>
> **The known gap this opened, and it is in the delete path.** Removing the
> uploads source forgets its facts and its rows, and leaves *Zaram's copies of
> the documents on disk*. For a scanned folder that is correct — those are the
> user's originals and Zaram must not delete them. For uploads it is not: the
> file there is a copy Zaram made, the button promises "everything Zaram learned
> from it", and four files had to be removed by hand after verification.
> Deciding this is deleting user documents, so it is not a change to make
> quietly. **This is the next thing to fix in ingest.**
>
> **Rule 7h is what shapes the paste.** Files on the clipboard go straight in —
> the user copied a file and there is nothing to decide. Text is *offered*,
> with the real text shown back and a 40-character floor, because a short paste
> is far more often a path meant for the folder field. A dropped folder is
> named rather than swallowed: the browser hands it over as a zero-byte file
> that would be indexed as an empty document, and "I can't do that yet" is the
> true answer where that would be a wrong one.
>
> ### The interface said the engine was down while the engine was answering 200
>
> Reported as "Zaram engine not running", and it was a real defect rather than a
> slow start. `installApiCredential` resolved Vite's build-time value first and
> asked the desktop host only if that was empty. Both exist at once in the case
> nobody had run — the *real* `electron/main.js` loading the Vite dev server —
> and they disagree: `main.js` mints a fresh secret per launch and passes it over
> IPC, while Vite baked in whatever `backend/api-secret` held at boot, a file the
> backend stops writing once `ZARAM_API_SECRET` is set. The stale one won.
> Measured: 401 on everything before, **zero 401s** after.
>
> **A browser tab at `localhost:5173` will still show this, correctly** — it has
> no desktop host to ask. Test in the Electron window. This is the trap that cost
> the most time this session.
>
> ### Ctrl+C was not copying
>
> Toggle Chat was bound to Ctrl+C and `useShortcuts` calls `preventDefault()` on
> every match outside a text field — so it did not shadow Copy, it deleted it, on
> all six surfaces. Measured with a live selection. Now **Alt+C**.
>
> Alt chords match on physical position, because macOS Option is a compose key:
> ⌥C emits `key: "ç"`, so a chord compared on `event.key` would have been printed
> on the keycap and never fired — the Ctrl+K/Win+K defect the matcher already
> carries a comment about. `Ctrl+S` and `Ctrl+O` are **still** swallowed by the
> orb debug shortcuts; same bug class, left for a decision.
>
> ### The orb ignored reduced motion, and its restlessness was arithmetic
>
> `UI-SPEC` requires the gate. `LivingOrb` — the only orb that renders — had none
> across seven infinite animations. Fixed, with colour still transitioning,
> because reduced motion means less movement rather than less information.
>
> The busy feeling had a cause: ten particles ran at `3.5 + p.delay`, ten
> distinct periods, so the field never repeated. Cycles sharing no common factor
> cannot resolve. Every live idle period is now a multiple of 4s and the
> composite repeats every **8s** instead of never. The pulse is unchanged for
> anyone who has not asked for less motion.
>
> **Eleven of the fifteen orb components were imported by nothing, and are now
> deleted** — 464 lines. Only `LivingOrb`, `OrbStatus`, `OrbStatusLabel` and
> `OrbHint` ever rendered. This had already produced a wrong finding in a
> written assessment: "the core of the orb is the cloud accent at rest" is true
> of `OrbCore`'s source and false on screen, because it never mounted. Config
> was read and assumed to render — this repository's signature failure applied
> to its own analysis rather than to a feature. Dead code that looks live is not
> inert; it is a standing invitation to reason about the wrong file.
>
> `settle` and `settleAll` went with them rather than becoming two dead
> functions in place of eleven dead components.
>
> Two colour findings stand and are unfixed, both in `STATE_CONFIG`, which does
> render: **speaking and listening are 29° apart** in hue (emerald against cyan,
> the pair that alternates fastest in a voice exchange), and **idle and thinking
> are the same two hues with dominance swapped** — so "is it working?" is carried
> by rate alone. All five states sit inside a 111° arc. The proposed fix is to
> stop using hue as the state channel at all, since cyan and violet already mean
> local and cloud, and let the orb's *motion character* carry state instead.
>
> ### Also landed
>
> One `SurfaceHeader` replaces six hand-rolled copies — `pb-3` against `pb-4`,
> and Project's title in the wrong typeface. The Zaram mark now appears on the
> landing, quiet and inert. `useIsReducedMotion` returns a real boolean.
>
> **Start here, in this order.**
>
> ### The uploads delete path is closed
>
> *"Forget this folder and everything Zaram learned from it"* now is true.
> Withdrawing a staged source deletes the copies Zaram wrote and asks first,
> naming the count; withdrawing a scanned folder still never touches the user's
> originals. Three conditions guard the delete, and the third — that the stored
> path resolves *inside* the uploads directory — is what stops an outcome row
> from being followed anywhere it likes.
>
> ### Knowledge domains scope retrieval
>
> A named set of sources Zaram can answer from on purpose.
> `knowledge/domain_recall.py` resolves domain → sources → outcomes → fact ids,
> and `MemoryQuery.only_ids` narrows recall to that set.
>
> **The filter sits where the scope filter sits, and that is the design.**
> `retrieval.py` enforces rule 7i once, after every strategy, because
> `_vector_search` never passes through the store's filters — "a boundary
> enforced per code path is a boundary with a hole in it per code path". Domain
> narrowing rides with it, and a test fakes a vector hit to prove it did not get
> its own hole.
>
> **An empty domain is not an absent one.** `frozenset()` is falsy, so testing
> `if only_ids` would widen a domain holding nothing to the entire Spine. The
> check is `is not None`; weakening it to truthiness was tried against the suite
> and the empty-domain test fails, as it should.
>
> Many-to-many, never a tree — a contract is Clients *and* Legal, and a parent
> column would be rule 7h smuggled back in. One memory, many domains: deleting a
> domain deletes a lens, not facts, which matters because the button beside it
> withdraws a source and *does* delete documents. Withdrawing a source unlinks
> it from every domain that held it.
>
> Verified live: a domain created through the interface resolved to exactly **1
> reachable fact out of a 13-record Spine**, with the phrase *"your Investing
> domain"* for the reply to end on.
>
> **Not yet wired into `/chat`.** The scope exists and is proven at the
> retriever; the conversation does not yet let the user pick a domain to ask
> inside. That is the next piece and it is small — `only_ids` is already a
> parameter on `retrieve`.
>
> **Start here, in this order.**
>
> 1. **Let a question be asked inside a domain.** The plumbing is done; the
>    conversation needs a picker and the reply needs to say which domain it read
>    from.
> 2. **The session/memory split** — the structural fix rule 7d actually needs.
> 3. **Run the installer on a clean machine.** Unchanged, and still only the
>    maintainer can. Note the current build predates the ingestion routes.

## Superseded — 17 August 2026

> ### Web search was unreliable for four separate reasons, and none of them was the search.
>
> Suites: **2120 backend passed / 0 failed**, 102 skipped · **158 frontend** ·
> **48 Electron** · typecheck clean · lint passes · guards pass. Working tree
> clean; `Zaram-V0.1` pushed to origin.
>
> **Run the suite with no backend running.** A live backend holds the SQLite
> lock on the real `spine.db` and the suite stalls on `test_memory_scope_api`
> rather than failing. Measured: **3m20s** clean, **34m** with a backend up.
>
> The maintainer reported that Zaram answered confidently and wrongly about the
> world — "Joe Biden" for the current president, a wrong Osun State result, "I
> don't know" about South Africa, while the American election and the World Cup
> came back right. Four defects, each measured, none of them in the search
> connector:
>
> 1. **The semantic router bypassed the keyword classifier entirely.**
>    `classify` returns the moment the semantic path answers, and that path
>    decided search by `intent == "search"` alone. "Who is the current president
>    of the United States?" routes to **`conversation` at 0.022 confidence**
>    while `needs_search` matches it on three patterns. The error is treating
>    `search` as a rival intent to `conversation`: a question can be perfectly
>    conversational and still have an answer that changes.
>
> 2. **300 characters was the entire evidence base.** Every connector truncates
>    to 300 chars and nothing fetched a page body, so the model was handed three
>    sentences that frequently did not contain the answer and filled the gap from
>    its weights. Prominent questions were right and regional ones wrong — not a
>    harder question, a **less quoted** one. `deep_read.py` fetches the top three
>    pages in parallel.
>
> 3. **Choosing a cloud model silently deleted the search step.**
>    `search_applies_to` was a blanket local/cloud switch, reasoned as "a
>    frontier model knows more so a live result matters less". True for general
>    knowledge, false for the one category where search matters most: every model
>    has a cutoff. Recency now outranks the economy. Nothing routes *to* cloud
>    because of a search — model selection runs first and search follows.
>
> 4. **The prompt told the model to name its sources.** With all three fixed,
>    the reply was *"You mentioned a few sources that might contain the latest AI
>    news. Let's review them:"* and a bibliography. Every fact correct and freshly
>    fetched; nothing answered. Deep-read had made the evidence good and the
>    framing was spending it on a reading list. It also forbade the `[S1]`
>    markers, which are the grounding mechanism — `lib/markers.ts` strips them
>    before a reader sees one, so suppressing them at the source breaks
>    provenance for no gain.
>
> Verified end to end after all four: *"What is the latest happening in AI this
> week?"* → **"Anthropic announced Claude 3 models this week. [S5]"** with five
> web sources cited, against a bibliography and no answer before.
>
> **Deep-read forced an egress question.** Reading a result means fetching a host
> the *search engine* chose, which the user cannot pre-allow, so default-deny
> refuses every page. The first attempt keyed the exemption off
> `source="internet.deep_read"` — a string the caller supplies about itself,
> which is `X-Zaram-Client` again. `SearchReadGrant` carries the exact URLs
> instead, GET only and no body, consulted *after* the policy so an explicit
> denial still wins.
>
> ### The API had no authentication, and now it does
>
> Any process on this machine could read the whole Spine. `ZARAM_API_SECRET`
> wins and packaged builds use only that — minted per launch, passed to the
> backend in the spawn environment and to the renderer over IPC, never in a
> command line. A file under `data_dir()` is the development fallback and is
> documented as weaker rather than glossed. Measured: **401** without, **200**
> with. Two follow-on defects found by running it — a resolution deadlock, and
> the file not being gitignored.
>
> `core/pairing.py`, the credential a second *device* needs, still has no caller.
>
> ### Rule 7d — the Spine held the user's own prompts
>
> "Say the single word: ping", "Reply with exactly: OK", "WHars your name",
> stored as durable facts beside real ones, and **being recalled into new
> answers**: three of the ten sources behind a live AI-news reply were the
> user's old prompts. The door check was a blocklist and failed open. It now
> requires positive evidence that a message asserts something.
>
> `GET /memory/traffic` reviews what got in before the fix; it proposes and never
> applies. **9 records deleted with explicit authorisation, 17 August.** The
> Spine now holds 13 and reports 0 traffic.
>
> One existing test asserted the violation — `test_exchange_is_stored_after_
> answering` required that "a new question" be stored, and passed throughout.
>
> **Start here, in this order.**
>
> 1. **Ingestion routes and the Knowledge drop zone.** The service layer is
>    committed and labelled unreachable; nothing calls it.
> 2. **Knowledge domains**, scoping retrieval.
> 3. **The session/memory split** — the structural fix rule 7d actually needs.
>    The door check is a heuristic standing in for it and says so.
> 4. **Run the installer on a clean machine.** Four reasons it could not have
>    worked are fixed; only that run proves it, and only the maintainer can.

## Superseded — 16 August 2026

> ### The desktop application never started its backend, and nothing had ever run the file that does.
>
> Suites: **2013 backend passed / 0 failed**, 100 skipped · **158 frontend** ·
> **48 Electron** · typecheck clean · lint passes · all four build guards pass.
> Committed in thirteen pieces. An installer exists at
> `dist-electron/Zaram-0.1.0-x64.exe`, 186 MB.
>
> **Three defects, all in the packaged product, all invisible to every test.**
> The theme of the session is that this repository had never executed
> `electron/main.js` — the file every installed copy of Zaram runs.
>
> 1. **`bootstrap()` threw, so `backend.start()` never ran.**
>    `windows._mainWindow.on('resize', …)`, a property `WindowManager` has
>    never had. Its only handler logs the message, so everything below the
>    throw was skipped: tray, global shortcuts, updater, deep links, the
>    `backend.onStatus` wiring that loads the interface, and the backend launch
>    itself. **The app opened a splash screen and waited for a backend nobody
>    had started.** Inside `if (loadedDesktop && desktopRuntime)`, and
>    `desktop/dist` ships — so the packaged path was the broken one, the same
>    asymmetry that hid the asar defect.
>
>    **Why nothing caught it: `npm run dev` starts a different main process.**
>    `desktop/dist/src/main/index.js` is forty-six lines and owns none of the
>    tray, shortcuts, backend launcher or static server. The shipped main is
>    `electron/main.js`, 429 lines, reached only through `extraMetadata.main`.
>    Every developer's machine looked healthy because no developer was running
>    the program. `test/bootstrap.test.js` now launches the real one and fails
>    in half a second if bootstrap throws.
>
> 2. **The egress log and the exporter were unreachable once packaged.** The
>    packaged origin proxies through `createStaticServer`, whose prefix list had
>    ten entries against the dev proxy's twenty-one. A missing prefix is not a
>    404 — it falls through to the SPA handler and returns **200 with
>    `index.html`**, which the client hands to `response.json()`. Measured
>    against the build with no backend running, so 502 means the proxy worked:
>    `/health` 502, `/chat` 502, `/memory` 502, and `/egress`, `/artifacts`,
>    `/providers`, `/export`, `/character`, `/routing/preference`, `/projects`
>    all **200 and a document**. Rules 3 and 7, unreachable in the only build a
>    stranger runs. The guard that exists to prevent this carried the false
>    premise "the packaged build does not use the proxy at all" — it now checks
>    both consumers.
>
> 3. **`npm run build:desktop` destroyed the repository's `package.json`.**
>    `directories.app: .` — which electron-builder warns about on every run —
>    made it write `extraMetadata` over the tracked file, leaving
>    `dependencies` and `"main"` and deleting all twenty-five scripts. Every
>    `npm run` then failed with "Missing script", including the ones that would
>    have rebuilt it. Recovered from git; the setting is gone.
>
> **The packaging blocker is closer to proven.** `test/packagedBackend.test.js`
> inspects a real build from a temporary directory — chdir out of the repo,
> because `_resolveBackendDir` lists `process.cwd()` and every machine that
> could have found the bug was standing in the one directory that hides it. In
> plain Node, because Electron's patched `fs` reads an asar and `python.exe`
> does not. Measured: backend resolved outside the archive, `main.py` readable,
> bundled interpreter chosen, spawn **status 0**. **Still not a clean-machine
> installer run** — that also exercises NSIS, the shortcut, the data directory
> and first run.
>
> ### The ambient surface landed
>
> `Ctrl+Shift+Space` and a 6px handle on the right edge, both created hidden at
> boot so summoning is a `show()`. `ambient.html` is a second Vite entry —
> 2.7 kB against the shell's 550 kB plus a 760 kB VRM chunk. **Invoked, never
> passive, asserted at source level** against the mechanisms by name, because a
> prohibition in a comment survives until somebody has a good reason. The egress
> line calls `describeSystem`, so the overlay and the orb cannot disagree.
> Verified working: a real question answered end to end, and the shipped main
> reporting `registered: true` with the handle at 6x128.
>
> **Selection capture is not built.** How a selection is read — synthesised
> copy, clipboard, or UI Automation — is a product decision with a different
> privacy cost per option, and it wants a decision rather than a default.
>
> **Three defects that mattered, each invisible to a passing suite.**
>
> 1. **The packaged app could not start its backend.** All 322 backend `.py`
>    files were sealed inside `app.asar`, with no `asarUnpack` anywhere.
>    `_resolveBackendDir` checked `appPath/backend` first — inside the archive —
>    and Electron's patched `fs` said it existed, because that check runs in
>    Electron. It then spawned the bundled `python.exe` with that as its working
>    directory. Proven with plain Node: same executable, `cwd` inside the asar →
>    **ENOENT**; `cwd` on the real filesystem → **exit 0**. Every machine holding
>    a checkout fell through to `process.cwd()/backend` and worked, which is why
>    nobody who could have seen it did. Fixed with `asarUnpack`, a resolver that
>    can never return an archive path, `original-fs` for the existence check,
>    four tests, and a payload guard that was mutation-tested.
>
> 2. **Every database wrote into the install directory.** All five store paths
>    resolved to `os.path.dirname(__file__)/..` — correct in a checkout,
>    unwritable under Program Files. `build/installer.nsh` had already been
>    written against the fix, offering to export or delete `%APPDATA%\Zaram`, a
>    directory Zaram never wrote to. `core/paths.py` now owns the one answer; a
>    checkout that already holds data keeps it. 10 tests.
>
> 3. **Nothing in the live search path compared the query to the result.**
>    `_rank_results` sorted on `r.score` — a constant each connector stamps on
>    everything it returns, Wikipedia 0.8, GitHub 0.7, DuckDuckGo 0.6 — then on
>    a second copy of the same prior. **The order was identical for every
>    question ever asked**, which is the complete explanation for an election
>    query returning a junk GitHub repo. Those constants reached the citation
>    chips as relevance, which `UI-SPEC` forbids outright. `ranker.py` held a
>    second implementation that did compare terms, was unreachable, and would
>    have raised `FrozenInstanceError` on its first result.
>
>    `runtimes/internet/relevance.py` replaces it: content-only relevance with
>    light stemming, **selection on relevance alone**, ordering by RRF so no
>    fused magnitude can be compared against the floor, query-dependent
>    freshness weighting, and per-host diversity. Measured on the reported case
>    — junk repo **0.052 dropped**, Reuters article **0.448 cited**, floor 0.18.
>    24 tests.
>
> **A security hole, found while checking whether privacy was over-implemented.**
> Loopback stopped the café network; it did not stop a web page. DNS rebinding
> reached `/memory`, `/egress` and `PUT /egress/policy` as *same-origin*
> requests, so CORS never ran. Measured: **200 and the whole Spine** without a
> guard, **400** with one. A `Host` check now refuses it — 9 tests. **Half the
> fix**: there is still no authentication, so any local process can read
> everything. A per-launch secret is the remaining half and belongs before
> strangers.
>
> **Rule 7 stopped being dead.** `core/export.py` was complete with twenty test
> assertions, no caller, no route and no control. `GET /export` and
> `/export/manifest` now exist, with a Settings button.
>
> **Lint was a config bug, not 157 defects.** Core ESLint's `no-undef` and
> `no-unused-vars` were running on TypeScript with no plugin, so every warning
> was false — `RequestInit` and `JSX` reported as undefined globals, 114 type-only
> usages reported as unused. Replaced with typescript-eslint's rules. **This is a
> repair, not a threshold change.**
>
> ### The character landed, and the no-name rule was reversed
>
> **`assistant_name`, `manner` and `voice` are user settings**, carried into
> `identity_preamble` as facts. The 13 August prohibition was fixing two
> failures with one ban and only ever fixed one: attachment comes from being
> remembered, not from a name.
>
> **The test was written before the feature**, deliberately, and that ordering
> is the point — 21 assertions including five hostile manners of the kind a
> downloaded character file would carry. The guarantee is **order, not
> filtering**: the user's name and manner sit *before* the rules about
> self-description, so the last instruction a model reads is the true one.
> `tests/test_identity_stays_truthful.py` asserts that index comparison
> directly, so an edit that reverses it fails.
>
> **And it is reachable by nothing.** `GET/POST /character` are served, tested
> and called by no interface — the same shape as the five dead features found
> on 15 August, recorded at commit time rather than left to be rediscovered. A
> user cannot name it until Settings can.
>
> ### An invoice that is an invoice
>
> `ArtifactService` could already build a real invoice, spreadsheet and deck,
> and `POST /artifacts/generate` reached all three. **The conversation reached
> none of them.** `DocumentsRuntime` called `create_document` for every kind, so
> "make me an invoice" produced a `.docx` of prose with *invoice* in the
> filename and "make me a PowerPoint" produced a `.docx`, because DECK was not
> among the words that pick a kind. Reported by the maintainer as "Zaram simply
> creates an unformatted document" — the tenth instance of the shape.
>
> `artifacts/extract.py` reads the answer already produced into fields. It reads
> rather than re-writes, because the file must be the answer the user approved
> of; it **refuses rather than fills in**, naming each missing field back while
> there is still a conversation to have it in (rule 9); and **arithmetic never
> comes from the model** — only descriptions, quantities and unit prices are
> read, and `total_of` does the multiplication, because the total is the one
> number a client checks.
>
> `OllamaEngine.read_structured` constrains decoding to JSON at temperature 0.
> Measured: **7 of 8 installed models** extracted an invoice correctly that way,
> while the same model refused through the chat path, which samples. Reached by
> `getattr`, so an engine without it degrades rather than breaks. It runs
> against the **local** engine specifically — re-reading an answer the user has
> already seen is not worth billing, and a document step quietly becoming egress
> would be a rule 5 surprise on a generative tool.
>
> **Start here, in this order.**
>
> 1. **Run `dist-electron/Zaram-0.1.0-x64.exe` on a machine that has never seen
>    this repo.** An installer now exists and three of the reasons it could not
>    have worked are fixed. This is still the only step that can prove it.
> 2. **Decide how the ambient surface reads a selection**, then build it. The
>    window is there and does nothing with what is on screen yet.
> 3. **Mint the launch secret.** The `Host` guard closed the browser route only;
>    any local process still reads the whole Spine.
> 4. **Give the character a Settings panel.** `GET/POST /character` are served
>    and no interface calls them.
> 5. **Ingestion by drop, paste and upload**, then knowledge domains. The
>    parsers exist and the Knowledge surface cannot reach them.
>
> **One structural thing to decide, because it caused two of the three defects
> above.** There are two Electron main processes: `electron/main.js`, which
> ships, and `desktop/src/main/`, which is what `npm run dev` runs. Until they
> are one, development exercises a program nobody installs and everybody
> installs a program nobody has run. The smoke test makes that survivable; it
> does not make it right.
>
> Full reasoning for the direction — daily driver, free tiers, domains, the
> character, and the business model — is in `CLAUDE.md`, which was updated this
> session rather than left to drift.

## Superseded — 15 August 2026

> ### Settings became real, and five dead features were found behind it.
>
> `Zaram-V0.1` is **64 commits ahead of `origin/main`**, and this session's work
> is **uncommitted** — 44 changed or new files in the working tree. Measure with
> `git rev-list --count origin/main..HEAD` rather than trusting that number.
>
> Suites, all measured this session: **1987 backend passed / 0 failed**, 9
> skipped · **155 frontend** across 20 files · typecheck clean ·
> `scripts/drive-settings.mjs` **14/14** and `scripts/drive-composer.mjs`
> **9/9**, both against the running product in a real browser.
>
> **Two things built late and not seen by a human**: the artifact Preview panel
> over the orb area, and speech barge-in. Both are asserted by construction;
> `probe-preview-geometry.mjs` skipped because the probe browser had no
> artifacts, and nothing drives barge-in yet. Given what the pointer-tracking
> gaze cost, look at both before building on them.
>
> **What this session was.** The maintainer asked for a Settings screen they
> could actually operate, and for cloud and web search they could test. Both
> now work. Getting there turned up **five separate features that were complete,
> tested, and could not happen** — the shape this file keeps recording, found
> five times in one day:
>
> 1. **`/providers/*` was never mounted.** A full router with its own passing
>    test file, 404 on the running product for the entire life of the provider
>    layer, because its tests build their own app and mount it themselves.
> 2. **`chatClient.ts` hardcoded `model: 'gemma3:latest'`** on every message.
>    The provider layer's vetted selection ran, applied its residency and
>    data-policy gates, and was overridden by a string literal in the transport.
>    No routing decision was observable and no cloud model was reachable from
>    the interface however the backend was configured. Nothing asserted what the
>    request body contained.
> 3. **`KnowledgeRuntime` never had an internet runtime.** `search()` reads web
>    results from `self._internet_runtime` and nothing ever constructed one, so
>    the web half of every search silently returned nothing.
>    `create_internet_runtime` was defined, exported, and never called.
> 4. **`InternetRuntimeImpl.initialize()` raised `AttributeError`** on its last
>    line — three of the four `InternetStatus` values it used do not exist. Live
>    broken code in a module nothing had ever executed.
> 5. **The routing preference control I built was itself a dead switch** —
>    persisted, served, rendered, read by nothing. Recorded here rather than
>    quietly fixed, because it is the same defect as the four above, committed
>    by someone who had spent the day finding them.
>
> **And one that was worse than dead: web search *appeared* to work.** Every
> DuckDuckGo call site imported `duckduckgo_search`, which has been superseded
> and, against the current endpoints, **returns an empty list without raising**.
> Measured: 0 results where `ddgs` returned 3, same connection, seconds apart.
> So search was enabled, left the machine, was logged as allowed at 107 bytes,
> and produced answers with no web sources — indistinguishable from "the web had
> nothing to say". Every layer reported success. `core/ddgs_import.py` is now
> the single import site and `test_search_uses_the_working_package.py` guards
> it. Web search now returns real results: Guardian, TechCrunch, NYT.
>
> **Start here, in this order.**
>
> 1. **Nothing is committed.** 44 files. Read *What this session built* below
>    and commit in coherent pieces; do not commit `backend/settings.json`, which
>    is now gitignored alongside the egress policy.
> 2. **`npm run lint` still cannot pass** — 143 pre-existing warnings against
>    `--max-warnings 0`. Untouched this session. Fourth instance of *a gate
>    nobody can run*.
> 3. **The cloud round trip is still unverified by a human.** LM Studio on
>    loopback proves the connect path without a credential; nobody has connected
>    a real key, selected a cloud model and watched a reply arrive. That needs
>    the maintainer's own key — see *Testing cloud and search* below for the
>    exact steps and the one non-obvious blocker.
>
> ### Testing cloud and search — the step that is not obvious
>
> **Connecting a provider does not permit it.** The key is stored; the
> destination still has no rule, and the default is refuse. So *Look for models*
> is denied, the list comes back empty, and there is no way to select a cloud
> model — with nothing on screen explaining why. That happened to the
> maintainer. The Cloud section now names the host and offers a one-click
> *Allow*, but the sequence is worth stating:
>
> 1. Settings → Cloud providers → pick the provider, paste the key, **Connect**.
> 2. Allow its host when the amber line offers it (`openrouter.ai`, say).
> 3. Models → **Look for models** — this is the network call.
> 4. Pick one under *Which model answers*.
>
> Until step 4, Zaram answers locally and says so truthfully. "No, nothing in
> this conversation has left the device" is **correct** while `default_model` is
> null, not a bug — it is `core/identity.py` working.
>
> For search: it is on, `duckduckgo.com` is allowed, and the question has to
> actually look like it needs live information — `needs_search()` decides.
> "Are you connected to the cloud?" is not such a question, so no search runs.
>
> ### The avatar became a character, and the character became the mascot
>
> **Decided 15 August 2026.** The shipped VRM is a helmeted robot with a
> dot-matrix LED face, and it is also Zaram's mascot. Rules written into
> `CLAUDE.md` and `docs/EMBODIMENT-SPIKE.md`; palette into `docs/UI-SPEC.md`.
> The short version, so the next session does not re-argue it:
>
> - **Mascot and renderer are two jobs for one asset.** It smiles in key art;
>   inside the product its rest face is `sil`. The embodiment rule governs the
>   status indicator, not the marketing.
> - **The landing default is still the orb.** Unchanged.
> - **The face uses `textureTransformBinds`, not morph targets** — a UV window
>   over a sprite atlas. Weights must be **binary** and only **one expression
>   per material** may be non-zero, both read off
>   `VRMExpressionTextureTransformBind.applyWeight`, not assumed. The existing
>   eased lerp in `VrmAvatar.tsx` is correct for morph rigs and would smear a
>   sprite mouth across cells.
> - **The face carries no state.** Constant `#818cf8`. Violet was rejected
>   because `UI-SPEC` assigns `#8B7FD4` to *cloud*, and a permanently violet
>   face states falsely that data left the device.
>
> **Assets: done and verified, 15 August 2026.** `Zaram_LED_Face_Sprites.zip`
> at the repo root — two 3×2 atlases at 768×512, 256px cells, 32×32 lattice at
> 8px pitch, plus a `manifest.json` carrying the UV table as data. Verified by
> measurement rather than by reading its README: all 12 cells cropped at the
> manifest's own `repeat`/`offset` matched their standalone frames byte for
> byte, every frame sits on the same dot lattice, and the minimum cell gutter is
> 32px — which is why `applyTextureFiltering` needs **no** exemption and
> `NearestFilter` would be wrong here. The dots are anti-aliased, not hard
> pixels.
>
> **What is not done, in order.**
>
> 1. **Nothing consumes the atlases yet.** They are not in the repo, only in a
>    zip at the root, and no test asserts they match `visemes.ts`. The manifest
>    is a spec nothing enforces — write that test first; it needs no model and
>    no renderer.
> 2. **The model work is unstarted**: two quads on the visor, separate material
>    slots, full 0–1 UVs, black base with the atlas on `emissiveMap`, exported
>    with the manifest's binds.
> 3. **The driver change is unstarted**: snap-not-lerp gated on bind type, plus
>    mutual exclusion per material.
> 4. **Two known asset gaps.** The mouth frames are narrower than the eye span,
>    where the reference has them about equal — both quads must be the same
>    world size for the dot pitch to match, so this is fixed by redrawing, not
>    by scaling. And `eyes_spare.png` is genuinely empty; if `warming` is bound
>    to that cell before a frame is drawn, the face goes dark during a cold
>    start and reads as a crash.
>
> ### Old current-state block — 14 August 2026
>
> ### `Zaram-V0.1` is **62 commits ahead of `origin/main`**, nine of them
> unpushed, ending with this docs commit.
>
> (No hash for this commit: an earlier version of this line named one, and
> amending to correct a count changed the hash out from under it. Measure with
> `git rev-list --count origin/main..HEAD` rather than trusting the number
> above — it is right when written and stale the moment anything lands.)
>
> Suites, all measured this session: **1929 backend passed / 0 failed**, 9
> skipped · **141 frontend** across 19 files · **30 Electron** · typecheck clean.
>
> **Start here, in this order.**
>
> 1. **`npm run lint` cannot pass and has not been able to for some time** —
>    143 warnings across `frontend/src` on a script that runs
>    `--max-warnings 0`. Nothing I added caused it and nothing I added is worse
>    than what was there, but this is the fourth instance of the shape this file
>    keeps recording: *a gate nobody can run*. The Electron tests had no script,
>    the frontend tests had no script, the signing check only ran where the
>    defect wasn't. Either fix the warnings or change the threshold and say
>    why — a lint script that always fails is not a lint script.
> 2. **Two things were built this session that nobody has looked at.** The
>    avatar's state transitions now ease over 0.22s and the user's chat messages
>    moved to the right. Both are asserted — the easing by maths, the alignment
>    by measured DOM geometry — and **neither has been seen by a human**. This
>    shell cannot screenshot: the browser pane does not composite frames. Given
>    what the pointer-tracking gaze cost, thirty seconds of somebody's eyes on
>    both is worth more than any further assertion.
> 3. **The offer executor is still the next real feature.** The first-run screen
>    reports what is missing and can act on exactly one of the four things it
>    offers ("look around"). See *What is next*, item 0.
>
> **What changed since the 12 August block below:** first-run screen, provider
> catalogue, the assistant's identity, the avatar dropping locality, eased state
> transitions, streaming speech, and a loader gate for avatar files. Each has its
> own section; the 12 August block is kept because everything in it is still
> true about packaging, signing, the API binding and the installer.

### What this session built — 15 August

**Settings, whole.** `SettingsWorkspace` was read-only and lied in both
directions: it reported "Egress log: not built" and "Kill switch: not built"
while `/egress` and `/egress/policy` had been served for weeks. *"Not built"
about something that exists* is the more damaging of the two lies here — it
tells a user worried about their data that Zaram is not recording what leaves,
when it is. Now: kill switch, per-source rules, web search with its scope,
routing preference, model choice, cloud providers, speech, renderer.

**The kill switch is new, not relabelled.** It lives in `EgressPolicy.decide`
rather than in a route, so it covers tool traffic and model discovery, not just
chat, and an `allow` rule cannot survive it. Loopback is deliberately untouched
— a request to 127.0.0.1 cannot leave, so there is nothing to cut, and sealing
it would stop the local model answering. Verified live: with it on, discovery
was refused and logged as *"the kill switch is on"* while a local chat with full
recall answered normally.

**Several cloud providers at once**, not one. The environment-variable design
could express exactly one endpoint and key, which is not how people hold keys —
the maintainer wants coding on one service and images on another.
`cloud_config` holds a set; `CloudFanout` resolves per model and strips the
`provider_id:` prefix before the wire, which also fixes a latent bug where a
discovered cloud model's real id would have been sent verbatim and 404'd.

**The three tiers of routing control now do something.** `prefer_local` is a
*constraint* — Zaram will not auto-pick a cloud model at all, and returns
nothing rather than falling back, because the strictest setting must not be the
one that silently sends data off-device. `auto` ranks local first and may fall
back. `prefer_cloud` ranks cloud first among models already consented to. None
of the three is a permission: `selectable_by_default` still gates on data
policy, and `test_routing_preference_is_not_inert.py` asserts that the claim the
screen makes to the user is true.

**Web search works, and is honest about what still blocks it.** The row states
whether the environment is overriding the toggle, whether the kill switch is on,
and whether the search host has a rule yet — because "on" alone would have the
user turn it on, get a refusal, and conclude the feature is broken.

**Search scope: local models only, by default.** The maintainer's call — search
compensates for what the answering model does not know, and a local 12B knows
least. One honest caveat is recorded in `SearchScope`: **cloud models do not
generally come with web search**, so this trades recency for latency rather than
avoiding something the provider was going to do anyway. Carried per-request in a
`ContextVar`, not a global — two chat requests with different models are in
flight at once the moment a second window exists.

**The orb reports connected cloud providers.** `inference_providers` was
hardcoded to Ollama with a comment saying a cloud engine "must list it, or the
Orb will under-report egress"; a cloud engine arrived and the line never did. So
connecting OpenRouter changed nothing on screen. `routing.mode` was likewise the
literal string `"local"`. Both derived now.

**"Warming up" was appearing on almost every message.** Nothing set Ollama's
`keep_alive`, so its five-minute default applied and any ordinary pause cost a
full cold start. Two halves: `keep_alive: 30m` keeps weights resident once
loaded, and `warm_local_model()` preloads them seconds after boot in a thread.
Measured: `gemma4:12b` resident at 8.08 GB within ~15s of launch, nobody having
asked anything. 30 minutes rather than forever — pinning weights indefinitely
would make a background app the reason a game will not start.

**Citations were labelling memory as web.** `_search_provenance_events`
hardcoded `kind="web"` for every result, and a knowledge search returns the
*merged* list. The moment the internet runtime was wired, facts from the user's
own Spine arrived as web citations with `memory:` URIs and egress-coloured
chips. Derived per result now, defaulting to `web` when unknown — over-warning
about privacy is the safe error, under-warning is not.

**Chat controls**: copy on every message, edit and ask-again on the user's own.
**No thumbs**, and `drive-composer.mjs` asserts their absence — rule 7f, and
this is the row where every other product puts them. Editing loads the text back
into the composer rather than rewriting the transcript: a Zaram answer carries
citations and may have put facts in the Spine, so deleting the question that
produced them would leave provenance pointing at something the user cannot see.

**Preview beside Download** on generated files, in a panel over the blurred
orb — the treatment `CitationPanel` already uses. The preview is the HTML the
file was built from, so fidelity is structural. Rendered in an `iframe` with an
empty `sandbox` and a `default-src 'none'` CSP: the HTML is model-generated, and
an external `<img>` in it would be a request the egress gate cannot see, because
that gate intercepts what the *backend* sends. Same hole `vrmSafety` closed for
avatar files, arriving by a different route.

**The composer's mic and send buttons overlapped on hover.** Two hand-computed
offsets — `right-9` and `right-2`, each 28px wide, adjacent with a gap of
exactly zero — and `whileHover` scaling either one closed it. Replaced with a
flex row. Measured: 3.5px gap at rest, still separated when hovered.

**The orb is calmer.** Speaking ripples at a third the rate and a fraction of
the opacity; the waveform bars are gone. Worth recording *why* the bars were
wrong beyond taste: their heights were the hardcoded array
`[28, 44, 60, 72, 60, 44, 28]` on a fixed loop. They never read the audio — a
level meter that measures nothing, which `UI-SPEC` forbids outright. If one
returns it must read `useSpeechStore`'s audio element, the way visemes already
do.

**Three new guards, and two found real defects on their first run.**
`check-proxy-covers-backend.mjs` caught `/vision` never having been proxied
(served and unreachable from the dev frontend the whole time) and then caught
`/search` the moment it was added. `test_routes_are_mounted.py` asserts
reachability against the real app object. `test_egress_chokepoint.py` now
matches full dotted import paths, because centralising the DuckDuckGo import
into `core.ddgs_import` **erased five modules' entries from that guard in a
single refactor** — a guard a refactor can switch off is not a guard.

### Speech has a north star now — 15 August 2026

Set by the maintainer: **speech follows the text without lag, the user never
waits, and the user can interrupt by typing or by microphone.**

**Barge-in is built.** `bargeIn()` is a separate action from `stop()`
deliberately — `stop()` is the mechanism and fires on every `beginSpeech`, on
cancel, on teardown; `bargeIn()` is the *intent*, so a call site reads as "the
user interrupted". They do the same thing today; when they stop doing the same
thing (a resume, a fade rather than a cut) only one of them changes and every
barge-in site changes with it.

Two call sites. Typing in the composer, on *change* rather than on focus —
clicking in to re-read is not an interruption, and stopping there would make
speech feel fragile rather than responsive. And the microphone, where it is a
**correctness requirement rather than a courtesy**: without it the mic records
Zaram's own voice from the speakers and transcribes it back as if the user had
said it.

**A queue of clips is easier to interrupt than a live stream**, which is worth
recording because the instinct runs the other way. There is no half-received
buffer to discard and no connection to tear down — a generation counter is
bumped, every async step checks it and bails, the queue is released so the loop
is not left blocked on it, and the worst case is one already-synthesised clip
thrown away. What it cannot do is *resume* mid-utterance, because the unit of
playback is a sentence.

**`/voice/stream` exists, is unused, and moving to it would not help** — noted
so it is not "fixed" later on the assumption that it would. Kokoro is not a
streaming model: it synthesises a whole utterance and returns a whole waveform,
so those SSE chunks are chunks of a *finished clip*, not frames emitted as the
model produces them. Backend chunking would change where the split is decided
without changing when the first sound arrives, and would cost the one thing the
client can uniquely do — decide "will this sentence change?" against text that
is still arriving, which the backend cannot know because it sees one utterance
at a time. **The layer follows the engine**; if a genuinely frame-streaming
model ever replaces Kokoro, this inverts.

Full write-up, with every measurement and the open questions:
`docs/SPEECH-ARCHITECTURE.md`.

### Preview sits over the orb, not over everything — 15 August 2026

The panel occupies the orb's half of the window and stops where the
conversation panel begins. Covering the whole window would hide the exchange
that produced the file — the context that makes the document make sense — and
would put the preview over the message that was clicked.

Its width derives from the same fraction the conversation panel and the orb's
own offset derive from, so the three cannot disagree. The panel is resizable; a
hardcoded 55% would drift the moment anybody dragged the divider.
`scripts/probe-preview-geometry.mjs` measures it at two divider positions for
that reason. **It skipped on its last run** — the browser profile had no
artifacts — so the geometry is asserted by construction and not yet by
measurement. Generate a document and re-run it.

Preview is on **both** surfaces, the conversation card and Work's detail panel,
using one component. A control that exists in one place and not the other reads
as a bug in whichever lacks it.

### This session — 13–14 August

**The assistant introduces itself as Zaram**, not as whichever model is
answering, and names that model truthfully instead of guessing from training
data. Eight character personas became tone-only presets. Full reasoning under
*The assistant knows what it is*.

**Speech keeps pace with the text.** It used to wait for the whole reply to
finish generating before saying a word. Measured against the running product:
first synthesis at 35.8s against a stream that closed at 52.4s — speech started
**16.6 seconds before generation finished**, and the gap grows with reply
length. Found on the way: citation markers were being read aloud, because the
automatic speech path was the one caller of three that never stripped them.

**Bring your own VRM is agreed and designed**, and an avatar store is split into
three businesses that must not be argued as one. See *Avatars: bring your own,
and the store question*.

**An avatar file cannot phone home.** glTF can reference external URIs that the
browser fetches, which is rule 3 broken by a data file with nothing reporting
it — invisible to the egress gate (backend only) and to the remote-asset check
(source only). Refused before any request is made, with a `LoadingManager`
backstop. This is the prerequisite for bring-your-own-VRM.

**The user's messages sit on the right**, capped at 85% width, with the speaker
label kept because side is a cue a screen reader cannot use.

**The avatar gate blocked the avatar, and a person found it, not a test.** A
`LoadingManager`'s URL modifier applies to *every* URL that manager resolves,
and both loaders were given the same one — so the top-level `.vrm` fetch, which
is not a `data:` URI, was replaced with an empty one. The bundled avatar arrived
as zero bytes and the gate refused it as unreadable: **the guard blocked the
only file it was written to protect**, and the landing page showed "Avatar
unavailable" where a face should be.

Twelve unit tests passed throughout, because every one of them tests
`inspectAvatar` against bytes handed to it directly — none could see the wiring
that decided which bytes arrived. Fixed by giving the restrictive manager to
`GLTFLoader` only: it governs *sub-resource resolution during parse*, and the
top-level fetch is a path this component chose rather than a URI a stranger's
file asked for. The two must not be governed by one rule.

**No test was added for it, deliberately.** Nothing short of loading the app
could have caught it, and a unit test that appeared to cover it would be the
assertion-free kind this file already warns about. What catches this class is
looking — which the handoff had just finished saying, one section above, about
two other changes shipped unseen. It took under an hour for that to cost
something. Verified fixed by loading it: 14 expressions, all five visemes,
humanoid rig, 71 textures at anisotropy 16.

**Three of my own claims were wrong first and the tests caught all three** — a
clamp said to prevent an overshoot the formula cannot have, a divergence figure
of 1% that measures 0.68%, and a justification for the avatar change that the
DOM contradicted. Each is recorded in its section rather than quietly corrected,
because the pattern is the point: an assertion written to sound right is the
same failure as a number written without measuring.

## Superseded — 12 August 2026

> ### The first-run screen is built — `b243e17`. *(Counts in this block are as
> of 13 August and are superseded by the current state above.)*
>
> The screen that "The next task" specifies now exists and has been driven
> against the running product in both unready states. **Read "What is next"
> rather than "The next task"** — that section has been rewritten to say what
> is left, which is the executor behind the offers.
>
> Suites, all measured this session: **1929 backend passed / 0 failed**, 9
> skipped. **121 frontend** across 17 files. **30 Electron**.
>
> **The assistant introduces itself as Zaram now**, not as whichever model is
> answering, and it names that model truthfully instead of guessing from its
> training. The eight character personas are tone-only presets. Avatar state
> changes ease rather than cut, and every lerp in that file is frame-rate
> independent for the first time. See the two sections below the current state.
>
> **Three numbers in the block this replaces were wrong, in three different
> ways, and each is worth a line.**
>
> *Stale by environment.* It read 1848 passed / 76 skipped against the same
> 1924 collected. Nothing about the backend changed; the voice and mic extras
> are installed in this shell and were not in that one. The file already says
> to read the skip count as a fact about the environment — this is what that
> looks like from the other side, and the total is what stays constant.
>
> *Stale by measurement.* "51 commits ahead of `main`" is 142 if you measure it
> against local `main`, which is at `7a4a89d` and dates from 26 July. The
> figure that means anything is against `origin/main`.
>
> *Contradicted by history.* "The PR was not opened" is no longer true and had
> already stopped being true: `origin/main` is `d29b19b`, **"Merge pull request
> #1 from Uchayanisiuba/Zaram-V0.1", 10 August**. The branch has been merged
> once and has run ahead again since. `gh` is still not installed here, so this
> is read from the commit graph rather than from GitHub.
>
> The earlier note about a *fabricated* 1835 stands and is worth keeping: a
> made-up number is worse than a stale one, because nothing about it looks old.
> Every count in this block is from a run.
>
> ### The session is committed, on `Zaram-V0.1`, unpushed.
>
> Committed in coherent pieces, re-verified green before staging rather than on
> the previous session's word. Read the two "found by running it" sections below
> before debugging anything, because four of the defects fixed here were
> invisible to a passing suite.
>
> **M10 is finished and cloud generation now sends**, after a person says it
> may. **M11 has an installer**: `Zaram-0.1.0-x64.exe`, 186 MB, plus a portable
> build — the NSIS step had never once completed, because an unset signing
> variable killed it after packaging had already succeeded. `Zaram.exe` launches
> its own bundled Python and reaches `kernel: online`.
>
> **The only thing left in M11 is running it somewhere that has never seen this
> repo**, which cannot be done from here.
>
> Suites, measured 12 August: **1647 backend passed / 0 failed**, 76 skipped,
> 3m29s. **103 frontend** across 14 files. **30 Electron**. Every skip names its
> reason — the voice and mic extras are absent from this shell and the scale
> eval is opt-in behind `ZARAM_SCALE_EVAL=1`. An earlier note here read "1714 /
> 9 skipped" against the same 1723 collected: the same suite on a machine that
> had the extras installed. **Read the skip count as a fact about the
> environment, not the code**, and `-rs` prints why.

### The lesson this session kept teaching

**A feature's tests can all pass while the feature cannot happen.** It happened
twice, in unrelated places, and both times the only thing that could see it was
starting the product and asking it to do the thing.

Confirm-before-send was complete: the gate blocked, the question appeared, an
approval released the thread, an edit reached the wire — all asserted. It could
not work. `ChatRouter._kernel_stream` was an `async def` generator driving the
engine's *synchronous* generator with a plain `for`, so every blocking step ran
on the event loop thread. When the gate blocked on its confirm hook the whole
backend stopped answering, `/egress/pending` could not be served, the dialog
could never appear, and the only reachable outcome was a two-minute timeout with
`/health` dead throughout. The gate, the confirmations, the engine and the
endpoints were each correct in isolation and still are. **The defect lived in
the seam.**

The second: the packaged installer would have shipped `spine.db` and
`egress.db`. Every unit test was green. Nothing tests what a glob matches.

Both are now covered — `backend/tests/test_confirm_does_not_freeze.py` and
`scripts/check-installer-payload.mjs` — and both were verified by reintroducing
the defect and watching the new test fail.

### M10 — confirm before send, done and driven

`GET /egress/pending`, `GET /egress/pending/{id}`, `POST /egress/pending/{id}`
taking `{approved, body}`. Answering something already decided is a 404, so a
double-click cannot approve a second send. `get_pending()` / `set_pending()` sit
beside `get_gate()`; the bootstrapper wires
`gate.set_confirm(lambda r: get_pending().ask(r))` — **resolved per call, not
bound once**, or a later `set_pending` leaves the gate asking a store nothing is
watching. `cancel_all()` runs first at shutdown, before anything awaits.

`ConfirmSendDialog` is mounted in the shell on every surface, because a tool can
reach the network from anywhere. It polls at 1s while something is in flight and
renders nothing otherwise. Recalled facts become removable chips by **parsing
the outbound body** for the engine's `[M1] (date) …` lines — parsed rather than
handed over, so the chips cannot drift from the text they describe. A body it
cannot parse gets the plain decision and **no chips**, never invented ones.

**Verified against a running product.** A fake OpenAI-compatible provider on the
LAN address (non-loopback, so the gate treats it as egress), a real cloud-routed
chat, the dialog on screen with three genuinely recalled facts. Struck the one
holding the day rate, approved, and compared all three: preview, append-only
log, and what arrived at the destination — **byte-identical at 1650 bytes, and
the struck fact in none of them.**

Two more defects fell out of that run:

* **The log said the user refused when nobody was asked.** A timeout was
  recorded as "you chose not to send this" — a permanent, tamper-evident record
  of a decision that never happened. `EgressRequest.refusal_reason` now carries
  the truth: nobody answered, Zaram was shutting down, or it could not ask.
* **Discovery asked for `/v1/v1/models`.** The engine normalises a trailing
  `/v1`; the discoverer did not. Given `ZARAM_OPENAI_ENDPOINT` written the way
  providers print it, discovery 404s, no cloud model is known, and routing
  silently sends every message local. Chat still works, which is what makes it
  hard to notice.

A guard sits under the freeze: asked from the event-loop thread, the confirm
hook refuses in milliseconds and says why, rather than freezing the server that
would have answered it. **The call site is fixed; the guard is so the next one
costs a refusal instead of the product.**

**One clause of M10 was deliberately not built.** The acceptance line asks for
edits "written through as supersessions". Striking a fact in the dialog changes
*that request only*. "Do not send my day rate to this provider" and "this fact
is wrong" are different statements, and writing one through as the other would
delete a correct fact at the exact moment the user is being careful. Reasoning
in the M10 section below.

### The API was published to the network

`main.py` bound `0.0.0.0` — every interface — and `backendLauncher.js` launches
the packaged app through exactly that path. **No endpoint has authentication.**
On any café, hotel or shared-office network, anyone reaching port 8420 could
read the whole Spine through `/memory`, read the egress log, set a host to
`allow` through `/egress/policy`, and approve a pending confirmation.

Now `LISTEN_HOST = "127.0.0.1"`, **not configurable** — a setting that reopened
it would be set once while debugging and never unset, and the failure is silent
because everything keeps working. Verified live: loopback answers, the LAN
address refuses, `netstat` shows `127.0.0.1:8420`.

**How it happened is the more useful half.** `test/backendLauncher.test.js`
asserted the launcher passed `--host 127.0.0.1`. The launcher changed to run
`main.py`, the test started failing, and **nothing in this repo ran it** — there
was no script wired to `test/`. Twenty-six Electron tests existed, two were
failing, and the failing one encoded the loopback guarantee.

`npm test` now runs them and both failures are fixed. The second was
`staticServer`, whose fake returned `arrayBuffer()` from when the proxy
buffered; the proxy streams now, because `/chat` emits tokens as they are
generated. **Production code was correct in both cases** — the tests had rotted
where nobody could see them. The replacement assertion grades the *property*
rather than the argument list, so it survives either launcher shape.

### M11 — packaging

**The installer had never been buildable.** electron-builder exited before
packaging anything, on missing `name` and `version` in `package.json` and on
`electron` / `electron-builder` sitting in `dependencies`. All fixed.
`build:desktop:portable` also never returned to the repo root after
`cd desktop`.

**What it would have shipped is the finding that matters.** The config included
the backend as one glob with four exclusions:

* `!backend/.venv` does not match `backend/venv`, which is what the directory is
  actually called here. **376 MB**, plus 61 MB of `audio_cache` and
  `audio_output`.
* Nothing excluded `spine.db`, `egress.db` (with its `-wal` and `-shm` sidecars,
  which hold the most recent writes), `artifacts.db`, `projects.db`,
  `egress-policy.json`, or `backend/generated/`. **The maintainer's memory,
  their record of everything that has ever left the machine, their invoices, and
  their per-host privacy rules — all on disk today, all matching the glob.**

The backend is now included by **allow-list**. That is the opposite polarity to
`pyproject.toml`'s argument about test collection, and deliberately: a stale
exclusion there collects an extra test, while a missing exclusion here publishes
private data. Two checks hold it — `scripts/check-installer-payload.mjs` runs
inside `build:desktop` with the real `minimatch` and exits non-zero, and
`backend/tests/test_installer_payload.py` catches a bad edit in the suite long
before anyone builds.

**Python is bundled and the packaged app runs.** `resolvePythonCommand` resolves
`ZARAM_PYTHON` → bundled runtime → dev venv, and **PATH is deliberately not a
fallback**: finding a stranger's Python 3.9 is worse than finding none, because
it fails later and reads as a broken product. The runtime is found via
`resourcesPath` when packaged, since the backend is inside `app.asar` and an
archived file cannot be executed.

**Relocatable CPython, not PyInstaller — the product already decided this.**
`backend/ingest/quality.py` tells the user "pip install zaram[ingest]". Voice,
mic and OCR are extras installed after the product is running, on its own
instruction, and **you cannot pip install into a frozen bundle.**

CPython 3.11.9 from python-build-standalone, SHA-256 verified, base
requirements only. **401 MB runtime, 679 MB unpacked app.**
`dist-electron/win-unpacked/Zaram.exe` launches
`resources/runtime/python.exe` — confirmed by process path — reaching
`kernel: online` in about five seconds, with voice degrading exactly as
designed: *"Kokoro package unavailable … (speech disabled, chat unaffected)"*.
The asar carries 323 backend entries, 271 of them `.py`, and **no database, no
venv, no generated document, no policy file and no tests** — verified by listing
the archive, not by trusting the payload checker.

**Dev tooling is out of the base install: 83.5 MB, measured.** An earlier note
guessed "probably 30–40 MB" and was under by more than half — mypy alone is
42.1 MB, ruff 32.9 MB. Now `backend/requirements-dev.txt`.

**Jinja2 stays where it is.** Not a leftover: spaCy and torch both require it
unconditionally. Answered from declared metadata, which is trustworthy in that
direction — a package *declaring* a dependency is evidence; nothing declaring
one is not, which is the misaki/spaCy trap.

**The installer icon was one clone away from being wrong.** `electron-builder.yml`
names no icon at all — electron-builder finds `build/icon.ico` by convention —
and `/build/` was gitignored. On this machine the icon is present because the
brand generator wrote it here; on a fresh clone there is none, and the build
does not fail, it just produces an installer wearing the default Electron icon.
`build/icon.ico` is now tracked, for the same reason the brand PNGs under
`frontend/public/` are: **the build must not depend on someone having run the
generator first.** This is the same class as the two above — a check that
passes locally and means nothing anywhere else — and it sits on the one path
that matters, which is a stranger installing this.

**The frontend suite had no way to run it.** 14 vitest files, 103 tests, vitest
in `devDependencies`, and no `test` script anywhere pointing at them: reachable
only by knowing to type `npx vitest run`. Exactly the shape of the Electron
`test/` directory that hid a failing loopback assertion for who knows how long.
`npm test` at the root now runs both JS suites, and `npm run test:backend`
encodes the venv interpreter so the wrong-`python` trap costs nothing.

**The installer exists.** `Zaram-0.1.0-x64.exe`, **186 MB**, NSIS, plus
`Zaram-Portable-0.1.0-x64.exe` beside it — from 679 MB unpacked, most of which
is the 410 MB Python runtime. Built unsigned, which `check:signing` permits for
a development build and refuses under `ZARAM_RELEASE=1`.

**Why it had never been built is the finding.** `electron-builder.yml` set
`certificateSubjectName: "${env.ZARAM_SIGN_SUBJECT}"`, with a comment claiming
an unset variable resolves to empty and signing is skipped. It resolves to
nothing of the kind — the literal reaches the signer, which looks for a
certificate by that name and fails:

```
⨯ Cannot find certificate ${env.ZARAM_SIGN_SUBJECT}, all certs:
```

So **no machine without a code-signing certificate could produce an installer**,
which is every machine today. What hid it is *where* it fails: packaging
succeeds, `win-unpacked` is written, `Zaram.exe` starts — and the build dies
afterwards, signing the *uninstaller*. Both earlier statements were true at
once and nobody connected them.

`scripts/build-installer.mjs` injects the subject only when there is one, which
YAML cannot express, and `check:signing` now refuses any `${env.}` macro in the
config. **That check runs before the development-build exit, unlike every other
check in the file** — every one of them was release-only, which is exactly how
the setting that made an unsigned build impossible was never examined on an
unsigned build. A check that only runs where the defect isn't is not a check.

The installed tree was verified directly rather than through the payload globs:
no `.db`, no `-wal` or `-shm` sidecar, no `egress-policy.json`, no venv, no
generated documents, and nothing matching inside `app.asar`.

**Still missing from M11's acceptance:** a run on a machine that has never seen
this repo. That is now the whole of it, and it is the one part that cannot be
done from here.

### Code signing — decided, prepared, not purchased

`docs/CODE-SIGNING.md` is the runbook. **OV, and not EV later either.**

An earlier version of that document said EV buys immediate SmartScreen
reputation. **That is false**, and it is worth recording as false because it is
the most repeated code-signing advice there is. Microsoft, checked 12 August:
*"EV certificates no longer bypass SmartScreen … Paying a premium for EV solely
to avoid SmartScreen warnings is no longer justified."* Their table gives OV and
EV the same first-download behaviour: a warning until reputation accrues. What
signing buys is **your name in that warning**, and the ability to accumulate
reputation at all — unsigned starts from zero every version, forever.

**Microsoft Artifact Signing is ruled out on geography, not merit.** It is the
better architecture — ~$10/month, no token, HSM-backed, CI-native, and it would
keep the key off the dev machine. But Public Trust certificates are limited to a
listed set of countries, and **individual developers must be in the US or
Canada.** Nigeria is on neither list. Re-check before public beta; the list has
grown before.

Two things that raise the stakes beyond a click-through: **Smart App Control on
Windows 11 blocks unsigned executables outright**, on all executables rather
than only downloaded ones; and **modifying a file after signing breaks the
signature**, which matters for the bundled runtime — post-processing happens
before signing, never after.

The repo is ready. `electron-builder.yml` names the identity by environment
variable and never names a key. Timestamping is configured, because without it
every signature dies with the certificate *including on machines where it is
already installed*. `scripts/check-signing.mjs` fails a release that is
unsigned, that signs from a key file, or that has no timestamp server.
`.gitignore` carries certificate patterns.

### Brand

**Tagline: "One memory. Every model."** Settled. Not yet placed — it belongs in
`README.md` and `docs/PITCH.md`, not the app chrome.

The mark was **traced** from `Logo_Image/`, not eyeballed: threshold the hero
glyph, follow the boundary, reduce with Ramer-Douglas-Peucker. Each plane came
down to six and eight corners, which is itself the check that the trace found
real geometry. It corrected three things an earlier reconstruction had wrong —
the mark is **1.31:1, not square**; it is **two interlocking planes, not three
slabs**, and the diagonal gap between them is its whole character; and the
gradient ends in **cyan (#4BADE6), not blue**.

`scripts/build-brand-assets.py` emits SVG, PNG and a seven-size `.ico` from one
definition, so the favicon, app icon and installer icon cannot drift into being
three logos. The top-left of every workspace is now the rounded app-icon tile,
51px, **icon only** — it returns to the landing with the conversation closed,
which keeps the orb's single meaning as the way *in*.

Previews write to `Logo_Image/`, never `frontend/public/` — everything under
`public/` is built into `dist` and shipped.

### Before you run anything

The short list. *Read this before debugging anything*, further down, has the
restart command and the longer catalogue — including why a run under the wrong
interpreter reports 54 failures that all look like product defects.

**Run the suite as `.venv\Scripts\python.exe -m pytest`.** Bare `python` on PATH
is a broken shim that reports a missing install path — this costs the first ten
minutes of a session that does not know it.

**Measure the suite with nothing else running.** A run that reported 435s
against a normal 245s produced one failure in
`test_measure_exemplar_separation`; it passes alone with a wide margin and
passed two clean runs after. That test is a `measure` test against a live local
model, which is the class most sensitive to a loaded machine. **Not hardened,
deliberately** — loosening a measurement to survive contention is how it stops
measuring.

**Whatever is on 8420 is stale.** Restarting it is step one of testing anything.
Confirm `build.commit_short` matches `git rev-parse --short HEAD` before
believing a single response.

**Building the installer needs a privilege this shell does not have.**
electron-builder extracts its `winCodeSign` cache using symlinks, which requires
Developer Mode or elevation; without it the build fails on two irrelevant
*darwin* `.dylib` links and the error names 7-Zip rather than the privilege.
**`--config.win.signAndEditExecutable=false` gets past it** — at the cost of the
exe's icon and version metadata, which is also the step that applies
`build/icon.ico`. The icon and the signature arrive together or not at all.

**GNU tar cannot extract to a Windows absolute path.** It reads `C:\…` as
`host:path` and tries SSH. Git for Windows puts GNU tar on PATH while Windows
ships bsdtar, so *which tar answers* decides whether a build works. Use relative
paths.

### First run is built — what it does, and the half that is still missing

`b243e17`. The screen below is no longer the next task; it exists. It is
`FirstRunPanel`, and it renders **in place of the composer** inside the
conversation rather than as a modal over the landing — the failure is explained
at the exact spot where it would otherwise be silent, and there is nothing to
dismiss and no decision remembered anywhere. `useReadiness` asks on every mount
of the conversation, so someone who sets a model up and comes back finds the
composer without touching a setting. Rule 7e: measure what happened rather than
asking the user to predict it.

**Doubt renders chat.** `setupToOffer` takes the composer away only on a known
`can_chat: false`. Still checking, or unable to ask, both leave it — and the
second is the one a later reader will want to collapse. "The probe failed, so
nothing is set up" is a reasonable-sounding inference and it is wrong: a failed
fetch says nothing about whether a model is installed. It is pure and exported
so the two states that must do nothing are asserted, since they differ only in
what they refuse to claim.

**Of the four offer kinds, exactly one can be carried out, and that is the
whole of what is left.** Looking around is a navigation and needs nothing
behind it. Install, pull and store-a-key each need an executor that does not
exist, so they are disabled and say why in a sentence. They are **not**
actionable buttons that swallow a click, and no instruction was invented to
fill the gap — a command to type or a site to visit would be a value in the
interface that nothing else in the product maintains, which is the
hardcoded-status-indicator failure by another route. `canBeCarriedOut()` in
`FirstRunPanel.tsx` is the single place a new executor is admitted.

**The wording was wrong first, and reading the rendered text is what showed
it** — not reading the code, and not the tests, which were green either way. A
shouted pill beside the label, `SET UP OUTSIDE ZARAM FOR NOW`, read as jargon,
and it sat directly above a detail line promising "installs the engine that
runs models on your own machine" on a button that installs nothing. The
sentence moved under the detail: the detail says what the option *is*, the line
below says why the button will not do it.

**`/readiness` was missing from the Vite proxy**, exactly as `/projects` was,
and that failure is silent — the dev server answers 200 with `index.html`, so
nothing errors. `frontend/src/services/proxied.test.ts` now reads the literal
`${API_BASE}` paths out of every service client and the rule keys out of
`vite.config.js` and requires a prefix match. Mutation-tested by deleting the
rule.

**Two things about verifying it here, so the next session does not chase
them.** The backend on 8420 was stale *again* — started 11:49, predating the
`/readiness` route, so the endpoint 404'd through it while answering fine on a
fresh process. Third recurrence; check `build.commit_short` first, always. And
the browser pane in this environment does not composite frames, so there is no
screenshot and `AnimatePresence` exits never complete: after "Look around
first" the panel stays in the DOM even though the store has closed the
conversation, which `LandingHint` reappearing confirms. That is the
environment, not a leak.

Both unready states were driven against the running product with payloads from
the shipped `diagnose()`: composer gone, `1.1 GB` and `397 MB` on their
buttons, no size at all on the two that fetch nothing, `still_works` listed.
The ready state was checked live through the proxy and leaves the composer
alone.

### The rest of the block this was the first item in

**Settings has no toggles at all, and that was deliberate.**
`SettingsWorkspace.tsx` is a read-only report built from `GET /health`, and its
own docstring gives the reason: a settings screen full of inert switches tells
the user they have control they do not have, which on a privacy product is the
worst thing to be wrong about. That was right when nothing behind it worked. It
is now the single thing holding the most value back — **seven working
capabilities are stranded behind one screen**: the cloud key, per-source egress
policy, egress retention, export, the first-run offers, device pairing, and the
three tiers of routing control.

Memory is the exception and already works end to end — correct, delete, forget,
pin and scope are all wired in `MemoryWorkspace.tsx`. Rule 4 is honoured today.

**The first-run screen is built — the payload below is kept because the rules
under it still bind, and because the executor will be written against the same
shape.** `GET /readiness` returns exactly:

```json
{ "readiness": "no_engine | engine_without_model | ready",
  "summary": "one line, plain language, no model filenames",
  "can_chat": false,
  "offers": [ { "kind": "install_engine | pull_model | use_cloud_key | explore",
                "label": "...", "detail": "...",
                "download_bytes": 1201483776, "download_label": "1.1 GB" } ],
  "still_works": [ "Add documents to Knowledge — …", "…" ] }
```

The screen is a render of that payload. Rules it must not break — each already
enforced on the backend side, each now asserted in
`FirstRunPanel.test.tsx`, and every one of them still a single careless edit
away from being lost:

* **Never show a dead composer.** Every unready state carries offers; render
  them. `still_works` exists so the screen reads as unconfigured rather than
  broken, and it is the difference between someone exploring and someone
  uninstalling.
* **Show `download_label` on the button itself**, not behind a tooltip. Naming
  a fix without naming its price is not a choice someone on a metered
  connection can make.
* **`download_bytes` of `null` means nothing is fetched.** Render no size at
  all — not "0 MB", which reads as free rather than as absent.
* **No model filenames anywhere in the primary path.** There is a backend test
  asserting the strings are clean; do not reintroduce them in the component.
* **Choosing an offer must not act on its own.** `/readiness` reports and never
  fetches, by design and by test. The executor that performs an install or a
  pull **still does not exist, and is now the next piece.** Three of the four
  offers are disabled until it does. Order of tractability: `pull_model` is a
  `POST` driving `OllamaAdapter` with progress; `use_cloud_key` needs Electron
  `safeStorage` and a relaunch of the Python child, since the backend reads the
  key from its environment at start and a running process cannot see a change;
  `install_engine` means fetching and running an installer and is the largest
  by a wide margin.

Then the **cloud key field**, which is the smallest change that unblocks the
friend test: anyone with a key can use Zaram without installing Ollama at all.
Recommended shape is Electron `safeStorage` (DPAPI on Windows) with the value
passed to the Python child as `ZARAM_OPENAI_KEY`, which is what the backend
already reads — **so no backend change is needed**. Never expose an endpoint
that returns a key; the local API has no authentication.

Order after that: export button, per-source privacy and retention, the
*Prefer local · Auto · Prefer cloud* control, then linked devices — which needs
the pairing endpoints written first.

### What is next — reordered 15 August

These come before the older list below, which is still accurate about
everything it covers.

0a. **Name the model that answered, on every reply.** `CLAUDE.md` requires it —
   *"Every reply names the model that answered and why, with a per-message
   override available inline"* — and nothing does. The maintainer asked "how do
   I know which model answered?" and the honest answer was: you cannot. The
   backend knows (`_resolve_model`, `locality_of`); it never reaches the
   message. This is the last missing piece of routing legibility and the
   cheapest remaining trust win.

0b. **Voice selection, male by default — done 19 August 2026.** The default is
   `am_michael`, decided in `voice/config.py` and nowhere else. The caution here
   was right and was honoured the strongest way available: rather than reading
   `/voice/voices` and trusting the list, the running backend was asked to
   synthesise with it and returned a 108 KB clip, so the name is one this
   machine is known to make sound with.

   The larger half was not the default at all. `user_settings.voice` — the
   control the *user* sets — reached no synthesis path, so voice "selection"
   existed only as a stored string. See the current state block at the top.

0c. **Persist cloud keys with Electron `safeStorage`.** Connections live in
   memory, so a restart forgets them. `CLAUDE.md` names the shape: DPAPI at
   rest, handed to the Python child as an environment variable at launch, which
   `cloud_config.seed_from_environment()` already adopts. Never an endpoint that
   returns a key.

0d. **Task-based routing across providers.** The maintainer's ask: coding to one
   service, images to another. The foundation is in — several connections at
   once, per-model resolution, `ProjectType` sitting unused with five values.
   The shape argued and agreed: **project type supplies a prior, never a
   decision**; per-message classification still runs, by embedding similarity
   against exemplars, never by a generative call. A project is not one task — a
   coding project still needs its invoice written. And a project type must
   **never** cause a silent cloud route.

0e. **Two providers the catalogue grades unreachable, both fixable.** Gemini's
   OpenAI-compatible root ends in `/openai` with the chat path hanging directly
   off it, and Zaram's URL builder assumes `<root>/v1/...` — the catalogue calls
   this "a small change to how endpoints are built" and it is. Anthropic needs a
   real adapter: `/v1/messages`, `x-api-key`, system prompt as a top-level field
   rather than a message, which matters here because that is where recalled
   facts live. OpenRouter reaches both today.

0f. **Search relevance.** The internet runtime queries Wikipedia, GitHub *and*
   DuckDuckGo for every question, so an election query returned a junk GitHub
   repo. Deliberately not touched — it is a ranking problem, not a gate problem,
   and the gate work was what was asked for.

0. **The offer executor.** The first-run screen states what is missing and can
   act on exactly one of the four things it offers. Until something carries out
   a pull, an install or a stored key, a fresh user's only working choice is to
   look around — which is honest, and thin. `pull_model` first: it is the
   smallest, it is the state a user reaches *after* installing the engine, and
   it is the one where a stated size becomes a real download the user agreed to.
   Admit it in `canBeCarriedOut()`.

0b. **Look at the two unseen changes**, and fix `npm run lint`. Both are in the
   current-state block at the top; neither is large and both are the kind of
   thing that rots if it waits.

0c. **Bring your own VRM — agreed 14 August, designed, not built.** The gate
   that blocked it exists, so this is now five pieces and only one of them is a
   decision. See *Avatars: bring your own, and the store question* below for the
   full shape and for what a store would and would not cost.

   | | |
   |---|---|
   | File picker in Settings, plus drag-and-drop onto the avatar | not built |
   | Refuse an unsafe file — `inspectAvatar` | **built** |
   | Resource ceilings: triangles and texture memory | **not built, needs a number** |
   | Store the file: IndexedDB blob, loaded as a `blob:` URL | not built |
   | Remember the choice in `embodimentStore` | not built |

   `VrmAvatar` already takes `src` as a prop, so pointing it at a blob URL is
   nearly free. **The ceiling is the only open question and it must be
   measured, not guessed**: the bundled avatar is 37,678 triangles and ~190 MB
   resident, and a limit invented from those without headroom would refuse
   legitimate avatars — which is as bad as accepting a hostile one. Same
   argument as the reranker table: a constant that gates a decision has to come
   from a measurement.
1. **Run the installer on a machine that has never seen this repo.** The
   installer itself now exists — `dist-electron/Zaram-0.1.0-x64.exe`, 186 MB —
   and its payload has been checked against the built tree, so what that run
   tests is install, first launch and the bundled interpreter finding itself
   under a different path. Take the portable build too; it isolates whether a
   failure is NSIS or the app. **Nothing else in M11 is unknown.**
2. **Obligation extraction (M9a) — the extractor exists; nothing calls it yet.**
   `backend/obligations/` reads payment, deliverable, expiry and renewal
   clauses with the sentence each came from, resolves `net 30` against an issue
   date, and returns a *question* rather than a commitment when it cannot
   honestly resolve one — an ambiguous `03/04/2026`, a relative term with no
   anchor, a date that does not exist. 28 tests.

   What remains is everything around it: nothing calls it on ingest, there is
   no store, no surface, and no reminder. The acceptance line — day 31, Zaram
   says the payment is late, shows the clause, and has the follow-up drafted —
   is not met and cannot be until obligations persist. Direction is deliberately
   `UNKNOWN` until a caller supplies it, and the caller that knows is the ingest
   path, via rule 7b's origin.

   One bug worth carrying forward: the sentence splitter cut `£2,400.00` at the
   decimal point, so precise figures extracted nothing while round ones worked.
   It failed on realistic input and passed on tidy examples, which is why the
   suite now holds a whole scruffy invoice rather than only single sentences.
3. **The business base layer** — invoices exist; quotes, receipt capture,
   expense categorisation and the monthly picture do not. Largest remaining
   volume of v1 work and the most likely to be underestimated.
4. **Cloud's Settings surface and the three tiers of control.** The key comes
   from the environment today. The recommended shape is Electron `safeStorage`
   (DPAPI on Windows) with the key passed to the Python child as an environment
   variable — which is what the backend already reads, so no backend change.
   **Never expose an endpoint that returns a key**, given the local API has no
   authentication.
5. **The avatar.** **Five** states, closed set, from `useEmbodimentState`: idle,
   thinking, listening, speaking, swapping — `local` and `cloud` were removed on
   13 August, see below. Six mouth visemes — `sil aa ee ih oh ou` — from
   `src/lib/visemes.ts`. Eyes are state-derived only, no gaze. The acceptance
   test is two states side by side in a screenshot at the size they will
   actually render.

   Before a second character or any avatar the maintainer did not author: **the
   loader has no URI policy.** `new GLTFLoader()` in `VrmAvatar.tsx` takes no
   `LoadingManager`, and glTF buffers and images may carry absolute `https://`
   URIs, which the browser would fetch on load. That is the class
   `check-no-remote-assets.mjs` bans — a request no gate can see — arriving as
   *data*, which is why a build-time source scan structurally cannot catch it.
   Same shape as `core/untrusted.py`: a downloaded avatar is not something the
   user typed. Needs an embedded-and-`data:`-only allow-list plus texture and
   triangle ceilings, and it is the prerequisite for bring-your-own-VRM.

**Blocked on the maintainer, and only this:** buying the OV certificate. Every
day it is not begun adds a day to the end.

### The phone — decided 12 August, foundation built

**A PWA served from the user's own machine over a Tailscale tunnel.** No app
store, no server, no account. Decided because it is the only shape that keeps
the product's claim intact: the phone reaches *into* the machine rather than
the machine copying itself outward.

**The bind is never widened.** `tailscale serve` runs locally and proxies
tailnet traffic into `127.0.0.1:8420`, so `LISTEN_HOST` stays loopback and
non-configurable. The morning's security fix survives the feature that would
most obviously have undone it.

**No accounts.** Device pairing instead — the machine holding the Spine is the
authority, as in WhatsApp and Signal. Accounts become necessary at exactly
three points, none of them now: teams, sync with the machine off, and payment.
When they arrive, an account authenticates and never takes custody.

**Cloud-only inference on the phone, and it changes the consent shape.** Every
phone message is an egress event, so the per-message confirmation that works on
the desktop becomes the reason people uninstall it. Standing consent per
project and per provider, revocable, with the log still complete. And the phone
recalls only what the per-source policy already permits to leave — which needs
no second privacy model — and **says what it withheld**.

`core/pairing.py` is the first authentication the API has ever had: one-time
tokens that expire in a minute, credentials returned once and stored only as
hashes, constant-time comparison, and revocation that refuses through the same
path as a forgery so no caller can forget to check. 25 tests.

**Not built:** the endpoints, the QR, the linked-devices UI, the mobile bundle,
and the `tailscale serve` toggle. The mobile build must exclude `three` and
`@pixiv/three-vrm` — megabytes of avatar that is pointless on a phone.

### Documents as templates — agreed 12 August

Asked for on 12 August — upload an existing invoice or letterhead and have
Zaram produce new documents that look like the company's own. Agreed the same
day, including the cut below.

**The shape that is worth building, and the part that is not.** Exact layout
cloning is refused, for the reason that already excluded an embedded office
engine: reproducing an arbitrary `.docx` means reimplementing Word's layout,
and a PDF carries no structure to reproduce at all. The failure mode is the
specific one that matters — a *near* miss. A document 90% in the house style
is worse than one obviously Zaram's, because the client notices the wrong font
on something carrying their letterhead.

What users want decomposes into three things that are reliable: **identity**
(logo, trading name, address, accent colour), **boilerplate** (terms, footer,
bank details, numbering scheme) and **conventions** (standard terms, currency).

**The second and third are facts, not formatting**, and that is what makes this
cheap: they belong in the Spine with provenance and scope, correctable under
rule 4, rather than in a template store. Which means uploading three past
invoices does not merely style new ones — it teaches Zaram the business.
CLAUDE.md already promises Zaram "knows the client's rate, their terms, and
that they pay late"; this is how that is true on day one instead of day ninety.
It is the onboarding path for the business layer, not a formatting feature.

`Letterhead` and `render_document` are the seam, and HTML-as-source-of-truth
means a style profile is CSS variables plus masthead content. No new pipeline.

Conditions, if it is built: a review step before first use — never silently
adopt an extracted identity; refusal rather than approximation when a logo
cannot be extracted cleanly; fonts matched to a bundled family **and said so**,
since remote fonts are banned and embedding a licensed one is a licensing
question; and per-project templates, which `scope` already allows. An uploaded
template is a source in Knowledge under the per-source policy like any other.

**The layout-cloning cut is accepted.** Everything above depends on it.

### Two ideas worth taking from outside

Read against an external memory-architecture proposal, 12 August. Most of it
was already here under rules with recorded failures behind them, and four
parts contradict things this repo has measured — a mandatory reranker (bought
nothing at 1,000 documents, and `bge-reranker-v2-m3` cannot run through Ollama
at all), a raw-dialogue experience log (rule 7d inverted), a merged
relevance-and-trust score (the blend-versus-threshold bug, three times), and a
graph database (a stranger cannot install it). Two parts are better than what
exists:

* **Supersession — built, as detection.** The *recording* half already existed
  and is good: `correct()` writes a replacement, marks the original superseded,
  drops it from the index and keeps it visible struck through. What never
  existed was anything that **noticed**, so the ordinary path was to store both
  and let recall choose between "the target is developers" and "the target is
  consumers" — a coin toss dressed as an answer.
  `runtimes/memory/conflicts.py` reads simple assertions and reports
  contradictions. **It resolves nothing**, and that division is the part most
  likely to be argued away later: auto-resolving on recency is wrong about as
  often as it is right, and auto-resolving on confidence lets a well-phrased
  sentence in an uploaded PDF overwrite something the user said aloud. Both
  fail silently and both destroy the record rule 4 protects.
  **Scope is what makes it tractable**, and it is what the external designs
  cannot express: two projects holding different payment terms is the normal
  case, not a conflict, so a conflict requires the same scope. 20 tests.
* **Ingest is an unguarded path into memory — the rule is now code.**
  `core/untrusted.py`: only what the user typed may instruct, written as an
  allow-list of one value so a channel added later is refused by omission
  rather than permitted by it. `scan()` labels blatant injection attempts and
  **never filters** — stripping suspicious text corrupts real documents and
  teaches the user nothing, and a clean scan is explicitly not clearance.
  This matters now rather than later because obligation and template
  extraction both turn a file somebody else wrote into something Zaram acts
  on: a hostile invoice is a way to put a deadline in someone's week or a
  different bank account on their letterhead. 15 tests.

  **Not yet wired.** The module is a boundary with no call sites — the ingest
  path does not yet tag what it produces with a `Provenance`, and until it
  does, this is a guard nobody has asked. That wiring is the next step and it
  is the one that makes the rule real rather than stated.

### What changed, in one screen

Read the sections further down for the reasoning; this is the index.

| | |
|---|---|
| **Cloud engine** | `OpenAICompatibleEngine`, no new dependency, **no HTTP client of its own** — `EgressGate.stream_lines` carries the bytes. Recorded deviation from CLAUDE.md's LiteLLM entry, with reasons, reversible behind `LLMEngine`. |
| **Cloud routing** | `RoutedEngine` picks local or cloud per message by the model's **declared locality**, never by name — `gpt-oss` runs on Ollama. Every unknown routes local; `HYBRID` counts as remote. |
| **Confirm-before-send** | The confirmation may *edit* the outbound text, and the gate now reads the body back after the check so the edit reaches the wire and the log identically. **Answerable as of 12 August** — endpoints, dialog, and the event-loop fix that made delivering the question possible at all. |
| **Chat streams off the loop** | Both `ChatRouter` paths iterate the engine's synchronous generator in a worker thread. Previously any blocking step froze the whole backend; with a confirm hook in the path that made the feature unreachable rather than merely slow. |
| **Loopback only** | The API bound `0.0.0.0` with no authentication on any endpoint — the Spine, the egress log and the policy were readable by anyone on the same network. Now `127.0.0.1`, not configurable. The test that would have caught it existed and had never been run. |
| **Installer payload** | Included by allow-list, not denylist. A denylist was shipping 437 MB of venv and scratch **plus `spine.db`, `egress.db`, the artifacts and projects databases, the privacy policy and the generated invoices.** Two gates hold it — one in the suite, one in the build. |
| **Python in the installer** | Relocatable CPython 3.11.9, SHA-256 verified, 401 MB. PyInstaller ruled out because the product tells users to `pip install zaram[ingest]` and you cannot pip into a frozen bundle. **`Zaram.exe` packaged and starting its own backend for the first time.** |
| **Electron tests run** | `npm test` wired to `test/`, which held 26 tests nobody had ever run and two failures. Both were stale tests over correct production code — and one of them encoded the loopback binding. |
| **Frontend tests run** | Same shape, found later: 103 vitest tests across 14 files with no script pointing at them. `npm test` now runs both JS suites; `test:backend` encodes the venv interpreter. |
| **Installer icon** | `electron-builder.yml` names no icon and `/build/` was ignored, so a fresh clone would have built an installer with the default Electron icon and no error. `build/icon.ico` is tracked now. |
| **The installer exists** | 186 MB NSIS plus a portable build. It had never been buildable without a code-signing certificate: `${env.ZARAM_SIGN_SUBJECT}` does not resolve to empty when unset, and the literal killed the build while signing the uninstaller — after packaging had already succeeded, which is why "packaged" and "no installer" were both true and never connected. |
| **Code signing** | OV, prepared, not purchased. **EV buys nothing** — Microsoft's own docs say it no longer bypasses SmartScreen. Artifact Signing unavailable in Nigeria. Identity by env var, timestamping mandatory, release gate refuses unsigned. |
| **Brand** | Mark traced from the source image rather than eyeballed — it is 1.31:1, two interlocking planes, gradient ending in cyan. One generator emits SVG, PNG and a seven-size `.ico`. Top-left app icon returns home. |
| **Project adoption** | `harbour` and `northwind` existed on files but were not projects, and assignment validation had made that a one-way door. Adopt keeps the id exactly; generation is validated so no new ghosts arrive. |
| **Recall at scale** | Measured at 10/100/1,000: margin +0.131 → +0.108 → **+0.106**, 5/5 recalled at rank 1, zero false citations. The curve saturates. Reranker stays unbought. |
| **Shortcuts** | Every chord was dead on Windows — the matcher waited for the Win key while the overlay advertised Ctrl. |
| **Invoices / formats** | Decimal money, terms → due date from one number, refusal rather than invention. `.html`, `.txt`, `.csv`, `.pptx` added; slides are headings, not a second pipeline. |
| **Speech** | Time-to-first-sound 9.9s → 2.5s, no longer scaling with reply length. |
| **Landing** | Orbit nodes drag and spring back to their live slot. One Settings in the rail, not two; 440px → 260px. |

### Read this before debugging anything

**Check which build is answering.**

```
curl -s localhost:8420/health | jq .build
```

It reports the commit and uptime. A backend started at 06:32 on 10 August served
that port for the rest of the day while two *already fixed* bugs — the audio 404
and recall firing on a greeting — were reported as live and re-diagnosed against
it. Both fixes had been correct the whole time. **Windows lets a second uvicorn
bind `0.0.0.0:8420` beside a `127.0.0.1:8420` without an error, and the older
process wins for loopback.** A backend with no `build` field at all predates
this commit and is stale by definition.

Proven rather than assumed, same input to both, same second:

```
port 8420 ('Hello') -> 3 source events     (the stale process)
port 8425 ('Hello') -> 0 source events     (current code)
```

**It happened again on 10 August and cost the same way.** A backend from 06:32
was still serving 8420 at 19:00 with **no `build` field at all** — it predated
the stamp. Restarting it is what made the new routes reachable. To restart:

```
powershell -Command "Get-NetTCPConnection -LocalPort 8420 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
```

then `backend/start.bat`, and confirm `build.commit_short` before testing.

**The venv is `C:\Zaram\.venv`, and bare `python` on PATH is a broken shim** —
it exits with "the install path was not found". Use
`C:\Zaram\.venv\Scripts\python.exe` for every pytest run. `py` is also
unreliable here.

**Run pytest from the repo root**, with `.venv/Scripts/python.exe` — not with
whatever `python` resolves to. `--ignore` in `pyproject.toml` is rootdir-relative
so running from `backend/` aborts the whole suite, and the system Python 3.11
has pytest but not the dev install, where the suite reports 54 failures that all
look like product defects and none of which are.

Live measurements against a local model carry a `measure` marker and skip when
Ollama is absent. `pytest -m measure` re-runs every one of them — do that when an
embedding model changes, because several recorded numbers are calibrated to
bge-m3 and do not transfer.

**Run it with `.venv/Scripts/python.exe`, not with whatever `python` resolves
to.** The system Python 3.11 on this machine has pytest but not the dev install,
and the suite reports **54 failures** there — python-docx, openpyxl and the rest
are missing, so ingest reports "Nothing installed can read this file" and twenty
artifact tests fail on exporters that are not there. Every one of them looks
like a product defect and none of them is. Recorded because it cost twenty
minutes: a suite that fails differently depending on which interpreter found it
is not telling you about the code.

One run on 9 August took **36m25s** and has never reproduced; the two runs
since were 2m19s and 1m19s. Three wrong explanations were offered for it
before measurement (live DuckDuckGo calls in the suite — real, but 2.8s;
`pytest-randomly` — not installed; a first-use HuggingFace download — cache
untouched). Recorded so nobody spends another hour on it: **it is not
reproducible and it is not understood.** If it returns, run with
`--durations=25` first.

### Project is the sixth node — decided 10 August 2026

**The navigation is now six: Work · Project · Memory · Knowledge · Activity ·
Settings.** Maintainer's decision, and it reverses an argument I made against it
in the same conversation, so both halves are recorded.

The case against: a project only groups artifacts, and a grouping of artifacts
is a filter inside Work rather than a surface — the same test that cut Canvas
and Plugins.

**Why that was wrong: rule 7i.** Project scope applies to *facts*, not only
files. `project:<id>` is a field on the Spine, the queued plan object carries
the same scope, and Knowledge sources carry it too. A project spans Work, Memory
and Knowledge at once, and a filter living inside Work cannot own something that
scopes Memory.

The precedent the maintainer named is the right one: **Memory and Knowledge are
similar and are not the same**, which is why they are two nodes and not one.
Project stands in that relation to Work — adjacent, overlapping, distinct.

It also passes "does it hold something real?" more clearly than Work does. A
project holds a type (which activates a pack), its scoped facts, its assigned
artifacts, and eventually its plan with decisions taken and rejected.

**Bounded, and the bounds are the point.** No folder tree, no subfolders, no
nesting — one level. Work is the output; Project is the organisation of it.
Deleting a project asks what happens to the facts and files inside, never one
button. `CLAUDE.md` and `docs/UI-SPEC.md` are updated.

**Also declined in the same conversation: sub-apps inside Work for file
editing.** Already settled in the dependency stack — OnlyOffice is AGPL,
LibreOffice headless is hundreds of megabytes, both are separate services.
Zaram generates; users edit in what they already have. The narrow defensible
version, post-v1 and unpromised, is that HTML is the source of truth for every
generated document, so *editing Zaram's own generated HTML before export* needs
no embedded editor. That is a preview that accepts edits, not a word processor.

### Documents are laid out for paper now — and it was never the model

The report was that generated PDFs and Word files "lack design, have no header,
and would not pass as a document anyone deals with in 2026", and the suspicion
was that the local LLM was the limit. **It was not.** The model writes the
words. Every visual property came from eight lines of CSS at the bottom of
`artifacts/html.py`:

```css
body{font:14px/1.6 Georgia,serif;max-width:44em;margin:3em auto;color:#111}
```

`max-width` and `margin:auto` are screen conventions on something destined for
paper, and there was **no `@page` rule anywhere** — so no paper size, no print
margins, no page numbers, no running foot, no letterhead. A larger model would
have written better prose on the same unstyled page.

Now: A4 with document margins, "page N of M", a real type scale, a ruled
masthead, an optional metadata block, and the print rules that are invisible
when they work — `orphans`, `widows`, `break-after` on headings, `break-inside`
on tables. One stylesheet with `@media screen` / `@media print`, because the
same string is the preview *and* the WeasyPrint input and two templates would
drift. No web fonts: a generated document is opened on machines Zaram does not
control, so a linked font would make it phone home from a stranger's laptop.

**Tables are set the way printed documents set them.** The old rules boxed every
cell in a 1px grid, which is a spreadsheet convention. Three details separate a
document from a table dump: `tabular-nums` so a money column aligns on the
decimal, `thead{display:table-header-group}` so headings repeat on every page,
and `break-inside:avoid` on rows so a line item is never cut in half.

**Branding.** `Letterhead` carries a name, free-form lines and a logo. The logo
is **embedded as a data URI, never linked** — `export/pdf.py` calls WeasyPrint
with no `base_url`, so a path cannot resolve. SVG is refused with a reason: it
can carry `<image href="https://…">` and no scanner sees inside a data URI.

**Sources and claims are no longer printed into the document.** An invoice goes
to a client, and the client has no use for `memory:55b6` at the foot of it. This
does not weaken rule 2 — rule 2 is traceability, and its operational test
(`test_provenance_invariant.py`) is about the *stream*. The anchors stay in the
markup and on `Artifact.claims`; the preview renders provenance as chrome around
the document, the same relationship `CitationPanel` has to a reply.
`include_provenance=True` turns it back on for a research brief or a proposal,
where citation is part of the genre.

### Where branding is captured — decided, not yet built

Global scope, captured in chat, offered at the moment of doubt. Rule 7i decides
it: a letterhead is about *the user*, not about the work, so it is global with a
per-project override for someone genuinely trading under two names. Rule 7e says
do not make them fill a form before their first document — drop the logo in the
composer and say "use this as my letterhead". Rule 7h says offer it the first
time a document is generated without one. **Settings is where it is visible and
editable afterwards, never the only way in.**

### Scope changed this session, deliberately

Two reversals of `CLAUDE.md` as previously written, both the maintainer's
decision. `CLAUDE.md` has been updated to match; this is the reasoning.

- **Voice is in v1, both directions.** Speech out (Kokoro) and speech in
  (faster-whisper, local), because a character that cannot speak or listen is
  a skin rather than an embodiment. **Speech follows the renderer** — avatar
  speaks, orb is silent unless asked — so it needs no second setting.
- **The 3D embodiment is in v1**, no longer a spike. Toggle on the landing for
  now; the shipped control belongs in Settings.
- Extras split: `zaram[voice]` ~905 MB speaks, `zaram[mic]` **81 MB measured**
  listens. Light installer, extras fetched **on demand after the product has
  proved itself** — not during install, which is the same blocking download
  moved earlier.

### Avatars: bring your own, and the store question — 14 August 2026

**Bring your own VRM is agreed.** Shape and status are in *What is next*, item
0c. The one open decision is the resource ceiling, and it needs a measurement.

**Storage is IndexedDB as a Blob, loaded through a `blob:` URL**, and the
reasoning is worth keeping because a filesystem path looks like the obvious
answer. A blob works in Electron *and* in a browser surface, which `CLAUDE.md`
deliberately keeps possible by having the frontend call the backend over HTTP
rather than through IPC; there is no packaged path to get wrong, which is the
class of bug that made the bundled Python runtime hard to find; and the URL
modifier added with the loader gate already permits `blob:`, so nothing else in
the renderer changes.

**BYO does not strain the embodiment rule, and this distinction is what makes
it safe to build.** The rule refuses a *someone* — no name, no pronoun, no
expression not derived from system state. Choosing what the indicator looks like
is skinning; the rule is about behaviour, and it holds whatever mesh is
rendering. What creates pressure is *selling* characters, because to sell one
you market it as somebody, and that pull comes from the revenue side, which is
the hardest kind to resist later.

**"An avatar store" is three different businesses and they must not be argued
as one.**

| | What it is | What it costs |
|---|---|---|
| **First-party set** | Zaram ships a handful it commissioned | Files. No accounts, no moderation, no payouts. |
| **Curated directory** | A manifest pointing at avatars hosted elsewhere — VRoid Hub, Booth, a creator's own site. Zaram holds no money and hosts nothing; each download is an explicit, logged egress under the existing per-source policy. | Small, and it buys **discovery**, which is the part that makes a store feel like something. |
| **Marketplace** | Users sell to each other | Accounts, IP and adult-content moderation, cross-border payouts, tax, disputes. A different company. |

The middle one was not offered clearly enough when this was first argued down on
13 August, and it is the interesting answer: browse-and-pick with none of the
machinery, and honest about what Zaram is — a safety gate and a bookmark list,
not a merchant.

**Sequence: BYO → directory → measure whether people actually swap → then
decide about money.** If nobody changes their avatar, a marketplace was never
going to work. If many do, that is the evidence that justifies accounts — which
`CLAUDE.md` already says arrive only at teams, off-machine sync, or payment.

**One argument this file previously under-weighted**, recorded because it is the
strongest case for doing any of it: an avatar is the first thing in Zaram a user
can make *theirs*, and every creator who lists one markets the product to an
audience that already runs local models. That is a distribution argument, and it
is better than the revenue argument.

**Attaching avatars to agents remains where a character legitimately becomes a
someone** — an agent is a thing with a job. Post-v1, and it is what makes a
store coherent with the embodiment rule rather than in tension with it.

### The assistant knows what it is — 13 August 2026

**Reported symptom: asked what it was, the product answered "I am Qwen, made by
Alibaba".** Three things were producing it and only one was obvious.

`core/identity.py` is the fix and the reasoning is worth keeping: **a model does
not know what it is deployed as.** Ask a local model its identity and it answers
from training data — fine-tunes claim to be GPT-4 all the time — so "which model
am I talking to" is a question about *system state*, and the true answer exists
only where routing already resolved it. The module composes it and `main.py`
puts it in front of the persona on every request. Nothing is suppressed; the
model is handed a truer answer than its weights contain.

**The personas were the larger half.** Eight entries in `main.py`, each opening
"You are Baba, a wise and analytical AI assistant" or "You are Nova, fast-paced
and technical". Every one made an identity claim, so the assistant had three
candidate answers to "what are you" — the persona's, the model's training, and
the truth — with no reason to prefer the last. They were also precisely the
*someone* the embodiment rule refuses, sitting in the prompt rather than on a
face; removing it from the avatar the same day and leaving it here would have
moved the projection rather than ended it. They are tone-only presets now.
`zaram_prime` carries an empty prompt, its one genuinely behavioural instruction
— prefer recalled facts over training and say which you used — having moved into
the identity block where it applies to every request rather than one preset. The
`/personalities` endpoint keeps its shape and the speech path keeps its Kokoro
voice selection, which is why they were rewritten rather than deleted.

**Locality had to be split, and this is the part most likely to be merged back.**
`ModelsRuntime._is_remote_model` returns `False` for a model it cannot resolve,
which is the correct fail-safe for routing: guessing local costs a
possibly-wrong model, guessing cloud costs the user's documents leaving on a
lookup that failed. Identity inheriting that would have described an unresolved
model as *running on this machine* — a confident false claim on the one thing a
user is most likely to check. `locality_of` returns `local`, `cloud` or `None`,
and `identity_preamble` renders nothing for `None`. Same input, two questions,
two answers, exactly as `vram_bytes` returns `None` rather than `0`.

**Verified by asking the running product**, which is the only thing that could
have shown it:

> *"I am Zaram. I'm a memory and control layer running on this machine … Right
> now, gemma3:latest is answering you."*

Names Zaram, does not claim to be Gemma, reports the real model. 14 tests, and
the one that would have caught the original defect asserts no preset contains
"You are".

### State changes are transitions, not cuts — and the lerps were frame-tied

The rim light is the avatar's state channel and it was assigned absolutely every
frame, so idle-to-thinking swapped slate for cyan between two frames. On a
surface briefed as *calm over delight*, an instant colour flip is the one motion
that reads as a glitch rather than as a state. It eases now, over 0.22s.

**The larger finding was underneath it.** Every lerp in the file was
`lerp(a, b, dt * k)`, which covers a different fraction of the distance per
*second* at every refresh rate — so the avatar eased at visibly different speeds
depending on the display, and the tuning was only correct on the machine it was
tuned on. `approachRate(dt, τ)` is the exponential form, `1 - e^(-dt/τ)`, and
head, mouth and rim all use it. The time constants were chosen to match what the
old factors produced at 60Hz, so nothing looks different on the machine it was
tuned on and everything looks the same on the machines it wasn't.

**Two of the new tests failed first and both were the test correcting the
comment**, which is worth recording because it is the file's own lesson pointed
at a claim rather than at code. The comment said the clamp prevents overshoot on
a long frame; `approachRate(5, 0.22)` returned `0.9999999998`, not `1`, because
`1 - e^(-x)` cannot reach or pass 1 for any finite input — overshoot is
impossible by construction and the clamp is belt-and-braces. The *linear* form it
replaced genuinely did overshoot: at `dt = 0.5` the old factor is 1.5, and a lerp
past its target springs back. The second failure was an assertion that the two
forms diverge by more than 1% between 60Hz and 240Hz; the real figure is 0.68%,
because `dt * k` is a first-order approximation that agrees closely at short
frame times. The test now asserts what is true — that the error *grows* with
frame time, and that past `dt = 1/3` the old form breaks completely rather than
gradually.

**Not verified visually.** This environment cannot take a screenshot — the
browser pane does not composite — so what is asserted is the maths, which is
frame-rate independence and the absence of overshoot. Whether 0.22s reads as
calm or as sluggish is a judgement nobody has made yet. Given the pointer-gaze
lesson, that gap is stated rather than glossed: **somebody should look at it.**

### The avatar stops reporting which model answered — 13 August 2026

Maintainer's decision, narrowing the spike's own constraint. `local` and `cloud`
are gone from `EmbodimentState`, which is now five states and is the *same type*
as `OrbState` rather than a copy of it. `useEmbodimentState` no longer reads
`sessionStatusStore` at all.

**The justification for this was written wrong first, and driving it in the
browser is what caught it** — which is the file's own lesson arriving again, on
a docs change rather than a feature. The claim written into three documents was
that `OrbStatusLabel` renders under either renderer, so nothing is lost. Reading
the DOM at rest returned no status element at all: the label is behind
`{chat && …}` in `Landing.tsx`, deliberately, because *"at rest the landing is
meant to be quiet"*.

**The real finding is better than the wrong one.** `LivingOrb` reads
`orbStore.orbState` directly and has **never rendered locality**. The avatar was
therefore the only renderer that reported where an answer came from, and the
same status told the user different things depending on a toggle. The spike's
claim that both renderers read one derived state was half true — the derivation
existed and one consumer ever saw it. Removing `local` and `cloud` makes the two
agree.

Where locality is reported is `OrbStatusLabel`, in words: "Local only", "Local ·
can send", "Cloud enabled". `describeSystem`'s comment records why three rather
than two — permitting one search host once flipped it to "Cloud enabled" while
every answer was still generated locally, *"on the one indicator whose entire
job is to be trusted."* A colour cannot express that, so the colour and the
label could only ever have agreed by luck.

**And the loss, stated rather than papered over.** The avatar surfaced
`local`/`cloud` **only at rest**, which is exactly when that label is absent, so
the two were complementary rather than redundant. At rest, nothing now reports
locality — already the case on the orb path. If it should be visible at rest,
that is one condition in `Landing.tsx`, not a colour on a face. Also noted while
checking: CLAUDE.md says *"the Orb shows system state (idle / thinking / local /
cloud)"* and `OrbState` has never held the last two. The codebase wins.

**The other half is the reason it came up.** A face that reports where an answer
came from is read as a *someone* — "she used the cloud" — which is the exact
projection the embodiment rule exists to prevent, and the pressure toward it
comes from anything that sells or personalises characters. Recorded rather than
merely done, because that pressure arrives from the revenue side, which is the
hardest kind to resist later.

**What replaces it, eventually: an avatar attached to an agent.** An agent is a
thing with a job, and a face standing for one claims nothing about
infrastructure. Not designed and not scheduled — agents are out of scope until
v1 ships and get no menu item when they arrive. Noted so the removal reads as a
redirection rather than a deletion.

`swapping` stays, and it is the judgement call. It is about model residency, so
it is adjacent to what was removed — but it answers *what is happening now*
(nothing, while a model loads) rather than *who answered*, and CLAUDE.md
requires a swap to be visible because an invisible one reads as a broken
product.

### One avatar, then bring your own — the store stays out

Decided in the same conversation. **One character ships.** Three would be ~48 MB
of VRM into a 186 MB installer against "never block on a download", three rigs
to pose, and two shading models to light — the sample is MToon, and a robot is
the case that needs real PBR.

**PBR is not configured today**, which is worth knowing before a robot is
authored: no `scene.environment`, no `PMREMGenerator`, no `toneMapping`
anywhere in `src/`. `GLTFLoader` builds `MeshStandardMaterial` correctly, but a
metallic surface with nothing to reflect renders near-black however many lights
are added. The fix needs no downloaded asset — `RoomEnvironment` is procedural
and in-bundle, which matters because `check-no-remote-assets.mjs` would refuse
an HDR fetched from anywhere. Enabling tone mapping will visibly change the
MToon avatar that exists, so it is a deliberate change rather than a free one.

**Sketchfab's renderer is not worth reimplementing.** Their viewer is
proprietary; the open piece was `osgjs`, MIT and long unmaintained — worth
verifying before anyone relies on that. What makes such viewers light is the
*asset pipeline*, not the shading, and every part of it already ships with
three: KTX2/Basis (textures stay compressed in VRAM, which is the real win
against six 2048² maps), Draco or meshopt geometry, and prefiltered IBL via
`PMREMGenerator`. Rebuilding a renderer to get those is the trade CLAUDE.md
already rules on — rendering is commodity and improves every quarter; the
state mapping is not.

**Bring your own VRM is the next step, and an avatar store is not.** BYO needs a
file picker and a validator, no account, no payments, no moderation — and it is
the same posture as bring your own key and bring your own model. A store is an
extensions marketplace under another name, which the scope list already defers
past v1, and it is the feature that forces accounts, since payment is one of the
three things this file already says require them. It also brings IP and NSFW
moderation over an ecosystem saturated with derivative characters, and
cross-border payouts — which deserve the same early geographic check that code
signing needed rather than a late one. If BYO shows people actually swapping
avatars, that is the evidence a store is worth it. Behaviour, not a guess.

The validator BYO needs is the loader URI gate described in item 5 above, and it
is required before *any* avatar the maintainer did not author is loaded.

### Decided against, so it does not return as a reasonable suggestion

- **Hospitals as a segment. Cut.** The proposal was storing patient records and
  using GPT Vision to review x-rays and infer patterns across tests. That is
  diagnostic support — regulated as a medical device (FDA SaMD, EU MDR IIa+) —
  and it is already on the never-build list. It also means patient data leaving
  the device to a provider with no BAA. The defensible neighbour is medical
  *documents* for individual clinicians, never diagnosis, and not before M12.
- **Cloud speech recognition in Settings. Cut.** Probed in Electron 28.3.3
  (`electron/probe-speech-support.js`): the constructor exists, `start()` errors
  `not-allowed`. That result is **confounded** — the probe denies all
  permissions — and resolving it would mean sending real audio to Google. It
  does not matter: broken means a dead control, working means microphone audio
  leaving unlogged. Same answer from both branches.
- **A `Creative` embodiment state. Cut.** Every other state answers *what is the
  system doing*; `Creative` answers *what kind of task is this*, which is a genre
  label. Rendering it means the avatar performs a mood based on subject matter —
  the drift into personality the spike exists to prevent. Fold into `working`.
- **"Everything ChatGPT can do" as positioning.** Those are model capabilities;
  Zaram trains no models and would be permanently one release behind. The claim
  is **any model, one memory, nothing leaves without you seeing it** — which
  gets stronger as models improve. Capability arrives by routing and tools,
  never by Zaram implementing a modality.
- **An agent framework for the plan object.** ADK, LangGraph, CrewAI all ship
  their own memory and session abstraction, and memory is the product.

### What this session built

Six commits, `1ccc339..7a7bd45`, all pushed.

- **`66736fa` DuckDuckGo asks the gate.** `DDGS` opened its own socket, bypassing
  `get_gate()`, while `test_egress_chokepoint.py` exempted the module as
  *"dormant"* and `test_knowledge_runtime.py` called it for real on every run.
  The guard checked reachability **at boot**, so it passed while the suite made
  the unlogged live request. 0.67s live → 0.01s refused and logged. The three
  web-provider tests were also vacuous *and machine-dependent* — `if results:`
  asserted nothing, and whether they touched the network depended on the
  gitignored `backend/egress-policy.json`. Now driven against gate doubles:
  69 tests, 0.89s, no network.
- **`f22d06f` The embodiment spike runs.** `useEmbodimentState()` derives one
  state from `orbStore` (activity) and `sessionStatusStore` (locality) without
  either duplicating the other. Activity wins over locality, so `local`/`cloud`
  surface only at rest. `<Embodiment />` picks at mount, no crossfade, VRM lazy
  so the orb path never pays for `three`. Confirmed in `AvatarSample_Z.vrm`:
  14 expressions, **all five visemes**, humanoid rig.
- **`e5e55f0` Kokoro's phoneme timings survive.** They were discarded by tuple
  unpacking at `kokoro.py:242`; `pred_dur` comes out of the same forward pass, so
  the cost of keeping them is zero. They cross the interface as `SpeechTiming`,
  never as Kokoro's `MToken`. Offsets are absolute across chunks; `None`
  timestamps are skipped, not zeroed.
- **`576e5aa` The mouth is driven by those timings**, scrubbed against
  `audio.currentTime`. `check-visemes.mjs` asserts the mapping and was
  **mutation-tested** before being believed. `check-no-cloud-speech.mjs` bans the
  Web Speech API and asserts the `legacy/` quarantine.
- **`cfaa191` The avatar speaks its replies.** Closes the gap that mattered:
  every piece was green while the character was silent, because nothing called
  `speak()`.
- **`7a7bd45` The STT contract.** `SpeechRecogniser`, `Transcript`,
  `TranscriptSegment` — which mirrors `SpeechTiming` on purpose. `language` is
  `Optional` and never defaults to `"en"`.

Then seventeen more, `0cef961..a0d2bed`, all pushed. Each is written up in full
in the sections below.

**Voice**
- **`0cef961` The audio URL 404.** `audio_filename` crosses the connector
  boundary; `base_url` defaults to empty so the URL is relative.
- **`b7bca96` Zaram listens.** `WhisperRecogniser`, `/voice/transcribe`,
  `micStore`, `MicButton` — and `speechStore.error` finally rendered.
- **`2c4c819` A dictated amount is flagged, never corrected.** The audio says
  *naira*; Whisper said **$**.
- **`67ca372` The orb can be asked to speak.** The "unless asked" half of
  "orb, silent unless asked", which was never implemented.

**Guards and correctness**
- **`fc1fb42` Three holes in the guards.** The CSS universal selector, the
  block-comment blind spot, and exemptions that had stopped being needed.
- **`0c8cc8b` A greeting no longer pulls the user's files into the prompt.**
- **`b69b147` `/health` says which build is answering.**

**Embodiment**
- **`09e5303` The avatar's GPU cost, measured — 190 MB, not 1.5 GB.**
- **`2cbe9bb` The avatar was pixelated, and `antialias:true` was not the fix.**
- **`f2a2a16` Triangle count reported alongside VRAM.** 37,678 today.

**Documents**
- **`3d3d0a1` Laid out for paper, and carrying the user's branding.**
- **`517c3da` The client sees the document, not the working.**

**Navigation**
- **`faabf4a` Project is the sixth node** — docs only.
- **`a0d2bed` The sixth node exists in the app**, not only in the docs.

**Also** `9f22bfb` the page-load 404 (it was `/favicon.ico`), and three `docs`
commits including this file.

### Project is a real object now — and the lesson from building it

`a0d2bed`. A project used to be `SELECT DISTINCT project_id FROM artifacts`, so
it existed only once a file had been saved into it, could not be created,
renamed or deleted, and had nowhere to keep the type that activates a pack.

Both endpoints remain and answer different questions: `/artifacts/projects` is
"which projects hold files" (Work's filter, which cannot lead to an empty list),
`/projects` is "which projects exist". Conflating them was the bug.

**Deleting states what it will do and then does only that.** `contents=keep`
re-scopes facts to global — the grouping goes, the knowledge stays — and is the
default because it is recoverable. `contents=delete` is never implicit; an
unrecognised value is a 400 rather than a guess at the destructive branch. Files
are never touched and the response says so, because "the project is gone" would
otherwise read as "the files are gone". Fact counts are `-1` when the Spine
cannot answer, rendered as "an unknown number", and the destructive button is
**disabled** in that state — "0 facts" on a confirmation that then destroys
eleven is the failure the sentinel exists for.

**Renaming never moves the id**, because facts carry `project:<id>`.

**The lesson worth carrying forward: a comment describing a bug does not prevent
the bug.** `registry.ts` calls `orbitOrder` the canonical node list and warns, in
prose, that three components had each restated it and CommandPalette had
silently lost Activity as a result. That was written down and never enforced —
and `orbitOrder` ended up with **no consumers at all**. So adding Project
updated the rail, the command palette and the router while the orbit, the first
thing anyone sees, kept rendering five nodes. It was caught by taking a
screenshot, not by reading the code. `Landing.test.ts` now asserts the orbit
against `orbitOrder` for membership, order, labels and spacing.

Two more found the same way: `slugify` **stripped accents instead of folding
them** ("Ünïcodé Studio" → `n-cod-studio`, which is what a French, German or
Yorùbá business name would have become), and `/projects` was **missing from the
Vite proxy**, so every call from the frontend would have hit the dev server.

### TencentDB Agent Memory, read and mined — 11 August 2026

Reviewed at the maintainer's request. **It is not a competitor and it is not a
dependency; it is a source of two retrieval ideas Zaram should take.**

**Why it is not a competitor.** Its user is a team wiring an agent fleet, with a
control panel governing what a fleet shares. Zaram's user is one person who uses
more than one AI and wants their own continuity. The overlap is the substrate,
not the product — and `CLAUDE.md` already says the substrate is commodity and
the surfaces are not. A strong open-source local memory engine **commoditises
the layer Zaram was never going to win on while validating the thesis**. The
convergence is worth noting: SQLite plus `sqlite-vec`, zero external calls,
provenance back to raw evidence, share-versus-private governance. Four
architectural choices Zaram made independently, arrived at by a team at Tencent.

**Why it is not a dependency, despite MIT.** Node ≥ 22.16, distributed as three
Docker services. The actual blocker is that a stranger cannot install Zaram;
adding a container runtime to a Python backend moves that blocker backwards.
Licence was the gate everyone expects to fail and it passed — packaging is the
one that fails.

**Taken: rank fusion (RRF).** They fuse BM25 and vector results by rank position
rather than by blended score. This is the most valuable thing in the project for
this codebase, because merging a ranking blend with a selection or citation
threshold has cost it three times and the current defence is a discipline —
`relevance` selects, `score` orders, remember which. RRF is on no source's
scale, so there is no magnitude that *could* be compared against a cosine floor.
It converts a rule someone must remember into one that cannot be broken. Taken
for ordering only.

**Taken: real lexical retrieval, fused rather than averaged.** `_keyword_match`
is term overlap and its own comment records that function words score against
everything. The argument is not tidiness — it is **rule 9's documented
failure**. "Write that up as a proposal" retrieves nothing because five
referential words resemble nothing; but a client name or a reference number is
precisely what a lexical index finds and a dense embedding misses. This is the
one retrieval change with a known failure already waiting for it.

**Corrected from the first read of this project.** I described their tiered
retrieval as a membership gate and warned it would reintroduce the rank-43
defect. Reading the design, that was wrong: L2/L3 are a *fast context bootstrap*
and specific-fact queries fall back to BM25 + vector + RRF over L1 and L0. It is
two-phase, not a gate. The caution survives in a narrower form — if a bootstrap
answers and the fallback never runs, tier decided membership after all — but the
architecture as built does not make that mistake.

**Rejected: the four tiers.** L1 atom / L2 scenario / L3 persona is Zaram's
scope field with more machinery. Rule 7i already argues one field on one store
is better: facts move, recall needs both at once, and the correction loop stays
uniform. Their pyramid would buy nothing and cost that.

**Rejected: L0.** Persisting raw dialogue is rule 7d inverted, and 7d was
written from a specific failure — duplicate citations and Zaram quoting its own
replies. They keep L0 for verification; Zaram keeps provenance, which is the
same guarantee without the store.

**Deferred: symbolic short-term memory.** Compressing intermediate tool logs is
genuinely applicable — the execution engine runs multi-step plans and those logs
are the bloat this targets — and it touches **session state only**, so rule 7d
is untouched and nothing changes about what enters the Spine. Worth prototyping;
not started.

**Their numbers are a hypothesis.** 61% fewer tokens and +50% task success come
from secondary write-ups. `CLAUDE.md` says benchmark against LoCoMo /
LongMemEval, not by feel, and this codebase has already been burned by an eval
that graded itself and by a corpus whose filler answered the question. Those
figures get measured on Zaram's own harness or they do not count.

### Assignment exists — a project can be filled

`PATCH /artifacts/{id}` and `POST /memory/{record_id}/scope`, wired into the
Project and Memory surfaces. This closes **item 7** and makes **item 8**
testable: a file and a fact can now be put into a project after the fact, which
is the only way project scope was ever going to be exercised on real data.

**Assignment lives in Project, not Work.** `CLAUDE.md` splits them — Work
browses and previews, Project creates, names, types, assigns, moves and deletes
— so a project row expands to show what is in it, with a picker for what is not.
Adding a file that already belongs somewhere says **"Move here"** and names
where it currently lives, because a file has one project and a button reading
"Add" would look like a copy while quietly emptying somewhere else.

**The destination is validated, and that is the whole point.** An unchecked
write lets a typo create a project that exists only as a string on one row:
absent from `/projects`, so unnameable, undeletable, and able to collect facts
under a scope nothing points at — rule 4 broken by a spelling mistake. This is
the same ghost the `/projects` ÷ `/artifacts/projects` split was made to kill,
approached from the other end.

**`null` and `""` are different instructions** on both routes. Omitted means
*the caller said nothing* and is a 400; empty means *take it out*, and restores
the value a file is born with rather than inventing a third state.
`assignment.test.ts` asserts the client actually sends `""`, because every
ordinary instinct — dropping falsy fields, `|| undefined` — collapses the two,
and the only symptom is that **Remove silently stops working** while everything
else looks fine.

**`scope` was missing from both memory serializers.** A fact could be scoped to
a project and there was no way to see that it was: rule 7i's field existed and
was invisible from outside the backend. Now on `/memory` and `/memory/{id}`, as
one field — the surface derives the project id from it rather than being handed
a second spelling that can disagree.

**The artifacts store's mutation guard was counting instead of naming.**
`test_no_sql_deletes_or_blanket_updates` asserted `count("UPDATE ARTIFACTS")
== 1`, so a second named mutation failed it even though the class docstring
asks for exactly that ("adding a second has to be a deliberate act"). It now
asserts an allow-list of mutable columns and one column per statement. A count
says *how many* named mutations exist and not *which*, so swapping a safe one
for a dangerous one left it green — the number was never the property worth
guarding.

**A test that passed alone and failed in the suite.** The fact fixture drove
`asyncio.get_event_loop().run_until_complete`; by the time the full run reaches
it another module has closed the thread's loop and it raises rather than making
one. Now `async def` and awaited. A test that only passes in isolation gets
blamed on the suite.

**Driven in the browser, on the real Spine**: created a project, added a file
(0 → 1 file), removed it (back to 0), moved one in from another project, moved
a fact in (0 → 1 fact) and watched Work's filter follow. Everything touched was
put back — the fact to global, the file to its original id, the test project
deleted.

**Left open, and found by that restore.** Existing artifacts carry `project_id`
strings for projects that were never objects — `harbour`, `northwind`. Project
cannot see them, and validation now makes them a **one-way door**: a file can
leave such a group and can never go back, because the destination does not
exist. Restoring the file needed a direct store write. Someone with existing
work therefore opens Project to an empty screen while Work shows their files
grouped, which reads as two products. The fix is an adoption path — Project
listing artifact-only ids as "not a project yet", or a backfill at startup —
and it is a migration decision, so it was flagged rather than guessed at.

### Two Settings buttons, and a rail twice as wide as its own labels

Both reported by the maintainer from a screenshot, which is twice now that the
navigation's defects have been caught by looking rather than by reading.

**Settings was in `surfaceOrder` *and* pinned at the foot**, so the rail drew
the same destination twice, three rows apart — which reads as two different
places. The node list has now drifted three times in three distinct shapes:
CommandPalette silently **lost** Activity, the landing orbit silently **missed**
Project, and the rail silently **doubled** Settings. A
`Record<WorkspaceId, …>` catches the first, `Landing.test.ts` catches the
second, and neither catches the third — a Record proves every node has an entry
and says nothing about how many times it is rendered. `LeftRail.test.tsx` now
renders the rail and asserts each node appears exactly once.

The list is still derived, minus one named id. A derivation with a deliberate
omission is not a restatement: a seventh node still arrives on its own.

**The rail defaulted to 440px** to hold labels that need about 210 — a band of
empty rail as wide as the content beside it, on the surface `UI-SPEC.md` says
density matters most. Now 260, still draggable.

**The migration is the part that nearly shipped broken.** A persisted width
beats a constant, so lowering the default reaches nobody who has opened the app
before — the change lands and the rail stays wide, looking like an edit that did
not take. The first attempt was `from < 1`, which read correct and did nothing,
and the browser said so: still 440 after a reload. Two facts, both checked
rather than assumed:

- zustand gates migration on `typeof stored.version === 'number'`, so an entry
  with **no version key is never migrated at all** — it is loaded as-is and
  `migrate` is not called.
- every entry zustand itself wrote carries `version: 0`, because that is the
  default when the option is absent. So real users migrate, and the version-less
  case is unreachable through the normal path.

The comment in the code originally claimed the opposite, and asserting the wrong
reason for a real behaviour is how the next person inherits a false model of it.

### Every keyboard shortcut was dead on Windows, and the interface said otherwise

The same lesson again, one file over. `chordTokens` and `matches` both read
`keys.meta`, and they disagreed about what it meant. The renderer treated it as
*the platform's primary modifier* and printed **Ctrl** on Windows. The matcher
took it literally and required `event.metaKey` — the physical Windows key, which
the OS claims before the page sees it.

So the help overlay listed fourteen shortcuts, every chord correctly labelled,
and **not one of them fired**: not Ctrl K, not Ctrl 1–7, not the orb states.
Nothing threw, nothing logged, and the keycap was a claim about the system the
system did not honour — which is rule "never render invented values" in its
quietest form, because the value here was a promise rather than a number.

**`meta` now means the platform's primary chord key, and that is written down
where both halves read it.** On Windows `meta` and `ctrl` collapse onto Ctrl,
exactly as the label says; holding the Windows key is a non-match rather than a
forgiven near-miss, so Win+K does not open the palette.

`registry.test.ts` is the enforcement, and it is the shape worth copying: for
every shortcut, on both platforms, it **synthesises the exact event the rendered
chord describes and requires the matcher to accept it**. A label and a matcher
agreeing is not something a type can express. Reverting the fix fails it with
`nav.landing is shown as "Ctrl 1" and does not respond to it` — checked, not
assumed, because a test written after the fix has never seen the bug.

Driven in the browser afterwards: Ctrl K opens the palette, Ctrl 2 and Ctrl 3
land on Work and Project, `?` opens the overlay and all fourteen chords read
`Ctrl …`. The one remaining restatement, `components/palette/CommandPalette.tsx`
with its own `metaKey || ctrlKey` listener, has no importers — it is not the
palette the shell renders.

Mac glyphs are gone from the live frontend and from `UI-SPEC.md`. TopNav derives
its `Search (Ctrl K)` label from the registry instead of spelling it out.
`src/legacy/` and `figma-assets/` still contain `⌘` and were left alone: the
first is quarantined and unreachable, the second is imported design source
rather than shipped UI.

### The avatar costs ~190 MB of VRAM, not the invented 1.5 GB

`backend/tests/test_avatar_vram_budget.py` weighs `AvatarSample_Z.vrm` by
parsing the glTF container — a VRM *is* glTF 2.0, so no VRM library is needed
and none was added — and computing what the GPU actually holds:

| | |
|---|---|
| File on disk | 16.4 MB |
| Textures, 27 images, decoded RGBA8 + mipmaps | **182.5 MB** |
| Geometry, vertex and index buffers | **7.5 MB** |
| **Texture + geometry VRAM** | **189.9 MB** |

Six 2048×2048 textures at 22.4 MB each are 134 MB of the 182. **The file size is
not the footprint** and is out by a factor of twelve: textures ship compressed
and land decoded at four bytes a pixel, plus a third again for mipmaps. A test
asserts that direction so the mistake cannot be made quietly.

**Against the budget this is nothing.** `CLAUDE.md` reserves ~9.1 GB on the
12 GB card for a chat model; 190 MB is 2% of it, and the gaps between installed
model sizes are 1–3 GB. The avatar cannot change which model fits. The "~1.5 GB"
that appeared in conversation was wrong by eight times, in the direction that
would have killed the feature.

**Corroborated live, and the live instrument is the weaker one.** Toggled
orb↔avatar three times on the RTX 3060 at 1280×720 in a real browser, reading
total board memory with `nvidia-smi`: deltas of **189, 433 and 122 MiB**. Same
order of magnitude, nothing near 1.5 GB, and memory returned *below* its
starting point afterwards — so nothing leaks per cycle. But a 3.5× spread is
what total-board memory is worth on a shared desktop, which is why the asset
arithmetic is the number and this is only its check. GPU utilisation went 25% →
31% with the avatar rendering.

Two things this deliberately does **not** include: the framebuffer and depth
buffer, and three.js's own allocations. Those scale with the viewport and the
renderer rather than with the model, so they do not move when the avatar is
swapped — and a ceiling can only protect the half that moves. Also confirmed by
reading the live page: **the orb landing creates no canvas at all**
(`document.querySelectorAll('canvas').length === 0`), so the orb path genuinely
pays nothing for `three`.

The ceiling is set at 512 MB. It is a budget decision, not a measurement, and
raising it means re-checking that it still cannot change which model fits.

**`AvatarSample_Z.vrm` is a placeholder and 190 MB is its number, not the
product's.** The intent as of 10 August is to replace it with a humanoid robot
with an LED face carrying five or six textures. What carries across the swap is
the per-texture arithmetic, not the total: **22.4 MB per 2048×2048 map, 5.6 MB
per 1024×1024**. Six of the first is 134 MB and six of the second is 34 MB, so
the intended asset lands well inside the ceiling either way — and the thing to
watch is texture *dimensions*, never texture count. This is why the figure is
recomputed by a test on every run instead of written down here.

### The avatar was pixelated, and `antialias: true` was not the fix

Two settings, both wrong in the way that is hardest to see: the code already
looked like it handled the problem.

**The render buffer was 320×320.** `setPixelRatio(Math.min(dpr, 2))` capped a
high DPR — correctly — but had no floor, so on an ordinary 1× display the entire
head rendered into 320 pixels square. Now `max(dpr, 2)` capped at 2, which
supersamples to 640×640 and resolves down. The old comment priced that as
unaffordable beside a resident local model; the arithmetic disagrees — 409,600
fragments against the 2,073,600 in one 1080p frame, a fifth of a single frame of
the screen it is drawn on. Measured: GPU utilisation over the orb went from
+6pp to +5–10pp, which is to say it did not move.

**Every texture sat at anisotropy 1**, three.js's default. Six 2048² maps on a
head a couple of hundred pixels tall is ~10× minification, sampling one texel
per fragment. Now 16, with the mipmapped min filter set alongside it — raising
one without the other is a no-op that reads as a fix.

`antialias: true` was already on and confirmed live at `SAMPLES = 4`. **MSAA
smooths silhouettes and does nothing for shading or texture sampling inside a
surface**, which is where aliasing on a face lives. The setting that looks like
the answer was the setting already applied.

**The first attempt reported `textures filtered: 0`** and its unit tests passed.
`MToonMaterial` extends `ShaderMaterial` and exposes `map` and
`shadeMultiplyTexture` as *prototype accessors* over `this.uniforms`, so
`Object.values(instance)` enumerates neither — while the test fixture, a
`MeshBasicMaterial`, held its textures as own properties and agreed with the
bug. The walk now searches uniforms too, the fixture that would have caught it
is in `VrmAvatar.test.ts`, and the count is printed at load: **71 textures at
anisotropy 16**, `render buffer: 640px for a 320px box`. The diagnostic is why
this was caught in minutes rather than shipped.

This matters more after the asset swap, not less: an emissive LED dot grid
aliases harder than skin.

### The page-load 404 was the favicon nobody declared

Open since 8 August, closed 10 August. `frontend/index.html` declared no icon
link, so every browser asked for `/favicon.ico` by default — and nothing serves
it, because `public/` holds `favicon.svg`, unreferenced.

It survived two days because of where it does *not* appear: a favicon request is
in neither the console nor `performance.getEntriesByType('resource')`, so both
places anyone looks were empty while the request was real. It was found by
reading the HTML, not by watching the network. `curl` settles it —
`/favicon.ico` 404, `/favicon.svg` 200.

**Two more defects in the same file, same cause.** The title was literally
`<!-- figma:title -->` and `lang` was `<!-- figma:lang -->`: an unfinished Figma
export still rendering its own placeholders. The browser tab said
`<!-- figma:title -->`. `lang` is not cosmetic — a screen reader takes its
pronunciation from it.

All three are guarded by `frontend/src/index-html.test.ts`, mutation-checked
against the pre-fix file. This is the one file nothing else covers — not
imported, not type-checked, not rendered by any component test — and it is also
the file the next Figma export overwrites, which is why the placeholders get a
test and not just a fix.

### The avatar was silent because every audio URL 404'd

`cfaa191` shipped "the avatar speaks its replies" and it has been silent ever
since. Synthesis succeeded, the response looked correct, and `audio_url`
pointed at a file that never existed:

- `AudioCache.generate_filename()` writes `{voice}_{sha256[:16]}.wav` —
  `af_heart_05322cae55732340.wav`
- `runtimes/speech/runtime.py` built the URL from `result.audio_id`, which is
  the **request** id — `tts-f68ca98d.wav`

Two naming schemes that could never agree. `new Audio(url)` failed, `speechStore`
set `'The audio could not be played.'` — **and nothing in the UI rendered that
field**, so the only symptom was silence.

**Found by a human saying "I didn't hear it", then curling the endpoint.** No
test covered the seam: the provider tests assert a file is written, the runtime
tests assert a URL is returned, and nothing asked whether they were the same
file. That is the sixth instance of this codebase's signature failure — a
contract with two implementations where the tests exercise the one the product
does not run.

**Fixes:**

- `SynthesisResult.audio_filename` carries the real filename across the
  connector boundary — the one place that knows both sides, exactly as it
  already does for `timings`.
- `base_url` defaulted to a hardcoded `http://127.0.0.1:8420` that nothing ever
  overrode. Now `""`, making the URL **relative**: the backend port is
  configurable, an absolute URL bypasses the Vite proxy and turns audio into a
  cross-origin fetch, and a packaged build has no reason to hardcode loopback.
- `speechStore.error` is rendered in the composer beside the mic's line.
- `/voice/stream` has the identical defect, is called by nothing, and is
  **marked KNOWN WRONG in place** rather than migrated — fixing it needs the
  same field on `AudioChunk`. It must not be wired up as-is.
- `test_the_returned_audio_url_names_a_file_that_exists` is the missing seam
  test.

**Verified live:** `POST /voice/synthesize` → `200 audio/wav, 124844 bytes`.
Warm synthesis is 1.6s; the first call is ~12.7s because that is when the model
loads (lazily, since the boot-egress fix below).

### The guards had holes — all three, and one was covering a bug in itself

Asked to make the guards trustworthy before adding any parallelism, on the
grounds that every parallel worker is safe exactly to the degree the guards
catch what it cannot see.

**`check-no-remote-assets.mjs` — two defects, both found by writing its
self-test.**

1. `COMMENT_OR_DOC = /^\s*(?:\/\/|\*|\/\*|#|<!--)/` treated any line *starting
   with* `*` as a comment and skipped it. `*` is also the CSS universal
   selector, so `* { background: url('https://cdn.example/x.png') }` was
   **silently ignored** in every stylesheet and CSS-in-JS template literal.
   Confirmed by mutation: with the old heuristic restored the fixture yields
   **0 findings** where it should yield 1. That is the dangerous direction —
   missing a real request rather than flagging prose.
2. Every finding was **double-reported**, because the patterns overlap
   (`@import url(…)` matches both the `@import` rule and the generic `url()`;
   `<img src=…>` matches both markup and JSX). The "N remote asset
   reference(s)" headline was twice the truth. Now deduped on where the scheme
   sits in the file, so two URLs on one line stay two findings.

**`test_egress_chokepoint.py` — a third hole**, beyond the two already recorded
below. The staleness test only asks whether the exempted *file* exists. An
entry for a file that no longer imports a network library keeps its waiver
forever and silently covers whatever is added back. Two such entries existed;
**one of them had been granted to paper over a bug in the scanner itself** (a
relative `from .kokoro import …` read as the PyPI `kokoro`). An exemption
granted to quiet a false positive outlives the false positive.
`test_no_exemption_is_unnecessary` now fails on any entry that imports nothing.

**`check-visemes.mjs` needed nothing** — it asserts real behaviour against a
clear oracle and was already mutation-tested.

**Both scanners now self-test before scanning** — 9 fixtures each, run by
`npm run build`, each case observed failing against a deliberately broken
scanner. The general rule this session kept re-learning: **a guard whose logic
changed and was believed on inspection is a guard nobody has verified.**

### Workflow: the parallelism question, answered

Asked twice how to parallelise Zaram's development, against two detailed
multi-agent proposals (an Opus/Sonnet/Haiku tier hierarchy, then a Kilo agent
roster). Recorded because it will otherwise be re-asked.

**Parallelism is not the bottleneck, and unpaid-for parallelism makes this
codebase worse.** The signature failure is cross-boundary — six instances now.
Every defect found on 10 August was found by leaving the assigned scope: a
startup log read while serving a URL, an endpoint curled outside the task, a
test failing for a reason that needed thinking about. A reviewer handed
SPEC + PLAN + DIFF passes all three, because each diff *was* correct against
its spec. More parallel workers means more boundaries.

**So: guards first, hierarchy second.** Parallelism is affordable in proportion
to what the guards catch — which is why they were fixed before anything else.

- **Split by subsystem, not by role.** Splitting by job (explorer / tester /
  reviewer) puts every agent in the same files. Packaging, ingest, voice, and
  the frontend surfaces are independent; the queued architecture (project
  record → plan object → plan in recall) is a strict chain and does not
  parallelise at all.
- **`.kilo/worktrees/` already contains stale divergent copies** using
  `backend/garage/`, renamed at M2. That is the parallelism failure mode
  already present in this repo. Delete or refresh before adding more.
- **Start the long-lead items now.** Code signing and Nigerian sole-trader
  business verification are weeks of *waiting*, not weeks of work. They block
  nothing and nothing blocks them; every day unstarted is a day on the end.
- **Kilo is not needed yet.** Worktrees plus a merge gate cover it. Adopt it
  after two features have run SPEC → IMPLEMENT → REVIEW by hand — CLAUDE.md's
  own rule about not building the pack system before two packs exist.
- **`docs/MILESTONES.md` stays the single status file.** A second
  `CURRENT_STATE.md` is precisely the "two lists, one goes stale unread"
  failure this file already names.

### The backend contacted huggingface.co on every boot, unlogged

Found by reading a startup log while bringing the app up to test the
microphone, and it is the most serious thing in this entry. Rule 3 says every
byte that leaves is logged. This left, and was not.

**The mechanism, and it is a pattern this codebase has now hit five times: a
flag deliberately turned off, and another path doing the thing anyway.**
`KokoroConfig.load_model_eagerly` is `False`. `KokoroProvider.initialize()`
ends with `self._last_health = await self.health_check()`. And
`health_check()` called `_ensure_pipeline()` **unconditionally** — so reporting
health is how the model got loaded, KPipeline resolved through
`huggingface_hub`, and the fetch happened before any policy had been consulted.
A health check that changes what it is measuring is not a health check.

**Three guard defects let it hide**, all in `test_egress_chokepoint.py`, and
all now fixed:

1. **Dormancy was checked by grepping one file for a dotted path.** The
   bootstrapper does not name `runtimes.speech.connectors.kokoro`; it imports
   `runtimes.speech.runtime`, which does. The check asked whether the
   bootstrapper *names* a module when the question is whether it *reaches* one.
   `_reachable_from_boot()` now walks the import graph, following relative
   imports, and is deliberately over-approximate — an import inside a function
   body counts. On the first run it caught **three** false dormancy claims, not
   one.
2. **A relative import was read as a third-party package.**
   `from .kokoro import KokoroProvider` in `voice/providers/__init__.py` has
   `node.module == "kokoro"`, so the scan flagged the PyPI `kokoro` — and the
   module had been given a standing exemption to silence it. **An exemption
   granted to quiet a scanner bug is a hole that outlives the bug**, because
   nothing revisits it once the noise stops. `node.level` is now checked.
3. **Two exemptions named modules that import no network library at all.** The
   staleness test only asks whether the *file* exists, so an entry that has
   stopped being necessary looks identical to one that is load-bearing.

**The fixes.** `health_check(*, probe_model=False)` no longer loads anything by
default, and `test_health_check_does_not_load_the_model` is the guard.
`_ensure_pipeline()` now does what `voice/stt/whisper.py` does: try the cache
offline first — via `HF_HUB_OFFLINE`, since `KPipeline` has no
`local_files_only` — and ask the gate only when weights are genuinely absent.
`runtimes/internet/runtime.py` had a second ungated `DDGS` and got the
`66736fa` treatment. Both moved to `NETWORK_LIBRARY_GATED`.

`available` also changed meaning for Kokoro, deliberately: it is now "the engine
is installed and can write its output", **not** "the weights are here" —
establishing the second requires loading them. That is asymmetric with
`WhisperRecogniser.is_available()`, which does require a loaded model, and the
asymmetry is the honest one: listening decides whether to *offer a button*, so
it must know before the user presses; speaking follows a reply that has already
arrived, so resolving weights on first use costs a delay rather than a dead
control.

**Verified by restarting the server**: four HuggingFace and torch lines in the
boot log before, **zero** after.

### Speech is measured now — and dictated figures cannot be trusted

`backend/tests/test_speech_roundtrip.py`, seven tests, with two committed
fixtures under `backend/tests/fixtures/`. Kokoro speaks a sentence, it is
encoded to Opus-in-WebM — the container `MediaRecorder` produces — and Whisper
transcribes it. The listening half runs on the fixtures, so it needs
`zaram[mic]` and nothing else: **no torch, no spaCy, no 905 MB**.

Observed, live, through the real route over HTTP:

```
said:  My day rate for Harbour Lane is four hundred and twenty five thousand naira.
heard: My day rate for Harbor Lane is 425,000 Nira.
heard: My day rate for Harbor Lane is 400 and 25,000 Nira.
heard: My day rate for Harbor Lane is $400,000 and $25,000.
```

One sentence, one voice, one model, three transcripts. Two findings, and the
second is much the worse.

- **The figure is unstable.** "four hundred and twenty five thousand" parses as
  one number or two, depending on the run.
- **The currency is invented.** The audio says *naira*. The third transcript
  says **$**, twice, unhedged. A Nigerian day rate rendered as dollars is wrong
  by a factor of about fifteen hundred, in the direction that looks reasonable
  on an invoice, and nothing downstream can detect it because `$400,000` is a
  well-formed amount.

**So: speech is for prose. Amounts get typed, or get confirmed.** That is a
constraint on M9/M9a rather than a bug to fix in the recogniser, and it is
exactly what rule 9 exists for — the number leaves the building. Recorded as
`test_a_dictated_figure_is_not_guaranteed`, which asserts only that *some*
digits survive, because that is the strongest true statement available. Whether
`small` fixes the currency is worth measuring before the business layer ships.

**Where the variance lives, traced rather than assumed.** Kokoro's waveform is
not byte-identical between calls. Whisper on a *fixed* clip inside one process
is exact — three runs, one string — which is what located it. Across processes
it is not: `cpu_threads=0` lets CTranslate2 size its own pool from machine load,
and floating-point reduction order follows thread count. The test is named
`test_transcription_is_deterministic_within_one_process` for that reason; the
shorter name would assert something false while passing.

**Measured while doing it:** the mic extra is 61.7 MB of *new* wheels here
(av 27.6, ctranslate2 19.2, onnxruntime 13.8, faster-whisper 1.1) on top of what
the voice extra already brought — consistent with the 81 MB from-scratch figure.
Whisper `base` weights are **141 MB on disk**, not the 145 MB carried in from
the packaging notes; corrected everywhere.

### Zaram listens — the engine, the route, and the one moment it can leave

`voice/stt/whisper.py`, `POST /voice/transcribe`, `stores/micStore.ts`,
`components/chat/MicButton.tsx`. `zaram[mic]` pins in
`backend/requirements-mic.txt`.

**The chokepoint entry landed before the provider did**, which was the whole
point of putting it first: `faster_whisper` is in `NETWORK_LIBRARIES` because
`WhisperModel("base")` resolves through `huggingface_hub` and downloads 141 MB
without asking anyone.

**`NETWORK_LIBRARY_EXEMPT` is now two lists, and the split fixed a live
falsehood.** Every entry claimed to be justified by dormancy, and the
DuckDuckGo one had not been since `66736fa` — it is gated, not dormant, and
`test_..._not_reachable_at_boot` was therefore asking it the wrong question.
Had the bootstrapper ever imported it, a correctly-gated module would have
failed a test that could only be silenced by weakening the guard.

- `NETWORK_LIBRARY_DORMANT` — unreachable, checked against the bootstrapper.
- `NETWORK_LIBRARY_GATED` — reachable, and **asserted in the AST** to call
  `get_gate()` and to name `EgressDenied`. Prose in the reason column survives
  the deletion of the code it describes; a parametrised test does not.

**How the weights are governed, and why the order matters.** Offline first
(`local_files_only=True`), which is the ordinary case after the first run and
touches nothing. Only on absence does it ask the gate about
`huggingface.co/Systran/faster-whisper-base`, and under default deny the library
is never constructed. Asking unconditionally would log a decision about a
request that was never going to happen, and **a log full of entries for traffic
that did not occur is worth less than no log.**

**A refusal is the ordinary answer here, not an error**, so it reads like one:
the reason names the host and the size, the route returns 503 carrying it
unedited, and the composer renders it as written. Only `tiny` (75 MB) and `base`
(141 MB) have measured sizes; anything else says *"size not recorded"* rather
than inventing a number, and a test asserts that.

**Deliberate departures, both recorded so they are decisions rather than
drift:**

- **The button is press-to-start / press-to-stop, not hold-to-talk.** Holding is
  a pointer gesture: a keyboard or screen-reader user activating a button gets
  one event, not a down and an up. A control that is *both* asks the user to
  discover which gesture they performed. Same reasoning that gave the collapsed
  left-rail buttons real accessible names.
- **The transcript lands in the composer as editable text and is never sent.**
  A recogniser that mishears and then submits has spoken for the user.
- **`vad_filter` is on.** Whisper hallucinates on silence and push-to-talk audio
  is mostly silence, so this is rule 9 one surface earlier: invented words in
  the user's own input box.
- **The microphone is released on every exit path**, including the failures,
  and that is what `micStore.test.ts` spends three of its twelve tests on. The
  browser's recording indicator is the only sight the user has of Zaram
  listening, and nothing in the UI would reveal a leaked track.

**`check-no-cloud-speech.mjs` was flagging prose, and now has a self-test.** It
strips `//` comments but never tracked block comments, so a module explaining
*why* it does thirty lines of `MediaRecorder` plumbing instead of three lines of
the banned API was reported as a finding — the check disagreeing with its own
docstring, which promises that comments may discuss the API by name. Block
tracking is deliberately conservative (an opener must start the line), because
between "flag a comment" and "miss a use" only one of those errors matters.

Changing a guard and then reading it is not testing it, so the mutation cases
are checked in rather than run once in a scratchpad: `npm run check:speech` now
runs nine fixtures first, including *code after a block comment closes* and *an
unterminated block comment must not swallow the rest of the file*. Both were
observed to fail against a deliberately broken tracker. `check-visemes.mjs` was
mutation-tested before being believed; this is the same debt paid the same way.

### How the commit split actually went

Seven commits, not the six sketched here beforehand, and in a different order.
The plan put the shortcut fix first and folded invoices and formats together;
the dependency graph did not allow it.

**`artifacts/html.py` imports `.invoice` at module scope, and
`test_invoice_api.py` generates with `fmt: "html"` — an exporter that did not
exist yet.** So the exporters had to land before invoices, and invoices before
slides, because `render_deck` lives in the same module as `render_invoice`. The
real order was: formats → invoices → slides → project and memory scope → speech
→ shortcuts and rail → orbit drag → docs.

`backend/main.py` was touched by three of them, not two. It was split by
writing each intermediate state as *the final file with the later commits'
blocks removed* — never by retyping, which would produce a fourth version of
the code that can disagree with the one that was tested. Each state was
compiled and its own tests run before the commit was made.

Worth keeping for next time: **the split is a review.** Reading the tree one
commit at a time is what surfaced the `kind: "deck"` 500 — the branch and the
model that fed it were written in the same session and never read against each
other.

### Do these first

Worst first. Nothing is broken. **Restart the backend before testing anything** —
see the build-stamp note at the top; a stale process cost two rounds on
10 August.

1. **Speech now plays promptly and lip-syncs — the remaining unknowns moved.**
   The maintainer's *"I've never heard Zaram respond with speech"* was answered
   on 11 August in part: the avatar was driven in a browser, `orbState` reached
   `speaking`, 31 viseme cues were live, and the mouth was caught open
   mid-word. **What is still unconfirmed is a human hearing it through a real
   output device** — every check so far reads `audio.currentTime` advancing,
   which is not the same as sound leaving a speaker.

   Two new items from that work:
   - **Synthesis runs at roughly real time on CPU (RTF ≈ 1.0).** Chunking hides
     the first sentence's cost, but there is *no headroom*: a reply of many
     short sentences can out-run synthesis and pause mid-way. Fixing that
     properly means Kokoro on the GPU, which is the VRAM decision `CLAUDE.md`
     deliberately took. Kokoro-82M is ~0.3 GB against a ~9.1 GB chat budget —
     worth revisiting now there is a number.
   - **`/voice/stream` is still known-broken and unused.** It builds the audio
     URL from the request id; the comment in `main.py` says it must not be
     wired up in that state. The chunking fix went through `/voice/synthesize`
     instead, so this is untouched and still a trap.

   The standing list below is unchanged for the input half:

   Both directions work against
   real audio at the API level — Kokoro synthesises, the URL serves
   `200 audio/wav`, Opus-in-WebM decodes, Whisper transcribes, the weight
   download was refused and then permitted and observed. What remains untested
   is the browser at both ends: `MediaRecorder` with a live input device, and
   `<audio>` playback with a live output device. The specific unknowns:
   - whether Chromium's muxer produces something PyAV decodes. The fixtures are
     Opus-in-WebM written by `av`, not by Chromium, so the *format* is exercised
     and the *producer* is not.
   - whether `vad_filter` handles real room noise. It is proven on synthetic
     silence, which is the easy case; a fan and a street are not.
   - whether autoplay policy blocks the reply audio. `speechStore` handles it
     and now renders the reason, but it has never fired.
   - ~~speech only plays when the toggle is `avatar` and nothing says so.~~
     Closed by `67ca372`: a **Speak** button on each reply when the orb is the
     renderer. The remaining unknown is whether it works against a real output
     device.
2. ~~**Speech must not write figures.**~~ Decided and enforced, 10 August:
   **confirmed, not typed-only**. `backend/voice/stt/figures.py` flags any
   amount, currency or number in a transcript and `/voice/transcribe` returns
   it; the composer renders an amber caution naming the observed failure. It
   **never corrects** — rewriting `$` to `₦` is guessing intent from unreliable
   audio. Still open: whether Whisper `small` fixes the currency, worth
   measuring before M9/M9a.
3. **The citation UI's `web` half has never been rendered with real data.**
   Unchanged from 8 August. Built against a shape the backend can emit and has
   not, because search is default-deny. **Do not treat that path as verified.**
4. ~~**The avatar's GPU cost is unmeasured.**~~ **Measured: ~190 MB.** See
   below. What remains is not measurement but the decision it unblocks — the
   warning copy, and whether `docs/UI-SPEC.md`'s ban on 3D on the landing
   survives a number this small.
5. **`Artifact.indexed` interaction with project scope is unexamined.**
5b. **Pointer-tracking gaze was built and removed on 11 August.** Not on
   principle — because it did not visibly work, and the reason is the lesson:
   the maths had unit tests and the `.vrm` was confirmed to carry a `lookAt`
   bone rig, and **neither is evidence that an eye moved on screen.** The
   asset's fringe covers the eyes at 320px, which was noted at the time and
   then not checked. `lib/gaze.ts` and its tests are deleted; if it returns it
   returns with a screenshot showing two different eye positions.
5c. **`RECENT_CONTEXTS` in `LeftRail.tsx` is invented data** — "zaram-core
   v0.4.2", "Vector store sync", "Agent: code-review", with timestamps. It
   renders on every workspace and violates "never render invented values".
   Flagged 10 August, left alone because removing it versus wiring it to real
   data is a product decision nobody has taken.
6. ~~**One unexplained 404 on every page load.**~~ Closed, 10 August: it was
   `/favicon.ico`. See below.
7. ~~**Project exists but nothing can be moved into it yet.**~~ Closed,
   10 August. Files and facts both move, from Project and from Memory. See
   below.
7b. ~~**Projects that exist only on artifacts cannot be adopted.**~~ Closed,
   11 August. Project lists them under "not projects yet" with an **Adopt**
   action; `GET /projects/unclaimed` finds them and `POST /projects/{id}/adopt`
   claims one, keeping the id exactly. The startup-backfill alternative was
   rejected: it would invent a name and a type nobody chose, and the type is
   rule 7e's one genuine exception — it activates a pack and cannot be inferred
   from behaviour. Adoption **is** the creation moment, so it is where the
   question is asked.

   The second half matters as much and is easy to forget: **generation was
   validated too.** `PATCH /artifacts/{id}` checked its destination and
   `POST /artifacts/generate` did not, so a file could be *born* into a project
   it was then forbidden from moving into. That asymmetry is how `harbour` and
   `northwind` arrived. Adoption without it would keep refilling the list it
   had just emptied.

   Verified against the real database on this machine: both ghosts listed with
   their counts, `harbour` adopted through the UI as "Harbour Lane"/business
   with its file intact, then reverted with `DELETE /projects/harbour?contents=keep`
   so the maintainer picks the real name and type. Chat's `project_id` is still
   unvalidated and deliberately so — refusing a message because of a stale
   selection is worse than a ghost scope, now that ghost scopes are reclaimable.
8. **The whole project-scope path is still barely exercised on real data.**
   `spine.db` held **zero** `project:*` facts before this session. One fact was
   scoped, observed and moved back during verification, so the path is *proven*
   — but proven once, by hand, is not the same as exercised. Rule 7i's project
   half still has not run in anger.

### The road to alpha — asked for 11 August, one fork still open

Four steps, and the first costs no code.

**0. Code signing, starting now, in parallel.** The longest-lead item and the
only one here that *cannot be compressed later*. Windows business verification
as a Nigerian sole trader is an unknown that needs a real answer before M11
finishes, not after. Unsigned, SmartScreen warns on a product whose entire
claim is trustworthiness — the alpha's day-30 number would be measuring the
warning rather than the product. Paperwork and waiting; every day not started
is a day added to the end.

**1. M9a, obligation extraction.** The half the alpha measures. Needed under
every branch below, so it is never wasted work.

**2. The cloud engine + M10, as one commit.** This is the step that will be
argued down, and the argument is wrong. `runtimes/models/engines/` contains
**only `ollama_engine.py`** — there is no cloud chat, and "chat routed to at
least two providers (one cloud, one local)" is a failing v1 scope line.

The tempting shortcut is a local-only alpha. It fails on **recruitment**, not
on capability: every tester would need Ollama and adequate VRAM, which filters
fifteen freelancers down to the technical ones — and `CLAUDE.md` says plainly
that the target user is not technical. A day-30 number from fifteen people who
can configure Ollama measures a different market than the one being aimed at,
so six weeks buys a number nobody can act on. M10 ships in the same commit
because rule 8 gets teeth the moment a cloud engine exists.

**Decided by the maintainer, 11 August: cloud is in v1**, on exactly that
ground — "people without a graphics card and low hardware".

> **Step 2a — the engine, landed 11 August.**
> `OpenAICompatibleEngine` exists, satisfies `LLMEngine`, and is covered by
> `test_cloud_generation_invariant.py`. It has **no HTTP client**: the body is
> built and handed to `EgressGate.stream_lines`, which is new and is the gate
> growing the one shape it lacked. The first draft did own a client —
> `check` then `requests.post` — and `test_egress_chokepoint.py` rejected it on
> the first run, correctly. The remedy the scan demands was the right one.
>
> **No LiteLLM**, deviating from `CLAUDE.md`'s dependency table and recorded in
> the module rather than done quietly. `/v1/chat/completions` is already the
> lingua franca — OpenAI, OpenRouter, Groq, Together, DeepSeek, Mistral, vLLM,
> llama.cpp, LM Studio — and OpenRouter fronts Anthropic and Gemini. So the
> whole surface is one POST and an SSE parser with no new dependency, against a
> library that would enlarge the installer packaging cut by 81% *and* need an
> exemption from the chokepoint scan, since it brings its own client. Reversible:
> nothing above `LLMEngine` knows what is inside.
>
> **Step 2b — wired, 11 August.** `RoutedEngine` satisfies `LLMEngine` and
> sits where the single engine used to, so `ModelsService` and everything above
> it are unchanged. It delegates per message on the model's **declared
> locality**, read from what discovery recorded — never from the shape of the
> name. `gpt-oss` runs on Ollama, so a router matching `"gpt"` would send a
> local model's system prompt, recalled facts included, to a cloud provider.
>
> **Every unknown routes local**, and the asymmetry is the argument: guessing
> local costs a possibly-worse answer, guessing cloud costs the user's
> documents leaving on a lookup that failed. `HYBRID` counts as remote for the
> same reason — a maybe has to be treated as a yes. The gate would still refuse
> an unapproved host, but a design that leans on its last line of defence for
> ordinary behaviour has one line of defence.
>
> Configuration reuses the variables the provider layer already reads —
> `ZARAM_OPENAI_ENDPOINT` + `ZARAM_OPENAI_KEY`, or `OPENROUTER_API_KEY` — so a
> key configured once is *discovered and callable* rather than producing a
> catalogue of models that cannot be reached. No network call at construction
> (rule 7g): a key is validated by being used, at which point the gate has
> already logged and asked. **With no key, the engine is the local one
> unchanged**, so nothing about the previous behaviour depends on this path.
>
> Cloud requested with no key configured **says so** rather than answering
> quietly from a small local model — "disabled capabilities are visible, not
> silent", applied to model choice.
>
> Still missing at this layer: a **Settings surface**, so today the key comes
> from the environment; and `CLAUDE.md`'s three tiers of control
> (*Prefer local · Auto · Prefer cloud*) — there is a router, not yet a
> preference the user can express.
>
> **Step 2c — M10's dialog.** Until it exists the gate has no confirmation
> handler, and a gate with no handler *refuses*. That is the designed resting
> state and it is asserted: cloud generation is wired, tested, and declines to
> send. Shipping it half-done fails closed.

**3. M11 packaging + guided first run.** Acceptance unchanged. Three decisions
are already queued inside it — GTK for WeasyPrint, dev tooling in the base
install, and whether Jinja2 is a real transitive dependency.

**~~The gate nobody has scheduled.~~ Run 11 August, and it passes.** Recall had
only ever been evaluated on five documents; it is now measured at 10, 100 and
1,000. The margin narrows and then flattens — **+0.131, +0.108, +0.106** — with
5/5 targets recalled at rank 1 and zero false citations at every size. Full
numbers and the caveat are in Open questions.

**This does not clear the alpha, it clears one hypothesis.** The synthetic
corpus has four templates and ten client names, so it stops adding *kinds* of
document long before a real folder does — which is the most likely reason the
curve flattens. The measurement to want is the same one on real material, and
the honest place to get it is the alpha itself: `test_recall_eval.py` prints
the margin on every run, so a narrowing gap is visible before a user feels it.
**Watch that number during M12 rather than treating this as settled.**

**Paced out of the alpha, not cut — decided by the maintainer, 11 August.**
The distinction is the whole point and the wording of an earlier draft was
wrong: **none of these is dropped.** They keep their place in v1 and each has a
named re-entry point, because a thing "cut" quietly stops being anyone's
problem, and three of these are things the product has promised.

Each is *off the alpha's critical path* only, and none costs anything today,
because none is built or on by default.

- **M9c, read-only MCP for Unreal and Blender.** Not started. **Re-enters after
  M12 intake**, and the alpha itself decides how fast: if a tester's segment is
  3D rather than admin, it moves up. It is one of two v1 verticals and stays
  there — `CLAUDE.md`'s integration tests still pass for it.
- **Web search.** Already default-deny in code and needs no change:
  `planner.web_search_enabled()` reads `ZARAM_WEB_SEARCH` at call time and is
  off unless explicitly set. **Re-enters on its stated sequence, unchanged** —
  egress log, then per-source policy, then search as their first governed
  source. Both prerequisites exist, so this is nearer than its position
  suggests; the alpha simply does not need it to produce a day-30 number.
  Verified 11 August rather than assumed: the `config.json` that once declared
  `ENABLE_WEB_SEARCH: true` beside a default-deny product is deleted.
- **Image and video generation.** Post-v1 already. **Re-enters when the cloud
  engine lands**, which is step 2 — so this is paced behind a step the alpha
  may well include, not behind the alpha. The shape is settled: Zaram ships no
  weights ever, routes to a provider, logs the egress, carries project context.

**Ordering, set by the maintainer 11 August: M9a goes last**, after the cloud
engine, packaging and the recall-at-scale gate. That does not shorten the path
— the alpha cannot start without obligation extraction, since it is the half
the alpha measures — but it attacks the *stated* blocker earlier, and it means
M9a is built against a packaged product rather than a dev tree. The cost to
watch: it is the least-understood piece, and discovering a problem in it last
is the expensive way to discover one.

**~~Still open~~ — answered 11 August: the alpha waits for the cloud engine**,
and the maintainer's reason is the one that matters more than the
recommendation above: *"Zaram is local first, but v1 should come with cloud, so
people without a graphics card and low hardware"*. Local-first is not
local-only, and the constraint was never capability — it was who can run it.

**What is genuinely still open**, and neither blocks the next session:

* **Where the API key is captured.** It comes from the environment today, which
  is fine for a developer and useless for the freelancer the cloud path exists
  to serve. Settings is the obvious home; nobody has designed it.
* **The three tiers of control** — *Prefer local · Auto · Prefer cloud*. There
  is a router; there is no preference the user can express, so today the model
  chosen per message is the only lever.

### Next, in the order I would take them

Not a queue anyone has committed to — a recommendation, with the reasoning, so
the next session can disagree cheaply.

**Superseded for the alpha by "The road to alpha" above**, which the maintainer
set on 11 August: the cuts are decided and M9a goes last. The list below is
kept because the *reasoning* per item is still the best record of why each
thing is worth doing — read it for the why, and take the order from the road.

**Re-ordered 11 August**: the maintainer asked for the business layer directly
("work on the invoice and other types of document"), so item 1 is now partly
built — invoices generate, and `.docx`/`.xlsx`/`.pdf`/`.md`/`.html`/`.txt`/
`.csv`/`.pptx`/`.png` all export. **What M9 still needs is obligation
extraction**, which is the half that was never started and the half the alpha
measures. The invoice was deliberately built first so obligations have real
terms to read rather than fixtures written to make them pass.

1. **Obligation extraction — M9a, and the half M9 is still missing.** The
   invoice half landed on 11 August, and it landed as a **refusal surface**
   exactly as this item argued: `invoice.py` raises `InvoiceIncomplete` rather
   than defaulting a price, a quantity or a line, and the route returns it as a
   400 the caller can act on. That is rule 9 working where it does the most
   damage.

   What remains is the keystone: **dates and commitments pulled out of
   documents and surfaced before they lapse, each showing its source clause and
   correctable.** The due date is already derived from `terms_days` and carried
   on the record, and the terms sentence is printed on the page — so the seed
   and its evidence both exist. Acceptance is unchanged: on day 31 Zaram says
   the payment is late, shows the clause it read that from, and has the
   follow-up drafted; correcting a wrongly-extracted date moves the reminder.

   A quote template is the second pack example and is still worth building by
   hand — *build two packs by hand before building the pack system*.
2. **The preview panel with page navigation.** Asked for directly. Much cheaper
   now that documents have real pages — the HTML *is* the paginated document, so
   this renders what exists rather than reimplementing pagination. The pattern
   to copy is a scroll container of page-sized sheets, not a PDF viewer.
3. ~~**Assignment**~~ — done, 10 August. ~~Its successor is **item 7b**~~ —
   also done, 11 August. Project adopts the groups that existed only as strings
   on artifacts, and generation now validates its `project_id` so no more
   arrive. See item 7b for what was decided and what was deliberately left.
3b. **Rank fusion and lexical retrieval**, from the TencentDB review above.
   Small, and it is the only change on this list that attacks a *documented*
   failure rather than adding capability: rule 9's invented "Project Phoenix"
   is a rare-token problem, and rare tokens are what a lexical index finds and
   an embedding misses. RRF is the safe way to combine the two here, because it
   cannot be compared against a citation floor by accident — which is the
   mistake this codebase has now made three times.
4. **Packaging.** `CLAUDE.md` still calls this *the actual blocker*: "a stranger
   cannot install this… capability is not what stands between the current state
   and a 15-person retention test." Nothing this session moved it. If the next
   milestone is real users rather than more capability, this is the honest
   answer and it should jump the queue.

### Asked for, and deliberately not built

- **TencentDB Agent Memory as a dependency.** MIT, so not a licence question —
  a packaging one. Node ≥22.16 as three Docker services against a Python
  backend whose stated blocker is that a stranger cannot install it. Its ideas
  were taken; its code was not. See the review above.
- **The four-tier memory pyramid.** L1/L2/L3 is Zaram's `global` /
  `project:<id>` scope field with more machinery, and rule 7i already argues one
  field on one store is the better shape. L0 is rule 7d inverted and is refused
  outright.
- **Pointer-tracking gaze.** Built and removed the same day — see item 5b. The
  argument for it still stands; the verification did not.
- **Running the user's apps from a repo inside Zaram.** Splits in two. Rendering
  generated or simple web content in a **sandboxed frame** is v1-feasible and is
  the same technology as the document preview. Executing code from a repository
  is arbitrary execution on the user's machine — queued step 5, "tier-gated,
  post-v1", and rule 6 says tools confirm before acting. It needs a sandbox
  story before anyone touches it.
- **Folder trees inside Project.** One level of grouping, permanently. A
  hierarchy competes with scope, provenance and recall; if a tree is needed to
  find your own work then recall has failed and the tree hides that.
- **Sub-apps inside Work for editing.** See the note above — settled on licence
  and size grounds, with the narrow HTML-editing version recorded for post-v1.

### Queued — the architecture discussed, not started

In build order. Steps 1–3 are weeks and step 3 is where a to-do list becomes
Zaram.

1. **A project record.** There is none — `/artifacts/projects` derives the list
   by collecting distinct `project_id`s off artifacts, so a project is an
   emergent label rather than an object. Everything below needs one, and its
   creation is the only honest moment to choose a **type** (business, coding,
   MCP, 3D), which activates a pack.
2. **A durable plan object in the Spine**, scoped `project:<id>` — steps, state,
   decisions taken **and rejected**. A plan is an obligation you owe yourself,
   so it is M9a's object with `origin = authored` rather than a new subsystem.
   **Naming collision to settle first:** `RoutingPlan` and `PlanState` already
   exist and are ephemeral — a `RoutingPlan` decides which model answers one
   message. The durable user-facing object should be "Plan"; rename the internal
   one while it is still internal.
3. **Plan carried into recall** — the current step is context, and the Spine is
   already provider-neutral, so this works across models for free.
4. **Outcome and drift** — recorded from conversation, never from autonomy.
   Never infer a plan step and assert it: a plan that quietly decides you
   committed to something breaks the rule that a missed deadline is worse than
   no reminder.
5. **Execution** — tier-gated, post-v1. Per-project agent config should be a
   **tool-tier grant**, not a list of agents: "may things be changed in this
   project" is answerable at creation; "which agents may run" is not.

Also queued: **the consistent mind is unbuilt and will not emerge from recall.**
Consistency comes from constraining inputs and outputs — schema-constrained
generation where shape matters, one provider-neutral system prompt carrying
global-scope style facts, few-shot from outputs the user accepted. Transport is
solved by LiteLLM; behaviour is solved by nobody. Mine Letta, Aider's
`CONVENTIONS.md`, Continue.dev, Instructor/Outlines for patterns — never adopt
as architecture, and verify every licence at adoption. It needs an eval, built
as carefully as the recall eval, or it is a claim in a pitch deck.

### The local model is not the centre of truth — the Spine is

Decided 10 August 2026, in conversation, and written here because it is the
shape of the consistent mind above and the question will otherwise be re-asked
every time someone notices how much a cloud turn costs.

**The proposal.** Make a resident local model the centre of truth: it holds
context across sessions, projects and chats, recalls fast, stays consistent, and
keeps the cloud models in line — so a session uploads almost nothing and spends
almost no tokens.

**The half that is right, and it is the more important half.** Sending recalled
*facts* instead of transcripts is the whole economic argument for this product,
and it compounds per turn. `MAX_RECALL` is 6. That is the difference between
carrying a project's history into every message and carrying six sentences.

**The half that is wrong.** Truth must live in records, not in weights. Rule 2 —
every recalled fact carries provenance — is only enforceable when a fact is a
row with a source. A model *is* the hallucination the Spine exists to remove, so
promoting it to the authority reintroduces the failure and removes the ability
to detect it: an answer from weights cannot be corrected, deleted, or traced,
which takes rules 2 and 4 with it. **The model is a renderer of the Spine, never
a copy of it.**

**What the local model can be trusted with — one test: is the output checkable
against a source?**

| Job | Checkable | Verdict |
|---|---|---|
| Routing | deterministic, no generation | already built, embeddings |
| Query rewriting for recall | against what it retrieves | yes |
| Schema-constrained extraction (obligations, invoice fields) | against the source clause | yes — and it is M9a |
| Session → fact compaction | against the transcript | yes |
| Open-ended reasoning and drafting | no | route it |

A local model **supervising** a cloud model fails that test and is rejected:
it is a second thing that can hallucinate, holding no ground truth the Spine
does not already hold. Where a check is genuinely possible it should be a
lookup — does every claim trace to a source — not an inference. That is rule 2
and rule 9, which already exist, rather than a new subsystem.

**Two consequences worth designing for now.**

- **Prompt-cache order.** A recall block that varies every turn sits in front of
  the stable text and busts the provider's prefix cache, so the token saving is
  paid back as a lost cache discount. The payload wants **stable prefix first**
  (the provider-neutral system prompt, global-scope style facts, project
  constants) and **varying recall after it**. This is a constraint on the
  consistent mind's system prompt, not a separate piece of work — and it is
  measurable, so it belongs in that eval.
- **Do not put the local model on the critical path of every request.** Rule 1
  means the user brings their own model, so on a 6 GB machine that model is
  small. If every request must pass through it, Zaram's quality is gated by the
  user's GPU in a way *any model, one memory, nothing leaves without you seeing
  it* does not promise. The **Spine** is what belongs on the critical path: it
  is deterministic and needs no accelerator at all.

### Two inert features became real, and both were inert for the same reason

`apply_decay` and the citation floor were each written, tested, green, and
never actually reached the thing they were about. The pattern is worth naming
because it has now happened four times in this codebase: **a contract with two
implementations, where the tests exercise the one the product does not run.**

- `access_count` incremented on `InMemoryMemoryStore` and not on SQLite.
- `apply_decay` read `store._records` — a private dict only
  `InMemoryMemoryStore` has. On SQLite `hasattr` was simply false, the id list
  came out empty, and every pass reported a clean run over zero records. No
  error, no warning, nothing decayed, ever.
- The citation threshold was compared against the ranking blend rather than
  the similarity.
- And now: the *shortlist selection* was made on the ranking blend too.

`test_decay_runs.py` is parameterised over both stores for exactly this
reason. Never test one without the other.

### Closed on 8 August

- ~~**Nothing calls `beginModelSwap`.**~~ ✅ Now a *pre-flight* check, below.
- ~~**Nothing sets a project scope.**~~ ✅ M8 is real, below.
- ~~**Citation UI at step 3 of 5.**~~ ✅ Steps 3–5 done and driven in a browser.
- ~~**The eval's filler answered its own questions.**~~ ✅ Fixed, and guarded by
  a test that runs in the default suite.

The live thread list is in **Do these first** at the top of this file, not here.
Two lists of what to do next is how one of them goes stale unread.

### The swap is announced before it happens, not during

`ProviderManager.swap_preflight(model)` asks Ollama `/api/ps` what is
**actually resident right now** and decides before generation starts. The orb
gets a `model_load` stream event ahead of any token.

"Before" is the whole point. A spinner appearing once the machine has already
stalled is not visibility — by then the user has spent the seconds and drawn
their own conclusion about why Zaram is slow.

**Four outcomes, because the remedies differ**, and a boolean would hide that:

| kind | means | remedy |
|---|---|---|
| `resident` | already loaded | nothing said |
| `load` | fits alongside what is there | a cold start; passes on its own |
| `swap` | something resident must be evicted | recurring, it is a model assignment the user can change in Settings |
| `oversized` | bigger than the whole budget | a hardware fact no setting changes |

Plus a fifth answer that is not an outcome: **`None`, for "cannot tell"** — no
accelerator, unreadable VRAM, unreachable Ollama, unknown model. Nothing is
announced then. Announcing a swap that does not happen trains the user to
ignore the indicator, which costs more than staying quiet.

**Verified live**, with gemma3 actually loaded on the dev machine:

```
resident now: {'gemma3:latest': 2.84 GB}
  gemma3:latest       -> resident
  qwen3:latest        -> load
  qwen2.5-coder:14b   -> swap, evicts ['gemma3:latest']
```

**Two defects found only by running it against the real provider layer**, both
invisible to the unit tests:

- **Three spellings of one model name are in play** — the catalog id is
  provider-prefixed (`ollama:gemma3:latest`), `/api/ps` and the chat path use
  the provider-native name (`gemma3:latest`), and a config file may use the
  bare name (`gemma3`). Comparing ids alone matched none of them, so
  `swap_preflight` returned `None` for *every model on the machine* while the
  tests passed — the fakes happened to be keyed the same way as `/api/ps`. It
  failed the right way, silently rather than falsely, and it failed completely.
  `TestTheRealCatalogShape` now uses discovery's actual shape.
- **A model too big for the whole card was reported as a `swap` evicting
  nothing.** Not a swap — nothing displaced would make room, and an indicator
  that names nothing evicted cannot explain itself. That is what `oversized`
  is for, and it was found by a test asserting the embedder was excluded, which
  it correctly was; the empty `evicts` was the real defect underneath.

### M8 is real — project scope reaches the Spine

`ChatRequest.project_id` → `ChatRouter.route` → `ExecutionEngine.execute` →
recall scoped to `project:<id>` plus global, and capture written under it.
`ProjectScopePicker` sits under the chat input, sourced from
`/artifacts/projects`.

**Verified with real embeddings**, not just tests:

```
scope='project:harbour'  'My Harbour Lane day rate is 425,000 naira.'
scope='global'           'I prefer short emails.'
recall inside harbour -> project:harbour | ... | relevance 0.593
```

`None` and `global` are deliberately different instructions. As a *recall*
filter `None` means every scope — right when the user is not inside a project,
where `global` would hide their own project material from them. Capture
converts `None` to `global` separately.

**Found by driving it:** `/artifacts/projects` returns `[{id, count}]`, not
`[string]`. The picker assumed the simpler shape, rendered an object as a React
child, and **took the entire conversation surface down** — a blank page after
clicking the orb. The same drift that made `sampleArtifacts.ts` disagree with
the backend model, and the reason the artifacts client uses backend field names
directly rather than through a mapping layer.

### Citation UI — steps 3, 4 and 5, driven in a browser

`CitationChips.tsx` (chips + summary line) and `CitationPanel.tsx` (grouped by
egress). `frontend/scripts/drive-citations.mjs` is re-runnable.

Observed, against a live backend:

```
summary line: "4 sources · nothing left this device · 2 recalled, not cited"
chips: numbered, cyan rgb(120,220,240) — the local colour
panel:  nothing left this device
        1  My day rate for Harbour Lane is 425,000 naira.   relevance 1.00
        2  My day rate for Harbour Lane Studio is 425,000…  relevance 0.95
        3  My day rate for Ashgrove Films is 750,000 naira. relevance 0.77
        Recalled but not cited — read, and not what carried the answer
        INVOICE FROM BILL TO … · 0.50    INVOICE Services … · 0.48
Escape closes: true
empty state on "capital of France": true
```

**`MIN_CITATION_SCORE = 0.55` is visibly doing its job** — cited at 0.77–1.00,
recalled-and-not-cited at 0.47–0.50, with the gap shown rather than hidden.
That is the "cited versus *used*" problem from the last session, closed.

**A defect driving found:** the panel printed a memory's text twice — once as
the title, once as the excerpt. The guard compared them for equality, and they
are never equal because the title truncates at 120 characters and the excerpt
at 400. It reads as a bug in recall rather than in layout. Now compared on the
prefix, and skipped entirely for `memory`, whose title *is* the fact.

### Rule 7e now runs — daily, plus once shortly after boot

`runtimes/memory/maintenance.py`. `SpineMaintenance` calls `apply_decay()` and
`promotion_candidates()` on one pass, wired into the backend lifespan and
stopped cleanly on shutdown. `GET /memory/maintenance` reports what the last
pass did.

**Why that schedule, and it is not a guess.** Every threshold in `DecayConfig`
is expressed in whole days — a 90-day half life, `age_days > 30`,
`age_days > 7` — so a pass more often than daily cannot change a single
outcome. Daily is the finest interval the rules can distinguish. Daily *alone*
would not be enough, though: Zaram is a desktop app, and someone who opens it
for an hour each morning never reaches a 24-hour timer. The startup pass (60s
in, clear of the first question) is what makes it real for how the product is
actually used. Both are overridable by env for testing, and nothing in the
product sets them.

**Verified against a live server, not just tests:** booted on 8422, waited for
the pass, `GET /memory/maintenance` returned
`{"decay":{"boosted":14,"total_records":14,...}}` — fourteen real records in a
real SQLite Spine. Before the fix that pass reported zero records and did
nothing, silently.

**Promotion proposes and never promotes** (rule 6). The endpoint returns
candidates with their content and `recalled_in` evidence; promoting is a
separate call the user makes. Note that it will return **nothing** until
something sets a project scope — see "Do these first" item 2.

**One thing to watch.** Decay *boosts* `importance`, and importance carries
weight 0.20 in the ranking blend — see below. Now that decay actually runs,
frequently-accessed facts will climb the ordering over time. That is intended,
but it is a feedback loop that has never been able to operate before, and its
effect on recall quality has not been measured over any real span of time.

### The reranker question is closed — 5/5 at 1,000 documents

```
[1000 docs] recalled in top-6: 5/5 answerable targets
[1000 docs] target ranks by relevance: [1, 1, 1, 1, 1] — deepest 1, headroom 5
[1000 docs] blend-driven exclusion: none
[1000 docs] false citations: 0/18 (0%) at floor 0.42
[1000 docs] related_min 0.517 - unrelated_max 0.410 = +0.106
[1000 docs] mean recall latency: 673 ms
```

**Every answerable target is now the single most relevant document in a
thousand.** Two changes got there and neither was a purchase: selection moved
onto relevance, and the eval's corpus stopped answering its own questions.

**The margin reads lower — +0.106 against the +0.179 recorded before — and that
is not a regression.** `related_min` was 0.589 only because the document
scoring 0.517 was being excluded from the shortlist entirely and so never
entered the sample. Recalling it correctly put a real 0.517 into the population
that had been silently missing from it. The old number was flattering because
of the defect. This one is honest, and 0.42 still sits inside it with room.

**Worth watching:** +0.106 is a narrower gap than the headline used to suggest,
and `test_recall_eval.py` prints it on every run for exactly that reason. If it
narrows further as real corpora grow, *that* is when the reranker question
reopens — on evidence about scoring, which is what a cross-encoder actually
fixes, rather than on a miss count that turned out to be about something else.

### The ranking fix, and what the eval got wrong

**Instruction for this session was "fix the depth, not the ranking". The
measurement says depth was never the problem, so this is a deliberate
departure — recorded here with the numbers that forced it.** No reranker was
bought; the change is cheaper than raising depth, not more expensive.

At 1,000 documents the eval reported one miss and diagnosed it as displacement
at rank 7 — a shortlist too narrow. Widening the shortlist did not fix it, and
looking at *why* found something worse. For *"How should I write to clients?"*
the target sat at **rank 43 with relevance 0.599 — the highest similarity
anywhere in the eval** — behind 42 documents it out-scores on relevance.

The arithmetic makes that inevitable rather than unlucky:

| signal | weight | realistic range | swing |
|---|---|---|---|
| semantic | 0.35 | 0.30–0.60 | **~0.10** |
| importance | 0.20 | 0.0–1.0 | 0.20 |
| recency | 0.15 | 0.0–1.0 | 0.15 |
| access | 0.10 | 0.0–1.0 | 0.10 |
| keyword | 0.10 | 0.0–1.0 | 0.10 |
| session | 0.10 | 0 or 1 | 0.10 |

Similarity contributes a swing of about **0.10** against **0.55** for
everything else, because cosines live in a narrow band while the other factors
are normalised across their full range. **Non-relevance signals outweigh
relevance roughly four and a half to one**, so on a corpus of near-identical
invoices the blend decides almost everything.

**The fix is selection by relevance, ordering by the blend.** `rank()` now
picks the top `max_results` by similarity and *then* sorts those by the blend;
`_recall` does the same before its cut. Ordering inside the shortlist by the
blend is right and stays — a pinned, recent, frequently-used fact should be
shown first among equally relevant ones. What must not happen is a document
being *excluded* on anything but relevance.

This is the same lesson the citation floor already taught, one step earlier in
the pipeline. The floor was moved off `score` and onto `relevance` because
ordering and permission are different questions. **Membership of the shortlist
is a third question, and it belongs with relevance too.**

**Where exactly the loss happened, traced rather than assumed.** The index
already returns its top `max_results` *by cosine*, so the candidate pool was
never the problem — `_vector_search` takes `indexed[:max_results]` off a
similarity-ordered list. The pool of 25 genuinely contained the best document.
It was the **final 25 → 5 cut in `_recall`** that threw it away, because that
cut took the first five of whatever order retrieval returned, and that order is
the blend. So the fix that matters is three lines in `_recall`; the matching
change in `rank()` guards the same mistake against the keyword path, which
merges its own candidates into the pool and can displace on the blend before the
engine ever sees them.

`MAX_RECALL` 5 → **6**, and it is no longer also the citation count —
`MIN_CITATION_SCORE` decides that separately, so widening what the model can
use no longer widens what the user is asked to check.

**Two of the eval's own tests were measuring the wrong list**, which is why
this took three runs to see. They read the raw blend-ordered results and then
asserted things about the shortlist; those are different lists, and reading the
second while reasoning about the first is what made an ordering defect look
like a depth defect for a whole cycle. `_engine_shortlist()` now mirrors
`_recall` exactly and the tests assert against that.

**And a diagnostic that agreed with me was wrong.** A stability check compared
two consecutive top-10 slices, passed, and proved nothing — the instability
lives at the shortlist boundary among documents whose scores differ in the
third decimal, not in the top ten where the gaps are wide. Rewritten to track
the target's own rank across six repeats, it showed retrieval is in fact
perfectly deterministic (`[54, 54, 54, 54, 54, 54]`). The earlier
disagreement between two tests was the ordering change, not non-determinism.

### The eval was grading itself, and had been for three cycles

The last residual miss was not a product defect at all. `_filler()` drew
deliverables from a list containing **"title sequence"**, and emitted them in a
brief template carrying a duration and a date — the same shape as the expected
answer to *"How long is the title sequence?"*. Counted: **64 of 995 filler
documents answered that question exactly as well as the target did**, for
different clients, and the question names no client.

Ranking the expected document 54th out of 65 equally valid answers is *correct
retrieval*. The eval had been reporting it as a recall miss and inviting a
reranker to fix it.

`_SVC2` no longer contains "title sequence" — the filler is still the same
*shape* of document, which is what makes it a useful distractor, it simply no
longer answers the question being graded. `TestTheCorpusIsFitToMeasureWith`
enforces that, runs in the default suite, needs no Ollama, and fails with the
collision count.

**The general lesson, and it is the sharpest one here.** This file already says
a stable failure count everyone stops looking at is how a real regression hides.
This is the mirror image: *a stable failure count nobody can explain is how a
broken instrument survives.* "4 of 5 recalled" survived three measurement
cycles and nearly bought a cross-encoder, because nobody asked whether the
corpus could grade the thing it was grading. **Check the instrument before
reading the measurement.**

### Citation UI — step 2 of 5 done

`StreamEvent.source` now carries `excerpt`, `relevance`, `cited`, `number`,
`egress_id`, `bytes_sent`, `origin` and `record_id` alongside `kind`, `url`,
`title`. Keyword-only past `title`, because five optional strings in a row is
how an excerpt ends up in the url slot at one call site and nowhere else.

- **`MIN_CITATION_SCORE = 0.55`** — a second, higher cut on the same
  `relevance` field. Sits inside the observed 0.50–0.61 band from the day-rate
  reply, so the fact that carried the answer is still cited and the
  merely-adjacent ones move to the panel's quieter section.
- **Recalled-but-uncited sources are still emitted**, with `cited=False`.
  Dropping them would hide the gap between the two thresholds, and that gap is
  what makes the cut arguable rather than magic.
- **Web sources are always cited**, never thresholded. That is an egress
  disclosure, not an attribution judgement, and a relevance score is not a
  reason to stop telling someone what left their machine. `kind` is normalised
  to `web` rather than passing the provider name through — the UI colours by
  egress, and a chip saying "tavily" makes the user learn a vocabulary to
  answer the only question that matters.
- **A fact from one of the user's files is `document`, not `memory`**, and its
  title is the filename they recognise rather than a snippet of its text.
- **Citation numbers are assigned server-side, after dedupe**, at the single
  point every source event passes through. Numbering in the emitters would
  double-count a source that recall and search both surfaced, and the user
  would see a reply citing 1, 2 and 4.

### The orb has a `swapping` state

`orbStore` (visual), `systemStore` (`OrbActivity`, the model name, and the
plain-language label), rendered by `LivingOrb`, `Aura`, `Halo` and `OrbCore`.
Dimmer and slower than every other state, in desaturated slate — every other
state animates *faster* to signal effort, and a swap is the one state where
nothing is resident and no work is being done. Cyan and violet are not spent
here because they already mean "stayed" and "left" on the orb and in citation
chips.

Set it through `systemStore.beginModelSwap(model)` / `endModelSwap()`, never
`setOrbState('swapping')` — the orb and its label are two renderings of one
fact, and setting one without the other turns the orb slate-grey while the
words still read "Local only".

**Found doing it:** the per-state variant maps in `Aura`, `Halo` and `OrbCore`
were untyped object literals, so adding a state produced no build error and
framer-motion silently animated to nothing. Now `Record<OrbState, …>` — the
same remedy M6 applied to the surface list. `LivingOrb` also declared its own
four-member copy of `OrbState` instead of importing the store's; it now
re-exports it.

### What this session settled

**The frontend has been driven.** M4's UI acceptance, outstanding for four
milestones, is met — see M4 below. Four defects came out of it that no unit
test had, including the citation threshold being compared against the wrong
number for the entire life of the product.

**The reranker question is answered: don't buy one.** `docs/RERANKER.md` has
the options and costs; `test_recall_at_scale.py` has the measurement that
decided it. The margin *holds* as the corpus grows — +0.147 at 10 documents,
+0.181 at 100, +0.179 at 1,000, with zero false citations at the floor. The one
miss at 1,000 was **displaced at rank 7 with relevance 0.517**: above the floor,
outside a top-5. A depth problem, not a scoring one, so `RECALL_CANDIDATES = 25`
and cut to `MAX_RECALL` after the floor. Costs one wider read.

Also verified there: the Ollama reranker route crashes llama-server *and* evicts
bge-m3 and gemma3 with it.

**Residency is measured and CLAUDE.md is corrected**: bge-m3 0.66 GB resident,
reranker 0 GB, KV reserve 2.58 GB, budget ~9.1 GB. The old "~1.8 GB" was wrong
in both directions. **It changed no decision**, because the fit gate never read
that constant — it computes from whichever embedder discovery found. One real
imprecision recorded: the gate uses on-disk size (1.16 GB) as a proxy for
resident VRAM (0.66 GB), which over-reserves ~0.5 GB and flips nothing between
4 and 24 GB.

**M8 is done** — see below.

**The avatar spike is scoped, not built**: `docs/EMBODIMENT-SPIKE.md`. Both
questions answered against the code.

**M7 is done and driven for real.** `backend/ingest/` — parser interface, light
parsers, quality floor, loud failures. Verified against a real folder: an
invoice indexed, an image-only scan reported with its reason and the OCR
remedy, an encrypted .docx reported as password-protected, then a cited recall
naming the source document.

**Recall was broken and is now measured.** The eval harness found, on its first
run, that hybrid retrieval was ranking on stopword overlap — an unrelated
question outscored a genuinely relevant document. Fixed in three places. See
"What the recall eval found" — this is the most consequential thing in this
entry.

**Docling is now an optional extra**, decided by measuring 1,080 real files.
CLAUDE.md's dependency table is updated; the reasoning is recorded there.

**Base install: ~317 MB.** 267 MB plus a *measured* 50 MB for the exporters
(matplotlib 31, fonttools 16, openpyxl and the rest 3). Voice remains an
optional 905 MB extra. If that 50 MB has to come back, the split is charts-only
— .docx, .md and .xlsx together are 2 MB, and matplotlib is the whole cost.

**M9b and Session 4 are committed.**
`backend/artifacts/` now has the model, the write path, the HTML layer,
`export/` (Markdown, .docx, .xlsx, PNG), `records.py` (SQLite) and
`service.py`. `main.py` serves `/artifacts`. Work reads real records and
`sampleArtifacts.ts` is deleted. **PDF is the only exporter not working**, and
it is blocked on packaging rather than on code — see Open questions.

**Verified against a live server**, not just tests: three artifacts generated
over HTTP, listed, previewed and downloaded through the Vite dev proxy on the
same path the browser uses.

**Generation is reachable from chat.** "Write that up as a proposal" routes to
`document.generate`, writes a .docx grounded in the conversation, and returns
it as a card in the transcript and a row in Work. M9b's acceptance criterion
is met.

**Routing is embedding-based.** `core/retrieval/` embeds the query with bge-m3
and compares against task exemplars. Keywords remain the fallback.

**Last commits:** semantic routing + chat-reachable generation → Work reads
real artifacts → the exporters → artifacts write path → Work surface →
dependency removals → packaging split → VRAM detection.

### The citation threshold was never applied to a similarity

The biggest single defect this session, found by driving the browser and seeing
a reply cite **five** memories — including a deploy target and an unrelated
client — for a statement the user had just made.

`MemoryRankerImpl.rank()` **overwrote** `result.score` with a blend:

```
0.35 semantic + 0.20 importance + 0.15 recency
+ 0.10 access + 0.10 keyword + 0.10 session_match
```

`ExecutionEngine` then compared that to `MIN_RECALL_SCORE = 0.42`, a threshold
measured and documented as a **cosine similarity** floor. Similarity carried a
weight of 0.35, so a fact with a true cosine of 0.20 could clear the floor on
recency and session membership alone. Every reply in the product has been
citing on that number.

`MemoryResult` now carries **two** numbers, because they answer two questions:

- `relevance` — similarity as retrieval produced it. What the citation floor is
  compared against.
- `score` — the ranking blend. Ordering only.

CLAUDE.md already draws this line for tools: *"retrieval produces a shortlist;
the model chooses; a retrieval score authorises nothing."* Citation is the same
shape — rank on whatever is useful, but decide **whether to cite** on relevance
alone.

The index was also made to return a similarity rather than a blend: keyword
overlap decides *membership* of the candidate set, and `MemoryRankerImpl`
already weights it at 0.10 for ordering, so adding it to the score double-counted
it and made the number something other than the cosine the floor was measured
against.

**Measured effect: the eval margin went from +0.080 to +0.147** — related
bottoming out at 0.517, unrelated topping out at 0.369, floor 0.42 in the gap.
Those are now raw bge-m3 cosines, which means the distribution recorded in
`MIN_RECALL_SCORE`'s docstring in April describes reality for the first time.
Verified live: the unrelated deploy-target fact is no longer cited.

**Still open, and known:** a reply about a day rate still cites five memories,
now all genuinely about day rates and payment terms (0.50–0.61). That is
cited-versus-*used*, which the queued citation-UI brief already anticipates —
"local sources are cited only when they carry the answer… use a second, higher
relevance threshold than the one that decides injection". It is a separate cut
on the same number and it is not built.

### What the recall eval found — read this one

**Hybrid retrieval was ranking on stopword overlap.** Recall is the moat, it
had never been measured end to end, and the eval failed within minutes of
existing. Three bugs, in three different places, all pointing the same way:

1. **`HybridMemoryRetriever` ran keyword search *beside* vector search in
   HYBRID mode and kept whichever scored higher** (`retrieval.py`). Keyword
   scoring split on whitespace with no stopword filter, so *"What is the
   capital of France?"* overlapped a Harbour Lane project brief on `is`, `the`
   and `of` — three of six terms, a score of 0.5 — while the true cosine
   similarity was **0.226**. The max won. An unrelated document was cited with
   a number that looked like a similarity and was not.
2. **`HybridMemoryIndex` blended `0.7 * vector + 0.3 * keyword`**, which capped
   any document matching on meaning alone at 0.7 of its true score. A genuinely
   relevant note scoring **0.599** under bge-m3 arrived as **0.407** and was
   dropped by the 0.42 floor. Keyword now *boosts* into the headroom above the
   semantic score and can never dilute it.
3. **Stopwords scored at all**, in both places, with two hand-maintained
   tokenizers that disagreed — `France?` was a term and `is` was a good one.
   One shared `content_tokens()` now.

**Before: the populations were inverted** — genuinely related documents bottomed
out at 0.407 while unrelated ones reached 0.493, a margin of **−0.086**. No
threshold could separate them, so no value of `MIN_RECALL_SCORE` was correct.
**After: +0.080**, related min 0.469 against unrelated max 0.389, with 0.42
sitting in the gap. `test_recall_eval.py` prints that margin on every run, so a
narrowing one is visible before a user feels it.

**`MIN_RECALL_SCORE = 0.42` was not "chosen by feel"** — that claim was wrong.
It was measured, with the distribution recorded in its docstring and asserted by
`test_recall_relevance.py`. What was wrong is subtler and worse: it was measured
*through* the distortion above, on a two-fact Spine. It held there and collapsed
at five documents. It is now validated against real embeddings on a deliberately
confusable corpus.

**`bge-reranker-v2-m3` cannot be wired through Ollama.** Both `/api/embed` and
`/api/generate` terminate llama-server with a stack-buffer overrun
(`0xc0000409`). It is not merely unreferenced — it is unusable by this route, so
CLAUDE.md's ~1.8 GB "embeddings and reranker resident" arithmetic is fiction
until a different route exists. Decide it deliberately; do not assume the model
being pulled means it works.

### What the 27 actually were — the count was four separate bugs

The previous entry said "13 = one stale test double, 14 = voice, out of scope".
Both halves were wrong, and the second was the more misleading.

- **The stale `FakeLLM` was real but was only the top layer.** Fixing the
  signature moved the failure one level down: `test_streaming_conversation` and
  the voice integration module were written against a `ConversationManager`
  that took a `VoiceManager` and yielded `audio` events. Sprint Alpha.6
  replaced that with the event bus. **Half those tests could never have passed
  again**, whatever was done to the fake. They now test what the manager
  actually promises; the audio assertions went back to the voice stack.
- **The 14 "voice, out of scope" failures were not voice.** Five were
  `test_kokoro_provider` asserting that discovery populates `_voices`, which
  stopped happening when `voice_discovery_enabled` was deliberately defaulted
  **off** — real discovery contacts huggingface.co at startup and rule 7g
  forbids that before consent. Nine more were the ConversationManager problem
  above. "Out of scope" was the label that stopped anyone reading them.
- **Two were a live NameError.** `main.py` used `SEARCH_MARKER` without
  importing it — a real crash on the web-search path, latent only because
  search is default-deny.
- **One asserted a rule violation.** `test_alpha10c_acceptance` required
  `/chat` to trigger a search; search has since moved behind `chat_router` and
  become default-deny, so the test demanded that a question reach the internet.

The lesson is the one this file already recorded and then fell for anyway: a
stable failure count everyone stops looking at is how a real regression hides.
The specific trap was the *taxonomy* — "13 core, 14 voice" made 27 feel
understood. Nobody had run them individually.

### Still open from the last audit

**Test the seams, not just the components.** Unchanged and still true. Every
real bug found by driving the live kernel passed unit tests. `test_ingest.py`
and `test_recall_eval.py` are the first two acceptance-shaped tests; the
end-to-end recall demo still has no test that boots the real kernel.

**`--ignore` in `pyproject.toml` is rootdir-relative.** Running pytest from
`backend/` aborts the whole suite on `test_kernel.py`, which is committed
truncated mid-expression (ends at line 18, `SyntaxError: '(' was never
closed`). It is a manual smoke script from early kernel work, not a test.
Delete it or rename it `manual_*.py` — the ignore line is a workaround for a
file nobody wants.

### Decisions taken that are not yet obvious from the code

- **An externally edited file returns as a new artifact**, origin
  `user_document`, never as an update to the generated one. We cannot verify
  which claims survived a Word edit, and letting unverified text inherit
  citations is the product failing in miniature. **The UI must say this** when
  it happens — silent lossiness is the same class of problem as silent
  ingestion failure. Not yet built.
- **`Artifact.indexed` defaults to `False`**, against rule 7b's default-on. The
  deprioritisation that makes default-on safe needs origin *on facts*, which
  lands with M8. Until then, not indexing is safer than indexing unranked.
  **Flip it in the M8 commit.** This is a known, time-boxed gap.
- **Collisions increment by default** (`proposal-2.docx`); asking is the escape
  hatch when the bounded retry exhausts.
- **`Claim.source_revision` and `verified_at` exist and are unused.** Staleness
  detection is not built; the fields are there so adding it later does not mean
  migrating every artifact.
- **Claims reach Word as bookmarks, not as attributes.** `data-zaram-claim`
  does not survive export — Word discards unknown markup — so each claim is a
  real internal hyperlink to a real bookmark on its Sources entry. Clicking a
  sentence in Word jumps to the source, with Zaram not running. The
  machine-readable mapping stays on `Artifact.claims`, independently. Word
  drops a bookmark whose name has a hyphen or exceeds 40 characters *silently*,
  rendering every link as dead text, so `_bookmark_name` is asserted by test
  rather than trusted.
- **The .xlsx exporter refuses to guess.** "₦425,000" becomes the number
  425000; "50%" and "2026-07-02" stay text. 50% is 0.5 to Excel and 50 to a
  naive strip, and writing the wrong one into a cell that feeds a formula is
  the failure the module exists to prevent. Text is visibly unfinished; a wrong
  number is invisibly wrong.
- **Charts always ship their data table, and it cannot be turned off.** Three
  of the eight categorical slots fall below 3:1 contrast on white, which
  obligates relief. The table is that relief, so the picture is never the only
  copy of the numbers. A ninth series is refused rather than given an invented
  hue.
- **Unavailability is a return value, not an exception.** `export.formats()`
  lists every format with whether it runs here and why not. An `ImportError`
  surfaced as "PDF failed" tells a user nothing actionable and reads as a bug
  in Zaram rather than a missing system library.
- **Two artifact stores, on purpose.** `store.py` holds files and cannot unmake
  them; `records.py` holds records and has no general `update` and no `delete`
  — one named method for the one field the user controls
  (`set_remember_override`). The module this replaced had an `update()` that
  `setattr`'d anything passed to it. A second mutation has to be a second named
  method, which is a conversation rather than a keyword argument nobody
  reviews.
- **The file is written before the record, always.** The reverse ordering makes
  Work show a row for a document that does not exist. This ordering, on
  failure, leaves a file the user has and Work has not listed — under-claiming,
  which is visible and recoverable. Over-claiming is neither.
- **`remember_override` is three-valued.** `None` (undecided, a default may
  still apply), `True`, `False` (a refusal, which a default may not override).
- **Work shows project *ids*, not names.** There is no project-name store, and
  turning `harbour` into "Harbour Lane Studio" would be a value nobody entered.
  The sample data had names because it was invented.
- **The preview is an iframe of the stored HTML**, sandboxed with no
  permissions. HTML is the source of truth, so the preview *is* what the file
  was rendered from — not a second rendering that can disagree with it.

### Routing and generation

`core/retrieval/` is **one index with two decision rules**, built that way so
MCP tool selection lands on it rather than beside it. Routing needs a decision
(one winner, above a floor, with the margin over the runner-up as confidence);
tool selection needs a shortlist (top-k, no floor). `search()` ranks and stops;
both rules sit on top as thin functions.

For MCP, what already holds: namespaces with independent drop/re-register (a
server disconnects, its tools stop being offered), a content-hash embedding
cache (a reconnect re-registering 200 unchanged descriptions costs nothing),
and a dimension lock (cosine across two embedders is meaningless, not weaker,
so the index refuses). **What must never change: a retrieval score authorises
nothing.** A tool description is third-party text and can be written to sit
near every query; retrieval produces a shortlist, the model chooses, the risk
tier gate still runs.

**Keywords remain the fallback and should stay.** The embedder degrades to a
hash backend when Ollama is unreachable, and similarity over hash vectors is
arbitrary rather than merely worse. The router reports that and hands back.

Four bugs stood between "every piece works" and "the feature works", and all
four were only visible end to end:

1. **The reasoning step got the literal prompt.** Asked to "write that up as a
   proposal" with no framing, the model described its own operating protocol
   and that text became the file. The planner now derives a writing
   instruction; the *user's* words still reach the runtime, which reads them
   for "spreadsheet" or "invoice".
2. **Recall could not resolve "that".** Similarity against five referential
   words retrieves nothing, and the model invented a whole client — one run
   produced a confident document about a "Project Phoenix" with the real
   client's name and day rate nowhere in it. Fixed with an **ephemeral session
   buffer on the engine** (rule 7d: session state and the Spine are separate
   stores). `_remember` deliberately stores the user's words as a fact and not
   the exchange, which is right for memory and leaves nothing that can answer
   "what is 'that'".
3. **The card lacked `exists`.** The `/artifacts` listing had it and the card
   did not, so a card for a file written a second earlier said "file not found
   where it was written".
4. **The title printed two or three times**, and Markdown `**` reached the
   .docx as literal asterisks.

**Charts from chat are refused, deliberately.** A chart is a claim about
numbers and the runtime has prose; inventing figures to plot would be worse
than refusing, and quietly returning a document nobody asked for would be too.
The refusal names what is missing and offers what works. A real chart path
arrives with the business layer, where figures come from invoices.

### Providers and data policy

**OpenRouter is registered only when `OPENROUTER_API_KEY` is set**, and its
models carry `data_policy=None` — unknown — except the `:free` tier, which is
stated as `LOGGED_AND_TRAINED_ON`. Nothing it returns is
`selectable_by_default`, so Zaram never routes there on its own initiative.

This came out of an audit that proposed registering OpenRouter with
`YOUR_KEY_NO_TRAINING`. That one line would have made every model it returns
auto-selectable, **including the free tier that is free precisely because
prompts are logged** — a privacy guarantee displayed over the opposite
behaviour. `test_openrouter_policy.py` asserts the *absence* of that claim so
it cannot come back quietly.

The asymmetry worth remembering: **we can sometimes prove a model logs; we can
never prove one does not.** Free tier is stated, everything else is None.

**`backend/config.json` is deleted.** Nothing read it — not the backend, not
the frontend, not Electron. It declared `ENABLE_WEB_SEARCH: true` beside a
product whose default is deny, plus model names and a `SYSTEM_PROMPT`
instructing the model to cite web URLs. All inert, all misleading to the next
reader. Web search is gated by `ZARAM_WEB_SEARCH` in the environment, read at
call time by `planner.web_search_enabled()`.

### Open questions

- ~~**How does recall behave as the Spine grows?**~~ **Measured 11 August
  2026, at all three sizes. The floor holds and the reranker stays unbought.**

  | docs | `related_min` | `unrelated_max` | margin | recalled | false citations | latency |
  |---|---|---|---|---|---|---|
  | 10 | 0.517 | 0.386 | **+0.131** | 5/5 | 0/18 | 41 ms |
  | 100 | 0.517 | 0.409 | **+0.108** | 5/5 | 0/18 | 65 ms |
  | 1,000 | 0.517 | 0.410 | **+0.106** | 5/5 | 0/18 | 285 ms |

  The structural worry was right in its mechanism and wrong in its size.
  `related_min` does not move at all — it is a cosine between two fixed vectors
  and corpus size cannot touch it. All movement is on `unrelated_max`, exactly
  as predicted. But the curve **saturates**: 10→100 cost +0.023, 100→1,000 cost
  **+0.001**. A linear reading of the first two points predicts 0.432 at a
  thousand and a crossed floor; the real answer was 0.410. Every answerable
  target returns at **rank 1**, headroom 5 on a shortlist of 6.

  **Read this as bounded, not settled.** `_filler` draws from four templates
  and ten client names, so a thousand synthetic documents hold a few hundred
  distinct texts and no new vocabulary — which is the most likely reason
  `unrelated_max` flattens. You stop adding *kinds* of document and only add
  instances. A thousand real documents have far more variety and the maximum
  may keep climbing. This shows the floor survives **this corpus** at scale.
  It is the same "check the corpus before reading its numbers" rule that cost
  three measurement cycles, applied to its own result.

  **The margin metric was hardened in the same pass.** Both populations are now
  read at full corpus depth rather than at `SHORTLIST`. The exclusion bias was
  already diagnosed and fixed at the *selection* end — see `docs/RERANKER.md`,
  "Which number is real: +0.106, not +0.179" — but the measurement still
  depended on that fix holding: at shortlist depth, a crowded-out target stops
  contributing and the reported margin *improves*. Measured both ways at 10 and
  100: identical, because the bias is inactive. Inactive is not absent, and
  `test_every_target_contributes_to_the_margin_however_it_ranked` is the guard.
  At 1,000 the unrelated population went from 18 samples to 3,000 and
  `unrelated_max` did not move.

  **What would reopen it:** the margin narrowing on a *real* corpus, or targets
  falling below the floor rather than being ordered badly. Both are scoring
  failures and both are what a cross-encoder buys. Neither has been observed.
- ~~**Dev tooling still ships in the base install.**~~ **Split, 12 August:
  `backend/requirements-dev.txt`. 83.5 MB measured** — the "probably 30–40 MB"
  guess was under by more than half, because mypy is 42.1 MB and ruff 32.9 MB
  on their own. `wheel` was never in base. The exclusive transitive packages
  went with them; `typing_extensions` stayed, since twenty-odd runtime packages
  require it. **Not yet proven by a clean install** — see the next item.
- **A base install has never been built and run.** The split above is
  reasoned from declared dependencies and a source scan, which is good evidence
  and is not the evidence this project accepts for a dependency claim. The
  check is a fresh venv with `requirements.txt` alone that boots the backend and
  reaches a cited answer. `tabulate` is the one entry riding on the weaker
  argument: nothing declares it and nothing imports it, which is exactly the
  reading that once recommended deleting spaCy.
- ~~**Jinja2 is declared in the *voice* extra and used by nothing.**~~
  **Answered 12 August: it is a real transitive dependency and stays.** spaCy
  and torch both require it *unconditionally* — not behind an extra. No removal
  experiment was needed, because the metadata is trustworthy in this direction:
  a package **declaring** a dependency is evidence it needs one. The unreliable
  direction is the absence of a declaration, which is the misaki/spaCy trap.
- **WeasyPrint on Windows needs native GTK libraries**, which is a packaging
  decision rather than a `pip install`. This is the only part of M9b not
  working. The exporter is written and the format reports itself unavailable
  with the reason and a per-platform remedy, so the gap is visible rather than
  silent — but a Windows user cannot produce a PDF until the installer carries
  the MSYS2 GTK runtime. **Decide this in the packaging spike, not before**:
  the alternative is ReportLab, which would mean a second document pipeline
  and breaks "HTML is the source of truth". Markdown and .docx work on every
  machine, so nobody is blocked from getting a file out meanwhile.
- **Code signing** is the long-lead packaging item. Windows business
  verification as a Nigerian sole trader needs investigating now, in parallel.
  Unsigned costs Zaram more than a typical app: SmartScreen's warning appears on
  a product whose entire claim is trustworthiness.
- **`speech.tts` is reachable from the chat path** while voice is out of scope.

---

## Done

### M0 — Recall loop ✅
Spine on SQLite with `bge-m3` embeddings. Facts stored, retrieved, injected with
citation markers, provenance events emitted.

**Verified:** a fact stored in one session was recalled in a separate session
with provenance.

### M1 — Egress log ✅
Append-only hash-chained log, per-host policy, default deny, all outbound calls
through one gate. `test_egress_chokepoint.py` fails the build on any direct HTTP
call outside `core/egress/`, and on a stale exemption naming a deleted file.

### M2 — Provider layer ✅
`backend/providers/` connected, renamed from `garage/`. Model metadata carries a
data policy with no default value — unknown is `None`, never a guarantee.
`select_default_model()` refuses rather than choosing something unlabelled, and
reports *why* each candidate was refused.

**Verified:** booted against real Ollama, 10 models discovered and labelled.

### M3 — Frontend integration ✅
`chatClient.ts` does `POST /chat`, parses NDJSON, handles JSON split across
chunks and multi-byte characters split mid-character.

### M4 — Verify the integration ✅ (the UI half, finally)
**Driven in a real browser, 8 August 2026.** Outstanding for four milestones
because the Playwright browser install kept failing here. The MCP server wants a
chromium build that will not download on this connection; the package already in
`frontend/node_modules` has one, so `frontend/scripts/drive-*.mjs` uses that
with an explicit `executablePath`. Re-runnable.

**The recall demo works end to end, watched:** state a fact → ask about it →
cited answer carrying the right figure → click a citation → a panel showing the
fact, when it was stored, how often recalled, and Forget → correct it in Memory
→ the old value stays struck through as *"superseded Aug 8 · you corrected
this"* → ask again → **the answer changes to the corrected figure and no longer
mentions the old one** → Activity shows real bytes, blocked count and an
unbroken hash chain.

Four defects came out of driving it, none of which any unit test had:

1. **`access_count` was never incremented on the store the product runs.**
   Every fact read "Recalled 0×" forever. `InMemoryMemoryStore` incremented as
   a side effect of `get`; `SQLiteMemoryStore` had no equivalent — two
   implementations of one contract, drifted. Rule 7e's whole
   promotion-through-use mechanism is that integer, and `decay.py` forgets
   anything never accessed after 30 days, so the Spine looked entirely unused.
   Fixed as an explicit `record_access` on the protocol: **reading a fact is
   not recalling it**, or browsing Memory would make everything look
   load-bearing.
2. **The citation threshold was applied to the ranking blend, not to
   relevance.** See below — the largest of the four.
3. **Collapsed left-rail buttons had no accessible name.** The label renders
   only when the rail is expanded, so the navigation announced itself as five
   anonymous buttons and "Knowledge" was unreachable to anything finding
   controls by name. Now `aria-label` + `title` + `aria-current` always.
4. **A 404 on every page load.** Unidentified, one request, harmless-looking.
   Left as a thread to pull.

**Corrected on the way:** the orb does *not* vanish inside a workspace and the
return path is not broken. The route back is `OrbStatus` in the header, labelled
"Ask Zaram", `aria-label` ending "Open conversation." An earlier reading of this
session looked for the landing orb's `data-testid` and wrongly concluded there
were zero routes back.

**Not done:** stop/abort mid-reply is still unverified.

---

Earlier, at transport level against a live backend. Found and fixed two real
bugs:

- **`invoice` contains `voice`** — keyword matching was substring-based, so every
  invoice request routed to text-to-speech and returned a fallback with no model
  call. Also `essay`→`say`, `profile`→`file`, `research`→`search`. Now matched on
  word boundaries.
- **The requested model was logged and then discarded.** `/chat` accepted a
  model, the dispatcher logged it on the line above the call that did not pass
  it, and the engine always used its own default.

**Not done:** no UI walkthrough. The Playwright browser install failed on this
connection, so the interface has never been driven. Whether **stop** actually
aborts a request is still unverified.

### M5 — VRAM detection ✅
`_vram_bytes` read `torch.cuda.get_device_properties`, which does not exist in a
packaged build — so VRAM was `None` for every user and the residency fit gate
never ran, while its tests passed against pinned profiles. Now nvidia-smi, with
the Windows registry for AMD/Intel. **Never `Win32_VideoController.AdapterRAM`**:
uint32, saturates at 4 GB, reports 4294967295 for a 12 GB card.

**Verified on the dev machine:** RTX 3060, 12 GB detected, a 9 GB model refused
when a 5 GB one fits, with the reason logged.

### M6 — Shell cleanup ✅
Orbit carries five nodes: Work · Memory · Knowledge · Activity · Settings.
*(Six as of 10 August 2026 — Project was added; see the Current state block.)*
19 unreachable files moved to `legacy/`. **Bundle unchanged — byte-identical,
same content hash** — which is the proof they were never linked. The win was
repo clarity, not size.

Found on the way: the surface list was restated by hand in TopNav, LeftRail and
CommandPalette, and the palette had silently lost Activity. All three now derive
from `surfaceOrder` with `Record<WorkspaceId, …>` icon maps, so the compiler
names every file needing an entry.

### Packaging ✅ (the big one)
**1,436 MB → 267 MB base**, an 81% reduction, and the single most consequential
thing done for the alpha — the difference between an installer someone on
metered data will download and one they won't.

- Voice is an optional 905 MB extra. Voice tests skip with the install command in
  the reason rather than failing.
- `soundfile` was imported at module scope in the Kokoro provider, so the
  graceful-degradation path could never run — the module died three lines into
  its own imports. Now lazy.
- Removed `diffusers`, `openai-whisper`, `edge-tts`, `onnxruntime`, `accelerate`,
  then `scipy`, `numba`, `llvmlite`, `tiktoken`.
- **spaCy was nearly removed by mistake.** `pip show` reported no dependents
  because misaki reaches it at runtime without declaring it. Removing it broke
  speech. **Verify by removal and a green suite, never by metadata.**

### Session 1–2 — Orbit and Work ✅
Work added as the fifth node. The Work surface built against clearly-labelled
sample data: 20 artifacts, two projects, filter by project and type, detail panel
from the right with preview, sources and a link back to the conversation.
Download is inert and says why — a working button emitting a plausible invoice
from invented data is worse than no button, because the file outlives the screen
that explained it.

The landing hint ("Click Orb to Chat") replaced the persistent bar. **Two things
went with it:** the clickable topic line was the third route back and the only
one that named its destination, and the `local · model · N facts recalled` line
is no longer visible. `sessionStatusStore` still tracks all of it.

### Session 4 — Work reads real artifacts ✅
`sampleArtifacts.ts` is deleted. Work fetches from `/artifacts` through
`services/artifactsClient.ts`, with loading, error-with-retry and a truthful
empty state. The detail panel previews the stored HTML in a sandboxed iframe,
lists claims with their source excerpts, and downloads the real file.

The sample's shape had drifted from the backend model — `projectId` against
`project_id`, a nested `conversation` object against two flat fields, and a
`previewText` with nothing behind it. The model won, and the client uses its
field names directly rather than mapping, because a mapping layer is a second
vocabulary and a place for the two to disagree quietly.

**Download is real now.** It was inert and said why, because a working button
over invented data emits a file that outlives the screen explaining it. The
button now also distinguishes "no file" from "the file is not where it was
written" — the record can outlive the file, and 410 is a different problem from
404.

**Verified end to end against a live backend**, through the Vite dev proxy on
the browser's own path: generate → list → preview HTML with claim anchors →
download 37 kB of .docx with the right content type. Not driven in a browser —
Playwright is still unavailable here.

---

## The agreed path to alpha

Decided 7 August 2026, after an audit of what actually stands between here and
a 15-person retention test.

**~~Do these first~~ ✅ → ~~M7~~ ✅ → ~~M8~~ ✅ → ~~citation UI~~ ✅ →
M9/M9a → cloud engine + M10 as one unit → M11 + first run → M12.**

**The citation UI is done** — all five steps, driven in a browser. See the
Citations section of `docs/UI-SPEC.md` and "Queued — the citation UI" below for
the reasoning that produced it. Its `web` kind is built and unverified, and
becomes testable only when search lands behind its policy gate.

**Next on the path is M9/M9a — the business layer and obligation extraction.**
That is the wedge, and it is the first milestone since M7 whose acceptance is
about what a freelancer gets rather than about what the system does.

**Queued behind it: the avatar spike.** Afternoon-sized, not a milestone.
Scoped in `docs/EMBODIMENT-SPIKE.md`; both blocking questions are answered.

**Still true and still the blocker:** a stranger cannot install this. M11.

**Cut from the alpha path**, not from the product: **M9c** (Unreal/Blender is a
different wedge on a different day, orthogonal to freelancers) and **Session 5**
(CLAUDE.md: build two packs by hand before building the pack system — a
catalogue with no packs is a promise accumulating). Both stay in this file
below; neither is next.

**Local *and* cloud, decided deliberately.** An earlier proposal to make the
alpha local-only was overruled: both capabilities ship. That keeps M10 in
scope and adds one thing that is missing entirely — see below.

**Cloud is not just a provider setting. `OpenAICompatibleEngine` does not
exist.** `runtimes/models/engines/` holds `base_engine.py` and
`ollama_engine.py` and nothing else. The provider layer *discovers*
OpenAI-compatible endpoints and OpenRouter, but nothing can generate through
them, so the v1 scope line "chat routed to at least two providers (one cloud,
one local)" is **not met**. Two local models satisfies the recall demo; it does
not satisfy that line.

**M10 ships in the same commit as the cloud engine, not after it.** Rule 8 is
narrower than it looks: `test_outbound_query_invariant.py` enforces that Spine
content never reaches a *search query*, because recalled facts live in
`system_prompt` and the search path never reads it. But `system_prompt` is
exactly what a generation call sends. Today it only reaches `OllamaEngine` on
localhost, so it is not egress. **The moment a cloud engine exists,
`system_prompt` becomes egress and it contains Spine content by design.**
CLAUDE.md intends that — "carries project context into the cloud request" —
immediately followed by "showing the user exactly what leaves before it does".
So M10 is the enforcement point for the only path that sends memory
off-device, not a dialog bolted on later. Cloud generation without it is rule 5
with the safety removed. It needs a test in the same shape as the existing
invariant: recalled facts reaching a cloud engine must pass the gate *and* the
confirmation, structurally.

**Cloud lands after the wedge, not before it.** M10's dialog shows recalled
facts as removable chips, and that can only be tested honestly against a Spine
with real material in it. Built before M7 and M9, it is built against an empty
store and the interaction problems surface during the alpha.

**Start now, in parallel, because it is not coding work:** Windows code
signing and the Nigerian sole-trader business verification. Longest lead time
of anything here and it cannot be compressed later.

**Worth one afternoon, soon:** actually run the recall demo end to end and
record it — ask model A, ask model B later, get a cited answer, delete the
fact, watch the answer change, open the log. Every piece exists and it has
never been demonstrated. It is the closest-to-done, least-verified asset in the
repo, and a break in it should be found before M7 buries it under new code.

## Next

### M9b — Generative documents ✅
Reachable from chat as of this commit. See "Routing and generation" below for
the four bugs that stood between the pieces working and the feature working.

### M9b — the pieces (kept for the reasoning)
**Committed:** the artifact model, the write path, the HTML layer, and the
exporters — Markdown, .docx, .xlsx and PNG, verified end to end against real
output. 58 tests in `test_artifact_exporters.py`.

The write path is a property of the code, not a convention: `open(path, "xb")`
is create-or-fail atomically, there is no function named for deletion, and
`test_artifact_write_path.py` scans the module's source so the build fails on the
commit that introduces the capability rather than at runtime after a file is
gone. Path confinement gets eight traversal payloads — the *model* proposes
filenames, so `../../.ssh/config` is an input to assume.

**That guarantee now has a second gate.** The exporters return bytes and never
touch the filesystem; `ArtifactStore` stays the only writer. A source scan over
`artifacts/export/` enforces it, so adding a sixth format cannot quietly route
around the store. It matches *calls* rather than names, because `workbook.save`
and `write_pdf` both write to memory.

**Remaining:** PDF, blocked on GTK packaging (see Open questions), and the
**conversation half** — nothing generates from chat.

**Acceptance:** ask a question, say "write that up as a proposal", get a .docx
where claims link back to the source paragraph they came from. The file appears
as a card in the conversation and as a row in Work.

**Verified:** a proposal with recalled claims exported to .docx, both claim
hyperlinks resolving to bookmarks present in `word/document.xml`; and the same
document generated over HTTP, listed and downloaded through the dev proxy. The
document half and the Work half both hold.

**The gap, precisely.** `POST /artifacts/generate` is the seam and it works —
it is what a capability would call. What does not exist is the capability: chat
goes through `CapabilityRouter` / `IntentBasedRouter.INTENT_MAP`, and producing
a document from natural language means registering a runtime there, adding an
intent, and emitting a file-card event on the stream. Deliberately not
half-wired this session. Note also that routing is keyword-based, so
`INTENT_MAP` will match "proposal" by word rather than by meaning until
embeddings land.

### Session 5 — Settings → Tools, the pack catalogue
Each pack shows risk tier (generative / mutative / egressive), data policy, and
honest grading against this machine — greyed out where unavailable, with the
reason stated. Only packs that exist or are genuinely next; a catalogue of forty
things we will never build is a promise accumulating.

### M7 — Ingest ✅
`backend/ingest/` — a parser interface, four light parsers, a measured quality
floor, and an outcome for every file rather than only the ones that worked.

**Verified against a real folder**, not just tests: an invoice indexed and
recalled by a question about its day rate (0.492, cited by filename); an
image-only scan reported as *"2 pages produced only 1 character (0.5 per page).
It is probably a scan with a little text on top"* with the OCR remedy and its
size; an encrypted `.docx` reported as password-protected **without** falsely
offering OCR, since no parser opens those.

**Docling is an optional extra, decided by measurement.** It costs 321 MB of
wheels (torch, opencv, transformers, rapidocr, scipy) against a 267 MB base —
more than doubling the installer that the packaging milestone cut by 81%.
Probed against 1,080 real files: the light parsers read **50 of 54 PDFs**; the
four they cannot are image-only scans. `docling-slim` alone is a mirage — 40 MB
that parses nothing, because every format backend lives in the `standard` extra
that pulls torch.

`PyPDF2` was in `requirements.txt` and imported by nothing; replaced by `pypdf`
(0.4 MB), verified by removal plus a green suite rather than by metadata.

**The quality floor is measured, and the interesting half is where it *isn't*
set.** Zero characters is unambiguous — four files, all image-only scans, no
false positive possible. The band above zero is not: of twelve PDFs under 200
chars/page, those between 98 and 190 are *legitimately sparse* — a pitch deck
at 98.6, a cast sheet at 186.8. A floor at 200 looks reasonable and would tell
a user their own pitch deck was unreadable. The floor is **50 chars/page**, the
only place the two populations separate, and it **warns rather than rejects**:
sparse content is still indexed, because rejecting it would make the floor a
second, quieter way to lose a file.

**The Knowledge surface renders it, and this was verified in a browser.**
`ingest/records.py` persists sources and per-file outcomes; `/ingest` streams
one event per file as it is read; Knowledge lists folders with counts, a
per-source `local_only` policy toggle (rule 5, default deny), a Needs-attention
section carrying each reason and remedy, and a retry on every problem.

Driven end to end with Playwright against a real folder:

> **m7folder** — 3 indexed · 2 need attention · Local only
> **NEEDS ATTENTION · 2**
> `locked-exam.docx` — Couldn't read — *Password-protected or a legacy .doc
> renamed .docx.* — Retry
> `NDA WOTG Uche.pdf` — Almost nothing — *2 pages produced only 1 character
> (0.5 per page). It is probably a scan with a little text on top.* —
> *Reading scans needs OCR: pip install zaram[ingest] (321 MB, one time).* — Retry

**And it reaches the conversation.** A new `notice` stream event carries one
sentence into the transcript after the answer:

> *"2 files in m7folder didn't give me much to work with — locked-exam.docx
> among them. Password-protected or a legacy .doc renamed .docx. They're listed
> under Knowledge if you want to look."* → **Open Sources**

Once per scan, verified: it did not reappear on the next question. After the
answer, not before it — the user asked something, and interrupting with
housekeeping first is how a warning gets trained away. Rendered as a distinct
card, never as reply text: attributing it to the model would be putting words
in its mouth.

Progress is per file rather than a percentage, and it is real — `/ingest`
yields from a generator as each file completes. An earlier draft collected
every outcome and replayed them down the stream, which is a progress bar that
is always finished before it is shown.

**Failures must be loud.** A file that produced nothing appears in Knowledge
with a reason and a retry, and is mentioned in the conversation the first time
it matters. Silent ingestion failure is the most likely reason a user concludes
the product doesn't know their material and leaves.

**"Extracted almost nothing" is a failure, not a success.** A scanned PDF that
yields three garbled words will silently degrade every answer that touches it,
and it is *worse* than a hard failure because nothing signals it. The quality
floor sits beside the error path: a file that parsed cleanly but produced
almost no text lands in Knowledge with a reason and a retry, exactly like one
that could not be opened. Decide the floor from measurement (characters per
page, or extracted length against file size), not from a guessed constant, and
record how it was chosen.

**Rule 7c: no ingestion path may route documents off-device.** Managed parsing
APIs are prohibited. This is the exact trade the product refuses.

**Build the recall eval harness here** — see "Do these first" item 3. Ingest is
what puts real documents in the Spine, so it is the first moment an eval is
possible and the moment it becomes necessary.

**Acceptance:** point at a folder, watch it index, ask a question, get a cited
answer from a real document. Then point at a folder containing a scanned PDF
and watch Knowledge say which file gave nothing back and why. **Met at the
service level; the Knowledge half is not rendered yet.**

### M8 — Memory scope ✅
Every fact carries `scope` (`global` | `project:<id>`) and `origin`, migrated
together as planned — same rows, one migration over the user's data. Pre-M8
facts become `global`, the only honest reading: they were captured with no
project in play, and inventing one would be a value nobody entered.

**A leak was found doing it.** Scope filtering lived in the store's `query`,
which the vector path does not use — `_vector_search` asks the index for ids and
fetches records individually, so a semantic hit on another project's fact walked
straight past the filter and only the keyword path was ever scoped. Now enforced
at one chokepoint in `HybridMemoryRetriever.retrieve`: a privacy boundary with
one enforcement point per code path has one hole per code path.

**Promotion is evidence-based** (rule 7i). `recalled_in` keeps the project
*identities* rather than a count, because a count cannot answer "recalled across
three *different* projects". `promotion_candidates()` proposes and never
promotes — promotion changes what is shareable, and rule 6 says autonomy is
granted rather than assumed.

**`Artifact.indexed` is flipped to `True`**, and only once the thing that makes
it safe existed: `MemoryRankerImpl.GENERATED_PENALTY` demotes Zaram's own
restatements in the *ordering*, never in relevance. Pushing a generated fact
under the citation floor would be exclusion wearing a different hat; rule 7b
asks for tagging instead.

**Not built:** nothing sets a project scope yet. Every fact still lands
`global` in practice because no surface tells the engine which project is
active. The field, the filter, the migration and the promotion evidence are all
there — the caller is not. That is the next piece of M8 and it is small.

### M9 / M9a — The business layer and obligation extraction
The universal job: invoice → receipts → expenses → how is the business doing.
Then the keystone: dates and commitments pulled from documents, surfaced before
they lapse, **every obligation showing its source clause and correctable**.

**Acceptance:** generate an invoice with 30-day terms; on day 31 Zaram says the
payment is late, shows the clause it read that from, and has the follow-up
drafted. Correct a wrongly-extracted date and watch the reminder move.

### M9c — Read-only MCP: Unreal and Blender
Inspect, list, report. No writes, so no undo or sandbox needed — which is why it
ships in v1 and scoped writes do not. **Epic's plugin binds `127.0.0.1:8000`, so
the backend must stay on 8420.**

### M10 — Confirm-before-send, editable
The dialog shows the literal outbound text, the destination and the reason.
Recalled facts are removable chips, editable inline, edits written through as
supersessions.

**Done 12 August 2026, with one clause deliberately not implemented.**

Shipped: the literal text (behind a disclosure, so the primary view stays
legible for a non-technical user while the exact bytes remain checkable), the
destination, the reason, and recalled facts as removable chips. Removing a chip
rewrites the outbound body, and the gate logs and sends that rewritten text —
verified against a live backend by comparing preview, log and destination.

**Not implemented: "edits written through as supersessions."** Striking a fact
here changes *this request only*; the Spine is untouched. The two intents are
different and merging them destroys information. "Do not send my day rate to
this provider" is a statement about an outbound request; a supersession is a
statement that the fact is **wrong**, and it stops that fact being recalled
anywhere, permanently. Writing one through as the other would delete a correct
fact because it was once sensitive — and it would do so at the exact moment the
user is trying to be careful, which is the worst possible time to be surprised
by a side effect.

Correction already has a home that says what it means: the Memory surface, per
rule 4. If a user wants both, the honest shape is an offer *after* the send —
"you removed this from that request; should Zaram stop remembering it?" — which
is rule 7h's contextual offer rather than a hidden consequence of a button whose
label says something else. Not built, because nobody has asked for it yet.

### Queued — the citation UI
**Requested 7 August 2026. Not started. Order is fixed and each step stops for
review.**

Read `CLAUDE.md` and `docs/UI-SPEC.md` first. This **adds a section to the
spec, shows it, and only then implements it**.

**The core idea.** Zaram's sources come in three kinds and no competitor has to
make this distinction:

- `memory` — a fact from the Spine. Nothing left the device.
- `document` — a passage from an indexed file. Nothing left the device.
- `web` — bytes left, and there is an egress log entry for it.

The citation UI has to make that visible, because a citation that tells you
whether an answer cost you privacy is the product's thesis at the sentence
level.

**Not everything gets cited.** Web sources are *always* cited regardless of how
central the claim was — not for attribution, but because bytes left the machine
and anything involving egress is always visible. Local sources are cited only
when they carry the answer; the test is whether the claim would be different
without that source. Use a second, higher relevance threshold than the one that
decides injection — the retrieval score already exists, this is a separate cut
on the same number. Division of labour: **chips for what mattered, the recall
strip for what was used, the panel for everything.**

**Inline chips.** Small pill, kind icon and a number: document icon, memory
diamond, globe. **Colour encodes egress, not category** — the same cyan and
violet the orb uses for local versus cloud. Cyan for anything that stayed,
violet for anything that left. One meaning reused, so it needs no legend.
**Never render a chip that isn't clickable**: citing without linking fails the
verification task, and for this product a decorative citation is worse than
none.

**Summary line.** Below the reply, collapsed by default. Leads with the split —
"2 sources · 1 sent to the web" — because that is what someone wants at a
glance. Single-source answers skip the panel entirely and put the card inline;
a panel for one citation is overkill.

**The panel.** Right side, same anchor and pattern as fact detail — one
pattern, not two. Escape closes. Grouped by egress with a mono heading per
group: *nothing left this device* / *1,204 bytes left this device*. Numbering
matches the inline chips exactly so a chip maps to its card instantly.

Per kind:
- **document** — filename, the passage quoted with a left border, page and
  index date, open-document action.
- **memory** — the fact, its source and date, recall count, and correct /
  forget inline. This is the fastest correction path in the product and it sits
  exactly where the user is already checking.
- **web** — title, excerpt, domain, when it was sent and to whom, and a link to
  its row in Activity. **That link is the citation and the egress log being the
  same object viewed twice, and it is the thing nobody else can build.**

Below the cited sources, a quieter section listing what was recalled but not
cited — so nothing is hidden, it is just not interrupting the prose.

**The empty state is not optional.** When nothing from the user's material
contributed, say so: *"Answered from the model's own knowledge — nothing from
your files."* It is a claim about absence, which the user cannot infer from
missing chips — missing chips could equally mean we didn't bother. A visible
no-sources state is more trustworthy than confident prose with hidden
provenance.

**Backend first.** Check whether `StreamEvent.source` already carries kind,
excerpt and egress reference. It currently carries only `kind`, `url`, `title`
— so this is the first change. The frontend cannot render what isn't sent, and
inventing a kind client-side would be the fabrication rule all over again.

**Order — stop after each:**
1. ~~Write the spec section, stop, show it~~ ✅
2. ~~Backend: source events carry kind, excerpt, egress reference, relevance
   score~~ ✅ — plus `cited`, a server-assigned `number`, `origin`, `record_id`
   and `MIN_CITATION_SCORE`. See the Current state block.
3. ~~Chips and the summary line~~ ✅
4. ~~The panel~~ ✅
5. ~~The empty state~~ ✅

**All five done, 9 August 2026**, and driven with
`frontend/scripts/drive-citations.mjs`. The `web` kind is built and *unverified*
— nothing emits a web citation while search is default-deny. See "Do these
first" item 1.

### M11 — Packaging
**The real blocker.** A stranger cannot install this. See Open questions above —
code signing has the longest lead time and cannot be compressed later.

**Acceptance:** a Windows machine that has never seen the repo runs one installer
and reaches a cited answer from its own files in under ten minutes.

### M12 — Alpha
Ten to fifteen people, one segment. Onboard individually, watch, do not help.
Ask at intake: hours spent on admin last month, and what is past due — those
answers become the missing line in `docs/PITCH.md`.

**Acceptance:** the day-30 number. 5+ of 15 weekly → build the paid tier.
2–4 → the job is wrong. 0–1 → the thesis is wrong, learned in six weeks.

---

## Known broken

**Nothing.** 1703 passed, 9 skipped, 0 failures, ~4m05s from the repo root on a
full dev install, 12 August 2026. Frontend: 97 across 13 files.

**One flake seen once, and the cause is the trap at the top of this file.**
`test_measure_exemplar_separation` failed in a suite run that took **435s
against a normal 245s** — nearly double, which is contention, not code. It
passes alone with a wide margin (smallest social margin +0.220 against a
largest non-social +0.025) and passed two consecutive clean full runs
afterwards. It is a `measure` test against a live local model, which is the
class most sensitive to a loaded machine. Not hardened, deliberately: loosening
a measurement to survive a contended run is how a measurement stops measuring.
If it recurs on an idle machine, that is a real signal.

The 27 are gone
and the section explaining what they actually were is above, under "What the 27
actually were"; the method for classifying the next one is
`docs/KNOWN-FAILURES.md`.

The count in this section was stale by 271 tests and two months of runtime
before 11 August. Update it, or it stops being a signal — a number nobody
refreshes is how a real regression hides, which is the same lesson as the
stable-failure-count one above, wearing the opposite face.

Record any change to that number — but the sharper lesson from clearing them is
about *taxonomy*, not counting. "13 core, 14 voice" made 27 feel understood and
that is why nobody ran them individually for four milestones. A failure grouped
under a plausible label is more dangerous than an unexplained one.

**Skips are opt-in, not accidents.** `test_recall_eval.py`'s end-to-end half
needs Ollama with `bge-m3` on loopback — similarity over the hash fallback is
arbitrary rather than merely worse, so a green run against it would be a lie.
`test_recall_at_scale.py` additionally needs `ZARAM_SCALE_EVAL=1`, because
indexing a hundred documents takes ~45s and does not belong in a run-on-every-
change suite:

```
ZARAM_SCALE_EVAL=1 pytest backend/tests/test_recall_at_scale.py -s
ZARAM_SCALE_EVAL=1 ZARAM_SCALE_EVAL_SIZE=1000 pytest backend/tests/test_recall_at_scale.py -s
```

Written and inert, which is worse than broken because the suite is green:

- ~~**`apply_decay` is called by nothing.**~~ ✅ Fixed. `SpineMaintenance` runs
  it daily and once after boot, and the pass had a second defect underneath the
  scheduling one: it read `store._records` and so saw nothing at all on SQLite.
  Verified against a live server.
- ~~**Nothing sets a project scope.**~~ ✅ `ChatRequest.project_id` reaches the
  engine, recall is scoped, capture is scoped, and `ProjectScopePicker` sets it.
  Promotion now has evidence to accumulate.
- ~~**Nothing calls `beginModelSwap`.**~~ ✅ `swap_preflight` announces it before
  generation starts.

Still broken, found and not fixed:

- One unexplained 404 on every page load.

