# Zaram Execution Engine Specification
**Version:** 1.0
**Status:** Frozen (Requires ADR to modify)
**Dependencies:** `00_AI_ENGINEERING_MANIFEST.md`, `01_SYSTEM_ARCHITECTURE.md`, `02_RUNTIME_CONTRACT.md`, `03_RUNTIME_REGISTRY.md`, `04_EVENT_BUS.md`

> **The Execution Engine is the operational core of Zaram. It translates user intent into structured Execution Plans, resolves the required capabilities, and orchestrates their execution while strictly maintaining Subsystem Independence.**

---

## 1. Purpose & Scope
The Execution Engine is responsible for the end-to-end lifecycle of a user request. It is divided into three narrowly defined components to prevent architectural bloat:
1. **Execution Planner:** Analyzes intent and builds an `ExecutionPlan`.
2. **Capability Router:** A tiny, focused component that resolves a `Capability ID` to a `Runtime Provider`.
3. **Execution Executor:** Runs the plan, manages dependencies, handles retries, and processes cancellations.

**Crucial Rule:** The Capability Router must *never* execute logic. It only resolves capabilities. Execution belongs to the Executor and the target Runtimes.

---

## 2. The Execution Plan Object
The `ExecutionPlan` is the central data structure that flows through the engine. It expands upon the base contract defined in `03_RUNTIME_REGISTRY.md`.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

class PlanState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    DEGRADED = "degraded"  # Completed with fallbacks

@dataclass
class ExecutionStep:
    capability_id: str       # e.g., "tool.search_files"
    input_data: Dict[str, Any]
    output_data: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[int] = field(default_factory=list)  # Indices of previous steps
    status: str = "pending"

@dataclass
class ExecutionPlan:
    correlation_id: str
    original_prompt: str
    steps: List[ExecutionStep] = field(default_factory=list)
    state: PlanState = PlanState.PENDING
    priority: str = "normal"
    created_at: float = 0.0