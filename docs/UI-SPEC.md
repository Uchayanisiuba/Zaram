# Zaram — UI spec

Covers the full v1 interface. Replaces `docs/UI-MEMORY.md`.

Precedence: this file governs layout, behaviour, data model and scope. Design
exports in `docs/design/` govern visual language only — colours, spacing, type,
component appearance. Where they conflict, this file wins. The exports were made
for an earlier, wider product design; their screens are not the target.

---

## Foundation

Build this as one pass before any screen.

### Surfaces and colour

```
--bg-base      #0A0B0E    page
--bg-raised    #121419    panels, bars
--bg-overlay   #1A1D24    detail panel, popovers
--border       rgba(255,255,255,0.08)   0.5px hairline
--border-hover rgba(255,255,255,0.16)

--text         #F2F4F8
--text-2       #9BA1AC
--text-3       #6B7280

--accent       #5EE7DC    active, local, primary state
--accent-2     #8B7FD4    cloud, secondary emphasis
--warn         #E5A44C
```

One accent per screen region. Never both competing in the same area.

Radii: 12px cards and panels, 8px controls, pill only for chips.

### Type roles

- **Display** — headings and screen titles
- **Body** — prose, fact text, messages
- **Mono** — every value the system reports about itself: timestamps,
  filenames, counts, model names, log rows, keyboard hints

The mono is what gives the product its instrument character. Be consistent —
if the system is reporting a fact about itself, it is mono.

### Materials — glass vs opaque

The distinction is load-bearing. Translucency goes on chrome only; content
surfaces stay opaque. This is what separates a sophisticated dark UI from a
gimmicky one, and it keeps blur off scrolling regions on a machine that is
also running local inference.

**Translucent** (24px blur, 72% opacity, 0.5px top edge highlight): left rail,
top toolbar, persistent bottom bar, popovers, command palette, detail panel.

**Opaque** (no blur, no translucency): message thread, memory list rows,
activity table, cards, metric tiles.

### Navigation

**Left rail** — 64px collapsed (icons), 220px expanded. Glass.
**Four items: Work · Memory · Knowledge · Activity**, with Settings bottom-anchored.

**Work** holds what the user made — documents, spreadsheets, charts — each with the
conversation that produced it and its sources. Same layout across project types;
only the content differs. It exists because a navigation made only of Memory,
Knowledge and Activity is entirely about the system and holds nothing the user
made.
Sources live inside Knowledge. Active item takes a cyan left indicator bar and
raised background, not a filled pill.

Conversation is not a rail item — it is the shell. It is the landing state,
entered by tapping the orb, and animates aside when a surface opens. **The
return path must be visible and one click**: the orb reverses the animation, and
the persistent bar's topic line is clickable. Escape also returns. Never let the
animation be the only route back — a user who cannot find their way back to a
live conversation will reload the app.

The conversation stays **mounted** while a surface is open. Hidden, not
unmounted. A reply in flight survives the trip.

Tools never appear in the rail. They are actions inside the conversation,
configured under Settings. This is what lets capability grow without the
navigation growing. Generated files appear as cards in the conversation and land
in the output directory — there is no Files surface.

**Secondary nav is contextual, inside the content area** — never a second
sidebar. Memory carries its view toggle plus a Constellation link; Settings
uses a segmented control.

**Command palette** — ⌘K. Glass overlay, centred, 640px. Searches facts,
sources and commands, results grouped under mono section labels, keyboard
hints in the footer.

**Top toolbar** — glass. Screen title left, contextual actions right. On
Conversation it carries the privacy timer.

### Motion budget

Transitions ≤200ms. No spring physics on list rows. No continuous animation
anywhere except the orb while actively processing. Respect
`prefers-reduced-motion` — it disables the orb pulse too.

### Component inventory

Build these first; every screen composes from them.

`MetricCard` · `FilterChip` (default / active / disabled) · `SourceRow` (dot +
label + count) · `MemoryRow` (default / pinned / superseded / hover / selected)
· `CitationChip` · `Button` (primary / secondary / ghost) · `SearchField` ·
`EmptyState` (message + recovery action) · `KeyHints` (mono strip) · `Orb`

---

