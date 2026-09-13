# The code pack — a coding agent that is not a second product

Started 6 September 2026. Read with `CLAUDE.md` (the rules) and
`docs/MILESTONES.md` (status). This file holds the decisions, so they are not
re-argued from scratch each session.

## What it is, and what it is not

A person who uses Claude Code, Codex or Kilo Code should feel at home: point it
at a repository, ask about the code, have it find the right files itself, get
answers that name files and lines, and eventually have it make changes.

**It is a pack, not a node.** A project has a type, chosen once at creation,
and that type activates parsers, tools, output templates and routing
exemplars — which is exactly and only what a coding agent is. `CLAUDE.md`
settles the navigation question outright: *"Agents get no menu item… Agents are
actions inside the conversation"* and *"Tools never get menu items. This is
what lets capability grow without the navigation growing."*

The test for a new surface is **does it hold something real?** Walk the parts
and every one is already owned:

| what | who holds it |
|---|---|
| the repository as a retrieval scope | Knowledge — a domain |
| the codebase, its type, decisions taken and rejected | Project |
| files produced, and diffs | Work |
| what it did, and what left the machine | Activity |
| which model, which tools, which grants | Settings |

Nothing is left over, so a seventh node would hold a *view* of what the six
already own — a filter, not a surface. Claude Code and Codex are separate
because they are separate products from companies with no orb, no Memory and
no Knowledge to be part of; their separateness is an artifact of origin, not a
conclusion. Zaram's claim is one place with one memory, and a second surface
rebuilds the fragmentation the product exists to remove.

**It is also the second pack built by hand**, which is what *"build two packs
by hand before building the pack system"* asks for. Documents is the first.

## The two gates, answered

The tier table says a mutative tool needs undo, confirm and sandbox, and that
those are the work rather than the permission. For code, two of the three
already exist and are battle-tested:

* **git is the undo.** A branch per task, a commit per step, and undo is
  `git checkout`. Not a mechanism to build — a mechanism to *use*, the way
  Claude Code, Aider and Kilo all do.
* **the project folder is the sandbox.** Scoped writes to one directory tree,
  the same containment generated artifacts already have.
* **confirm** has 7j's shape already: one grant, per project folder, for file
  writes, remembered — not a dialog per call, which is a product nobody opens
  twice.

So the reason to hold the write path is no longer "the gates do not exist". It
is that reads come first and teach us how well the local model sequences tool
calls before anything can be broken.

## Slices

**1 — a repository can enter the Spine. Done, 6 September.**

A repository pointed at Knowledge indexed its README and skipped every file the
project is made of: `PlainTextParser` claims `.md`, `.json` and `.yaml`, and
nothing claimed `.py`, `.ts` or `.go`. Answers were thin and it looked like
weak recall; it was an empty index.

* `ingest/parsers/code.py` — source suffixes, and generated or minified files
  refused **out loud** with the reason, because a 2 MB bundle chunks into a
  thousand facts that then compete with real code for every retrieval slot.
* `ingest/service.chunk_code` — never splits mid-line, prefers a whole
  definition so the signature travels with the body, **no overlap** (prose
  overlaps so a straddling sentence stays findable; code overlapping would put
  the same function in two facts, which is rule 7d's duplicate-citation failure
  arriving through the chunker), and every chunk carries a 1-based line range.
* Provenance for code is therefore `readiness.py:156-181` — checkable — rather
  than "somewhere in readiness.py".
* A chunk names **every** definition it contains, not the one it opens on. A
  merged passage holding three functions captioned with only the first is
  wrong about its own contents, which is worse than being unlabelled.

`SKIP_DIRS` already pruned `venv`, `node_modules`, `.git` and `dist`, so the
walker was repository-safe before any of this.

**2 — identifiers are searchable. Done, 6 September.**

`content_tokens` lowercased *before* splitting on `\w+`, so `chunkCode` became
the single token `chunkcode` and *"where is chunk code"* could not match it —
silently, across every camelCase name in a TypeScript project. `snake_case`
failed in the mirror image.

Identifiers are now emitted whole **and** in parts, split on the original text
because lowercasing first destroys the camel boundary. This is the change
`CLAUDE.md` predicts by name: *"the rare tokens in a project… are exactly what
a lexical index is good at and a dense embedding is worst at."*

It widens candidate **membership** and the keyword term in the ranking blend.
It does not touch the similarity a citation is judged against — that stays the
vector's answer on the vector's scale, because merging those three questions is
the defect this repository has already paid for three times.

**3 — read-only tools, and the sandbox. Done, 6 September.**

`packs/code/tools.py` — `list_files`, `read_lines`, `search_code`, and no
write: not gated, not disabled, **absent**, which is the structural guarantee
the artifact write path gives by having no delete. A test scans the module for
one, because a tool list can stay honest while a module grows a private writer.

**They are an MCP server, not a new mechanism.** `CLAUDE.md` says MCP is *the*
tool protocol and no shim format may be invented, so `CodeTools` satisfies
exactly the interface `McpServer` satisfies and `McpRuntime.register_builtin`
attaches it in process. That is not ceremony: the tools inherit the policy
gate, confirm-once, the injection scan on descriptions and the log without a
line of new code, and the model reaches them the way it reaches a stranger's
server. `policy.looks_read_only` recognises all three names, so reads run
without a confirmation — which is the whole reason the inspection tier ships
first.

A built-in's config is **not** written to `mcp-servers.json`. That file is the
list of servers the *user* attached; one they could delete and that came back
would make the file disagree with the product. `_configs()` merges the two
views, user's last, so somebody who attaches their own `code` server keeps it.

