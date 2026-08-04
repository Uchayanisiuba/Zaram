# Zaram — UI spec

Four surfaces, each answering a different question the user actually has.

| Surface | The question it answers |
|---|---|
| **Memory** | What do you know about me? |
| **Knowledge** | What have you read? |
| **Activity** | What did you send? |
| **Settings** | How do you behave? |

**Every surface that shows you something also lets you change it.** That is the
difference between transparency theatre and the real thing: memory can be
corrected, sources can be scoped, egress can be cut, behaviour can be tuned.

> If you find yourself building a screen that only displays, it either needs a
> control or it does not need to exist.

Precedence: this file governs layout, behaviour, data model and scope. Design
exports in `docs/design/` govern visual language only. Where they conflict, this
file wins — the exports were made for an earlier, wider product design.

Each surface below marks what is **built**, **partial** and **not built**,
checked against the running code rather than intent. Where this file and the
codebase disagree, **the codebase wins** — fix this file rather than building to
a stale claim.

---

## Memory — what it knows about me, and can I change it

The transparency surface. Where a user goes to check, correct, or delete what
Zaram has learned.

**Core**

- The list — fact, source dot, and a mono meta line:
  `filename · date · recalled 41×`
- Three views on the same data: by source, by time, by recall
- Filters: all / local only / corrected / pinned, with a live count
- Sources rail down the left: dot + name + fact count, click to filter
- Search across facts

**Per fact, on click**

- Full text, the source passage highlighted, when learned, how often recalled
- Why it was recalled, **in plain language — not a similarity score**
- Related facts, clickable
- Actions: **Correct · Forget · Pin**

**Correction produces supersession, never deletion.** The old fact stays, struck
through, marked `superseded 18 apr · you corrected this`. Excluded from recall,
visible in the UI. That is the trust artifact — a system that shows you where it
was wrong is one you will believe when it says it is right.

**Tweaks that belong here:** how far back recall reaches, how many facts get
injected per reply, and whether a source's facts participate in recall at all.

### State

- ✅ Supersession in the store and the engine. Correcting writes a replacement,
  evicts the original from the index, keeps it visible, and survives a restart.
- ✅ Pinning — pinned facts sort ahead of merely-recent ones and survive a
  correction.
- ✅ `POST /memory/{id}/correct`, `POST /memory/{id}/pin`, `DELETE /memory/{id}`
- ⚠️ The workspace lists real records, but has no Correct/Pin controls, no three
  views, no filters, no sources rail and no search.
- ❌ `recalled 41×` — `access_count` is stored but never surfaced.
- ❌ Related facts. No edges are stored between records.
- ❌ "Why it was recalled" in plain language. Only a score exists, and the spec
  is explicit that a score is not an answer to that question.

---

## Knowledge — what it has read

Memory holds derived facts. Knowledge holds the material they came from.
Different questions, which is why they are separate surfaces.

**Core**

- Drag-and-drop to index a folder
- Each source: name, file count, fact count, last indexed, scope toggle —
  *local only* / *may send*
- Indexing progress, with **failures visible rather than silent**
- Open a document, see which passages became facts

**The one thing most tools get wrong: show what failed to ingest.** A scanned
PDF that produced nothing, a file type that was not handled. Silent ingestion
failure is the single most likely reason a user concludes "it does not know my
stuff" and leaves.

**Tweaks:** re-index, remove a source (and decide what happens to its facts),
scope per source, exclude patterns.

### State

- ❌ Nothing built. Folder ingest is in v1 scope and has no implementation.
  This is the largest remaining gap in the v1 list.

---

## Activity — what left this machine

Not knowledge, not history — **evidence**. A different mental posture: someone
here is checking, not exploring.

**Core**

- Dense mono table: `timestamp · what was sent · provider · why · bytes`
- The summary line: "0 bytes left this device today"
- Date and provider filters
- **Click a row to see the literal outbound text** — the full request, not a
  summary. That is what makes it evidence rather than a claim.
- Export the log

**Tweaks:** retention period, per-host policy (default deny), and the kill
switch — cut all outbound now.

**The honest caveat has to appear here**, on the screen and not only in a
docstring: the hash chain detects tampering by anything that did not go through
the append path. It cannot stop someone who already has write access to the
file. The UI must say what is verifiable and no more.

### State

- ✅ Built, reading the real egress log.
- ✅ Literal outbound text on row click.
- ✅ Per-host allow / ask / deny, in the rail and in the detail panel.
- ✅ Retention (7 / 30 / 90 / keep all). Pruning is itself recorded, so the log
  can always show that entries were removed even when it can no longer show
  what they were.
- ✅ Kill switch — sets every known host to deny rather than flipping a hidden
  global flag, so the resulting state stays visible per host.
