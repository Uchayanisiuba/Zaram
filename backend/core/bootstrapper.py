# backend/core/bootstrapper.py
from .event_bus import EventBus
from .registry import RuntimeRegistry
from .execution_engine import ExecutionEngine
from runtimes.health import register_runtime_for_health


class KernelBootstrapper:
    def __init__(self):
        self.event_bus = EventBus()
        self.registry = RuntimeRegistry(self.event_bus)
        self.execution_engine = None
        self.knowledge_runtime = None
        self.speech_runtime = None
        self.memory_runtime = None

    async def boot(self):
        print("[Bootstrapper] Initializing Zaram Kernel...")

        # 1. Initialize Memory Runtime first (other runtimes depend on it)
        self.memory_runtime = self._init_memory_runtime()
        await self.memory_runtime.initialize()

        # 2. Initialize Knowledge Runtime (providers) with Memory Runtime
        self.knowledge_runtime = self._init_knowledge_runtime(self.memory_runtime)

        # 3. Discover and Register Runtimes
        await self._register_runtimes()

        # 4. Initialize Core Services
        self.execution_engine = ExecutionEngine(self.registry, self.event_bus)

        print("[Bootstrapper] Kernel Ready.")

    def _init_memory_runtime(self):
        import os
        from runtimes.memory import create_memory_runtime

        # The Spine lives on disk next to the backend, and survives restarts.
        # ZARAM_SPINE_PATH overrides the location (used by the desktop host).
        spine_path = os.getenv(
            "ZARAM_SPINE_PATH",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spine.db"),
        )

        # Real semantic embeddings via Ollama. bge-m3 produces 1024-dim vectors.
        # Falls back to the hash backend if Ollama or the model is unavailable —
        # recall still works, but only on keyword overlap.
        backend = os.getenv("ZARAM_EMBED_BACKEND", "ollama")
        model = os.getenv("ZARAM_EMBED_MODEL", "bge-m3")
        dim = int(os.getenv("ZARAM_EMBED_DIM", "1024" if backend == "ollama" else "384"))

        runtime = create_memory_runtime(
            store_type="sqlite",
            db_path=spine_path,
            index_type="hybrid",
            embedding_dim=dim,
            embedding_backend=backend,
            embedding_model=model,
            event_bus=self.event_bus,
        )
        print(f"[Bootstrapper] Spine at {spine_path} (embeddings: {backend}/{model}, dim={dim})")
        return runtime

    def _init_knowledge_runtime(self, memory_runtime):
        from knowledge.runtime import KnowledgeRuntime
        from knowledge.providers import (
            MemoryProvider, VectorProvider, WikipediaProvider,
            DuckDuckGoProvider, RSSProvider, GitHubProvider,
            ProjectProvider, MarkdownProvider, PDFProvider,
            PlaceholderProvider,
        )

        runtime = KnowledgeRuntime(memory_runtime=memory_runtime)
        runtime.register(MemoryProvider(memory_runtime=memory_runtime))
        runtime.register(VectorProvider())
        runtime.register(WikipediaProvider())
        runtime.register(DuckDuckGoProvider())
        runtime.register(RSSProvider())
        runtime.register(GitHubProvider())
        runtime.register(ProjectProvider())
        runtime.register(MarkdownProvider())
        runtime.register(PDFProvider())
        runtime.register(PlaceholderProvider("future_gmail"))
        runtime.register(PlaceholderProvider("future_notion"))
        runtime.register(PlaceholderProvider("future_drive"))
        return runtime

    async def _register_runtimes(self):
        """
        Registers all active Runtimes with the Registry.
        Future Runtimes (World) will be added here.
        """
        # --- Memory Runtime ---
        self.registry.register(self.memory_runtime)
        register_runtime_for_health(self.memory_runtime)

        # --- Models Runtime ---
        from runtimes.models.models_runtime import ModelsRuntime
        models_runtime = ModelsRuntime(self.event_bus, self.knowledge_runtime)
        self.registry.register(models_runtime)
        await models_runtime.initialize()
        register_runtime_for_health(models_runtime)

        # --- Speech Runtime ---
        from runtimes.speech.runtime import SpeechRuntime
        self.speech_runtime = SpeechRuntime(self.event_bus)
        self.registry.register(self.speech_runtime)
        await self.speech_runtime.initialize()
        register_runtime_for_health(self.speech_runtime)

    async def shutdown(self):
        print("[Bootstrapper] Shutting down Zaram Kernel...")
        if self.speech_runtime:
            await self.speech_runtime.shutdown()
        if self.memory_runtime:
            await self.memory_runtime.shutdown()
        print("[Bootstrapper] Kernel Stopped.")