# Runtime Event Specification
**Version:** 1.0 | **Status:** Frozen

## 1. Event Taxonomy
All events follow `<domain>.<action>` format.

### Domains
- `system`: shutdown, boot, error
- `runtime`: ready, degraded, stopped, health
- `conversation`: started, finished, interrupted
- `speech`: listening_started, tts_started, audio_chunk_ready
- `memory`: search_started, context_retrieved, saved
- `presence`: embodiment_loaded, frame_updated, embodiment_changed
- `animation`: state_changed, rhythm_updated

## 2. Event Versioning
Events are versioned. `speech.completed.v1` and `speech.completed.v2` can coexist. Subscribers must declare the version they consume.

## 3. Delivery Guarantees
- **Critical:** Exactly Once.
- **High:** At Least Once (Retry with backoff).
- **Normal:** At Least Once (Standard Queue).
- **Low:** Best Effort (Fire and Forget).