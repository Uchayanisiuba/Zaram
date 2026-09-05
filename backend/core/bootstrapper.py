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
        self.images_runtime = None
        self.mcp_runtime = None
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
            get_pending,
            set_gate,
        )

        log = EgressLog(default_log_path())
        policy = EgressPolicy(default_policy_path())
        gate = EgressGate(log, policy)

        # The hook is installed here, with the gate, rather than by whoever
        # happens to serve the dialog. A gate that exists without one refuses
        # every `ask` host — correct as a resting state, and the wrong thing to
        # leave running once there is an interface that can answer.
        #
        # Resolved per call rather than bound once. `get_pending().ask` would
        # capture whichever instance existed at boot, so a later `set_pending`
        # would leave the gate asking a store nothing is watching — the question
        # invisible to the dialog, and the answer to it a two-minute timeout.
        gate.set_confirm(lambda request: get_pending().ask(request))
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
        self.knowledge_runtime = await self._init_knowledge_runtime(self.memory_runtime)

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

        # Let the engine ask whether a route forces a model out of VRAM, so a
        # swap can be announced before the user spends the seconds rather than
        # during them. Attached after construction because the providers
        # runtime is registered in step 3 and the engine does not exist yet
        # there; without this the engine simply never announces a load.
        providers = getattr(self, "providers_runtime", None)
        if providers is not None:
            self.execution_engine.set_provider_manager(providers.manager)

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

        # The Spine lives in the user's data directory and survives restarts.
        # ZARAM_SPINE_PATH overrides the location (used by the desktop host);
        # `core.paths` decides the default, which is the backend directory in a
        # checkout and %APPDATA%\Zaram — or its equivalent — once installed.
        from core.paths import in_data_dir

        spine_path = in_data_dir("spine.db", "ZARAM_SPINE_PATH")

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

    async def _init_knowledge_runtime(self, memory_runtime):
        from knowledge.runtime import KnowledgeRuntime
        from knowledge.providers import (
            MemoryProvider, VectorProvider, WikipediaProvider,
            DuckDuckGoProvider, RSSProvider, GitHubProvider,
            ProjectProvider, MarkdownProvider, PDFProvider,
            PlaceholderProvider,
        )

        # The internet runtime is where `KnowledgeRuntime.search` gets web
        # results from, and nothing had ever constructed one.
        #
        # **This was the missing link in web search**, and it is the third
        # instance of one shape in this codebase: a complete, tested component
        # that nothing wires up. `create_internet_runtime` was defined and
        # exported and never called; `search()` reads `self._internet_runtime`
        # and it was always `None`, so the web half of every search silently
        # returned nothing and the answer came from memory alone. The
        # `DuckDuckGoProvider` registered a few lines below goes into
        # `self._providers`, which `search()` does not read — so registering it
        # looked like wiring and was not.
        #
        # Nothing here opens a connection. Connectors are constructed in
        # `initialize()` and each one consults the egress gate before its first
        # request, so with web search off, or with no rule for the host, this
        # costs three objects and no bytes. Rule 7g holds.
        internet_runtime = None
        try:
            from runtimes.internet import create_internet_runtime

            internet_runtime = create_internet_runtime()
            await internet_runtime.initialize()
        except Exception:
            # Knowledge must still work without it. A failure here means no web
            # results, which is the default state anyway — it must never mean
            # no memory results.
            print("[Bootstrapper] Internet runtime unavailable; web search will find nothing")
            internet_runtime = None

        runtime = KnowledgeRuntime(
            memory_runtime=memory_runtime, internet_runtime=internet_runtime
        )
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

        # Hand the wired runtime to the legacy facade, which otherwise answers
        # from an unwired `KnowledgeRuntime()` of its own — no internet, no
        # memory, no providers. `POST /knowledge/search` and the provider-health
        # block both read it, so both reported nothing while this instance sat
        # beside them working. Set last, after every provider is registered, so
        # nothing can observe a half-built runtime.
        from knowledge.knowledge_service import set_runtime

        set_runtime(runtime)
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
        # Held rather than only registered, because connecting a cloud provider
        # from Settings has to reach *both* halves of the cloud path: the
        # adapter that discovers, which hangs off the provider runtime, and the
        # engine that sends, which is built once inside this one.
        self.models_runtime = models_runtime

        from providers import cloud_config

        cloud_config.attach_runtimes(self.providers_runtime, models_runtime)
        # A key exported before launch becomes an ordinary connection, so there
        # is one code path for a configured provider rather than an environment
        # mechanism running beside a Settings mechanism with its own bugs.
        # Reads variables only; rule 7g means no network call happens here.
        cloud_config.seed_from_environment()

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

        artifact_service = ArtifactService(
            ArtifactRecords(default_db_path()), ArtifactStore(default_output_root())
        )

        self.documents_runtime = DocumentsRuntime(artifact_service, self.event_bus)
        self.registry.register(self.documents_runtime)
        await self.documents_runtime.initialize()
        register_runtime_for_health(self.documents_runtime)

        # --- Images Runtime ---
        # The same tier and the same service as documents, sharing one
        # `ArtifactService` deliberately: a picture is an artifact, so it goes
        # to the one output directory, gets the one record and the one download
        # route. A second service would be a second write path whose
        # no-overwrite guarantee nobody had proved.
        #
        # Registered whether or not anything can draw. The runtime's refusal —
        # with the reason and the size of the fix — is the behaviour a machine
        # with no image model needs, and it can only be given by something that
        # is actually wired in. An image capability that registers only when it
        # works is one that says nothing on every machine where it does not.
        from imaging.local_flux import FluxProvider
        from runtimes.images.runtime import ImagesRuntime

        self.images_runtime = ImagesRuntime(
            artifact_service, FluxProvider(), self.event_bus
        )
        self.registry.register(self.images_runtime)
        await self.images_runtime.initialize()
        register_runtime_for_health(self.images_runtime)

        # Tools other people wrote. Registered here rather than left to a
        # caller that does not exist yet, because an unregistered runtime is
        # this repository's most-repeated failure — fifteen complete, tested,
        # unreachable subsystems, and the way each one got there was exactly
        # this line being deferred.
        #
        # `initialize` connects to nothing: a configured server is a stranger's
        # subprocess, and a cold `npx` one costs tens of seconds, so putting
        # them on the boot path would make Zaram's launch depend on somebody
        # else's package manager. They attach on first use.
        from runtimes.mcp.runtime import McpRuntime

        self.mcp_runtime = McpRuntime()
        self.registry.register(self.mcp_runtime)
        await self.mcp_runtime.initialize()
        register_runtime_for_health(self.mcp_runtime)

        # **Registering it is not reaching it, and that distinction is the
        # whole reason this line exists.** The runtime was registered here for
        # a fortnight while `planner.py` contained no occurrence of "mcp", so
        # no plan could name `mcp.call` and no question ever arrived. A test
        # named `test_mcp_runtime_is_reachable` passed throughout, because it
        # asserted the two lines above and called that reachability.
        #
        # This hands the planner the names of the attached servers, so
        # "blender" is a word that means *tool request* on a machine with
        # Blender attached and means nothing on one without. Passed as a
        # callable rather than a list: servers are attached and detached while
        # Zaram runs, and a snapshot taken at boot would be wrong by the time
        # anybody used it.
        if self.execution_engine is not None:
            self.execution_engine.set_tool_vocabulary(self.mcp_runtime.server_names)

        # An invoice is a table of line items, not paragraphs, so the documents
        # runtime needs a way to read an answer into fields. It is handed a
        # callable rather than the models runtime: the artifacts layer must not
        # acquire a dependency on the model layer, the same constraint
        # `cloud_config` and `wire_name` are injected under.
        #
        # Runs against the *local* engine specifically. Reading an answer the
        # user has already been shown is not a question worth sending to a
        # billed provider, and a document step silently becoming egress would
        # be a rule 5 surprise attached to a generative tool.
        models_runtime = getattr(self, "models_runtime", None)

        def _read_into_fields(prompt: str, system: str) -> str:
            engine = getattr(getattr(models_runtime, "_service", None), "engine", None)
            local = getattr(engine, "_local", engine)
            if local is None:
                raise RuntimeError("no local engine")
            # Constrained decoding where the engine offers it. Ollama's
            # `format: json` plus temperature 0 is the difference between an
            # extraction that works and one that works most times — the first
            # live run refused on a model the suite had just measured as
            # capable, because the chat path samples. `getattr` rather than a
            # protocol method: an engine without it still works, less reliably.
            structured = getattr(local, "read_structured", None)
            if callable(structured):
                return structured(prompt, system)
            return "".join(local.stream_response(prompt, system))

        if models_runtime is not None:
            self.documents_runtime.set_extractor(_read_into_fields)

    async def shutdown(self):
        print("[Bootstrapper] Shutting down Zaram Kernel...")
        if self.speech_runtime:
            await self.speech_runtime.shutdown()
        if self.memory_runtime:
            await self.memory_runtime.shutdown()
        print("[Bootstrapper] Kernel Stopped.")