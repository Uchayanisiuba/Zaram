# The agentic coding surface — what the industry converged on, and what Zaram takes

Written 12 September 2026, at the maintainer's request after watching Kilo Code
plan a task, keep a checklist, and tick it off when the session ended. Read with
`docs/CODE-PACK.md` (what exists) and `CLAUDE.md` (the rules the design must
survive). This file holds the study and the decision, so the shape of Zaram's
coding surface is argued once rather than re-argued per feature.

**Sources and their limit.** The comparison below is drawn from the products as
they stood by mid-2026 — Claude Code, OpenAI Codex (CLI and cloud), Cursor,
Kilo Code and its ancestors Cline and Roo Code, Windsurf Cascade, Aider, Devin,
GitHub Copilot's agent mode, Amp. None was re-measured for this note; where a
detail matters for a build decision, check the product before relying on it.

---

## Ten patterns, ranked by how many products converged on them

Convergence is the signal. When five products with different founders, models
and business models arrive at the same interaction, it is because users made
them.

| # | pattern | who has it | convergence |
|---|---|---|---|
| 1 | **Steps shown as collapsible rows with their output** | everyone | total |
| 2 | **Diff shown before or beside the reply, not behind a click** | Claude Code, Cursor, Cline/Kilo, Copilot, Aider | total |
| 3 | **Plan before act** — a written plan the person reads first | Claude Code (plan mode), Cline/Kilo (Plan/Act), Devin, Codex | strong |
| 4 | **A live checklist that ticks itself off** | Claude Code (todo list), Kilo (task todo), Devin, Codex cloud | strong |
| 5 | **Undo as checkpoints** — snapshot per step, restore any | Cline/Kilo (shadow git), Cursor, Aider (auto-commit), Codex (PR) | strong |
| 6 | **Permission tiers** — ask / auto-approve per category / everything | Claude Code, Codex (`suggest`/`auto-edit`/`full-auto`), Cline auto-approve | strong |
| 7 | **Context and cost meter** on the task | Cline/Kilo (tokens, $), Claude Code, Codex | moderate |
| 8 | **Session-end summary** — what changed, what remains | Devin, Codex cloud (PR body), Kilo | moderate |
| 9 | **Sub-agents / orchestrator** — a task split into delegated subtasks | Claude Code, Kilo (Orchestrator), Devin | moderate |
| 10 | **Background and parallel agents** with a manager view | Cursor, Codex cloud, Kilo Agent Manager | emerging |

