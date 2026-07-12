# backend/core/bootstrapper.py
from .event_bus import EventBus
from .registry import RuntimeRegistry


class KernelBootstrapper:
    def __init__(self):
        self.event_bus = EventBus()
        self.registry = RuntimeRegistry(self.event_bus)

    async def boot(self):
        print("[Bootstrapper] Initializing Zaram Kernel...")
        # Future: Load runtimes from config, sort by priority, and initialize.
        print("[Bootstrapper] Kernel Ready.")

    async def shutdown(self):
        print("[Bootstrapper] Shutting down Zaram Kernel...")
        # Future: Iterate runtimes in reverse priority and shutdown.
        print("[Bootstrapper] Kernel Stopped.")
