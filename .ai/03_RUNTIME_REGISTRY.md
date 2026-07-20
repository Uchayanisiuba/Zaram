# Runtime Registry Specification
**Version:** 1.0 | **Status:** Frozen

## 1. Purpose
The Runtime Registry is the OS Kernel Service Manager. It is the single source of truth for all Runtimes, Capabilities, and System Health.

## 2. Bootstrapper Pattern
The Registry is the owner, not the constructor. A separate Bootstrapper instantiates Runtimes and injects them into the Registry.

## 3. Startup Sequence
1. **Critical:** Core, EventBus, Registry
2. **High:** Models, Memory, Speech, Presence
3. **Normal:** Knowledge, Tools, Embodiment
4. **Optional:** Plugins, Task

## 4. Capability Discovery
The Registry maintains a dynamic mapping of Capabilities to Runtimes. If a Runtime fails, the Registry updates Capability mappings to fallback engines without restarting.