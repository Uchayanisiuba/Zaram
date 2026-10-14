# Zaram — Feature Menu (v0.1.0-alpha.5)

*Updated: 12 October 2026 — adds the pages, pictures, project and avatar work of 10–12 October*

---

## Navigation Overview

Zaram has **six orbital nodes** around the Living Orb, each answering a different user question:

| Node | Purpose | Key Features |
|------|---------|--------------|
| **Work** | What have I made? | Documents, spreadsheets, charts, generated apps — each with its conversation & sources |
| **Project** | How is it grouped? | Create/name/type projects, assign artifacts & facts, delete with scoping prompts |
| **Memory** | What do you know about me? | Fact list with provenance, correction/forget/pin, recall view, superseded history |
| **Knowledge** | What have you read? | Folder indexing, drop/paste/upload, per-folder privacy scope, domains, failure retry |
| **Activity** | What left this device? | Egress log with bytes, privacy timer, per-host policy, kill switch |
| **Settings** | How do you behave? | Models, routing, privacy, tools, appearance, storage, pairing |

---

## Recent Major Features (Last Development Cycle)

### 🆕 **10–12 October 2026**

#### Pages, apps and games
- **Tested starting points** — A Minecraft-style voxel world, a 3D racer and a 3D platformer, each played before it shipped; the model edits the starter (SEARCH/REPLACE) instead of re-inventing collision. "From scratch" and "a website *about* a go-kart track" are honoured; "our racing game" in a sentence about a site is not a request for one
- **Photos from the web, found not drawn** — Say "source images online" and the page gets real, credited photos (Openverse, Wikimedia Commons as backup), one consent question per source, paced under the free limit and cached. The model decides whether a page needs photos at all; a game or tool gets none
- **Pictures in documents** — Ask for a brochure or report with web photos and the file carries them, with a Photo credits section. Attached pictures go into pages, invoices (logo), CVs (photo) and decks (slide image), in HTML, Word and PowerPoint
- **A request for web pictures is never a drawing** — "Draw a dog" still draws; "get images online" never reaches the image generator
- **Your pictures survive reopening a conversation** — Kept per conversation, 1 GB cap with pruning, "remove pictures" in History
- **Attached text does not steer the plan** — A screenshot's words ("Select / Preview / Save") no longer turn a page request into a tool request; the model is told picture *names*, never bytes

#### Projects and apps
- **Zaram knows the open project** — "What are the unfinished tasks in Ride Share?" reads the project's folder instead of searching the web; "search online…" still searches
- **A started app opens itself** — Run app / Run all services open the front end in Zaram's own browser pane once it responds
- **Project row** — Change folder · Run app · Run all services, with icons
- **"Allow for this project" sticks** — The run-commands permission now covers `start_app_stack`; no more re-asking until "Allow for this conversation"

#### Avatar
- **Coding view** — The camera eases back while the avatar types so the head and hands are in frame, then returns
- **Neon keyboard** — A procedural holographic keyboard spawns under the hands in the coding state (space bar toward the avatar, one fixed size, wide enough that the reaching arm stays over it)

#### Local models
- **The model on TabbyAPI is loaded at launch** — Zaram asks the server to load your chosen model (`/v1/model/load`) as soon as it is up, instead of the first message paying the cold start; never swaps a model that is already there

### 🎯 **Memory & Recall** 
- **Citations as history** — TurnNotes keeps references (kind, id, number); `conversations/citations.py` resolves them against Spine on reopen with statuses: *live / corrected / deleted / recorded (web) / unchecked*
- **Fact correction supersedes, never deletes** — `correctFact(id, newText)` creates new fact, sets `supersededBy` on old; strikethrough rendering in Memory list
- **Purge by range** — Remove facts before/after/between dates or all; dry-run count shown first; superseded versions included
- **Recall strip** — Collapsed by default (`3 facts recalled`); individual fact chips dismissible; "×" excludes fact from next turn
- **Provenance in generated docs** — Claims in generated artifacts link back to sources; origin tagging (user_document / conversation / generated) deprioritizes Zaram's own output