**The project folder is the sandbox, enforced rather than promised.** Every
path is resolved *before* the comparison, so `../../.ssh/id_rsa`, an absolute
path and a symlink pointing out of the tree are refused by one check. The root
comes from the open project through a `ContextVar` — the precedent
`planner.py` sets for request-scoped state — and never from a tool argument,
because a root the model can name is not a sandbox. `Project.root` carries it,
with a `PRAGMA table_info` migration, because `CREATE TABLE IF NOT EXISTS` is
silent about a table that exists and differs.

Every read is capped: 400 lines, 60 matches, 500 files, each saying so when it
truncates. A model told nothing concludes the file ends where the read did.

**3b — the loop, and Continue. Done, 6 September.**

`MAX_TOOL_ROUNDS` was **1**, so the model could `search_code` *or* `read_lines`
and never *search then read what it found* — the minimum useful sequence, and
the binding limit on everything above.

* **Bounded by the window, not by rounds.** `ContextBudget.tool_output_tokens`
  is `TOOL_OUTPUT_SHARE` (0.4) of the input budget, read from the context the
  model was **actually loaded with** via `/api/ps`. An 8K model and a 64K model
  then degrade differently rather than behaving identically under one counter.
  The share sits below `DOCUMENT_SHARE` deliberately: a file the user attached
  was chosen by a person, one the model asked for was chosen by a guess.
* **The trade is written down.** Tool output competes for the same window as
  recalled facts, and three 400-line reads would evict the memory that makes an
  answer Zaram's. That is a decision in `TOOL_OUTPUT_SHARE`, not a consequence.
* **Two backstops a token budget cannot provide.** A verbatim repeat stops the
  loop — its result is already in the prompt — and `MAX_TOOL_ROUNDS` (now 6)
  catches the model that varies a query that returns nothing each time.
  `{"matches": []}` costs five tokens and would never fill a budget.
* **A permission stops it; a failure does not.** A refusal or a pending
  confirmation ends the loop, because looping past one lets the model shop for
  a tool that happens to be permitted. A call that *ran and failed* is handed
  back as its own result — that is the commonest recoverable error and the
  whole reason there is a second round.
* **The gate runs per call**, unchanged: `McpRuntime.execute` calls
  `policy.decide` itself, so more rounds is more decisions and never one reused.
* **At half the window the task hands itself over, silently.** It compacts —
  the steps travel, trimmed to `CARRY_SHARE` (0.25) so the next window has room
  to work — and carries on, `MAX_AUTO_CONTINUATIONS` (3) times. The trigger is
  the **measured size of the request being sent**, `HANDOFF_SHARE` (0.5) of the
  model's loaded context, not a count of rounds or bytes read: that is the
  number the model has to fit and a provider charges for, and everything else
  is a proxy for it.
* **Nothing is announced, and that is the point.** The maintainer's decision on
  6 September: *"I don't want Zaram to keep prompting users… optimise the
  context, do the handoff behind the scenes, so the UI stays fluid and
  seamless."* A task that carried on and finished has not failed; four
  bookkeeping notices in one reply is noise rather than disclosure. A task that
  runs out of windows **does** say so, with an offer to pick it up, because that
  one is the silent-degradation case.
* **The handoff is the cost control.** An earlier version gave a cloud model no
  automatic continuations at all, reasoning that rule 1 makes those tokens the
  user's money. Rejected, and the test that asserted it is kept as the test that
  asserts the opposite: a request that never exceeds half a window is smaller
  than one that fills it, so compacting is cheaper *and* seamless, while asking
  charges the user attention to save them nothing.
* **It is not a loosening of permission**: every call still goes through
  `policy.decide`, so carrying on buys more decisions, not fewer.

**3c — the plan object, so a task outlives the process. Done, 6 September.**

`projects/plans.py`, which `projects/records.py` had already predicted:
*"everything a project appears to contain (artifacts, facts, later a plan) lives
in its own store and points back here by id"*. A task that runs out of windows
is written down, and Project lists what is waiting with a Continue on each.
This is the half of *"no handoffs"* a person can see: the button under a reply
dies with the reply, and a row in Project does not.

Four properties, and three of them are rules:

* **It holds what the tools returned, never what was said.** Rule 7d, and the
  patterns section rejecting L0 by name. A step is a call and its result.
* **It holds no system prompt, deliberately — and that is rule 4.** The obvious
  design stores the context so a resume is identical, which would freeze a copy
  of whatever recall found at the time, and a fact the user corrected on
  Wednesday would come back to life on Thursday inside a task they had
  forgotten about. So a resumed task **re-recalls** from the question and
  re-lists the tools: rebuilt, not replayed, and not byte-identical on purpose.
* **A row exists only while a task is unfinished.** Finishing deletes it — the
  answer is in the conversation and the steps have done their job — so the
  store stays small by construction rather than by a sweep.
* **Seven days, then it is gone.** Long enough for *"stop on Tuesday, carry on
  Thursday"*; short enough that tool results, which hold file contents, are not
  a liability sitting on disk. Pruned on open and on every write, and the user
  can discard one from Project. *"No new store ships without an answer to how
  long it keeps things and how the user shortens that."*

Continuing still evicts whole steps, oldest first, when they no longer fit —
the call `transcript.py` already makes, for the same reason: evicting is
deterministic and summarising is a generation.

**What is still not built** is the other half of what `CLAUDE.md` asks of the
plan: *decisions taken and decisions rejected*, and a plan the user reads
**before** it runs. This is the steps and the resumability. The object now
exists to hang the rest on.

