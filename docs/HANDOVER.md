# Handover — 15 August 2026

Paste the block below into a new session. It is written to be read cold.

---

```
You are continuing work on Zaram (C:\Zaram), on branch Zaram-V0.1.

READ FIRST, IN THIS ORDER
  1. CLAUDE.md — the contract. Rules, scope, vocabulary. Authority on rules.
  2. docs/MILESTONES.md — the handoff. Read "Current state — 15 August 2026"
     at the top, then "What this session built — 15 August" and
     "What is next — reordered 15 August". Older blocks below are still true
     about packaging, signing, the API binding and the installer.
  3. docs/UI-SPEC.md — the interface.

BEFORE RUNNING ANYTHING
  - Run pytest as `.venv\Scripts\python.exe -m pytest` from the repo root.
    Bare `python` on PATH is a broken shim and reports phantom failures.
  - Whatever is on port 8420 is probably stale. Confirm build.commit_short
    matches `git rev-parse --short HEAD` before believing any response.
    Restart: kill the listener on 8420, then `backend/start.bat`.
  - The frontend dev server is on 5173 and binds IPv6 — use `localhost:5173`,
    not `127.0.0.1:5173`, or it will look down when it is up.

MEASURED STATE (15 August, all from a run)
  backend 1987 passed / 0 failed / 9 skipped · frontend 155 across 20 files ·
  typecheck clean · drive-settings.mjs 14/14 · drive-composer.mjs 9/9 ·
  64 commits ahead of origin/main.

THE FIRST THING TO DO
  **Nothing from the 15 August session is committed.** 44 changed or new files.
  Read "What this session built" and commit in coherent pieces. Do not commit
  backend/settings.json — it is gitignored alongside the egress policy.

WHAT THE LAST SESSION DID
  Settings became operable: kill switch, per-source egress rules, web search
  with scope, routing preference, model choice, several cloud providers at
  once, speech, renderer. Web search now returns real results. The local model
  preloads at launch so "Warming up" is once per session. Chat gained copy,
  edit and ask-again; generated files gained Preview beside Download.

  Getting there found FIVE features that were complete, tested, and could not
  happen — the unmounted /providers router, a hardcoded model in chatClient.ts
  that overrode every routing decision, a KnowledgeRuntime with no internet
  runtime, a live AttributeError in InternetRuntimeImpl.initialize(), and a
  routing preference control that was read by nothing. Plus one worse: web
  search APPEARED to work, because duckduckgo_search returns an empty list
  without raising. All six are written up in MILESTONES.

HOW TO WORK HERE
  - Verify by seeing it work. A feature's tests can all pass while the feature
    cannot happen; that has now cost this project ten times, five of them in
    one day. Use the drive-*.mjs scripts in frontend/scripts — they run a real
    browser and they have caught what unit tests could not.
  - When a doc and the codebase disagree, the codebase wins — say so.
  - A failing test is fixed or deleted, never left. A test that asserts nothing
    is worse than no test.
  - Never write a number you have not measured. A fabricated number is worse
    than a stale one, because nothing about it looks old.
  - Do not handle the maintainer's API keys. They paste them; you tell them
    where to put them. A key pasted into chat should be rotated.

NEXT, IN ORDER (see "What is next — reordered 15 August")
  0a. Name the model that answered, on every reply. CLAUDE.md requires it,
      nothing does it, and the maintainer has asked twice. Highest value left.
  0b. Voice selection, male by default. Read /voice/voices before choosing —
      do not hardcode a voice that may not be installed.
  0c. Persist cloud keys with Electron safeStorage.
  0d. Task-based routing across providers. Project type supplies a PRIOR, never
      a decision, and must never cause a silent cloud route.
  0e. Gemini's URL normalisation (small) and an Anthropic adapter (bounded).
  0f. Search relevance — every question currently also queries GitHub.

SPEECH — the maintainer's north star, set 15 August
  "Speech follows the text without lag. The user never waits. Zaram responds as
  fast as it can, and the user can interrupt by typing or by microphone."
  Full architecture, measurements and open questions: docs/SPEECH-ARCHITECTURE.md
  Barge-in is DONE. Still open, in the order I would take them:
   - Per-phoneme timings from Kokoro's `pred_dur` (currently a word's phonemes
     are distributed evenly across its span). DECIDE THIS WITH TWO VIDEOS AT
     320px, not with a duration table — the pointer-gaze lesson applies exactly.
   - Resume mid-utterance after a barge-in. The unit of playback is a sentence,
     so an interruption discards the current one. Whether that matters is a
     question about people, not architecture.
   - /voice/stream (SSE) exists and is unused. Note Kokoro is NOT a streaming
     model — those chunks are chunks of a finished clip, so moving chunking
     backend-side changes where the split happens, not when the first sound
     arrives. Do not "fix" this without checking that first.

UNVERIFIED BY HUMAN EYES (this shell can screenshot via
frontend/scripts/*.mjs, so there is no excuse — but these specific ones were
built late and only measured)
   - The artifact Preview panel over the orb/avatar area. Geometry probe is
     scripts/probe-preview-geometry.mjs; it SKIPS when the browser profile
     shows no artifacts, which is what happened on the last run. Generate a
     document, re-run, look at scripts/drive-shots/preview-over-orb.png.
   - Barge-in. No script drives it yet.

STILL UNVERIFIED BY A HUMAN
  A real cloud round trip. LM Studio on loopback proves the connect path
  without a credential; nobody has connected a live key, selected a cloud
  model and watched a reply arrive.

THE BLOCKER CLAUDE.md NAMES, UNCHANGED
  "A stranger cannot install this." Packaging, not capability. None of the
  above moves it.
```

