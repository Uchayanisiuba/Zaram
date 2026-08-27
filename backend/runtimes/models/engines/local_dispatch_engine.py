"""Local does not mean Ollama.

``RoutedEngine`` splits the world in two -- local or cloud -- and hands
everything local to ``OllamaEngine``. That was true while Ollama was the only
local server, and it silently stopped being true the moment the provider
catalogue gained ``lm_studio``: an OpenAI-compatible server on
``127.0.0.1:1234``, which is *also* local.

The failure it produced is the quiet kind. A model served by TabbyAPI on that
port is discovered, catalogued, listed in the picker with an honest
``NEVER_LEAVES_DEVICE`` policy, chosen by the user -- and then posted to
Ollama, which has never heard of it:

    Ollama refused the request for Qwen3.8-27B-exl3-2.20bpw:
    model 'Qwen3.8-27B-exl3-2.20bpw' not found

Nothing in that message points at the routing layer, and every individual
component was working. This is the shape ``CLAUDE.md`` calls out -- a complete,
tested subsystem with no reachable caller -- arriving in the one place it is
hardest to see, because the surface it breaks looks fully wired.

**Dispatch is by provider, never by guessing at the name.** The catalogue id
carries its provider (``lm_studio:Qwen3.8-27B-exl3-2.20bpw``), and the registry
knows that provider's base URL. Matching on the model *name* -- "looks like a
GGUF", "contains exl3" -- would be the string comparison against a list nobody
maintains that ``RoutedEngine``'s own docstring already rejects.

**Ollama remains the fallback for anything unresolved**, which is the same
fail-safe direction the rest of this layer takes: an unrecognised model is far
more often one Ollama can serve (``qwen3`` for ``qwen3:latest``) than one it
cannot, and refusing here would break the ordinary case to protect the rare
one.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterator, Optional

from .base_engine import LLMEngine
from .openai_compatible_engine import OpenAICompatibleEngine

logger = logging.getLogger(__name__)

#: Given a catalogue model id, the base URL of the local OpenAI-compatible
#: server that holds it, or ``None`` for "not one of those".
ResolveLocalEndpoint = Callable[[str], Optional[str]]

#: Given a catalogue model id, the name that provider speaks on the wire.
WireName = Callable[[str], str]


class LocalDispatchEngine(LLMEngine):
    """Routes an on-device model to whichever local server actually holds it."""

    def __init__(
        self,
        *,
        ollama: LLMEngine,
        resolve_endpoint: ResolveLocalEndpoint,
        wire_name: WireName,
        gate: Any = None,
    ) -> None:
        self._ollama = ollama
        self._resolve_endpoint = resolve_endpoint
        self._wire_name = wire_name
        self._gate = gate
        #: Engines are cached per endpoint. Constructing one is cheap, but a
        #: new object per message would discard nothing useful and make the
        #: logs harder to read.
        self._engines: Dict[str, OpenAICompatibleEngine] = {}

    @property
    def default_model(self) -> Optional[str]:
        return getattr(self._ollama, "default_model", None)

    @default_model.setter
    def default_model(self, value: Optional[str]) -> None:
        self._ollama.default_model = value  # type: ignore[attr-defined]

    def _engine_for(self, endpoint: str, wire: str) -> OpenAICompatibleEngine:
        cached = self._engines.get(endpoint)
        if cached is not None:
            cached.default_model = wire
            return cached
        # No API key, and that is correct rather than missing: these servers
        # are on loopback and ship auth-free. `OpenAICompatibleEngine` permits
        # a keyless endpoint only when the address is loopback, so a cloud
        # provider still cannot reach this path.
        engine = OpenAICompatibleEngine(
            base_url=endpoint,
            api_key="",
            default_model=wire,
            gate=self._gate,
            source="chat",
        )
        self._engines[endpoint] = engine
        return engine

    def stream_vision_response(self, prompt: str, images, system_prompt: str = ""):
        """Forwarded, not reimplemented.

        Wrapping an engine silently drops every method the wrapper does not
        name, and `Dispatcher` reaches for this one by attribute. Before this
        wrapper existed a keyless setup got a bare `OllamaEngine` and vision
        worked; adding a layer without forwarding turned that into

            AttributeError: object has no attribute 'stream_vision_response'

        `RoutedEngine` already had the same hole. Vision stays on the local
        engine because that is where it is implemented today -- routing it by
        provider needs `ModelInfo.supports_vision` to gate the choice, which is
        the modality-as-a-gate work `CLAUDE.md` describes and is not this
        change.
        """
        return self._ollama.stream_vision_response(prompt, images, system_prompt)

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        images: Optional[Any] = None,
    ) -> Iterator[str]:
        endpoint: Optional[str] = None
        if model:
            try:
                endpoint = self._resolve_endpoint(model)
            except Exception as exc:  # noqa: BLE001
                # Same posture as `RoutedEngine`'s locality lookup: a failed
                # resolution falls back rather than failing the message.
                logger.warning(
                    "local endpoint lookup failed for %r, using Ollama: %s", model, exc
                )
                endpoint = None

        if endpoint is None:
            yield from self._ollama.stream_response(prompt, system_prompt, model, images)
            return

        wire = model or ""
        try:
            wire = self._wire_name(model) if model else ""
        except Exception:  # noqa: BLE001
            logger.debug("wire_name failed for %r; sending id unchanged", model)

        logger.info("[LocalDispatch] %s -> %s (as %r)", model, endpoint, wire)
        engine = self._engine_for(endpoint, wire)
        yield from engine.stream_response(prompt, system_prompt, wire, images)
