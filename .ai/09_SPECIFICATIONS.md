# Core Specifications

## 1. FrameState Contract
The universal contract driving all embodiments. See `.ai/06_FRAMESTATE_SPEC.md` for the full specification.

### Namespaces
- **Visual:** `presence`, `energy`, `focus`, `activity`
- **Audio:** `voiceLevel`, `microphoneLevel`
- **Emotion:** `calmness`, `confidence`, `curiosity`, `warmth`, `empathy`, `playfulness`
- **System:** `state`, `cognitiveLoad`, `adaptiveQuality`, `visualIdentity`
- **Metadata:** `timestamp`, `correlationId`, `version`

## 2. Knowledge Runtime Architecture
The Knowledge Runtime is a **provider-agnostic** search and retrieval system.

### Architecture Flow
```text
Executive Runtime
      ↓ (requests: knowledge.search)
Knowledge Runtime
      ↓
Provider Manager
      ↓
Providers:
  - Memory (Local Vector DB)
  - Projects (Workspace files)
  - Local Documents (PDF, TXT, MD)
  - RSS Feeds
  - Wikipedia
  - DuckDuckGo
  - GitHub
  - Future: News, Finance, Email, Calendar, Browser, Vision