## The shell — architectural, not visual

The conversation is a **persistent shell, not a route**. Navigating to memory,
activity or settings must not unmount or reset it. If the current router
unmounts the conversation, fix that before building any screen here.

Persistent bar, always at the bottom:

```
[orb]  Continuing: pricing page copy
       local · qwen-14b · 3 facts recalled          [expand ↑]
```

### The orb

A 20px circle at the left of the persistent bar. Four states, no others:

| State | Appearance |
|---|---|
| idle | dim, still |
| thinking | slow pulse, accent |
| local | steady accent ring |
| cloud active | steady accent-2 ring + provider name in mono |

It never grows, never centres, never reacts to cursor position, never speaks.
It is an instrument light, not a character. This is deliberate — do not
reintroduce expressive behaviour.

---

## Data model

Three fields are load-bearing and must exist from the first write. `recallCount`
drives sizing, sorting and the recall view — retrofitting it means no history.
`supersededBy` makes correction a state rather than a delete. `pinned` is
user-elevated memory.

```ts
type FactId = string

interface MemoryFact {
  id: FactId
  text: string
  sourceId: string
  learnedAt: string              // ISO
  recallCount: number            // incremented on recall — never reset
  lastRecalledAt: string | null
  pinned: boolean
  supersededBy: FactId | null    // set on correction; row is NOT deleted
  supersededAt: string | null
  relatedIds: FactId[]
  recallReason: string | null    // plain sentence, never a score
}

interface MemorySource {
  id: string
  label: string
  colorSeed: number
  factCount: number
  scope: 'local-only' | 'cloud-allowed'
}

interface EgressEntry {
  id: string
  at: string
  provider: string
  summary: string                // what was sent, in plain language
  reason: string
  bytes: number
}

type ViewMode = 'source' | 'time' | 'recall'
```

`correctFact(id, newText)` creates a new fact and sets `supersededBy` on the old
one. It never removes a row. `deleteFact(id)` is separate and explicit.

---

## Screens

### 1. First run — connect a model

One screen, two options side by side: use a cloud model (paste a key) or use a
model on this computer (detected automatically). A plain-language line under
each explaining the privacy difference. No jargon, no model filenames.

### 2. Sources

Drag-and-drop target to point at a folder. Indexing progress with file count.
Per-folder scope toggle: local only / may be sent to cloud models. List of
indexed sources with dot, name, fact count, scope.

### 3. Conversation — the home screen

Message thread. Assistant replies carry inline `CitationChip`s. Above the input,
a strip showing 2–3 facts recalled into this reply, each dismissible.

Header carries a **privacy timer**: cloud off for 15 / 30 / 60 min. One tap,
with remaining time visible in mono while active.

### 4. Memory — the core screen

Top to bottom:

- Three `MetricCard`s only: facts stored, sources, bytes left device today.
  No more — additional metrics were cut deliberately.
- View toggle: by source / by time / by recall. One dataset, three orderings.
  Not three routes. Switching preserves the active filter.
  - `source`: grouped, sources by factCount desc
  - `time`: flat, learnedAt desc, day separators
  - `recall`: flat, recallCount desc; row weight scales with recallCount so
    frequency is readable at a glance
- Scope filter: **This project · All projects · About me**. Facts show their
  scope in the meta line; the detail panel offers "make this general" and
  "limit to this project"
- Filter chips: all / local only / corrected / pinned, plus a right-aligned
  live count in mono (`12 of 1,247`) that updates on every change
- Left rail of sources: dot + name + count, click to filter
- The list. Row = source dot, fact in sentence case, mono meta line
  `filename · date · recalled 41×`. Pin icon when pinned.

Superseded rows render struck through, dimmed, hollow dot, meta line
`superseded 18 apr · you corrected this`. Hidden unless the corrected filter is
on. **This is the most differentiated element in the product — do not simplify
it away.**

### 5. Fact detail

Slides from the right over the list. Full text, source with the passage
highlighted, date learned, recall count, and `recallReason` rendered as a plain
sentence — never a similarity score. Related facts listed and clickable.

Actions: Correct · Forget · Pin.

### 6. Activity

