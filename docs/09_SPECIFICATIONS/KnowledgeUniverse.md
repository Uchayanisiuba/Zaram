# Knowledge Universe Specification

**Version:** 1.0  
**Status:** Accepted (RC2)  
**Dependencies:** `06_FRAMESTATE_SPEC.md`, `04_RENDERING.md`

---

## 1. Purpose

The Knowledge Universe is not a visualization. It is an **operational intelligence workspace** that replaces the traditional 2D desktop paradigm with a spatial intelligence paradigm. It is a first-class embodiment alongside the Living Orb and Avatar, consuming the exact same `FrameState` contract.

The Living Orb serves as the **Sun** at the center of the Universe. All intelligence, reasoning, memory, and attention originate from the Orb. The Knowledge Universe orbits around it, responding to the Orb's state. Never the reverse.

---

## 2. Core Spatial Concepts

The Knowledge Universe is structured as a cosmic hierarchy. Each spatial object has a defined semantic meaning:

| Spatial Object | Semantic Meaning | Description |
|---|---|---|
| **Galaxy** | Domain | High-level context (e.g., "Work", "Personal", "Research", "Creative") |
| **Solar System** | Project/Client | A major initiative, client relationship, or long-term goal |
| **Star** | Core Entity | The central node of a Solar System (e.g., a specific project, a person, a company) |
| **Planet** | Sub-Context | Major sub-components of a Star (e.g., project phases, document categories, team members) |
| **Moon** | Task/Milestone | Actionable items, deadlines, or deliverables orbiting a Planet |
| **Comet** | Transient Event | Time-sensitive items, notifications, or temporary context that passes through |
| **Asteroid Belt** | Resource Pool | Collections of related files, bookmarks, or references |
| **Constellation** | Relationship Pattern | Visual connections between Stars/Planets across different Solar Systems |
| **Nebula** | Knowledge Cloud | Aggregated, unstructured knowledge or emerging patterns |
| **Black Hole** | Archive/Deleted | Items that are hidden, archived, or marked for deletion |
| **Wormhole** | Shortcut/Link | Direct connections between distant parts of the Universe |
| **User Presence** | The Observer | The user's current focal point and attention state within the Universe |

---

## 3. Data Node Types

The following data types exist as nodes within the spatial hierarchy:

- **Projects** → Solar Systems or Stars
- **Agents** → Autonomous entities that orbit specific Stars or patrol the Universe
- **Memories** → Planets or Moons (episodic context)
- **Knowledge** → Nebulas or Asteroid Belts (semantic context)
- **Tasks** → Moons or Comets (actionable items)
- **Plugins** → Satellites or Space Stations (functional extensions)
- **Documents** → Planets or Asteroids (file-based context)
- **Bookmarks** → Stars or Wormholes (saved references)
- **Search Results** → Transient Comets that appear based on user query
- **User Presence** → The camera/observer position

---

## 4. Orb Integration

The Living Orb is **always** the central intelligence of the Knowledge Universe.

### 4.1 The Orb as the Sun
- The Orb sits at the exact center of the Universe (coordinates 0,0,0).
- All spatial objects orbit the Orb.
- The Orb continuously animates using `FrameState` (presence, energy, emotion, audio).
- The Universe's visual state (lighting, particle density, orbital speed) is modulated by the Orb's `FrameState`.

### 4.2 Intelligence Flow
All cognitive processes originate from the Orb:
- **Speech** → Orb pulses, Universe ripples
- **Thinking** → Orb glows, Universe dims slightly (focus mode)
- **Attention** → Orb shifts color, Universe highlights relevant nodes
- **Knowledge Retrieval** → Orb expands, relevant nodes orbit closer
- **Reasoning** → Orb pulses rhythmically, connections form between nodes
- **Memory Activation** → Orb warms, related memories drift into view

**The Universe responds. Never the reverse.**

---

## 5. Interaction Modes

Users can instantly switch between three modes. All three maintain identical conversation state, memory, and intelligence.

### 5.1 Orb Mode
- **View:** The Living Orb fills the screen. The Knowledge Universe is hidden or rendered as a subtle background.
- **Use Case:** Ambient monitoring, quick conversations, low-distraction work.
- **FrameState Consumption:** Full `FrameState` (visual, audio, emotion, system).

### 5.2 Avatar Mode
- **View:** A 3D character (MetaHuman, RPM, VRM, etc.) replaces the Orb. The Knowledge Universe is hidden or rendered as a background environment.
- **Use Case:** Deep conversation, emotional connection, presentation.
- **FrameState Consumption:** Full `FrameState` mapped to blendshapes, gaze, and gestures.

### 5.3 Universe Mode
- **View:** The Living Orb is visible at the center as the Sun. The Knowledge Universe is fully rendered and navigable. The user can fly through space, zoom into projects, and interact with nodes.
- **Use Case:** Deep work, project management, knowledge exploration, spatial organization.
- **FrameState Consumption:** Full `FrameState` modulates the entire Universe (lighting, particle effects, orbital speed, node highlighting).

### 5.4 Mode Switching
- Switching is instant and seamless.
- No data is lost. Conversation state, memory, and context persist across all modes.
- The Presence Runtime handles the transition by simply changing which Embodiment Adapter is active.

---

## 6. Navigation & Interaction

### 6.1 Navigation
- **Fly Mode:** Free camera movement through the Universe.
- **Focus Mode:** Camera locks onto a specific Star or Planet.
- **Timeline Mode:** Camera moves through time, showing how the Universe evolved.
- **Search Mode:** User types a query, and relevant nodes light up as Comets that fly toward the Orb.

### 6.2 Interaction
- **Click/Tap:** Select a node to view its contents.
- **Drag:** Move nodes to reorganize the Universe (creates new relationships).
- **Voice Command:** "Show me all tasks related to Project X" → relevant nodes highlight and orbit closer.
- **Gaze (VR/AR):** Look at a node to bring it into focus.

---

## 7. FrameState Integration

The Knowledge Universe consumes the exact same `FrameState` as the Living Orb and Avatar. Specific mappings:

| FrameState Field | Universe Effect |
|---|---|
| `visual.presence` | Overall brightness and particle density of the Universe |
| `visual.energy` | Orbital speed of nodes around the Orb |
| `visual.focus` | Depth of field and highlight intensity on relevant nodes |
| `visual.activity` | Number of active Comets and transient events |
| `audio.voiceLevel` | Ripple effects emanating from the Orb |
| `emotion.calmness` | Color temperature (cool = calm, warm = excited) |
| `emotion.curiosity` | Expansion of the Universe (pulling distant nodes closer) |
| `system.state` | Universe mode (e.g., `thinking` = dim background, `speaking` = active ripples) |

---

## 8. Compliance Checklist

- [ ] Consumes the exact `FrameState` contract defined in `06_FRAMESTATE_SPEC.md`.
- [ ] The Orb is always at the center (0,0,0).
- [ ] All intelligence originates from the Orb. The Universe only responds.
- [ ] Mode switching (Orb, Avatar, Universe) is instant and preserves state.
- [ ] No renderer-specific code exists above the Embodiment layer.
- [ ] Spatial objects have defined semantic meanings (no arbitrary decoration).

---

*End of Specification.*