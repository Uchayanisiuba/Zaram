# Event Bus Specification
**Version:** 1.0 | **Status:** Frozen

## 1. Purpose
The Event Bus is the central nervous system. It is the only permitted mechanism for cross-Runtime communication via asynchronous Pub/Sub.

## 2. Universal Event Contract
Every event must contain:
- `event_id`, `timestamp`, `source_runtime`
- `event_type`, `version`, `priority`
- `data` (payload), `correlation_id`

## 3. Event Priorities
- **Critical:** `system.shutdown`, `user.interrupted`
- **High:** `speech.audio_chunk_ready`, `conversation.started`
- **Normal:** `memory.saved`, `tool.executed`
- **Background:** `analytics.tracked`

## 4. Strict Rules
- No Direct Calls.
- No Blocking Subscribers.
- No Circular Dependencies.
- Payload Immutability.