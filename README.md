# Zaram

**The memory and control layer for people who use more than one AI.**

Every AI conversation starts from nothing. You re-explain the client, the rates, what
you decided last week — every session, and from scratch again when you move from a
frontier model to a local one to whatever your editor has built in. Each tool is
capable. None of them remembers what happened in the others.

Zaram is the memory that stays put while the model changes. One knowledge base — the
**Spine** — on your machine. Any model can recall from it. You see what was recalled,
you can correct it, and you control what leaves the device.

Not a model: it routes to yours. Not an agent framework: it serves people doing work,
not developers building products.

## Who this is for

**Anyone who types on a computer.** That is not a hedge, it is the design: what earns a
daily open is an assistant one keystroke away that is fast, remembers you, reads your
documents, and sends nothing you did not send. There is no profession in that sentence,
and the product has no gate that adds one.

**It is a daily driver first**, which means it has to be good at the ordinary jobs
before it is clever at the rare ones. Writing, editing, summarising, rewriting,
translating — five of the eight things people actually use AI for, and a local 8–14B
model already does all five well. Those answer with no network round trip at all, which
is a kind of fast a cloud service structurally cannot be.

**Your models, your keys, and Zaram picks between them per question.** Bring a local
model, bring a cloud key, or bring both and let it route: the request is classified
against exemplars you can edit, capability filters the candidates before anything is
ranked, and a single *Prefer local · Auto · Prefer cloud* control biases the rest. Every
reply names the model that answered and why. Nothing here requires a subscription,
because Zaram never buys inference.

### Where it stops being a preference and becomes a requirement

The same product, for people who have no alternative:

**People whose documents cannot leave.** Therapists, accountants, lawyers, HR,
clinicians with case notes. They are told to use AI and forbidden to upload. Local
inference is the only permitted option, and an egress log naming every byte that left is
what a compliance conversation actually needs. Documents and drafting — never diagnosis,
never legal advice.

**People for whom cloud AI is expensive or unreliable.** Metered data, intermittent
connections, subscriptions priced in dollars against a local wage. A resident model
costs nothing per question and works with the connection down. That is a structural
advantage, not a philosophical one.

**People with a long project and a bad memory for it.** Researchers citing from a
library, students with a reading list, writers holding continuity across a manuscript,
developers whose code never leaves the machine, consultants who need to know what was
decided per client, freelancers with rates and terms buried in contracts nobody
re-reads.

That last group is where the **first pack** lives — invoices, quotes, expenses,
obligations. A pack adds parsers, tools, templates and routing exemplars. It adds no
screens, and it is never a different product.

## Why this is hard to copy

The ambient-assistant pattern is proven — Grammarly's Superhuman Go docks a panel to the
screen edge and offers to act on what you are typing. It works by sending that text to
their servers, which is their business. They cannot ship the same product where sending
it is the user's decision, because the sending is the company.

The labs have memory too, and it is locked to their own model. Memory that works *across*
competitors is against their interest to build, permanently.

Zaram never buys inference — you bring your own key or your own model — so its cost of
goods is approximately zero and an uncapped free tier is permanent rather than
promotional. Nothing funded by token margin can match that.

Local-first is copyable in principle by another small team. The accumulated memory of
your own work is not, and neither is the discipline: provenance on every recalled fact,
an append-only egress log, and a correction loop that changes the answers.

## A rented model can be taken back

On 9 June 2026 Anthropic shipped Claude Fable 5 and Mythos 5. On 12 June a US
export-control order barred access by any foreign national anywhere — and because
nationality cannot be verified live, **both models were disabled worldwide, for
everyone, paying US customers included**. Access was restored on 1 July. Eighteen
days, no appeal, three days after launch.

That is not a connectivity problem and not a developing-market problem. It is the
most capable model available, switched off globally by the government of the country
that built it, and nobody who had built their work around it had any recourse.

**Be exact about what Zaram does and does not survive.** Cloud routing stops in that
scenario too — that half was always somebody else's. What keeps working is the model
on your disk, your documents, and everything Zaram has learned about your work. The
Spine is exportable in an open format, so the memory outlives the provider, the
order, and Zaram itself.

That is the whole ownership claim, and it is deliberately narrow. What you own is
what is on your machine. It is also, on the evidence of June, the only part anybody
owned at all.