---

## Testing cloud and web search

The non-obvious part, which cost the maintainer an afternoon:

**Connecting a provider does not permit it.** The key is stored; the
destination still has no egress rule, and the default is refuse. So *Look for
models* is denied, the list comes back empty, and no cloud model can be
selected — with nothing on screen explaining why. The Cloud section now names
the host and offers a one-click **Allow**, but the sequence is:

1. Settings → Cloud providers → choose provider, paste key, **Connect**
2. **Allow** its host when the amber line offers it
3. Models → **Look for models** — this is the network call
4. Choose one under *Which model answers*

Until step 4, Zaram answers locally and says so truthfully.

> *"No, nothing in this conversation has left the device to reach the model,
> gemma4:12b."*

That reply is **correct** while `default_model` is null. It is `core/identity.py`
working, not a bug.

For web search: it is on, `duckduckgo.com` is allowed, and the question must
actually look like it needs live information — `needs_search()` decides.
"Are you connected to the cloud?" is not such a question, so no search runs and
nothing leaves.

## Prompt for generating the robot's LED face sprite sheet

For ChatGPT's image tool, Nano Banana, or any image model. Written against the
VRM constraint that actually governs it — see the note after the prompt.

```
A sprite sheet for a robot character's LED face panel, drawn as flat vector
emissive graphics on a pure black background.

Layout: a 4 x 3 grid, 12 equal cells, 2048 x 1536 px total (each cell 512 x 512).
No gutters, no padding, no labels, no grid lines — cells must tile exactly edge
to edge so a UV offset lands cleanly on each one.

Every cell shows only eyes and mouth as glowing cyan (#78DCF0) shapes on black.
No face outline, no head, no nose, no shading, no gradients, no texture, no
3D rendering. Think a dot-matrix or OLED panel: simple, bold, high contrast,
readable at 200 px.

The 12 cells, in reading order (left to right, top to bottom):
 1. neutral — two horizontal ovals, mouth a short flat line
 2. blink — two horizontal lines, mouth unchanged
 3. happy — eyes as upward arcs, mouth a wide upward curve
 4. thinking — eyes narrowed, one slightly higher, mouth a small flat line
 5. listening — eyes wide circles, mouth a small neutral dot
 6. speaking A — mouth a wide open oval, eyes neutral
 7. speaking E — mouth a wide flat rectangle, eyes neutral
 8. speaking I — mouth a narrow flat slit, eyes neutral
 9. speaking O — mouth a round circle, eyes neutral
10. speaking U — mouth a small tight oval, eyes neutral
11. surprised — eyes large circles, mouth a small round o
12. sleeping — eyes two downward arcs, mouth a flat line

Keep eye position and size identical across every cell except where the
expression requires a change, so the face does not appear to shift between
frames. Consistent stroke weight throughout. Pure black (#000000) background.
```

**Why 12 cells and why those.** VRM 1.0 expressions bind to a material's UV
**offset and scale** via `textureTransformBind` — the spec's own example is
blink as a UV shift. So each expression selects a cell. Five of the twelve are
the visemes `aa ee ih oh ou` that `src/lib/visemes.ts` already drives, which is
why the mouth shapes are named that way rather than by emotion.

**Two constraints that will bite if they are not designed in.**

- **The LED panel must be its own material.** The bind applies the same offset
  to *every* UV-sampling texture on the target material, so if the face shares a
  material with the body, expressions will slide the body texture too.
- **Drive the weight to 0 or 1, never in between.** The weight interpolates the
  offset, so a half-weight lands between two cells and shows two half-faces.
  This matters concretely: `VrmAvatar.tsx` currently *eases* visemes with
  `approachRate(dt, 1/15)`, because a snapped morph target reads as a puppet.
  For a sprite-sheet face that easing produces garbage mid-frames, so the mouth
  path needs a hard cut for a robot avatar. Worth knowing before commissioning
  the asset rather than after.

**Also true, and awkward:** an image model will not reliably produce an exactly
aligned 4x3 grid. Expect to composite the cells into the sheet by hand, or
generate each cell separately at 512x512 and assemble them. Ask for the cells
individually if the grid comes back uneven — that is the more reliable route.