**A UX cost taken deliberately, with a named way back.** Every generation in a
tool-using reply is now buffered, so those replies arrive whole instead of
typing out. The first one always was — a marker arrives split across tokens —
and the terminal one joined it on measured evidence: told plainly not to call
another tool, `qwen3-14b` emitted `[TOOL_CALL]` anyway. Streaming can return
behind a holdback filter that withholds any trailing text which could be a
marker prefix; that belongs in `tool_loop.py` with its own tests, and it is
worth doing when tool replies are common enough for the lost typewriter effect
to be felt.

**Measured, 6 September — the first time a model has driven any of this.**
`qwen3-14b-16k`, loaded with 16,384 tokens (measured, not assumed):
`search_code` → `read_lines` → the right value, from the right file and line.
`backend/tests/test_the_model_can_drive_the_tools.py -m measure`.

Two defects that only a model could have found, both now fixed:

* **The schema never reached the prompt.** `tool_instructions` listed a name and
  a description, and `mcp.list_tools` carried `input_schema` all the way to the
  point where it was dropped. So the model invented `start`/`end` for
  `read_lines` and `text` for `search_code`. With the schema in front of it, on
  the same question, it used `start_line`, `end_line` and `query`.
* **A wrong argument name succeeded.** `read_lines` ignored `start` and read
  from line 1; `search_code` with `text` searched for nothing and said "no query
  was given". Both are rule 9's shape in a tool — a plausible answer to a
  question nobody asked. An argument no schema declares is now refused by name,
  which is what lets the next round fix it.

**3d — a user can actually point it at a repository. Done, 7 September.**

Everything above was reachable by a test and by nobody else. `Project.root`
shipped with its migration, its `ContextVar` and a sandbox check that resolves
every path before comparing — and **no route could set it**:
`ProjectCreateRequest` had no such field and neither did the update, so a
repository could only be attached by calling `ProjectRecords` from Python. The
handoff written the day before said "reachable through the API only"; reading
the request model rather than the note is what found otherwise. This
repository's own failure shape, arriving through a missing form field instead of
a missing caller.

* `root` on create and on `PATCH /projects/{id}`; `""` withdraws it, which is a
  real operation and not a no-op.
* **Checked at the boundary, not in the store.** Whether a folder exists is a
  question about this machine right now — a drive gets unmounted — and
  `active_root` already asks it every request and answers `None`, which is the
  safety property. `_checked_root` in `main.py` normalises to an absolute path
  and refuses one that is not a folder *with the sentence*, because a typo would
  otherwise turn every later call into "outside the project folder": a true
  sentence about the wrong problem, sending the user to look at permissions.
* In Project: the folder field appears at creation when the type is `coding` —
  the moment the type is chosen is the moment the question is obvious — and on
  every coding project's row, since every one created before today has none. A
  project without a folder says so in amber, because in that state every tool
  call refuses.
* A native directory picker in the desktop app, a typed path everywhere else.
  The shape Knowledge already uses for folder ingest, for the same reason: a
  browser tab cannot learn a folder's real path.

**3e — the model's working is visible. Done, 7 September.**

`StreamEvent.tool_call` carried the server, the tool and the gate's verdict for
every call from the day the loop shipped, and `chatClient.parseEvent` dropped it
in its `default:` case. No frontend file mentioned `tool_call`. A reply that
searched a repository and read two files looked exactly like one answered from
memory — *"show routing decisions in plain language"* inverted, and the
difference between a claim and a checkable one.

`ToolCalls.tsx` renders one line per call, under the answer and above the
notices. Arguments and results are deliberately absent: a `read_lines` range is
a wall of numbers, and the result is file contents, which belong in the model's
context rather than on the screen. It is also what the surface shows *while* a
tool-using reply is in flight — that generation is buffered, so without it
nothing at all appears for the seconds the model spends reading.

`check:reachability` could not have caught this: it reports backend **routes**
no frontend file mentions, and has nothing to say about backend **events**
nobody parses. Two tests in `chatClient.test.ts` are the instrument for that
class.

## Slices 4–6 — the loop closes

Rewritten 12 September 2026. The three "next" items this section used to hold
— *the repository is offered as a project*, *diffs as cards*, *scoped writes* —
were three unrelated sizes of work numbered as if they were a sequence, and the
one that unblocks everything was listed last. They are folded in below, not
dropped: the offer becomes part of slice 4's discoverability, the diff card is
slice 4's review surface, and scoped writes *is* slice 4.

**The frame.** What builds Zaram is one loop run a few hundred times —
**read → edit → run → read the failure → edit → test → commit** — with a plan
carried across windows and a person approving the risky steps. Mapped onto
what exists:

| loop part | Zaram, 12 September |
|---|---|
| read the repository | **live** — `list_files`, `read_lines`, `search_code`, sandboxed |
| edit a file | **slice 4** — this session |
| run something | **slice 5** — nothing reaches a shell |
| read what it printed, fix, repeat | **slice 6** — the loop's second half |
| approve a risky step | **half-built** — `policy.decide` returns `CONFIRM`, the engine stops, and no button or grant exists for a server Zaram ships |
| carry work across windows | **live** — hand-off at half the window, `PlanRecords` for seven days |
| remember what was decided | **live** — the Spine, scoped `project:<id>`, with provenance |
| commit | slice 4 — one commit per write |

Nothing new is needed for *"build an app"*. It is this list, in this order,
and the order is forced by the tier table: each slice needs something the one
before it did not.

