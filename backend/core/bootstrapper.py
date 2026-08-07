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
        self.documents_runtime = None
        self.semantic_router = None
        self.egress_gate = None

    def _init_egress_gate(self):
        """Install the process egress gate, and apply retention on the way up.

        Retention runs at boot rather than on a timer because the log only
        grows when the machine is awake and using it; a pass per launch keeps
        the window honest without a background thread whose failure would be
        silent. ``ZARAM_EGRESS_RETENTION_DAYS`` of 0 means keep everything,
        which is a choice the user can make in the privacy pane but is not the
        default — a permanent record of every question asked is its own problem.
        """
        import os

        from .egress import (
            EgressGate,
            EgressLog,
            EgressPolicy,
            default_log_path,
            default_policy_path,
            set_gate,
        )

        log = EgressLog(default_log_path())
        policy = EgressPolicy(default_policy_path())
        gate = EgressGate(log, policy)
        set_gate(gate)

        days = int(os.getenv("ZARAM_EGRESS_RETENTION_DAYS", "30"))
        pruned = log.apply_retention(max_age_days=days if days > 0 else None)

        rules = policy.rules()
        print(
            f"[Bootstrapper] Egress gate ready — {log.count()} entries, "
            f"{len(rules)} host polic{'y' if len(rules) == 1 else 'ies'}, "
            f"retention {days or 'off'}"
            + (f", pruned {pruned}" if pruned else "")
        )
        if not rules:
            print("[Bootstrapper] No egress policy set. Every destination is denied.")
        return gate

    async def boot(self):
        print("[Bootstrapper] Initializing Zaram Kernel...")

        # 0. The egress gate, before anything that could make a request.
        #    Deliberately first: a runtime that reached the network during its
        #    own initialisation would otherwise do so before the log existed,
        #    and Rule 3 cannot be applied retroactively.
        self.egress_gate = self._init_egress_gate()

        # 1. Initialize Memory Runtime first (other runtimes depend on it)
        self.memory_runtime = self._init_memory_runtime()
        await self.memory_runtime.initialize()

        # 2. Initialize Knowledge Runtime (providers) with Memory Runtime
        self.knowledge_runtime = self._init_knowledge_runtime(self.memory_runtime)

        # 3. Discover and Register Runtimes
        await self._register_runtimes()

        # 4. Initialize Core Services
        #
        # Routing by embeddings rather than keywords (CLAUDE.md). It reuses the
        # Spine's embedder — bge-m3 is already resident, so this costs no extra
        # VRAM — and falls back to the keyword router when the embedder is not
        # running semantically, which is what happens if Ollama is unreachable.
        self.semantic_router = self._init_semantic_router()
        self.execution_engine = ExecutionEngine(
            self.registry, self.event_bus, semantic_router=self.semantic_router
        )

        print("[Bootstrapper] Kernel Ready.")

    def _init_semantic_router(self):
        """Build the intent router, or None if the Spine has no embedder.

        Never fatal. A kernel that refuses to boot because routing could not be
        built would trade a duller classifier for no product at all.
        """
        try:
            from core.retrieval import SemanticIndex, SemanticIntentRouter

            embedder = getattr(self.memory_runtime, "_embedder", None)
            if embedder is None:
                print("[Bootstrapper] No embedder; routing stays keyword-based.")
                return None

            router = SemanticIntentRouter(SemanticIndex(embedder))
            mode = "semantic" if router.is_semantic() else "keyword fallback"
            print(f"[Bootstrapper] Intent routing: {mode}")
            return router
        except Exception as error:
            print(f"[Bootstrapper] Semantic routing unavailable ({error}); using keywords.")
            return None

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

        # --- Provider layer ---
        # Registered before the models runtime because that runtime asks it
        # which model may be used by default. Registering providers does no
        # network I/O; the scan happens on demand.
        from providers.runtime import ProvidersRuntime
        self.providers_runtime = ProvidersRuntime(self.event_bus)
        self.registry.register(self.providers_runtime)
        await self.providers_runtime.initialize()
        register_runtime_for_health(self.providers_runtime)

        # --- Models Runtime ---
        from runtimes.models.models_runtime import ModelsRuntime
        models_runtime = ModelsRuntime(
            self.event_bus,
            self.knowledge_runtime,
            provider_manager=self.providers_runtime.manager,
        )
        self.registry.register(models_runtime)
        await models_runtime.initialize()
        register_runtime_for_health(models_runtime)

        # --- Speech Runtime ---
        from runtimes.speech.runtime import SpeechRuntime
        self.speech_runtime = SpeechRuntime(self.event_bus)
        self.registry.register(self.speech_runtime)
        await self.speech_runtime.initialize()
        register_runtime_for_health(self.speech_runtime)

        # --- Documents Runtime ---
        # Generative tier: creates new artifacts and changes nothing existing,
        # so it needs no undo, sandbox or confirmation and ships in v1. The
        # safety is structural and lives in ArtifactStore, not here.
        from artifacts.records import ArtifactRecords, default_db_path
        from artifacts.service import ArtifactService
        from artifacts.store import ArtifactStore, default_output_root
        from runtimes.documents.runtime import DocumentsRuntime

        self.documents_runtime = DocumentsRuntime(
            ArtifactService(
                ArtifactRecords(default_db_path()), ArtifactStore(default_output_root())
            ),
            self.event_bus,
        )
        self.registry.register(self.documents_runtime)
        await self.documents_runtime.initialize()
        register_runtime_for_health(self.documents_runtime)

    async def shutdown(self):
        print("[Bootstrapper] Shutting down Zaram Kernel...")
        if self.speech_runtime:
            await self.speech_runtime.shutdown()
        if self.memory_runtime:
            await self.memory_runtime.shutdown()
        print("[Bootstrapper] Kernel Stopped.")