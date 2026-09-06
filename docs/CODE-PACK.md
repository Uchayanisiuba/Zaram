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

**4 — next: the repository is offered as a project.** When a folder added to
Knowledge looks like a repository, offer to make it a coding project, with its
`root` set. Offer at the moment of doubt, never a choice in advance (7h). This
is what makes slice 3 reachable *by a user* rather than by a request that
happens to name a coding project.

**5 — diffs as cards.** Reviewing a change before accepting it is the one thing
none of the six nodes render today. It is a card in the conversation, the same
pattern generated files already use — **not** an editor. Work deliberately
gains no sub-apps for editing, and a code editor inside Zaram is that rejected
idea under a new name.

**6 — scoped writes.** Per-project grant, branch per task, commit per step.
Only after 4 has told us what the model can actually do.

## The unknown that decides how good this feels

**Whether the local model can drive it.** `docs/AIDER.md` records the binding
constraint and it is not the parameter count: `qwen3-14b-8k` is capped at
**8192 tokens** by its Modelfile. For scale, `ChatSurface.tsx` is ~15,000
tokens and `main.py` ~54,600.

That is survivable, because a tool-based agent reads *slices* — which is
exactly why slice 1 exists and why chunks carry line ranges. But 8K is tight
for a loop holding a plan, an excerpt and a diff at once, and 14B tool-calling
reliability across many turns is unknown rather than merely pessimistic.

**Two cheap measurements settle it, and neither has been taken:**

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
