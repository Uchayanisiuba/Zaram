# backend/runtimes/models/models_runtime.py
"""The runtime that answers ``reasoning.generate``.

Model choice comes from the provider layer, not from this module. It used to
construct ``OllamaEngine()`` directly, which meant a second and simpler
provider path grew beside ``providers/`` — the layer that was written, tested
and never wired up. That shortcut also hardcoded a model name, so the answer to
"which model is running, and may we send it this prompt?" lived in an engine
default with no data policy attached to it.

Now: ``ProviderManager.select_default_model()`` decides, and it will hand back
nothing at all rather than a model the user has not consented to. Boot still
works with no provider layer attached — the engine falls back to its own
default and says so in the log — because the chat path predates this wiring and
must not start depending on a network scan to come up.
"""

import logging
from typing import Any, Dict, Optional

from core.contracts import Capability, CapabilityLocality, Runtime, RuntimeMetadata, RuntimeState
from core.event_bus import EventBus, ZaramEvent

from .engines.ollama_engine import OllamaEngine
from .engines.local_dispatch_engine import LocalDispatchEngine
from .engines.openai_compatible_engine import from_environment as cloud_engine_from_environment
from .engines.routed_engine import RoutedEngine
from .models_service import ModelsService

logger = logging.getLogger(__name__)

#: Localities that mean "this leaves the machine".
#:
#: `HYBRID` is included deliberately. It says a provider *may* go off-device,
#: and a maybe has to be treated as a yes here — routing it local would be
#: right half the time and silently wrong the other half, with the wrong half
#: being the one where data leaves. `REMOTE_DEVICE` is another machine on the
#: network, which is not this machine, which is what the gate cares about.
REMOTE_LOCALITIES = frozenset(
    {
        CapabilityLocality.CLOUD,
        CapabilityLocality.HYBRID,
        CapabilityLocality.REMOTE_DEVICE,
    }
)


