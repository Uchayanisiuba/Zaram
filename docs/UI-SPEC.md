# Zaram — UI specification

**Status:** describes what is built, as of 3 August 2026.

This file was created, not updated. A `UI-SPEC.md` was referred to several times
but has never existed in this repository — `git log --all --diff-filter=A`
finds no file by that name in any commit on any branch. What follows is written
from the interface as it actually stands, so that the next person reads a
description of the product rather than of an intention.

`CLAUDE.md` remains the contract. Where this file and `CLAUDE.md` disagree,
`CLAUDE.md` wins.

---

## Behavioural rules

These are the part of the specification that does not change when the layout
does. A surface may look like anything; it may not break these.

### 1. Provenance — nothing is asserted without a source

Every claim derived from the Spine carries a citation, and every citation can be
opened. An answer that cites nothing is a bug, not a terse answer.

Concretely:

- Each recalled memory emits one `source` event on the reply stream, and the
  conversation renders it beneath the answer it supported.
- A citation is a control, not a label: clicking it opens the stored record.
- Anything injected into a model's context must be accounted for by a source
  event. This is asserted by `backend/tests/test_provenance_invariant.py`,
  which fails if a future feature injects context without attribution.
- Internal citation markers (`[M1]`, `[S2]`) are for grounding the model. They
  are stripped before storage and before display; the user never sees them.

### 2. Correction — the user can remove anything, and answers change

The correction loop is the product. It is not a settings-screen feature.

- Deletion is offered where the fact is inspected, not in a separate manager.
  Open a citation, read what Zaram believes, remove it.
- Deletion removes the record from the Spine. It is not a display filter: the
  next question genuinely cannot recall it.
- A destructive action confirms before acting, and says what will change
  ("Answers will change") rather than only what will be destroyed.
- A deleted source stays visible in the transcript, struck through and labelled
  "forgotten". A citation that silently disappears leaves the user unsure
  whether anything happened.

### 3. Supersession — later facts win, earlier ones remain inspectable

> **Unverified.** This rule was named in the request that prompted this file,
> but no prior definition of it exists in the repository and none was supplied.
> What follows is the reading that fits the rest of the product. Correct it if
> it is wrong rather than letting it stand.

When a newer stored fact contradicts an older one, the newer governs the answer.
The older is not silently deleted — it is superseded, and remains inspectable
through the record that replaced it, so the user can see what changed and when.

Supersession is therefore distinct from correction: correction is the user
removing something, supersession is Zaram preferring the more recent of two
things the user said. Both must be visible; neither may be inferred silently.

**Not yet implemented.** Today recall ranks by relevance and recency without any
explicit supersession relationship between records.

### 4. Real data only — never fabricate a signal to fill a slot

If a field can only say one thing today, it says one thing today. If it can say
nothing, it is not shown.

This rule has already been applied by deletion, more than once:

- The Runtime Panel displayed a `LIVE` badge over hardcoded numbers, an invented
  `code-reviewer` agent and fictional reasoning steps. Removed.
- The top bar showed `Local`, `Claude 3.5` and `Synced`. No cloud provider is
  wired and there is no sync. All three removed, replaced by one indicator that
  reports real backend state.
- Nav badges showed fixed counts. Removed.
- Seven files in `src/accessibility/` were empty, which read as a completed
  accessibility layer. Removed.

The standard is higher for the privacy indicator than anywhere else: a
fabricated signal there would be trusted, which makes it worse than no
indicator at all.

### 5. Say what is verifiable

Never claim absolute security. "Inference runs on this machine and nothing is
sent out" is checkable. "Completely private" is not.

---

## What is built

### The shell

A single app frame with a shared backdrop — a radial gradient and a faint grid —
so that every glass surface has the same ground to refract. The landing used to
paint its own and the workspaces sat on flat colour, which is why they read as
two different applications.

