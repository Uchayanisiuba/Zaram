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
        local = OllamaEngine()
        cloud = cloud_engine_from_environment()
        if cloud is None:
            return local

        logger.info("[ModelsRuntime] Cloud engine available (%s)", cloud.base_url)
        return RoutedEngine(local=local, cloud=cloud, is_remote=self._is_remote_model)

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
        """
        if self._provider_manager is None:
            return None

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
            rejected = self._provider_manager.rejected_default_candidates()
            if rejected:
                logger.info(
                    "[ModelsRuntime] No default model: %d available model(s) excluded "
                    "by data policy (%s). The user must choose one deliberately.",
                    len(rejected),
                    ", ".join(sorted(m.id for m in rejected)),
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