**Where the ceiling is, said before anyone builds a habit on it.** `CLAUDE.md`
records five jobs a local model does well, two adequately, and hard reasoning
as not bridgeable locally. Building an app is mostly the seven, with the eighth
showing up at the moments that matter — a design decision, a bug that is not
where the error is. So the local 27B will do **bounded** tasks well: scaffold
from a spec, add a feature to a small codebase, fix a failing test, write the
tests for a module — tens of tool calls, one window or two. It will do
multi-hour autonomous builds badly, and the failure is rule 9's: confident,
plausible, wrong, at step 40 of 60, with the earlier steps built on it. With a
cloud key it approximates Claude Code, rule 1 as written, and the product's
claim stops being *the agent* and becomes *the agent whose memory outlives the
provider and whose egress you can audit.* Difficulty is routed by reaction, not
prediction — the local model runs, and when it stalls or fails the test twice,
Zaram offers the cloud model for *that step*, with what would leave stated
before it goes. Never a "use cloud for coding" switch.

**Multiple apps is Projects plus residency, and residency is the honest
limit.** One Project per app: its own root as the sandbox, its own facts, its
own plan rows. On a 12 GB card one model is resident, so five projects on the
local model run *sequentially* — the loop is fast between calls, so it feels
concurrent, and it is not, and the card should say so rather than pretend.
Five projects on a cloud key run in parallel, egress-logged per project. That
per-project log is the thing no other agent manager has, and it exists because
rule 3 was built first.

### 4 — a file can change. Built 12 September.

The mutative tier needs undo, confirm and sandbox, and for code all three are
things to *use* rather than build.

**The write lives in its own module, and the read module still contains no
write.** `packs/code/writes.py` holds `write_file` and `edit_file`;
`tools.py` is unchanged in what it can do and its no-write scan still passes,
because the writer is *injected* — a `CodeTools` built without one has no
write tool, not a disabled one. This is the artifact-trash pattern from
`CLAUDE.md`: generation's own path stays unable to destroy, and the capability
that can change things is a separate module reached only through a grant a
person made.

**Two tools, not one.** `write_file(path, content)` creates or replaces a whole
file, which is how a new file is born and how a small one is rewritten.
`edit_file(path, find, replace)` replaces one exact occurrence of `find` — it
refuses if the text is absent, and refuses if it appears more than once, naming
the count, because "replace the first" silently edits the wrong one. This is
the search/replace shape every coding agent converged on, and `docs/AIDER.md`
measured it producing well-formed edits on the 27B with no retries. Line-range
editing was considered and not built: a model's line numbers drift the moment
its first edit lands, and the second edit then goes to the wrong place with
confidence.

**Git is the undo, and a write that cannot be undone does not happen.** Every
write is one commit, on the branch the folder is on, with the file's path and
the model's optional `summary` in the message, and the result carries the sha
and the sentence that reverses it. Three checks run *before* the file is
touched, in the safe direction each time:

* **The user's own uncommitted changes to that file refuse the write.**
  Committing after would sweep their half-finished edit into Zaram's commit
  and make the undo theirs to lose. The refusal says to commit or stash first.
* **No git, or no identity, refuses.** `git var GIT_COMMITTER_IDENT` fails
  when nobody has told git who they are; a write that lands and then cannot be
  committed is a write with no undo, so the check runs first.
* **A folder that is not a repository becomes one.** `git init` creates a
  `.git` directory and destroys nothing, and a new app starts as an empty
  folder — refusing here would make "build me an app" dead on arrival. The
  result says it happened.

**A branch per task is deferred, and this is a disagreement with the earlier
line recorded rather than hidden.** Moving somebody's checkout onto
`zaram/<task>` without asking changes where their *own* next commit lands, and
an editor open on `main` that is quietly on another branch reads as broken.
The unit is right — a branch is undo, audit and review in one — but it needs a
*task* with a start and an end, and the only object that has one is the plan
record. When a task begins as a plan, it can begin on a branch; until then a
commit per write on the current branch is the honest version. Re-entry point:
`PlanRecords` gaining a `branch` field.

**The grant is per project folder, not per server.** `WriteMode` lives on a
`ServerConfig` and `granted_tools` in `mcp-servers.json`, and the `code`
server appears in neither — it is a built-in, and `ServerStore.grant` returns
silently for a server it does not hold. So the confirm-once flow that exists
for a stranger's server was **unreachable for Zaram's own**. Rule 7j's unit is
*destination and data class*, and for file edits the destination is the folder:
`Project.writes` is one column, set from Project beside the repository field,
carried into the request by the same `ContextVar` as the root, and read by the
runtime as the built-in's grant. The `code` server is registered `HOST_UNDO`,
because git is the undo and the maintainer is the person who declared it.
Ungranted, a write is `CONFIRM` and the engine stops with the sentence that
says where to allow it; granted, it runs, and every call still goes through
`policy.decide`.

**What a person sees.** The Project row for a coding project gains one control
under the folder: *Zaram may edit files here — each change is a git commit you
can revert.* Off by default. The tool line under a reply shows `write_file`
with its verdict, the path and the commit. Diffs as a card — the review surface
the six nodes do not render — is still owed and belongs here, not in a slice
of its own; it is a card in the conversation, never an editor.

**The routing gap from 3d is closed — same day.** *"Add a dark mode
toggle"* classified as conversation and *"search the code for X"* as
`filesystem.search`, so nothing reached the tools unless the person named
them. **The project decides that the tools are offered, not the phrasing**:
`IntentPlanner.set_code_project_open` is injected at boot with
`active_root() is not None`, and with a coding project open a code, filesystem
or conversation intent plans `mcp.list_tools → reasoning.generate`. Image,
vision, speech, document and search keep their own plans — a request to draw
is not about the code because a repository is open — and an attached image
still answers with the image. `tests/test_a_coding_project_offers_its_tools.py`.

