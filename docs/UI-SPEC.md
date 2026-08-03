# Zaram — UI spec

Covers the full v1 interface.

Precedence: this file governs layout, behaviour, data model and scope. Design
exports in `docs/design/` govern visual language only — colours, spacing, type,
component appearance. Where they conflict, this file wins. The exports were made
for an earlier, wider product design; their screens are not the target.

> Implementation status against this spec — including where the current build
> contradicts it — is recorded in the appendix at the end. Read it before
> assuming any section here is already satisfied.

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
Conversation · Memory · Activity · Sources, with Settings bottom-anchored.
Active item takes a cyan left indicator bar and raised background, not a
filled pill.

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

### 7. Settings

Models · Privacy · Appearance · Storage as a segmented control, not a sidebar.
The Privacy pane is the one that matters: default scope for new sources, what
may leave, egress retention, and a prominent local kill switch.

### 8. Command palette

⌘K overlay. Three states: empty, typing, results. Results grouped by kind with
mono section labels.

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

---

## Appendix — implementation status, 3 August 2026

The spec above is the target. This records what is actually built, so no section
above is mistaken for done. Nothing in this appendix overrides the spec.

## Satisfied

- **Provenance.** Each recalled fact emits a source event; the conversation
  lists them under the reply. `backend/tests/test_provenance_invariant.py`
  fails if context is ever injected without attribution.
- **Citations are inspectable.** Clicking one opens the stored record, with
  Escape to close, focus trapped, and focus returned to the citation.
- **Real data only.** The Runtime Panel (fabricated telemetry, invented agent),
  the `Local` / `Claude 3.5` / `Synced` pills, hardcoded nav badges and seven
  empty accessibility files have all been deleted rather than left to imply
  function that does not exist.
- **Never claim absolute security.** The status line says "Inference runs on
  this machine and nothing is sent out", which is checkable.
- **Reduced motion** is honoured throughout.
- **The Spine persists** and recall works across a restart.

## Contradicts the spec — must be undone

**The orb.** The spec says: a 20px circle at the left of the persistent bar,
four states, "it never grows, never centres, never reacts to cursor position,
never speaks. It is an instrument light, not a character. This is deliberate —
do not reintroduce expressive behaviour."

What is built is the opposite: a 320px orb centred on the landing surface and an
84px orb centred in the top bar, both with continuous breathing, an amplified
glow, an animated inner pulse dot, orbiting satellite navigation, and a
click-to-open interaction. It grows, it centres, and it is the largest element
in the product.

This was built before the spec was available, and successive rounds of tuning
made it more expressive rather than less. It is the single largest divergence
and it is not a small revert: the landing surface as a whole is built around it.

**Conversation is still a route, not a shell.** The spec requires this be fixed
before any screen is built. Navigating away unmounts it; messages survive in a
store but in-flight replies are cancelled.

**Materials.** The spec puts translucency on chrome only, with content surfaces
opaque. Everything is currently glass, including scrolling content.

**Motion budget.** The spec allows ≤200ms transitions, no spring physics, and no
continuous animation except the orb while processing. Springs are used
throughout and the orb breathes continuously at rest.

**Colour.** The spec's accent is cyan `#5EE7DC` with `#8B7FD4` for cloud. The
build uses indigo `#6366f1` throughout.

**Navigation.** The rail is Home · Memory · Knowledge · Settings. The spec calls
for Conversation · Memory · Activity · Sources with Settings bottom-anchored.

## Not built

- The data model. `MemoryRecord` has no `recallCount`, `supersededBy`,
  `supersededAt`, `pinned`, `relatedIds` or `recallReason`. The spec is explicit
  that these must exist from the first write, and the Spine is already
  accumulating records without them.
- `correctFact()`. Only `deleteFact()` exists — correction currently destroys
  the row rather than superseding it, which is precisely what the spec forbids.
  Superseded rows, the "most differentiated element in the product", cannot be
  rendered because the state is not recorded.
- Activity, Sources, First run, Constellation, the privacy timer, metric cards,
  filter chips, view toggles, the component inventory.
- The egress log, which Activity displays.
- Settings and the workspace pages are unwired and still render sample data.

## Consequence for sequencing

The data model is the urgent item. Every day the Spine runs without
`recallCount` and `supersededBy` is a day of history that cannot be recovered —
the spec says as much, and it is already true of the records stored so far.
That work is cheap now and impossible to backfill.
