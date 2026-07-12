# Zaram Runtime Contract
**Version:** 1.0
**Status:** Frozen (Requires ADR to modify)
**Dependencies:** `00_AI_ENGINEERING_MANIFEST.md`

> **Every Runtime must be independently startable, testable, replaceable, and deployable without modifying other Runtimes.**

> **Any subsystem capable of independent lifecycle management is considered a Runtime and must implement this contract.**

---

## 1. The Architecture Hierarchy

Responsibilities are strictly separated into three layers. The Engine is always an Interface, never a hardcoded implementation.

1. **Runtime:** Owns the lifecycle, health, configuration, and Event Bus integration.
2. **Service:** Owns the business logic and orchestration.
3. **Engine (Interface):** Defines the contract for the underlying implementation.

---

## 2. The Universal Runtime Interface

```python
from typing import Protocol, Any, Dict
from enum import Enum

class RuntimeState(Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

class Runtime(Protocol):
    # --- Identity ---
    def get_runtime_id(self) -> str: ...
    def get_version(self) -> str: ...

    # --- Configuration ---
    def load_config(self, config: Dict[str, Any]) -> None: ...
    def reload_config(self, config: Dict[str, Any]) -> None: ...

    # --- Lifecycle ---
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...

    # --- Observability ---
    def get_state(self) -> RuntimeState: ...
    def health_check(self) -> Dict[str, Any]: ...
    def get_capabilities(self) -> Dict[str, Any]: ...
    def get_dependencies(self) -> list[str]: ...