Dense mono table of everything that left the device: timestamp, what was sent,
provider, why. Prominent summary line at top (`0 bytes left this device today`).
Date filter. This should look like a log, not a dashboard — density over
decoration.

### 6a. Message controls

Assistant messages carry a hover control row:

- **Copy** — copies the message as markdown
- **Redo** — regenerates with the same model
- **Redo with…** — opens a model picker and regenerates with a different one. The
  result appends as an alternative; small arrows in the message header switch
  between them, showing `2 of 3` in mono. Both variants stay in history. This is
  a feature only a multi-model product can ship — treat it as primary, not a
  menu item.
- **Speak** — plays TTS for this message, becomes stop while playing. Default off.

User messages: hover reveals edit and copy. Editing and resubmitting replaces the
message and regenerates from that point, discarding later turns after a confirm.

**No thumbs up/down on replies.** They conflate "the fact was wrong", "the tone was
wrong" and "you misunderstood me" into one uninterpretable signal. Correction is
the feedback mechanism.

### 6b. Generated file cards

When an assistant message produces a file — a document, spreadsheet, chart, or a
code block over 20 lines — render an attachment card beneath the message:
filename, type, size, with **copy · download · preview**, and a **Don't remember
this** override.

Generated documents carry provenance: claims inside them link back to the source
they came from, the same as citations in a reply. This is the differentiator —
a generated artifact you can defend.

**Files are indexed by default.** The protection against Zaram citing its own
restatements is origin tagging, not a prompt: every fact records whether it came
from a user document, a conversation, or Zaram's own output, and recall
deprioritises generated content where a user source says the same thing. The
memory row shows the origin and recall explanations name it — "from a proposal
Zaram generated in April" is different information from "from your client brief".

Asking at creation time is the worst moment to ask, because the user does not yet
know whether it mattered. "Don't remember this" is an override for the rare case
someone knows immediately, never a gate in the common path.

### 6b-ii. Document preview panel

Progressive disclosure, same anchor and pattern as fact detail — **right side,
never over the orb**. Covering the orb hides the local-vs-cloud indicator at the
exact moment a user is inspecting output.

1. **File card** in the reply
2. **Preview panel** slides in from the right, ~520px — rendered document,
   scrollable, with download and open-externally
3. **Expanded** fills the screen for real reading, with × and escape

Glass on the panel frame; the document itself sits on an **opaque** surface.
Reading a contract through a translucent layer over a scrolling conversation is
unpleasant.

Preview means PDF in v1. Formats without a renderer offer download and
open-in-default-app — honest, and an afternoon's work.

Charts render **inline in the reply** as well as being downloadable. A chart you
have to download to see is a chart nobody looks at.

### 6c-ii. The recall strip

Shows the facts pulled into the current reply. **Collapsed by default** — a single
quiet mono line, `3 facts recalled`, expanding on click. This keeps it out of the
way on the 95% of turns where nobody cares, and one click away when someone wants
to know why an answer said what it did.

Two distinct controls, and the separation is load-bearing:

- **Collapse the strip** — clears clutter, signals nothing
- **× on an individual fact chip** — excludes that fact from the next turn

The second is functional, so the intent is unambiguous. Nobody removes a single
fact to reduce clutter when collapsing the whole strip is available. A signal is
only trustworthy when the action producing it has a reason to exist independently.

Even so, treat removals as weak evidence: never act on one, never auto-delete.
A repeated pattern across different contexts may surface a prompt — *"you've
excluded this fact 5 times — still useful?"* — offering correct, forget, or dismiss.

### 6d. Discoverability of generation

Generation has no menu item, so users will not find it unless it is offered.

After an answer that drew on sources, show a small dismissible chip beneath it:
*Turn this into a document · spreadsheet · chart.* Only where it makes sense,
never on every reply.

The conversation's returning empty state occasionally carries an example in its
mono line — *"Try: summarise this week's changes as a client update."*

### 6c. Tool actions in the conversation

When a tool is used, the conversation shows what tool, what it did, and — for
anything mutative or egressive — a confirm step before it acts. Never a silent
action. Anything that touched the network also appears in Activity.

### 6e. Comparing models

**Never show two answers by default.** Two replies per turn doubles latency and cost,
and forces a comparison nobody asked for.