**The repository map — taken from Aider, same day.** `packs/code/repo_map.py`:
every source file and the definitions in it, ranked by lexical overlap with
the question (camelCase and snake_case split, the slice-2 lesson), trimmed to
`MAP_TOKENS` (1,200) by dropping whole files and *saying how many*, cached
per root for 30 s and forgotten on every write. No tree-sitter, no PageRank:
`_DEFINITIONS` from the chunker finds the symbols, and rare-token overlap is
the ranking `CLAUDE.md` already argues for. It reaches the prompt as a
`briefing` on the `mcp.list_tools` payload — only built-ins may brief, and it
is placed *before* the tool rules so the last instruction the model reads is
still Zaram's. Measured: with the map, *"Make the greeting end with an
exclamation mark"* — no file named — went `search_code(greeting, subpath=src)`
→ `read_lines(src/greet.py)` → `edit_file` → commit `ce982d9`, decoy skipped,
three rounds.

**Still owed in this slice.** *The repository offered as a project* when a
folder added to Knowledge looks like one (7h), and the diff card.

**Measured, 12 September, `qwen3-14b-16k` resident on the 12 GB card.**
Asked *"In app.py, make main() return 2 instead of 1. Read the file first,
then change it."* with the five tools offered: `read_lines(app.py, 1, 400)`,
then `edit_file(app.py, find="    return 1", replace="    return 2",
summary="Change main() to return 2 instead of 1")` → commit `72b71c8`, tree
clean, 34 s wall clock including the read. Two rounds, no invented argument
names, and it filled the optional `summary` unprompted.
`tests/test_the_code_tools_can_write.py -m measure` is the instrument; the
other 29 tests in that file run without a model.

**Acceptance — seen, on screen, 12 September, later the same evening.** In
the real interface (Vite + backend with a shared dev secret, in the browser
pane): a coding project pointed at a seeded repository; asked with nothing
granted → the reply read *"`run_command` on `code` needs your say-so before it
runs … Allow running the project's commands for this project in Project, then
ask again"* and the model answered honestly that it had not run anything;
both checkboxes ticked in Project (`writes: true, runs: true` confirmed over
the API); asked again → *"Ran 2 commands, read a file, edited a file"*, the
change card with `+1 −1`, the sha and **Revert**; pressed Revert → *reverted*,
`git log` showing `Revert "zaram: Fix add()…"` and `calc.py` back to `a - b`.

**The diff card exists** — `frontend/src/components/chat/ChangeCard.tsx`.
Every write's result carries its unified diff (`DIFF_CAP` 6,000 chars) and its
commit; the `tool_call` event carries both; the card is never folded, shows
the counts, and its one button is `POST /projects/{id}/revert`, which
`CodeWriter.revert` answers only for commits whose message starts `zaram: ` —
a button that could revert the person's own history is a button waiting to be
pressed by mistake. A revert that would overwrite the person's uncommitted
edit is refused with git's own sentence and aborted cleanly.

**Two defects only the screen could show, both fixed the same evening.**

* `set_tool_vocabulary` and the new `set_code_project_open` were called in
  `_register_runtimes` under `if self.execution_engine is not None` — and the
  engine is built one step *later*, so the guard was false at every boot since
  the vocabulary line was written. The routing fix passed on a bare planner
  and did nothing in the app. Both now attach in `boot()` after the engine
  exists, and `test_the_code_pack_is_wired.py` asserts both against the real
  boot path.
* `Qwen3.8-27B` on TabbyAPI, offered the native function specs, sometimes
  writes its chat template's own call form as text —
  `<tool_call><function=code__run_command><parameter=runner>pytest…` — which
  rendered raw and ran nothing. `parse_call` now reads that form too
  (`_XML_CALL_RE`), split back through `split_native_name`, and `strip_calls`
  removes it. `tests/test_a_models_own_call_form_is_understood.py`.

