# Zaram Event Bus Specification
**Version:** 1.0
**Status:** Frozen (Requires ADR to modify)
**Dependencies:** `00_AI_ENGINEERING_MANIFEST.md`, `02_RUNTIME_CONTRACT.md`

> **The Event Bus is the central nervous system of Zaram. It is the only permitted mechanism for cross-Runtime communication.**

---

## 1. Purpose & Scope

The Event Bus operates on an asynchronous, decoupled Publish/Subscribe model.

- **Publishers (Emitters):** Runtimes broadcast events when a state change occurs. They do not know who is listening.
- **Subscribers (Consumers):** Runtimes register interest in specific event types. They do not know who published the event.
- **The Bus:** Routes events from Publishers to all registered Subscribers.

**Crucial Rule:** The Event Bus is fire-and-forget. Publishers must never block waiting for Subscribers to process an event.

---

## 2. The Universal Event Contract

Every event transmitted across the bus must adhere to this structure:

```python
from dataclasses import dataclass, field
from typing import Any, Dict
import uuid
import time

@dataclass
class ZaramEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    source_runtime: str
    event_type: str
    version: int = 1
    priority: str = "normal"
    data: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""