What did *not* converge, and is therefore a choice rather than a requirement:
per-hunk accept/reject inside an editor (Cursor, Copilot — both *are* editors);
a chat-only interface with no panel at all (Aider); an autonomous default with
no approvals (Devin's early posture, since walked back by everyone).

---

## Where Zaram stands against each, as of tonight

| # | pattern | Zaram, 12 September |
|---|---|---|
| 1 | steps as rows | **done** — `ToolCalls`, one row per call with verdict, target and output pane |
| 2 | diff in front | **done tonight** — `ChangeCard`, never folded, with Revert |
| 3 | plan before act | not built; the plan object exists (`PlanRecords`) and holds steps taken, not steps intended |
| 4 | live checklist | not built — this is the Kilo feature the maintainer asked for |
| 5 | checkpoints | **done, and better** — a real git commit per write, not a shadow store; Revert on the card |
| 6 | permission tiers | **done, differently** — confirm once per project and data class, off by default, visible and revocable in Project. No per-call dialog and no "YOLO" |
| 7 | context meter | partly — `TokenUsageBar`; nothing says how much of the window a task has used |
| 8 | session-end summary | not built; a finished task says nothing about what it did |
| 9 | sub-agents | not built; one level, read-only, is the design already recorded |
| 10 | parallel agents | not built; Projects are the noun, residency is the limit (`CODE-PACK.md`) |

Two of the three strongest gaps — 3 and 4 — are one feature. The third, 8, is
its ending.

---

## The decision: the plan is a checklist, and it lives in Project

**What Kilo does that is right.** The agent writes a numbered list of what it
intends to do before it does it; the list stays on screen; items tick as they
complete; when the session ends the person sees what was done and what was
not. It turns a wall of tool rows into a shape a person can hold in their head,
and it makes "is it finished?" a glance rather than a read.

**What Zaram already owns that makes it better than a chat message.** `CLAUDE.md`
asked for exactly this object on 6 September, in the plan-object entry: *"the
other half of what CLAUDE.md asks of the plan: decisions taken and decisions
rejected, and a plan the user reads **before** it runs."* And `PlanRecords`
already exists, scoped `project:<id>`, pruned after seven days, holding tool
results and never dialogue (rule 7d). A checklist is the intended half of that
object. It is not a new store.

So the shape is:

**A `plan` tool on the code server, generative tier.** The model calls
`plan(items=[{text, status}])` to write or update the checklist; statuses are
`todo`, `doing`, `done`, `skipped`. It creates nothing on disk, changes no
file and needs no grant — it is the model writing its own intentions down,
which is the one kind of writing that cannot need undo. Read-only by policy
(`looks_read_only` learns the name), so it never asks.

**The checklist is a card under the reply, never folded, above the tool rows.**
Live while the reply is being written — items flip from `doing` to `done` as
tool calls land — and left in the transcript when it finishes, ticked. That is
pattern 4. It is rendered by Zaram from the plan record, not typed by the model
as markdown, so it cannot be fabricated as prose: an item is `done` because the
tool that did it returned, or because the model said so and the card marks the
difference.

**The same record is a row in Project.** Project already lists unfinished
tasks with Continue. It now shows the checklist beside each — what is ticked,
what is not — which is pattern 8's "what remains" without a summary anyone has
to generate. A finished task keeps its ticked list for the seven days the
record lives, so "what did Zaram do to this project on Tuesday" is answerable
from Project rather than from scrollback. **Decisions taken and rejected** ride
on the same record as items with status `skipped` and a reason, which is the
half `CLAUDE.md` asked for and the half that stops a resumed task re-taking a
decision the person already refused.

**Plan-before-act is an offer, not a mode.** Rule 7h: never make the person
choose in advance. Kilo has a Plan/Act switch; Claude Code has a plan mode you
enter. Zaram does neither. When the model writes a plan of more than a few
steps that includes writes or runs, the card shows it with **Go** and **Edit**
before any mutative call runs — the model plans, the loop pauses on the first
`write_file`, `edit_file` or `run_command`, and the person's press is the
consent for *this plan*. A short plan, or one that only reads, runs straight
through. "Just do it" is a sentence the person can type, not a setting.

**Session end is the checklist's last state plus the commits.** No generated
summary — a summary is a generation and can be wrong about what happened. The
card already knows: N items done, M skipped with reasons, the commits made
(each a `ChangeCard` above it), and whether the last test run passed. That is
what Codex puts in a PR body and Devin in its report, produced here from
records rather than from a model's memory of the session.

**What is deliberately not taken.**

* *Per-hunk accept/reject.* That is an editor, and Work gains no sub-apps for
  editing. Consent is per project, review is the diff card, undo is Revert.
* *A "YOLO" or full-auto mode by name.* Zaram's equivalent is the two
  checkboxes in Project, and they say what they grant rather than how brave
  the person is feeling.
* *Dollar cost on local models.* A local model costs nothing per token; a meter
  that shows $0.00 teaches nothing. Show tokens against the window and time
  taken; show money only where a metered provider was used, from its own
  numbers.
* *Nested sub-agents.* One level, read-only, is the recorded design; an
  orchestrator that spawns writers is the framework `CLAUDE.md` refuses to
  adopt, arriving by the front door.
* *A separate agent surface.* Kilo's Agent Manager is a seventh node. Projects
  are the noun and Project is the surface, with a row per task.

---

## The one thing Zaram can show that none of them can

Every row in every product above answers *what did it do*. None answers
**what left the machine to do it**. Zaram's tool rows already carry the gate's
verdict; the checklist and the session-end state should carry, per item, the
locality the step ran at — local, or which provider — read from the egress log
rather than from the model. On a machine with a key connected, a finished task
then reads: *seven steps, five local, two on OpenRouter, here is what those
two sent.* That is the pitch in one card, and it costs one column.

---

## Build order — slice 7 of the code pack

1. `plan` tool on `CodeTools`, read-only by policy; the record on
   `PlanRecords` gains `items` with status and reason. Tests: items round-trip,
   `skipped` needs a reason, the tool never asks.
2. `StreamEvent.plan` carrying the current list; `PlanCard` under the reply,
   never folded, live during the reply.
3. Project: the checklist beside each task row, finished tasks kept for the
   record's lifetime.
4. The pause-for-Go: the loop stops before the first mutative call when the
   plan is long enough to be worth reading; **Go** and **Edit** on the card.
5. Locality per item, from the egress log.

Acceptance, seen not passed: ask for a three-file change; watch the plan
appear with Go; press it; watch items tick as commits land; open Project and
see the ticked list on the task's row; revert one commit from its card and
watch the item un-tick.
