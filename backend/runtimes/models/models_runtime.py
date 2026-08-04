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

from core.contracts import Capability, Runtime, RuntimeMetadata, RuntimeState
from core.event_bus import EventBus, ZaramEvent

from .engines.ollama_engine import OllamaEngine
from .models_service import ModelsService

logger = logging.getLogger(__name__)


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

        engine = OllamaEngine()
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