## Principles

- **Never buy inference.** You bring your own API key or your own local model. This is
  why the single-user tier can be free and unlimited.
- **Every recalled fact carries provenance.** An answer that cites nothing is a bug.
- **Every byte that leaves is logged**, in an append-only egress log you can read.
- **Nothing leaves without an explicit, per-item policy.** Default deny.
- **Tools confirm before acting.** Autonomy is granted, never assumed.
- **The Spine is exportable in an open format.** No lock-in.
- **Generation fails rather than invents.** When recall cannot resolve what you are
  referring to, Zaram says so and asks. A wrong reply is corrected in the next turn; a
  wrong document is sent to a client.

## Status

**Pre-v1.** This section is maintained against the code rather than carried forward,
because it drifted once already — until 16 August 2026 it claimed there was no egress
log, no cloud provider, no folder ingest and no installer, all of which had stopped
being true. A status section that understates a project is the same defect as one that
overstates it, and it sits on the page a stranger reads first.

What has been observed working, rather than merely written:

- **The recall loop, end to end.** The Spine persists to SQLite with Ollama `bge-m3`
  embeddings, the index rebuilds on boot, and a fact stored in one session is recalled
  in the next — verified across a process restart.
- **Every recalled fact arrives with provenance** the interface displays and can open.
  Correcting or deleting one changes the answers that depended on it.
- **The egress log.** Append-only, hash-chained, viewable, with the literal text of what
  left. Per-host policy, default deny, and a kill switch that lives in the policy rather
  than in a route, so it covers tool traffic and model discovery too.
- **Confirm before send**, verified against a live provider: preview, log and wire were
  byte-identical at 1650 bytes, with a struck fact absent from all three.
- **The local API requires a credential.** A per-launch secret is minted at boot and
  enforced as middleware, alongside a `Host` check that refuses DNS rebinding. Tested
  for the cases that matter: no credential refused, wrong credential refused, health not
  exempt, and `X-Zaram-Client` asserted *not* to be a credential — it is a label the
  interface sends and nothing checks.
- **Task-aware routing.** The question is classified against editable exemplars, and
  modality gates the candidate set rather than scoring inside it: a model that cannot
  accept an image is not a worse answer to a question about a screenshot, it is not an
  answer. Every reply names the model that answered and why.
- **Untrusted content is bounded.** Recall folds passages into the system prompt, and
  those passages are often written by whoever sent you the file. Only what you typed may
  instruct; the enforcement is ordering rather than a blocklist, and content that reads
  like an instruction is reported rather than silently stripped.
- **Cloud providers and web search**, several connections at once, routed per model,
  with the data policy of each stated before it is chosen. When a question wants current
  information and search is off, the reply says so instead of answering quietly.
- **Folder ingest**, with per-source privacy policy.
- **Generated documents** — .docx, .xlsx, .pdf, .md, .csv, charts — with preview.
- **Speech both directions**, local and optional, keeping pace with the text rather than
  waiting for the reply to finish.
- **An installer**: `Zaram-0.1.0-x64.exe`, 186 MB, plus a portable build.
- **Export.** Everything Zaram holds, as JSONL and CSV in one .zip.

What is not built:

- **Image generation.** Zaram reads pictures; nothing routes a request for one. That
  needs a way to say "this reply should be a picture", which does not exist — building
  the gate before the request would be scoring a decision nobody can make yet.
- **The installer has not been run on a machine that has never seen this repo.** Until
  that happens, treat "a stranger can install this" as unproven. It is the actual
  blocker, and no amount of further capability substitutes for it.