class ModelsRuntime(Runtime):
    def __init__(
        self,
        event_bus: EventBus,
        knowledge_runtime=None,
        provider_manager: Optional[Any] = None,
    ):
        self._event_bus = event_bus
        self._state = RuntimeState.UNINITIALIZED
        self._service = None
        self._knowledge_runtime = knowledge_runtime
        #: The provider layer, when the bootstrapper has one to give. Typed
        #: loosely on purpose: this runtime must not import `providers` at
        #: module scope, or the chat path acquires a hard dependency on a layer
        #: that is still being connected.
        self._provider_manager = provider_manager
        self._selected_model: Optional[str] = None
        #: Builds the engine that serves every connected cloud provider, or
        #: returns ``None`` when none is connected.
        #:
        #: Injected by `providers.cloud_config` rather than imported, because
        #: this runtime must not depend on the provider layer — the same
        #: constraint `_provider_manager` is typed loosely for. Without it the
        #: only cloud configuration reachable from here is the pair of
        #: environment variables read at boot, which cannot express more than
        #: one provider and cannot change while the process runs.
        self._cloud_engine_factory: Optional[Any] = None

    def get_runtime_id(self) -> str:
        return "models"

    def get_version(self) -> str:
        return "1.0.0"

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id="models",
            version="1.0.0",
            priority="critical",
            capabilities=[
                Capability(id="reasoning.generate", runtime_id="models"),
                Capability(id="knowledge.search", runtime_id="models"),
                Capability(id="vision.analyze", runtime_id="models"),
                Capability(id="vision.screen", runtime_id="models"),
                Capability(id="vision.camera", runtime_id="models"),
                Capability(id="vision.document", runtime_id="models"),
                Capability(id="vision.ocr", runtime_id="models"),
            ],
            dependencies=["event_bus"],
            auto_start=True,
        )

    async def initialize(self) -> None:
        self._state = RuntimeState.INITIALIZING

        engine = self._build_engine()
        self._selected_model = await self._choose_model()
        if self._selected_model:
            engine.default_model = self._selected_model

        self._service = ModelsService(engine, knowledge_runtime=self._knowledge_runtime)
        self._state = RuntimeState.READY

        self._event_bus.publish(
            ZaramEvent(
                source_runtime="models",
                event_type="runtime.ready",
                data={
                    "runtime_id": self.get_runtime_id(),
                    "model": self._selected_model,
                },
            )
        )
        logger.info("[ModelsRuntime] Initialized (model=%s)", self._selected_model or "engine default")

    def _build_engine(self):
        """Local always; cloud as well when the user has brought a key.

        Ollama is constructed unconditionally and stays the default, because
        the product is local-first and because rule 5 forbids sending anything
        off-device as a default. Cloud exists so that **someone with no
        graphics card can use Zaram at all** — the constraint on the alpha was
        never capability, it was who can run it.

        With no key this returns the local engine unchanged, so nothing about
        the previous behaviour depends on the new path existing. No network
        call happens here either way: rule 7g, and `from_environment` reads
        variables rather than testing them.
        """
        # Ollama is one local server, not the only one. `LocalDispatchEngine`
        # sends a model to whichever on-device server actually holds it, and
        # falls back to Ollama for anything it cannot place -- see that module
        # for the failure this fixes.
        local = LocalDispatchEngine(
            ollama=OllamaEngine(wire_name=self.wire_name),
            resolve_endpoint=self._local_endpoint_for,
            wire_name=self.wire_name,
        )

        # The factory wins when the provider layer has attached one, because it
        # knows about every connection rather than the single pair of
        # environment variables. `from_environment` stays as the fallback so
        # this runtime still works standalone — it is constructed without a
        # provider layer in several tests, and boot must not start depending on
        # a layer that is still being connected.
        cloud = None
        if self._cloud_engine_factory is not None:
            try:
                cloud = self._cloud_engine_factory()
            except Exception:
                logger.warning("cloud engine factory failed; falling back", exc_info=True)
        if cloud is None:
            cloud = cloud_engine_from_environment()

        if cloud is None:
            return local

        logger.info("[ModelsRuntime] Cloud engine available (%s)", type(cloud).__name__)
        return RoutedEngine(local=local, cloud=cloud, is_remote=self._is_remote_model)

    def set_cloud_engine_factory(self, factory) -> None:
        """Tell this runtime how to build its cloud engine. Rebuilds immediately.

        Rebuilding here rather than waiting for the next reload matters at boot:
        the provider layer attaches after this runtime has already initialised,
        so without it the first message of every session would be answered by an
        engine built before the connections were known.
        """
        self._cloud_engine_factory = factory
        if self._service is not None:
            self.reload_engine()

    async def warm_local_model(self) -> bool:
        """Load the local model in the background, shortly after boot.

        **"Warming up" was appearing on almost every message**, which read as
        the product being slow and was in fact the model being unloaded between
        them: nothing set Ollama's `keep_alive`, so its five-minute default
        applied and any ordinary pause — reading a reply, answering the door —
        cost a full cold start on the next question.

        Two halves to the fix and both are needed. `keep_alive` keeps the
        weights resident once they are loaded; this preloads them so the *first*
        message does not pay for it either. After this, warming is a state the
        user sees once per session, at a moment when they are not waiting on an
        answer.

        Run in a thread: the load blocks for as long as it takes to move several
        gigabytes onto the card, and doing that on the event loop would freeze
        every endpoint — the same class of defect as the confirm hook in M10.
        """
        # **A preload of a model nobody chose is a preload of a guess.**
        #
        # `_selected_model` is ``None`` whenever `select_default_model` declined
        # everything installed — which on a machine whose only chat model does
        # not fit alongside the embedder is the *normal* outcome, not an edge
        # case. `warm(None)` then fell through to `OllamaEngine.default_model`,
        # a hardcoded `gemma3:latest`, and warmed a model that was not
        # installed. It failed at `logger.info` and returned False, so the
        # promise this method exists to keep — that warming is a once-a-session
        # state rather than a per-message one — was quietly not being kept, and
        # the first message paid the full cold start it was written to avoid.
        #
        # Nothing to warm is a fact worth logging, not a name worth guessing.
        if not self._selected_model:
            logger.info(
                "[ModelsRuntime] No preload: no model was selected, and warming "
                "the engine default would warm a model the user has not chosen."
            )
            return False

        engine = getattr(self._service, "engine", None)
        # `RoutedEngine` wraps the local one. Warming the wrapper would send an
        # empty prompt down whichever path the router picks, which for a cloud
        # model is a billed request to a third party — for a preload nobody
        # asked for. Reach the local engine specifically.
        local = getattr(engine, "_local", engine)
        warm = getattr(local, "warm", None)
        if not callable(warm):
            return False

        import asyncio

        return await asyncio.to_thread(warm, self._selected_model)

    def reload_engine(self) -> bool:
        """Rebuild the engine from the current configuration. Returns whether cloud is present.

        The cloud engine is built once, at boot, from environment variables —
        which was fine while the only way to set them was before launch. A key
        entered in Settings has to reach the thing that *sends*, or the user
        gets a screen saying connected and every message answered locally with
        nothing explaining why.

        The selected model is deliberately carried across rather than
        re-chosen. Rebuilding is a reaction to a configuration change the user
        made; silently moving them onto a different model at the same time
        would be a second change they did not ask for.
        """
        engine = self._build_engine()
        if self._selected_model:
            engine.default_model = self._selected_model
        if self._service is None:
            self._service = ModelsService(engine, knowledge_runtime=self._knowledge_runtime)
        else:
            self._service.engine = engine
        return isinstance(engine, RoutedEngine)

    #: Provider kinds that speak the OpenAI wire format on this machine.
    #: Compared by string so this runtime keeps its promise not to import
    #: `providers` -- the same reason `_provider_manager` is typed loosely.
    _LOCAL_OPENAI_KINDS = frozenset({"local_ai_server"})

    def _local_endpoint_for(self, model_id: str) -> Optional[str]:
        """The local OpenAI-compatible endpoint holding `model_id`, or None.

        None means "not one of those", which the dispatcher reads as "use
        Ollama". It is returned for every failure too: no provider layer, an id
        the catalogue cannot place that carries no provider prefix either, an
        unregistered provider, a lookup that raised. Ollama is the safe
        fallback because an id this cannot place is far more often one Ollama
        serves than one it does not.

        **The catalogue answers first, and that is the fix rather than a
        tidying.** `provider_of`, `locality_of` and `wire_name` all resolve a
        model through `_catalogued`, which normalises a bare provider-native
        name; this one asked a `split(":", 1)` instead. So one question had two
        implementations that disagreed, and the disagreement was reachable:
        `Qwen3.8-27B-exl3-2.20bpw` — the name TabbyAPI itself reports, and the
        one the catalogue stores as `display_name` — was announced to the user
        as `provider: lm_studio` by the answering event and posted to **Ollama**
        by the dispatcher, which answered `model not found`. Measured on this
        machine, 28 August 2026: the same request with the full catalogue id
        `lm_studio:Qwen3.8-27B-exl3-2.20bpw` reached TabbyAPI and generated.

        This is the same class as one score answering two questions, arriving
        from the other side: two answers to one question. The prefix split
        stays *below* the catalogue, for an id the catalogue does not hold that
        still names its provider — it was never wrong, only incomplete.

        Note what is *not* used to decide: the model's name. `RoutedEngine`
        already rejects name matching as "a string comparison against a list
        nobody maintains", and the same objection applies here with more force
        -- a user can pull a model called anything at all. Reading
        `display_name` off the catalogue record is the opposite of that: it is
        what discovery recorded, not what the string looks like.
        """
        manager = self._provider_manager
        if manager is None or not model_id:
            return None

        info = self._catalogued(model_id)
        provider_id = getattr(info, "provider", None) if info is not None else None
        if not provider_id and ":" in model_id:
            provider_id = model_id.split(":", 1)[0]
        if not provider_id:
            return None

        try:
            provider = manager.registry.get_model_provider(provider_id)
        except Exception:
            return None
        if provider is None:
            return None
        kind = getattr(getattr(provider, "kind", None), "value", None)
        if kind not in self._LOCAL_OPENAI_KINDS:
            return None
        base_url = getattr(provider, "base_url", None)
        return base_url or None

    def wire_name(self, model: str) -> str:
        """The name the provider itself speaks, for a model catalogued as `model`.

        Three questions about one model, and they must not be merged: *where
        does it run* (`locality_of`), *may it leave the machine*
        (`_is_remote_model`), and *what is it called on the wire* (this). The
        first two already had homes and this one did not, so the id the
        catalogue invented — ``ollama:qwen2.5-coder:1.5b`` — travelled all the
        way into the request body and Ollama answered 400.

        `display_name` is the provider-native name: the discoverer sets it from
        what the provider reported, and `ProviderManager._resolve_model`
        already documents it as "the name that both the chat path and
        `/api/ps` speak".

        Returns the input unchanged whenever the catalogue cannot place it —
        no provider layer, an unknown name, a lookup that raised. A model this
        cannot resolve is very often one Ollama can (`qwen3` for
        `qwen3:latest`), so refusing here would break the ordinary case in the
        name of tidiness.
        """
        info = self._catalogued(model)
        if info is None or not getattr(info, "display_name", None):
            return model
        return info.display_name

    def provider_of(self, model: Optional[str]) -> Optional[str]:
        """Which provider owns this model, or ``None`` when unresolved.

        For display only — "OpenRouter" beside a reply is how a user tells that
        an answer actually came from the service they connected, which was
        unknowable before. It gates nothing, and ``None`` is rendered as
        nothing rather than guessed.
        """
        info = self._catalogued(model)
        return getattr(info, "provider", None) if info is not None else None

    def _catalogued(self, model: Optional[str]) -> Optional[Any]:
        """The provider layer's record for `model`, or ``None``.

        The lookup only. Every caller keeps its own reading of ``None``, and
        those readings differ on purpose: routing treats it as "do not send",
        identity treats it as "do not claim", display treats it as "say
        nothing". Sharing the lookup must not become sharing the answer.
        """
        if not model or self._provider_manager is None:
            return None
        try:
            info = self._provider_manager.get_model(model)
            if info is None:
                resolve = getattr(self._provider_manager, "_resolve_model", None)
                info = resolve(model) if callable(resolve) else None
            return info
        except Exception as exc:
            logger.debug("catalogue lookup failed for %r: %s", model, exc)
            return None

    def locality_of(self, model: Optional[str]) -> Optional[str]:
        """Where this model runs: ``"local"``, ``"cloud"``, or ``None``.

        Deliberately *not* `_is_remote_model` with a nicer return type. That
        method answers "may this leave the machine?" and returns ``False`` for
        anything it cannot resolve, because the failure modes of routing are not
        symmetric. This one answers "where does this run?", and for that question
        an unresolved model is genuinely unknown — reporting it as local would be
        a confident false claim about the one thing the user has to be able to
        trust, which is worse than saying nothing.

        Same input, two questions, two answers. Callers must not swap them.
        """
        if not model or self._provider_manager is None:
            return None

        info = self._provider_manager.get_model(model)
        if info is None:
            resolve = getattr(self._provider_manager, "_resolve_model", None)
            info = resolve(model) if callable(resolve) else None
        if info is None:
            return None

        return "cloud" if info.locality in REMOTE_LOCALITIES else "local"

    def _is_remote_model(self, model: Optional[str]) -> bool:
        """Would answering with this model send data off the machine?

        Answered from what discovery recorded, never from the shape of the
        name. `gpt-oss` runs on Ollama; a router that matched `"gpt"` would
        send a local model's prompts to a cloud provider, which is the exact
        class of mistake `locality` exists to prevent.

        False whenever the question cannot be answered — no provider layer, an
        unknown model, an exception. The failure modes are not symmetric:
        guessing local costs a possibly-wrong model, guessing cloud costs the
        user's documents leaving the machine on a lookup that failed.
        """
        if not model or self._provider_manager is None:
            return False

        info = self._provider_manager.get_model(model)
        if info is None:
            # `get_model` is exact; `_resolve_model` normalises tags and
            # aliases the way the rest of the provider layer does.
            resolve = getattr(self._provider_manager, "_resolve_model", None)
            info = resolve(model) if callable(resolve) else None
        if info is None:
            logger.debug("no provider record for model %r, routing local", model)
            return False

        return info.locality in REMOTE_LOCALITIES

    async def _choose_model(self) -> Optional[str]:
        """Ask the provider layer which model may be used without being asked.

        Every failure here returns ``None`` and leaves the engine on its own
        default. That is deliberate: this wiring is new and the chat path is
        not, so a provider layer that is absent, unscannable or offline must
        degrade to the previous behaviour rather than take chat down with it.

        **That promise was written and then only half-kept, for two weeks.**
        The ``try`` below covered the two provider calls and stopped there, so
        the block that logs *which* models were excluded sat outside it — and
        an `AttributeError` in that block escaped through kernel boot, erroring
        53 tests at app startup with a traceback that named a logging line
        rather than the model layer. A guarantee that covers the part expected
        to fail, and not the part nobody thought about, is the shape of every
        bug this function exists to prevent.

        So the whole body is now inside the guarantee rather than the first two
        statements of it. `tests/test_choosing_a_model_never_takes_boot_down.py`
        asserts it against shapes the provider layer should never return,
        because the contract is about *failure* and cannot be satisfied by
        handling one more shape correctly.
        """
        if self._provider_manager is None:
            return None

        try:
            return await self._choose_model_inner()
        except Exception as exc:
            # Deliberately broad. Anything at all beats taking chat down, and
            # the engine default is a working fallback rather than a degraded
            # one — see the docstring.
            logger.warning(
                "[ModelsRuntime] Choosing a default model failed, using engine "
                "default: %s: %s",
                type(exc).__name__,
                exc,
            )
            return None

    async def _choose_model_inner(self) -> Optional[str]:
        """The body of `_choose_model`, which owns the failure guarantee.

        Split out so that guarantee is one ``try`` around everything rather
        than a ``try`` a later edit can append past — which is exactly how the
        logging block came to sit outside it.
        """
        try:
            await self._provider_manager.ensure_scanned()
            model = self._provider_manager.select_default_model()
        except Exception as exc:
            logger.warning(
                "[ModelsRuntime] Provider layer unavailable, using engine default: %s", exc
            )
            return None

        if model is None:
            # Not an error. It is the correct outcome when the only models
            # present are ones we may not choose on the user's behalf.
            #
            # **This line used to crash the backend on startup.**
            # `rejected_default_candidates()` returns `list[tuple[ModelInfo,
            # str]]` — the model *and why it was rejected* — and this read
            # `m.id for m in rejected`, so it raised `AttributeError: 'tuple'
            # object has no attribute 'id'` inside kernel boot. Not a logging
            # nicety: a user whose installed models are all unselectable could
            # not start Zaram at all, and the traceback named a log line rather
            # than the model layer.
            #
            # It also threw away the reason it was handed. The docstring on the
            # producing function says why that matters — "a user told 'no
            # default model' deserves to know whether that was their data
            # policy or their VRAM, since only one of those is something they
            # can act on" — while this message asserted *data policy* for every
            # rejection, so a model excluded for not fitting alongside the
            # embedder was reported as a privacy decision. Two different
            # remedies, one wrong sentence.
            rejected = self._provider_manager.rejected_default_candidates()
            if rejected:
                logger.info(
                    "[ModelsRuntime] No default model: %d available model(s) excluded "
                    "(%s). The user must choose one deliberately.",
                    len(rejected),
                    ", ".join(sorted(f"{m.id}: {reason}" for m, reason in rejected)),
                )
            return None

        return model.display_name

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        self._service = None
        self._state = RuntimeState.STOPPED
        logger.info("[ModelsRuntime] Shut down.")

    def get_state(self) -> RuntimeState:
        return self._state

    def health_check(self) -> Dict[str, Any]:
        return {
            "runtime_id": self.get_runtime_id(),
            "state": self._state.value,
            "healthy": self._state == RuntimeState.READY,
            "model": self._selected_model,
        }

    def get_service(self) -> ModelsService:
        """Helper to access the service for the Capability Router."""
        return self._service
