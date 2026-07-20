# ADR-011: Cognitive Runtime Separation
**Status:** Accepted
**Date:** Milestone 1.2

## Context
The AI must maintain internal state (reasoning, goals, planning, attention,
relationship) that is independent of how the embodiment renders it. Thinking
must be separated from embodiment. The renderer must never observe cognition
directly — it only consumes the projected `CharacterFrame`.

## Decision
Introduce a renderer-independent Cognitive Runtime layer (`src/runtime/cognitive`):
- `CognitiveRuntime` — reasoning, intent, goals, planning, task queue, attention
  priority, thinking status, knowledge/memory requests.
- `AttentionRuntime` — speaker, conversation/cursor/camera targets, notifications,
  memory relevance, focus confidence, with smooth (eased) transitions.
- `RelationshipRuntime` — trust, familiarity, history weight, preference
  confidence, interaction frequency, respect, humor; evolves gradually.
- `MemoryProjection` / `ConversationProjection` — read-only projection
  interfaces over the (unmodified) Memory and Conversation sources.
- `CognitiveBundle` — the single DI unit `PresenceRuntime` consumes.

`PresenceRuntime` is extended (not modified in its pipeline) to:
- feed the bundle **event-driven** from the existing aggregator subscription,
- advance the bundle on the **same existing 30 Hz tick** (no new render loop),
- drive `CharacterRuntime` intent from cognitive reasoning.

The renderer boundary (`CharacterFrame`) is unchanged: it carries no cognition
fields. All embodiments remain dependency-injected via the registry.

## Consequences
- The AI's internal state is now a first-class, testable, render-independent
  layer.
- No renderer changes; the Milestone 1.0/1.1 pipelines are preserved (118
  tests pass).
- Future cognition features (planners, memory search) plug into the bundle
  without touching the embodiment or renderer.
