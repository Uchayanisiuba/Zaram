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
from .openai_compatible_engine import LOCAL_SAMPLING, OpenAICompatibleEngine

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
        #: The runtime's chosen model, when nothing in the request names one.
        #: Held here rather than only on Ollama — see the `default_model`
        #: setter for the failure that caused.
        self._default_model: Optional[str] = getattr(ollama, "default_model", None)
        #: Engines are cached per endpoint. Constructing one is cheap, but a
        #: new object per message would discard nothing useful and make the
        #: logs harder to read.
        self._engines: Dict[str, OpenAICompatibleEngine] = {}

    @property
    def default_model(self) -> Optional[str]:
        return self._default_model

    @default_model.setter
    def default_model(self, value: Optional[str]) -> None:
        """Kept here as well as on Ollama, and *here* is the one that dispatches.

        **This property was the same defect as the one this class exists to
        fix, one door along.** It stored the runtime's chosen default on
        `self._ollama` and nowhere else, so a default served by TabbyAPI was
        recorded on the engine that cannot reach it — and `stream_response`
        below, handed ``model=None``, never attempted resolution at all and
        went straight to Ollama.

        That is the ordinary path, not an edge case. `_resolve_model` returns
        ``_ModelChoice(None, "zaram")`` whenever nobody named a model, which is
        every message where the user has expressed no preference. Measured on
        this machine, 28 August 2026, asking *"What are you, and who made
        you?"* with no model named::

            answering -> {"model": "Qwen3.8-27B-exl3-2.20bpw",
                          "locality": "local", "provider": "lm_studio"}
            answer    -> [ERROR] Ollama refused the request for
                         Qwen3.8-27B-exl3-2.20bpw: model not found

        The interface named one server and the dispatcher used another, which
        is the routing-legibility claim inverted on the surface whose whole job
        is to be trusted.

        Ollama keeps its copy so that everything about the Ollama-served case
        is unchanged, including what it falls back to when this wrapper hands
        it ``None``.
        """
        self._default_model = value
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
        # Sampling is supplied here and nowhere else. A local server has no
        # Modelfile to carry per-model defaults the way Ollama does, so with
        # nothing sent it generates at its own factory setting -- TabbyAPI's is
        # unconstrained. Cloud engines are built elsewhere and deliberately do
        # not get this: a provider's default is part of what the user chose
        # when they connected it. See `LOCAL_SAMPLING`.
        engine = OpenAICompatibleEngine(
            base_url=endpoint,
            api_key="",
            default_model=wire,
            gate=self._gate,
            source="chat",
            sampling=LOCAL_SAMPLING,
        )
        self._engines[endpoint] = engine
        return engine

    def warm(self, model: Optional[str] = None, *, timeout: Optional[float] = None) -> bool:
        """Preload `model` on whichever local server actually holds it.

        **This wrapper had no `warm` at all, and the preload died silently when
        it was introduced.** `ModelsRuntime.warm_local_model` reaches the local
        engine and asks::

            warm = getattr(local, "warm", None)
            if not callable(warm):
                return False

        `local` is this class. So the guard — written to tolerate an engine
        that cannot preload — swallowed the fact that the engine which *can*
        was one attribute further down, and every session since has paid a full
        cold start on its first message. The state was reported honestly; the
        preload the state exists to make unnecessary was never running.

        `test_the_selected_model_is_the_one_preloaded` passed throughout,
        because it injects a fake engine that has a `warm` method. That is the
        shape `CLAUDE.md` names — a test asserting the scaffolding rather than
        the contract — and the fix is the test at the bottom of
        `test_local_dispatch.py`, which builds the real stack.

        Dispatch is by provider, exactly as in `stream_response`. Nothing here
        guesses from the model's name.
        """
        chosen = model or self._default_model
        if not chosen:
            return False

        endpoint: Optional[str] = None
        try:
            endpoint = self._resolve_endpoint(chosen)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "local endpoint lookup failed for %r, warming on Ollama: %s", chosen, exc
            )
            endpoint = None

        if endpoint is None:
            warm = getattr(self._ollama, "warm", None)
            if not callable(warm):
                return False
            # `timeout` is forwarded only when the caller set one, so Ollama's
            # own `COLD_START_TIMEOUT` stays the single definition of how long
            # a load may take. Duplicating that constant here is the failure
            # `CLAUDE.md` describes as a number in one place that a gate reads
            # in another.
            if timeout is None:
                return bool(warm(chosen))
            return bool(warm(chosen, timeout=timeout))

        # **A second local server gets no preload, and that is deliberate.**
        # Ollama documents an empty prompt with `keep_alive` as the way to load
        # weights without generating. No OpenAI-compatible server has an
        # equivalent: the nearest thing is a real one-token completion, which
        # is a *generation* — it runs the model, it appears in that server's
        # logs as a request the user never made, and on a server configured
        # with a template that rejects an empty message it fails outright.
        #
        # Spending a hidden inference to remove a wait is a trade the user has
        # not been offered, so the honest answer is that this cannot be warmed.
        # `False` already means exactly that to the caller, and the cold start
        # is still announced by `model_load` when the message arrives.
        logger.info(
            "[LocalDispatch] no preload for %s: %s has no load-without-generate "
            "route", chosen, endpoint,
        )
        return False

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        images: Optional[Any] = None,
    ) -> Iterator[str]:
        # **The default is a choice, and it has to be resolved like one.** An
        # absent `model` does not mean "no model" -- it means the runtime's own
        # pick, which `_resolve_model` reports as `chosen_by: "zaram"` and which
        # the answering event already names to the user. Resolving only the
        # explicit case sent every unspecified message to Ollama while the
        # interface named whichever server actually held the default.
        chosen = model or self._default_model

        endpoint: Optional[str] = None
        if chosen:
            try:
                endpoint = self._resolve_endpoint(chosen)
            except Exception as exc:  # noqa: BLE001
                # Same posture as `RoutedEngine`'s locality lookup: a failed
                # resolution falls back rather than failing the message.
                logger.warning(
                    "local endpoint lookup failed for %r, using Ollama: %s", chosen, exc
                )
                endpoint = None

        if endpoint is None:
            # `model`, not `chosen`. Ollama holds its own copy of the default
            # and applies it itself, so forwarding the argument untouched keeps
            # the Ollama-served path byte-for-byte what it was.
            yield from self._ollama.stream_response(prompt, system_prompt, model, images)
            return

        wire = chosen
        try:
            wire = self._wire_name(chosen)
        except Exception:  # noqa: BLE001
            logger.debug("wire_name failed for %r; sending id unchanged", chosen)

        logger.info("[LocalDispatch] %s -> %s (as %r)", chosen, endpoint, wire)
        engine = self._engine_for(endpoint, wire)
        yield from engine.stream_response(prompt, system_prompt, wire, images)