### 📁 **Knowledge Ingestion (Sources)**
- **Four ingestion paths** — Folder scan, drag-drop, paste (≥40 chars), file upload
- **Per-folder privacy scope** — Toggle: *Local only* / *May be sent to cloud models*
- **Knowledge Domains** — Named, described collections (many-to-many, not a tree); each is a retrieval scope + shareable unit
- **Failure visibility** — Problems sort first; each states reason + remedy + cost (e.g., "scan-04.pdf: image with no text layer — needs OCR: `pip install zaram[ingest]` (321 MB)")
- **Retry per file** — Common fix: file was open in Word; retry button on every failed item

### 🤖 **Model Routing & Providers**
- **Three tiers of control** — Default (Zaram picks) → Preference (Prefer local/Auto/Prefer cloud) → Per-task (chat, coding, vision, long-document)
- **Locality-first picker** — Models grouped: *On this machine* / *Cloud — your prompt leaves* / *Where this runs not established*; free-tier cloud models never auto-selected
- **Residency gate** — Model > VRAM budget dropped; unknown fit survives (won't leave machine with no default)
- **Capability as precondition** — Vision/Image/Video are binary gates, not scores; modality never decides *membership*, only *ordering*
- **TabbyAPI self-start** — `providers/model_servers.py` finds, probes, starts Ollama/Tabby; rescans after Tabby answers; per-server *Starts with Zaram* switch in Settings
- **Hostname fix** — `127.0.0.1` not `localhost` for Ollama (2,105 ms → 73 ms per embedding on Windows)

### 🎙️ **Voice & Embodiment** *(requires `pip install zaram[voice]` ~905 MB / `zaram[mic]` ~81 MB)*
- **Kokoro TTS** — 54 voices, CPU under 2.5 GB, Apache 2.0; speech starts on first stable sentence (16.6s before generation finished measured)
- **Faster-Whisper STT** — Local only; cloud speech recognition prohibited (webkitSpeechRecognition streams audio to Google)
- **Avatar renderer** — VRM 1.0 character (helmeted robot, dot-matrix LED face); texture-transform binds (binary weights, one expression per material)
- **State-driven only** — Rim light: slate (idle), cyan (working); face constant `#818cf8` (indigo) — never reports routing
- **Speech follows renderer** — Avatar selected → replies speak; Orb → silent unless asked
- **Voice manifest** — Dated local `voices.manifest.json` (54 voices, offline); VoiceBrowser in Settings (searchable, grouped by language, install status)

### 🖼️ **Image Generation & Reading**
- **Vision reading (local)** — Ollama serves vision models; receipt/contract photo never leaves machine
- **Deterministic manipulation** — Crop, rotate, resize, convert via Pillow (generative tier, no overwrite)
- **Modality as capability gate** — Binary precondition, not ranking score; filters candidates before ranking
- **Image consent class** — Separate from chat; connecting provider for text ≠ consent for photos
- **No video generation** — Deferred (file sizes, maintenance)

### 🛠️ **Tools & MCP (Model Context Protocol)**
- **MCP Client first** — Attach any server (DaVinci, Office, DB, custom); Zaram maintains none
- **Risk tiers** — Generative (ships v1) / Mutative (undo, confirm, sandbox) / Egressive (egress log, per-source policy)
- **Tool selection by embeddings** — `bge-m3` resident; similarity ranks candidates; permission gate runs *after* selection
- **Built-in servers** — `zaram-self` (settings control), `zaram-memory` (Spine as tools, paired clients only)
- **Per-tool consent** — Confirm once per destination + data class, then remember (Rule 7j)

### 📦 **Projects & Packs**
- **Project = fact scope** — `project:<id>` on Spine facts, queued plan, Knowledge sources; not a file manager
- **Pack activation** — Project type chooses pack (documents, 3D/Unreal/Blender); packs = parsers + tools + templates + routing exemplars
- **Terminal integration** — Shared `TerminalTools` (kernel-held); 3 routes under `/projects/{id}/terminal`; shells close at shutdown
- **Unfinished tasks on empty chat** — Last project's open tasks + "Run all in order" + "Pick up where you left off"

### 🔐 **Privacy & Custody**
- **Egress log** — Append-only, tamper-evident; every byte (chat + tools) logged
- **Per-source policy** — Default deny; Allow / Ask / Never per host; exceptions shown as count + expandable list
- **Kill switch** — One tap cuts all egress; restores rules exactly on off
- **API secret** — Per-launch 32-byte credential; Electron mints, hands to backend (env) + renderer (IPC); `RequireApiSecret` middleware on all routes including `/health`
- **Host header guard** — Blocks DNS rebinding (`GET /memory` returned 200 before guard)
- **Paired clients** — Credential from Settings (revocable); memory routes only; egress logged as `client:<name>`

### 📄 **Document Generation (Generative Tier)**
- **HTML-first pipeline** — Generate HTML → WeasyPrint (PDF) / python-docx / openpyxl / python-pptx
- **Formats** — .docx, .pdf, .md, .xlsx, .pptx, charts (matplotlib), diagrams (Mermaid)
- **Preview** — PDF native in v1; .docx/.xlsx lightweight HTML render (v1.5)
- **No overwrite** — Filename collision increments or asks; files to dedicated output dir
- **Artifact staging** — Images wait in staging; user "Keeps" to promote to output

### 🌐 **Browser Pane**
- **BrowserView** — Own partition, policy in `browserPolicy.js` (42 tests)
- **Egress from Chromium** — `webRequest` → `POST /egress/browse` (Rule 3: backend gate can't see BrowserView fetches)
- **Shares preview surface** — Maximise/restore/close; full-screen corrected

### 🎨 **Design & Polish**
- **Contrast fix** --color-text-faint 1.6:1 → 4.5:1; --color-text-muted 3.5:1 → 5.0:1; `check:contrast` guard on every build
- **Landing scaling** — Ring fits window (asymmetric reserves); no lift on tall screens; caption anchored to ring bottom
- **Orbital motion** — 60° steps, 4°/sec, rAF throttled to 0.2° steps; freezes during chat; continuous on resume
- **Reduced motion** — Disables orb pulse, orbital animation, messengers

---

## Settings Sections (Detailed)

### Privacy
- Kill switch (cut all egress / restore rules)
- Per-source rules (Allow/Ask/Never + exceptions list)
- Browsing toggle (one decision for all sites)
- Web search (local-only / always scope; forcedByEnvironment / killSwitch warnings)
- Export everything (.zip: facts, egress entries, generated docs)
- Forget memory (by date range, dry-run count)

### Models
- Engine status (running/offline)
- Routing preference (Prefer local / Auto / Prefer cloud)
- Default model (Zaram decides / specific model)
- Model browser (capability badges, fit warnings, details drawer)
- Context window (per-model: server default / as much as fits)
- Advanced model field (type any catalogue ID)
- **Model Servers** — Ollama/Tabby install status, running state, Zaram-holds-models, Start button, auto-start switch

### Tools
- Installed MCP servers with risk tier badges
- Per-server permission scope (generative / mutative / egressive)
- Hardware grading (VRAM fit)
- Grant/revoke individual tools

### GitHub
- Connect by device code (a GitHub App you install on chosen repositories; no password and no token pass through the window)
- The sign-in stays on this computer, sealed to the Windows account; Disconnect forgets it (revoking on GitHub is a link away)
- Choose repositories on GitHub; list what Zaram can reach (private and read-only marked)
- Ask in conversation: push this project, open a pull request, file an issue — each asks every time, no standing yes; no force push

### Updates
- Asked once, default yes: check for a newer version when Zaram opens (a small card; changeable here) — an anonymous request for the release list, written to Activity, sending no version and nothing about you
- A newer version shows its size on the Download button; the installer is fetched through the egress gate (every redirect hop logged), checked against its published SHA-256, and kept
- Restart and install: Zaram closes, the installer runs silently and keeps your data, and the new version opens; nothing runs without that press
- The portable build and an unstamped development run are sent to the release page instead; Check now is always available

### Appearance
- Renderer: Orb / Avatar (frontend-only, not persisted)
- Reduced motion (respects `prefers-reduced-motion`)
- Theme: system / dark / light

### Storage
- Data directory location
- Spine size, egress log size
- Retention windows (egress: 30 days default)

### Pairing
- Issue/revoke credentials for paired clients (Claude Code, Cline, scripts)
- Paired clients access memory routes only

### Runs on Its Own
- Automation triggers (Settings section exists; Activity reporting undecided)

### Packs
- Available packs shown (greyed with honest hardware/licence/app grading)
- Project type activates pack

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + K` | Command palette |
| `Escape` | Return to landing / close panel |
| `Orb click` | Open/close conversation |
| `Drag node` | Reorder orbital nodes (landing only) |
| `Hover node` | Lift + label highlight |

---

## File Locations for Key Features

| Feature | Backend | Frontend |
|---------|---------|----------|
| Memory/Recall | `core/`, `runtimes/memory/` | `MemoryWorkspace.tsx`, `components/memory/` |
| Ingestion | `ingest/`, `knowledge/` | `KnowledgeWorkspace.tsx`, `DomainList.tsx` |
| Routing | `core/planner.py`, `providers/` | `SettingsWorkspace.tsx` (Models section) |
| Voice | `voice/`, `runtimes/speech/` | `VoiceBrowser.tsx`, `Embodiment.tsx` |
| Tools/MCP | `runtimes/mcp/`, `zaram_self.py` | `ToolsSection.tsx`, `ModelServers.tsx` |
| Projects | `projects/`, `artifacts/` | `ProjectWorkspace.tsx`, `TerminalPanel.tsx` |
| Egress/Privacy | `core/egress/` | `SettingsWorkspace.tsx` (Privacy section) |
| Generation | `artifacts/` | `WorkWorkspace.tsx`, `components/surfaces/` |

---

## Out of Scope (Post-v1)

- Mutative tools (file edits, VS Code, Blender/Unreal writes)
- Web search (awaits egress log + per-source policy)
- Agents, extensions marketplace, updates feed, multi-user, sharing
- Video generation
- Medical diagnosis, trading signals, legal advice (regulated)

---

## Getting Started

```powershell
# Full dev chain (clears ports, starts Vite + Electron + backend)
cd C:\Zaram
npm run dev

# Or manual backend for API testing
cd C:\Zaram\backend
$env:ZARAM_API_SECRET = (Get-Content api-secret).Trim()
venv\Scripts\python.exe main.py
# Then: curl.exe -H "X-Zaram-Auth: $env:ZARAM_API_SECRET" http://127.0.0.1:8420/health
```

---

## Key Design Principles (from CLAUDE.md)

1. **Never buy inference** — User brings keys/models
2. **Every fact has provenance** — Answer without citation = bug
3. **Everything that leaves is logged** — Including tool calls
4. **User can correct/delete any fact** — Answers change
5. **Default deny** — Nothing leaves without explicit per-item policy
6. **Tools confirm before acting** — Autonomy granted, never defaulted
7. **Spine exportable** — Open format, no lock-in
8. **Generation fails rather than invents** — Unresolved context → refusal
9. **Custody over consent** — `RequireApiSecret` + Host guard + per-launch secret

---

*This menu reflects the state as of alpha.5 (12 October 2026). Cloud image generation is set up but unproven on the maintainer's machine: NVIDIA's free Flux endpoint errors, so pictures need Together, fal.ai or another provider. The cold install of the published installer remains the standing blocker before wider testing.*