The local model answers. Beneath it, a quiet control: *Compare with Claude.* One
click appends the second answer as an alternative, switched with the same header
arrows as redo-with-model.

**Proactive but rare:** where a local answer is likely weak — long reasoning, recent
facts, code — offer rather than act. One dismissible line: *"This is at the edge of
what the local model does well. Check with Claude?"* This teaches the boundary
instead of letting the user discover it by being wrong.

**The product is the pattern, not the pair.** After enough comparisons, Settings can
report: *"For writing, local matched cloud 26 of 30 times. For code, 11 of 30."* A
fact about the user's own work that no other tool can produce.

### 6f. Searching with a local model

Local inference protects the conversation, not the query. Someone who believes
"I chose local, so this is private" is wrong in exactly the cases they care most
about. The design must make the moment visible rather than paper over it.

Zaram does not search silently. It asks:

> *I'd need to search the web for this. Your question would go to DuckDuckGo.
> Your memory would not.*
> **Search** · **Answer without searching**

*Answer without searching* must be real — the local model's answer with an honest
note about its cutoff. *Don't ask again for this kind of question* turns forty
interruptions into one decision, per-host, default deny.

For sensitive queries, offer redaction: *"Your question mentions a name. Search
without it?"* — showing the rewritten query before sending.

### 6g. Ingestion failures

A single line in Knowledge — *3 files didn't index* — expanding to what and why,
with retry. And surfaced **in the conversation** the first time it matters:
*"I couldn't read scan-04.pdf — it's an image with no text layer."* That is where
the user is when the gap actually costs them something.

Silent ingestion failure is the most likely reason a user concludes "it doesn't
know my stuff" and leaves.

### 6h. The returning state

One mono line, not a dashboard: *14 new facts from 3 sources · the Meridian deploy
target changed · 0 bytes left this device.*

Dismissible and skippable. The composer stays focused — someone who wants to type
immediately never experiences it as friction.

### 7. Settings

Models · Privacy · Appearance · Storage · **Tools** as a segmented control, not a
sidebar. The Tools pane lists installed MCP servers with their risk tier
(generative / mutative / egressive), hardware grading, and per-server permission
scope.
The Privacy pane is the one that matters: default scope for new sources, what
may leave, egress retention, and a prominent local kill switch.

### 8. Command palette

⌘K overlay. Three states: empty, typing, results. Results grouped by kind with
mono section labels.

### 8b. Fact history

Not a separate timeline screen. **Inside the fact detail panel**: this fact, its
prior version, and when it changed. *"In March this said staging-2. You corrected
it on 18 April."*

Contextual, costs no navigation, and appears exactly where curiosity strikes. The
correction data already exists — this is presentation, not new capability.

### 9. Constellation — secondary, on demand

Flat 2D only. Dots clustered by source, sized by recall frequency, connected by
faint thin lines. Time slider showing how memory accumulated. Sparse and
legible.

This is a trust artifact, not navigation. It should feel calm, never impressive.
**No 3D, no force-directed layout, no bloom or glow** — the machine is running
local inference and GPU budget is not free.

---

## Rules everywhere

- Every list has a designed empty state with a recovery action. Never a dead end.
- Keyboard hints shown persistently in a mono footer on list screens:
  `↑↓ navigate · ↵ open · esc close · / search`
- Virtualise any list that can exceed a few hundred rows. Assume tens of
  thousands of facts.
- Where the system reports on itself, say it plainly. "Recalled because it
  shares a source with your question" — not a confidence number.
- Never claim absolute security. State what is verifiable: inference ran
  locally, index is on disk, egress is logged.

## Out of scope

Agents, code studio, extensions marketplace, updates feed, voice, document
generation, multi-user, sharing, bulk multi-select, memory export.

## Build order

1. Foundation — tokens, motion, component inventory (one pass)
2. Shell — persistent bar and orb, conversation as shell not route
3. Memory list with fake data
4. Filters, live count, view toggle
5. Fact detail panel
6. Activity
7. Conversation thread, citation chips, recall strip
8. First run and sources
9. Settings, privacy pane first
10. Command palette
11. Constellation
