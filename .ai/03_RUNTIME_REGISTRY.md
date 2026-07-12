# Zaram Runtime Registry Specification
**Version:** 1.0
**Status:** Frozen (Requires ADR to modify)
**Dependencies:** `00_AI_ENGINEERING_MANIFEST.md`, `02_RUNTIME_CONTRACT.md`

> **The Runtime Registry is the OS Kernel Service Manager. It is the single source of truth for all Runtimes, Capabilities, and System Health.**

---

## 1. Purpose & Scope
The Runtime Registry discovers, monitors, and routes requests to all independent Runtimes. No external component interacts directly with a Runtime. They interact exclusively through the Registry.

---

## 2. Core Responsibilities
- **Lifecycle Management:** Initializes Runtimes in dependency order (Critical → High → Normal → Optional). Shuts down in reverse.
- **Capability Discovery:** Maintains a dynamic mapping of Capabilities to Runtimes.
- **Health Monitoring:** Listens to `runtime.health` and `runtime.degraded` events. Does NOT poll.
- **Dynamic Re-routing:** If a Runtime fails, the Registry updates Capability mappings to fallback engines without restarting.

---

## 3. First-Class Objects

### 3.1 The Capability Object
```python
@dataclass(frozen=True)
class Capability:
    id: str                  # e.g., "speech.tts", "memory.retrieve"
    runtime_id: str          # e.g., "speech", "memory"
    version: str = "1.0.0"
    category: str = "general"
    priority: str = "normal"
    locality: CapabilityLocality = CapabilityLocality.LOCAL
    status: CapabilityStatus = CapabilityStatus.ACTIVE