**And a third, on the notice under a finished task.** "Zaram's pick" is
`model=None` all the way into the engine, and `budget_for(None)` is the 4,096
fallback — so a task that had *finished*, tests passing, carried *"stopped at
half of the 4,096 this model has"* with a Continue button, on a model with
65,536. `ExecutionEngine._effective_model` now resolves the pick the way the
transport does (the models runtime's own report) before anything is sized or
placed; the same gap had been silencing the cloud offer.

### 5 — something can run. Built 12 September.

`packs/code/runners.py`. This is the dangerous one, dangerous in a way the
file sandbox is not: a shell reaches the whole machine. So it is not a shell.
**It is an allow-list of runners detected from the repository**, each a whole
command, and the model chooses one by name: `package.json` scripts (`test`,
`build`, `lint`, `typecheck`, …), `pytest` where a project looks like one,
`make` targets, `cargo`, `go`. Nobody configures anything and "run the tests"
works on day one — rule 7h.

* **Arguments are argv, never a shell.** `; rm -rf /` is a filename that
  does not exist. `..`, a flag on a non-test runner, more than eight
  arguments, or anything outside a plain-name character class is refused
  before a process starts.
* **Scripts that do not exit are detected and refused by name** — `dev`,
  `start`, `serve`, `watch` — because a timeout that kills a dev server
  reports a failure that is not one. Running the app is a different feature
  with a different shape, and it is not this tool.
* **Bounded in every direction.** 180 s, then reported as `timed_out` rather
  than raised; 12,000 characters kept as head *and tail*, because the tail is
  where a test runner puts its summary; exit code reported plainly.
* **The interpreter is probed, not trusted.** Measured on the maintainer's
  machine: the first `python` on PATH was a launcher stub whose install had
  been removed, answering `-m pytest` with exit 3 and *"the install path was
  not found"*. Detection now offers `pytest` only under an interpreter that
  starts and imports it — the project's own venv first, then `python`,
  `python3`, `py -3` — and never Zaram's own.
* **Same grant shape as writes, and a separate grant.** `Project.runs`,
  a second checkbox under the folder in Project that *names the detected
  runners* (`GET /projects/{id}/runners`) rather than asking for trust.
  `run_command` is not `looks_read_only`, so ungranted it is `CONFIRM` with
  *"Allow running the project's commands for this project in Project"*.

**The repeat guard was wrong for this, and it was measured wrong.** The
tool loop stopped on a verbatim repeated call because *"its result is
already in the prompt"* — true for a read, and false for `run_command(pytest)`
called before and after an edit, which is the entire point.
`ToolCall.is_repeat_without_progress` now lets a repeat through when any call
since the earlier one is not `looks_read_only`; two tests in
`test_the_tool_loop_is_bounded.py` pin both directions.

**Measured, `qwen3-14b-16k`, a seeded bug (`a - b` for `add`) and one test:**
`run_command(pytest)` → 1 failed → `edit_file(calc.py, "return a - b" →
"return a + b")` → commit → `run_command(pytest)` → 1 passed. Three rounds,
no read needed — the traceback showed the line. 70 s wall clock including
two pytest starts. `tests/test_the_code_tools_can_run.py -m measure`.

`runtimes/tool/connectors` still holds a Terminal connector nothing wires. It
is not this — a terminal is the shell this tool refuses to be — and it should
be deleted rather than left as a second route.

### 6 — the loop's second half. Built 12 September.

The loop's half landed with 5: a failed run is the next round's input, and the
repeat guard knows a run after an edit is progress. **The offer** is the rest,
and it is the reaction `CLAUDE.md` describes in place of predicting difficulty.

`ExecutionEngine._stuck_offer`: when a reply's `run_command` results include
at least `STUCK_AFTER_FAILED_RUNS` (2) failures **and the last run still
failed**, the answering model is positively local, and a cloud model is
connected, one notice follows the answer — `kind: stuck, action: cloud`,
carrying the model — that says how many times the tests failed, which model
would be tried, and *what would leave*: the question, the repository map and
the files Zaram read, to that provider. `NoticeCard` renders it as **Try this
step with <model>**, and `ChatSurface.tryCloud` re-sends the last question
with a per-message `model` override — the next question goes back to whatever
routing was. Never a mode.

`ProviderManager.best_cloud_model` picks the model to offer: remote,
`selectable_by_default` only — a tier that trains on input is never the thing
offered — ranked with `cloud_first`. `prefer_local` does **not** empty it,
because that setting governs what Zaram picks on its own and a button the
person presses is not that. Absent when the tests passed, when nothing remote
is connected, when the model is already remote, and when `locality_of`
cannot place it — no offer on a guess.

`tests/test_the_cloud_offer_for_a_stuck_step.py`, both directions plus a
broken manager never failing a reply. Not yet watched on screen: it needs a
local model to fail twice, and tonight's did not.

### 6b — the installed libraries are the documentation. Built 13 September.

**The maintainer's question:** *how do we solve hallucination without the
user downloading docs for every new environment?* The answer is structural and
it is the one nobody else is using: **the truth is already on the machine.**
Every project has its dependencies installed, at the exact version it uses.
`node_modules/<name>/package.json` says the version; `.d.ts`, `.pyi` and
source say every signature; JSDoc and docstrings say what they mean; the
README says how it is used. Kilo pipes docs in from Context7 (a cloud
service); Cline asks the person to attach them. Zaram reads the installed
package, deterministically, locally, with provenance to a file.

`packs/code/libraries.py`, three things in order of how cheaply each stops a
wrong API:

1. **Versions in the briefing** — *"react 19.2.8, vite 6.3.5 …"* under the
   repository map, "not installed" named as such. Most hallucinated APIs are
   version drift, and a model told the version reaches for the right one.
2. **`find_symbol(name, package?)`** — the real definition: signature, its
   JSDoc or docstring, file and line. `.d.ts` before `.js`, `.pyi` before
   `.py`, `@types/<name>` beside a JS-only package, Python from the project's
   *own* interpreter's `site-packages` (the same `_python_for` the runners
   use — never Zaram's venv).
3. **`read_library_docs(package)`** — the README head with the version.

Both tools are read-only by policy (`find`, `read`) and need no grant.
Nothing enters the Spine: it is a lookup, not an index, and `ingest` keeps
skipping `node_modules` and `venv` so the project's own index does not fill
with someone else's library. Cargo and Go get versions from the lock file and
no source lookup yet — "version known, definitions not" beats guessing at a
registry path.

**Bounded, and measured to need it.** Resolving Zaram's own backend (~200
distributions, torch among them) took 9 s and an unqualified
`find_symbol("Depends")` 69 s. The library table is now cached on a
fingerprint of the manifests and install folders — rebuilt when they change,
never on a clock (1.0 s first, 24 ms after) — and a lookup stops at 8 s or
3,000 files and says *name the package to narrow it* (1.7 s).

