# backend/runtimes/models/engines/base_engine.py
"""The one LLM engine contract.

There were four `stream_response` signatures in this repo and no single
interface, so drift in one place failed nowhere else. That is *why* the stale
`FakeLLM` went unnoticed for four milestones while it silently disabled the 13
tests covering streaming conversation.

Everything that generates text implements this and nothing else. A new engine —
`OpenAICompatibleEngine` next — has exactly one shape to satisfy, and
`test_llm_engine_contract.py` fails the build if a real engine or a test double
drifts from it again.
"""

from collections.abc import Iterator
from typing import Protocol, runtime_checkable


#: Prefix marking a yielded chunk as an error rather than model output.
#:
#: Errors travel in-band as text because that is where they end up anyway — the
#: user sees them in the transcript. Making it a named constant means the
#: convention is one thing engines share rather than a string each of them
#: reinvents.
ERROR_PREFIX = "[ERROR] "


def accepts_tools(generate) -> bool:
    """Whether a generate/stream callable takes a ``tools`` keyword. Never raises.

    The native tool channel is offered only to an implementation that can
    take it. A dozen engine and service doubles implement the older
    signature, and the marker instructions are still in the prompt, so an
    implementation without the keyword answers exactly as it did before. A
    signature check rather than a caught ``TypeError``: a generator that
    raises on its first ``next()`` has already been reported as a failed
    generation by the caller's fallback.
    """
    try:
        import inspect

        parameters = inspect.signature(generate).parameters
    except (TypeError, ValueError):
        return False
    if "tools" in parameters:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values())


def forward_stream(engine, prompt, system_prompt, model, images, tools):
    """Call ``engine.stream_response`` with ``tools`` only if it can take them.

    For the wrapper engines, which sit between the service and whichever
    engine — real or a test double — actually answers. Keeps the old
    positional call for an inner engine without the keyword.
    """
    if tools and accepts_tools(engine.stream_response):
        return engine.stream_response(prompt, system_prompt, model, images, tools=tools)
    return engine.stream_response(prompt, system_prompt, model, images)


@runtime_checkable
class LLMEngine(Protocol):
    """The universal interface for all Language Model Engines.

    Implementations yield **plain text tokens** — not SSE frames, not JSON.
    Transport framing belongs to the transport; an engine that emits
    ``data: {...}`` lines forces every caller to parse them straight back off,
    which is exactly what `ModelsService` used to do.

    ``system_prompt`` is the system/context message. It is second because every
    caller in the codebase already passes it second (`generate_response`,
    `dispatch`, `dispatch_stream`), and the odd one out was this protocol.

    ``model`` names which model answers; ``None`` means the engine's own
    default. The parameter was missing from this protocol while ``OllamaEngine``
    already accepted it, which is how callers came to drop it without anything
    complaining.

    Errors are yielded as a final chunk prefixed with :data:`ERROR_PREFIX`
    rather than raised, so a failure mid-stream reaches the user as text
    alongside whatever was already generated instead of tearing down the
    response.
    """

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        images: list[str] | None = None,
        tools: list[dict] | None = None,
    ) -> Iterator[str]:
        """Stream plain text tokens from the LLM.

        ``tools`` are the attached tools in the ``tools``-array shape every
        chat API speaks (`core.tool_loop.native_tool_specs`). An engine that
        can put them on the wire does, and re-emits any call the model makes
        as the ``[TOOL_CALL]`` marker on the text stream, so the loop above
        reads a native call and a typed one identically. An engine that
        cannot ignores them; the marker instructions are still in the prompt.
        Optional, and passed only when there are some, so every existing
        implementation and double is unchanged for an ordinary reply.

        ``images`` are base64-encoded, without a data-URI prefix, and are the
        images attached to *this* message. An engine whose model cannot see
        must not silently drop them: answering as though the picture were not
        there produces confident prose about an image nobody looked at, which
        is rule 9's failure in a new medium. Refuse instead.

        Optional so that every existing implementation and caller is unchanged
        when no image is involved.
        """
        ...
