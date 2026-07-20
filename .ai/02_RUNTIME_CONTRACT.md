# Runtime Contract
**Version:** 1.0 | **Status:** Frozen

## 1. The Architecture Hierarchy
Responsibilities are strictly separated into three layers:
1. **Runtime:** Owns lifecycle, health, configuration, and Event Bus integration.
2. **Service:** Owns business logic and orchestration.
3. **Engine (Interface):** Defines the contract for the underlying implementation.

## 2. Universal Runtime Interface
Every Runtime must expose:
- `initialize()`, `shutdown()`
- `get_state()`, `health_check()`
- `get_capabilities()`, `get_dependencies()`
- `load_config()`, `reload_config()`

## 3. Strict Runtime Rules
A Runtime may NEVER:
- Directly call or import another Runtime's implementation.
- Access another Runtime's internal state.
- Bypass Zaram Core or the Event Bus.

## 4. Failure Philosophy
A Runtime failure must never crash Zaram. It must catch exceptions, transition to `DEGRADED`, publish a `runtime.degraded` event, and continue operating in limited capacity.