**The measured harness now asks TabbyAPI first — the maintainer's
instruction, 13 September.** `_model()` in `test_the_model_can_drive_the_tools.py`
takes whatever `127.0.0.1:1234/v1/models` is serving before falling back to
Ollama, and `_generate` speaks to it through `OpenAICompatibleEngine`. The
27B served there is the model Zaram's own routing picks on this machine, so
every earlier measurement on the Ollama 14B was of a model the product does
not use by default. Re-run on `Qwen3.8-27B-exl3-2.20bpw`: the library task
went `read_library_docs` → `find_symbol` (to confirm the signature) →
`write_file`, correct; run→fix→run passed; the edit task passed in 93 s.
`ZARAM_MEASURE_MODEL` still pins either by name.

**Measured, `qwen3-14b-16k` first and then the 27B.** A library that exists only in the test, with
an API no model has seen — `forgeWidget(spec: { caption, cells? })`. Asked to
make a widget captioned "alpha": `read_library_docs(widgets)` → `write_file`
with `const { forgeWidget } = require('widgets')` and `caption: 'alpha'`.
Correct, and only because it looked. Against Zaram's own repositories:
`useEffect` from `@types/react/index.d.ts:2045` with its JSDoc, `FastAPI`
from `applications.py:42` with its docstring.
`tests/test_the_installed_libraries_are_the_documentation.py`.

**And "save the knowledge for use across the project" — the honest version.**
The library table is *derived* from the repository every time it changes,
not remembered, because a remembered version goes stale the day a dependency
is upgraded and a fact that was true on Tuesday is the hallucination the
feature exists to stop. What *is* worth remembering across the project is
what the model decided while working — which is the checklist's *decisions
taken and rejected* on `PlanRecords` (slice 7), and the project-scoped
exchange facts the engine already stores. Knowledge derived from the repo
stays derived; knowledge decided in conversation gets remembered.

### 7 — the plan is a checklist. Built 13 September; seen on screen up to Go.

`docs/AGENT-UX.md` is the design; `docs/MILESTONES.md`'s 13 September
handoff is the status in detail. In short: the `plan` tool whose result is
the record; `PlanRecords.items/approved/finished`; `StreamEvent.plan`;
`PlanCard` never folded; the checklist on Project's task rows and a finished
section; pause-for-Go before the first mutative call on a plan of four or
more items; Go remembered on the task. Seen: the list ticking live, the
model adding a step it discovered, the pause, and the resume committing.
`tests/test_the_plan_is_a_checklist.py`.

### 8 — run it and look at it. Built 13 September; seen on screen 13 September.

`packs/code/apps.py`: `start_app`, `stop_app`, `get_app_status`,
`read_app_log`, `look_at_app`. A managed process the person can stop; a
headless screenshot with their own Chrome or Edge of a loopback URL only;
read by a local vision model when one is installed and honest when none is.
`AppCard` shows the URL with Stop and the picture.
`tests/test_the_app_can_run_and_be_looked_at.py`, including a real
screenshot.

**Seen, on the TabbyAPI 27B, 13 September**: *"Start the app and look at
it"* on a seeded page → `list_files`, `start_app` (`npm:dev`), the
running-app line with **Stop**, `look_at_app`, the screenshot card, and a
description that named the seeded 502 banner and a real defect nobody
seeded — the page was served without a charset, so `€` and `'` were
mojibake, and the model said so. Three defects found by watching it, all
fixed the same day:

* *"look at it"* classified as a vision intent and was refused for having
  no image attached — on the one kind of project whose tool takes the
  picture. With a coding project open and nothing attached, a vision intent
  now takes the tool plan (`core/planner.py`,
  `tests/test_a_coding_project_offers_its_tools.py`).
* The screenshot card showed its alt text: an `<img src>` cannot carry the
  API credential, so the picture answered 401. The card fetches it with the
  credential and shows an object URL (`AppCard.tsx`).
* *"14 attached tools are available for this question"* wore the amber
  warning triangle — `kind: "tools"` was sent and never keyed to a tone
  (`NoticeCard.tsx`).

**And the vision model was there all along.** *"No local vision model is
installed"* was true of Ollama and false of the machine: the 27B on
TabbyAPI is loaded with `use_vision: true`, and the OpenAI-compatible
discoverer read `/v1/model` for the window and not for that flag. It reads
both now (`tests/test_a_second_server_can_see.py`), and a side task prefers
the model already in use, then its server, then anywhere else —
`select_model_for_task(near=…)`, a preference after the gates, never a
server name (`tests/test_vision_gate.py`). What still costs: the 27B's chat
template defaults reasoning effort to `xhigh`, so reading one screenshot
took about three minutes of thinking before a paragraph of answer.

### 9 — the eval set. Written 13 September; first numbers 13 September.

`tests/test_eval_bounded_coding_tasks.py`, eight bounded tasks through the
real loop with mechanical checkers. Run with `-m measure`.

**Measured — TabbyAPI, `Qwen3.8-27B-exl3-2.20bpw`, 65k window, 13
September 2026, Ollama holding only `bge-m3` beside it: 6 of 8, 10:36
total.**

| task | result | time | calls |
|---|---|---|---|
| fix_failing_test | PASS | 118s | 8 — plan, plan, run_command, plan, read_lines, edit_file, plan, run_command |
| add_function_and_test | PASS | 197s | 8 — plan, read_lines ×2, plan, edit_file, plan, edit_file, run_command |
| edit_unnamed_file_via_map | **FAIL** — greet.py not changed | 30s | 1 — search_code |
| new_file_in_empty_repo | PASS | 74s | 2 — list_files, write_file |
| rename_across_files | PASS | 83s | 4 — search_code, edit_file ×3 |
| unknown_library_api | **FAIL** — did not use the real API | 44s | 2 — list_files, read_library_docs |
| answer_from_code_without_changing_it | PASS | 51s | 3 — find_symbol, search_code, read_lines |
| refuses_what_it_cannot_do_honestly | PASS | 33s | 0 |