> **This list drifted again, and was corrected 29 August 2026 — understating, which
> the preamble above already names as the same defect as overstating.** It carried
> three entries that the 28 August work had made false, and a session building the
> launch site nearly published the understatement:
>
> * *"Obligation extraction is not wired… nothing outside its own tests imports it."*
>   `GET /obligations` is served at `main.py:3457` with `/correct`, `/dismiss` and
>   `/met` beside it, `ObligationRecords` is constructed at `main.py:3311`,
>   `services/obligationsClient.ts` calls all four, and `Commitments` is mounted at
>   `MemoryWorkspace.tsx:689`.
> * *"Ingestion by drop, paste or upload — the way in does not exist."* `POST
>   /chat/attachments` resolves through `attachment_store.resolve` into
>   `compose_attachments`; the paperclip, a drag and `Ctrl`+`V` all reach `takeFiles`,
>   and the paste path was driven in a browser on 28 August.
> * *"Images in either direction. In scope, not started."* Half right, and the wrong
>   half was load-bearing. Reading is built — `openai_compatible_engine.py` builds the
>   content-parts form from `images`, and a local vision model answers without the
>   picture leaving. Only *generation* is absent, which is why it is the one that
>   survives above.
>
> The lesson is the one the preamble states and this section keeps failing: a status
> list is only true on the day it is checked against the code. Check it, or delete it.
>
> **A fourth entry survived that first correction and should not have.** *"Knowledge
> domains"* was left in the not-built list because the session doing the correcting
> carried it over from the old list instead of checking it — the same fault it was
> mid-way through fixing, committed in the act of fixing it. Domains are built:
> `GET`/`POST /knowledge/domains`, `PUT` and `DELETE` on one, and
> `POST`/`DELETE /knowledge/domains/{id}/sources/{source_id}`, all at `main.py:3937`
> onward; `KnowledgeDomains` constructed at `main.py:3929`; `_domain_scope` narrowing
> retrieval in the chat path at `main.py:1292`; `services/domainsClient.ts` calling
> every route, `DomainList` in Knowledge and `DomainScopePicker` in the composer.
> **Verifying the entries you delete is half the job; the other half is verifying the
> ones you keep.**

## v1 scope

In scope:

- Ingest a folder, a dropped file, or pasted text into the Spine
- Knowledge domains, linkable to projects
- Chat routed across local and cloud providers, including free tiers, with the data
  policy of each stated before it is chosen
- Recall across providers, with visible provenance
- Correct or delete a fact and see answers change
- Viewable egress log, per-source privacy policy, export
- The business base layer: invoices, quotes, receipts, expenses
- Obligation extraction, surfaced before it lapses
- Reading images locally, and routing generation to a provider that can draw
- Generative documents, and read-only MCP for Unreal and Blender
- The character: your own name, manner, voice and VRM for it

Explicitly out of scope until v1 ships and has been tested with real users: agents, IDE
integration, extensions marketplace, mutative tools, multi-user, video generation, and
any additional workspace.

## Layout

```text
backend/     FastAPI service. Kernel, event bus, execution engine, runtimes.
frontend/    React + Vite interface. The live UI.
electron/    Electron desktop host (JavaScript).
desktop/     Second Electron host (TypeScript). Duplicate — see below.
packages/    zaram-engine. Currently unused by the frontend.
figma-assets/ Design exports.
```

Known duplication: `electron/` and `desktop/` are two implementations of the same
desktop host, and the root build scripts do not agree on which one ships. There are also
two virtualenvs. Both pairs are internally consistent, so no guard catches either, and
each has already cost a session. `docs/RUNNING.md` has the detail.

## Reading the code

`CLAUDE.md` is the project contract — vocabulary, immutable rules, v1 scope, technical
decisions. Read it first. `docs/VISION.md` holds the rationale, `docs/MILESTONES.md` the
current state, `docs/SPEECH.md` what speaks and when, `docs/RUNNING.md` how to start the
real app and the four ways it fails that each look like something else.

The working agreement in short: read before you write, verify against the code rather
than the documentation, and when a plan and the codebase disagree, the codebase wins.
Assume a subsystem is unreachable until you have seen its caller — fifteen complete,
tested, unreachable subsystems have been found in this repository, and "the tests pass"
has repeatedly meant nothing.

## Licence

**Source-available, all rights reserved. This is not open source.**

The source is public so that the central claim can be checked: that inference runs
locally, that the index is on disk, and that nothing leaves without a logged, consented
decision. That claim cannot be substantiated by a closed binary, and reading the code is
how you verify it.

Reading, auditing and evaluating are welcome. Copying, modifying, redistributing or
running Zaram in your own product are not granted. No licence is offered, so all rights
are reserved by default under copyright.

Publishing on GitHub grants other users the ability to view and fork within GitHub
itself, under GitHub's terms. That is a condition of public hosting and is not a licence
to use what you copy.

If you want to use any of this, ask.