Surfaces are translucent white films over that backdrop (`bg-white/5` in Project
B's idiom), not opaque dark fills.

| Region | Present on | Notes |
|---|---|---|
| Top bar | Every surface except the landing | Breadcrumb, the Orb, search, actions |
| Left rail | Every surface except the landing | Expands on hover; width is draggable |
| Bottom dock | Every surface except the landing | Home, Memory, Knowledge, Settings |
| Conversation | Any surface, on demand | Right-anchored, width is draggable |
| Source panels | Over the orb region | Cascaded, one per opened citation |

Build, Canvas and Plugins are out of scope for v1. Their surfaces are preserved,
unlinked, in `src/legacy/`.

### The Orb

One object, one definition of behaviour (`ORB_BEHAVIOUR` in `LivingOrb.tsx`),
appearing at two sizes. Only its diameter differs by surface; everything else —
breath amplitude, emphasis, the inner dot's ratio — is shared. Only one instance
is ever mounted.

Its job is to report system state. It is not a mascot and not a decoration:

| State | Shown when | Says |
|---|---|---|
| Local only | No route off the machine exists | "Inference runs on this machine and nothing is sent out." |
| Warming up | A request has produced nothing for 2.5s | "Starting the local model. The first reply of a session takes longer." |
| Thinking | Tokens are arriving | "Working on this machine." |
| Cloud enabled | Some request can leave | "Some requests can leave this machine. Check the egress log." |
| Offline | The backend is unreachable | "Zaram's engine is not running." |

All of it comes from `GET /health`. Nothing is inferred.

The status label appears **only while the conversation is open**, low on the
screen and clear of the orbital rings. At rest the landing stays quiet — there
is nothing to report until the user is about to ask something.

Before the conversation has ever been opened, a self-dismissing hint sits in the
same position: "Tap the orb to talk to Zaram". It waits 2.6 seconds so anyone
who acts immediately never sees it, breathes rather than pulses, and never
returns once the gesture has been used.

### The conversation

Right-anchored, over whatever surface is beneath it. Width depends on its role:
**45%** on the landing, where it is the main event; **28%** beside a workspace,
where it is an assistant. Each is remembered separately and both are draggable.

Replies stream token by token. Sources arrive before the tokens and appear as
they land. Failures are visible and specific: an unreachable backend is a
banner, a reply cut short keeps its partial text and is labelled.

### Source panels

Opening a citation presents a glass panel in the orb's region. The orb blurs and
recedes while any panel is open, and returns when the last one closes.

Multiple panels **cascade at a fixed offset**. They are not scattered and not
draggable. Free-floating windows become clutter past about four and hand the
user a window-management job, which is wrong for a non-technical audience.

Each panel shows the stored content, when it was stored, how many times it has
been recalled, and offers deletion. Escape closes, Tab is trapped inside, and
focus returns to the citation that opened it.

### Adjustable divisions

Every division between panels is draggable, through one shared component so they
behave identically. The visible line is 1px; the grab area is 9px. Keyboard
accessible: `role="separator"` with a live value, arrows to nudge, Shift for a
larger step, Home or double-click to reset. Sizes persist.

### Motion

Calm over delight. Spring physics arriving, quicker tweens leaving — a dismissal
that lingers feels unresponsive. Transitions are suppressed entirely while a
divider is being dragged, or the panel lags the cursor.

Everything honours `prefers-reduced-motion`: springs become short tweens, the
orbital dispersal becomes a fade, the hint stops breathing.

---

## Known gaps

Recorded so the specification is not mistaken for a completion report.

- **Supersession is not implemented**, and its definition above is unverified.
- **Settings and the workspace pages are not wired to the backend.** Memory and
  Knowledge still render sample data. They are the last surfaces in the shell
  standing in violation of rule 4, and they are next.
- **Knowledge has hardcoded colours** that the token change did not reach.
- **Speaker is distinguished by colour alone** in the transcript, which fails
  colourblind users and screen readers.
- **There is no egress log**, so "Cloud enabled" cannot yet be reached honestly.
- **No screenshots.** `docs/design/` is empty: this session had no browser
  automation available and Playwright is not installed. See
  `docs/design/README.md`.