Both failures are the same shape and it is not a tooling one: the model
made one or two reads and then *answered in prose* instead of acting —
after `search_code` found the file, and after `read_library_docs` returned
the real signature. The loop ended because the reply carried no tool call,
which is the loop working as designed. The next thing to try is a
briefing line for a task that names a change: *a task that asks for a
change is not done until a file has changed*. The `plan` tool is used
freely (four times in the first task) and costs a round each; whether that
is worth it on the 27B's `xhigh` reasoning is a measurement for the next
run. **The Ollama 14B has not been run yet** — it needs the Tabby server
stopped to get the card, and this session did not stop it.

### 10 — pairing, then the Spine as an MCP server. Built 13 September; pairing seen on screen.

`core/pairing.py` got its caller. `core/paired_clients.py` persists the
registry's devices to SQLite under `data_dir()`; `RequireApiSecret` in
`main.py` accepts a paired credential on the memory routes and nothing else
— `POST /memory/recall`, `POST /memory`, `POST /memory/{id}/correct`,
`GET /memory/{id}`, `GET /projects` — refusing the rest with a sentence
that names the caller; every call from a paired client is an egress entry
addressed to `client:<name>` with the bytes of the *response* counted, and
never the facts themselves. `POST /pairing/redeem` is the one route with
no credential behind it, because the caller has nothing yet but the token.
Settings gained *Other assistants*: a one-time code with a countdown, the
list with last-use and Revoke, and the code disappears the moment it is
used (`PairingSection.tsx`). One defect found by pairing on screen: one
token in sixty-four began with `-` and argparse read it as an option;
tokens are re-minted until they start with a letter or digit.

`zaram_mcp.py` is the server: stdio JSON-RPC in the standard library, four
tools — `recall`, `remember`, `correct`, `projects` — each an HTTP call to
the running Zaram as the paired client. `python -m zaram_mcp pair <token>
--name "Claude Code"` prints the credential once and the `.mcp.json` block
to paste. Tested for real: a live Zaram on a free port, the token redeemed
over HTTP, the server spawned and driven through Zaram's **own** MCP
client (`tests/test_the_spine_is_an_mcp_server.py`); the routes and the
allow-list in `tests/test_a_paired_client_reaches_the_memory.py`.

Seen on screen: the code issued in Settings, redeemed from a terminal as
*Claude Code* and again as *Cline*, both rows appearing with "used just
now", both surviving a backend restart. **Not yet seen:** a real Claude
Code session holding it — that is the next thing to watch, and it is a
paste of the printed block away.

`docs/AGENT-UX.md`, written tonight, is the study and the decision: a `plan`
tool, the checklist on `PlanRecords`, a card under the reply that ticks as
commits land, the same list on the task's row in Project, Go/Edit before the
first mutative call on a long plan, and locality per item from the egress
log. Build order is in that file.

**Acceptance.** Two projects, two specs, both scaffolded, tested and committed
while the steps are watched in Project — sequentially on the local model, and
in parallel the moment a key is pasted, with the egress log saying which was
which.

## The unknown that decides how good this feels

**Whether the local model can drive it.** `docs/AIDER.md` records the binding
constraint and it is not the parameter count: `qwen3-14b-8k` is capped at
**8192 tokens** by its Modelfile. For scale, `ChatSurface.tsx` is ~15,000
tokens and `main.py` ~54,600.

That is survivable, because a tool-based agent reads *slices* — which is
exactly why slice 1 exists and why chunks carry line ranges. But 8K is tight
for a loop holding a plan, an excerpt and a diff at once, and 14B tool-calling
reliability across many turns is unknown rather than merely pessimistic.

**Measurement 2 is taken and the answer is yes** — `qwen3-14b-16k` is verified
resident at 16,384 tokens on the 12 GB card, with `OLLAMA_FLASH_ATTENTION=1` and
`OLLAMA_KV_CACHE_TYPE=q8_0` (which saved 1.77 GB and is what makes 16K fit). And
the question underneath both measurements — *can the model drive it* — is
answered above: search then read, correct answer, on a 14B.

One thing the run exposed that neither measurement asked about: **a coding
question phrased naturally does not reach these tools.** "search the code for X"
and "find x in the code" both classify as `filesystem.search`, because the
planner checks the filesystem intent before the tool intent. Only phrasings that
name the tools — "use the code tools to…" — plan `mcp.list_tools`. That is a
routing gap, it belongs with slice 4, and it means the pack is currently
reachable by a user who already knows it exists.

**The remaining measurement:**

1. Aider is installed, configured, and has never produced a generation anybody
   has read. Point it at `core/readiness.py` (~2,100 tokens, comfortably inside
   the window) with `--yes-always` and stdin closed.
2. Whether `num_ctx` at 16K or 32K fits beside the weights on 12 GB.
   `MILESTONES` says it cannot rescue `main.py`, which is true and beside the
   point — the question is whether it clears a normal file.

## Two things that must not happen

**A second memory.** The moment the coding agent keeps its own context store or
session abstraction, a framework has been adopted by writing it — and memory is
the product. Facts go in the Spine, scoped to the project, like everything else.

**Competing with packaging.** A stranger still cannot install Zaram, and a
coding agent inside an uninstallable product reaches nobody. This is a
scheduling cost to take deliberately, not a veto.
