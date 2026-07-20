# backend/core/capability_router.py
from core.contracts import Runtime
from core.registry import RuntimeRegistry

class CapabilityRouter:
    """Resolves capabilities to Runtime providers via the Registry."""
    def __init__(self, registry: RuntimeRegistry):
        self._registry = registry

    def resolve(self, capability_id: str) -> Runtime:
        """Returns the Runtime instance that owns the requested capability."""
        return self._registry.get_runtime_for_capability(capability_id)