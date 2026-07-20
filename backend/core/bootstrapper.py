# backend/core/bootstrapper.py
from .event_bus import EventBus
from .registry import RuntimeRegistry
from .execution_engine import ExecutionEngine

class KernelBootstrapper:
    def __init__(self):
        self.event_bus = EventBus()
        self.registry = RuntimeRegistry(self.event_bus)
        self.execution_engine = None

    async def boot(self):
        print("[Bootstrapper] Initializing Zaram Kernel...")
        
        # 1. Discover and Register Runtimes
        await self._register_runtimes()
        
        # 2. Initialize Core Services
        self.execution_engine = ExecutionEngine(self.registry, self.event_bus)
        
        print("[Bootstrapper] Kernel Ready.")

    async def _register_runtimes(self):
        """
        Registers all active Runtimes with the Registry.
        Future Runtimes (Memory, Speech, World) will be added here.
        """
        # --- Models Runtime ---
        from runtimes.models.models_runtime import ModelsRuntime
        models_runtime = ModelsRuntime(self.event_bus)
        self.registry.register(models_runtime)
        await models_runtime.initialize()
        
        # TODO: Add Memory Runtime here
        # TODO: Add Speech Runtime here
        # TODO: Add World Runtime here

    async def shutdown(self):
        print("[Bootstrapper] Shutting down Zaram Kernel...")
        # Future: Iterate runtimes in reverse priority and shutdown.
        print("[Bootstrapper] Kernel Stopped.")