- ✅ Integrity check with its caveat rendered on screen.
- ⚠️ Colour is deliberately inverted from the obvious: `BLOCKED` is the calm
  colour and `SENT` is the one that draws the eye. On a privacy surface, traffic
  leaving is the exception worth noticing; colouring a send green for
  "succeeded" would invert the meaning the user came here for.
- ❌ Export the log.
- ❌ Date filter. Host filter exists.

---

## Settings

Five panes. **Privacy is the one that matters and should be first.**

| Pane | Contents |
|---|---|
| **Privacy** | Default scope for new sources, what may leave, egress retention, the kill switch, the confirm-before-send toggle |
| **Models** | Which local, which cloud, keys, which is default. Plain language, no quantization sliders in the main path |
| **Tools** | Installed MCP servers with their **risk tier** (generative / mutative / egressive), hardware grading, per-server permission scope. This is where safety-graded curation lives |
| **Appearance** | Theme, density, motion budget, including quiet mode |
| **Storage** | Where the Spine lives, its size, export, delete-everything |

### State

- ⚠️ One flat read-only pane. It reports real `/health` data and marks unbuilt
  controls "not built" rather than showing inert toggles — a settings screen
  full of dead switches tells the user they have control they do not have, and
  on a privacy product that is the worst thing to be wrong about.
- ❌ The five-pane segmented control.
- ❌ Every control listed above. Retention and per-host policy currently live
  only in Activity.
- ❌ Tools pane. MCP is the tool protocol, but no servers are installed and the
  risk tiers are an organising principle rather than code.

---

## The Orb

One object, one meaning. It reports system state — idle, thinking, routing to
cloud, local only. **It does not perform, and it is not the application.**

- Landing: the centrepiece, four orbital nodes, and a self-dismissing first-run
  hint — "Click the orb to begin".
- Everywhere else: the same orb at working size in the top bar, inside its
  status ring.
- **Clicking it always does the same thing** — returns to the conversation at
  full size. It previously slid a narrow chat column in beside the current
  workspace, so one gesture produced two different results depending on where
  the user was standing.

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

The mono is what gives the product its instrument character. If the system is
reporting a fact about itself, it is mono.

### Materials — glass vs opaque

The distinction is load-bearing. Translucency goes on chrome only; content
surfaces stay opaque. This separates a sophisticated dark UI from a gimmicky
one, and keeps blur off scrolling regions on a machine that is also running
local inference.

**Translucent** (24px blur, 72% opacity, 0.5px top edge highlight): left rail,
top toolbar, persistent bottom bar, popovers, command palette, detail panel.

**Opaque** (no blur, no translucency): message thread, memory list rows,
activity table, cards, metric tiles.

### Motion budget

Transitions ≤200ms. No spring physics on list rows. No continuous animation
anywhere except the orb while actively processing. Respect
`prefers-reduced-motion` — it disables the orb pulse too.

### Component inventory

`MetricCard` · `FilterChip` (default / active / disabled) · `SourceRow` (dot +
label + count) · `MemoryRow` (default / pinned / superseded / hover / selected)
· `CitationChip` · `Button` (primary / secondary / ghost) · `SearchField` ·
`EmptyState` (message + recovery action) · `Orb`

---

## The shell

The conversation should be a **persistent shell, not a route**. Navigating to
Memory, Activity or Settings must not unmount or reset it.

⚠️ It is currently a route. `App.tsx` swaps workspaces by conditional render, so
the conversation unmounts on navigation. Fix this before building screens that
assume continuity.

---

## Rules everywhere

- **Calm over delight.** Motion has a budget. Quiet mode ships from the start.
- **Density beats animation** on any surface used daily.
- **The target user is not technical.** No model filenames, quantization
  settings or context-length sliders in the primary path — put them behind an
  advanced view.
- **Show routing decisions in plain language:** what handled this, and why.
- **Never claim absolute security.** No "perfectly sealed", no "zero leakage".
  State what is verifiable: inference ran locally, the index is on disk, egress
  is logged.
- **An absent measurement must never read as a measured zero.** Before the
  egress log existed, `bytes_left_device_today` returned `null`, not `0`.
- **A citation the answer did not use is a false claim of provenance.** Recall
  below the relevance threshold is not shown. Irrelevant citations teach the
  user that citations mean nothing, and after that the real ones cannot help.
- **A question is not a fact.** Questions are never stored in the Spine, or
  Zaram ends up citing the user's own words back to them as a source.

---

## Out of scope until v1 ships

Agents, IDE integration, extensions marketplace, updates feed, voice, document
generation, multi-user, and any additional workspace.

Dormant code exists for several of these. Finding it is not permission to
activate it.
