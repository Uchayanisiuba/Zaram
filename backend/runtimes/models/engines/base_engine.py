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
        self, prompt: str, system_prompt: str = "", model: str | None = None
    ) -> Iterator[str]:
        """Stream plain text tokens from the LLM."""
        ...
