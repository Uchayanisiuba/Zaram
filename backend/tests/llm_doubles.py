"""Test doubles for `LLMEngine`.

One fake, imported everywhere, instead of a copy per test module.

Three near-identical `FakeLLM` classes had drifted from the real signature, and
because each lived beside the tests that used it, nothing connected them. When
M4 threaded `system_prompt` through `ConversationManager`, all three kept the
old two-argument shape and 13 tests covering streaming conversation — the
most-used path in the product — began failing identically and were normalised
as "pre-existing".

A double that lives in one place still drifts; a double that lives in one place
*and is checked against the protocol* cannot. See
`test_llm_engine_contract.py`.
"""

from __future__ import annotations

from collections.abc import Iterator

DEFAULT_TOKENS = [
    "Hello",
    " world",
    ".",
    " This is one sentence.",
    " This is another sentence.",
]


class FakeLLM:
    """Yields fixed tokens and records how it was called.

    The recorded calls are what make the double useful beyond "it does not
    raise": a test can assert the system prompt actually reached the engine,
    which is the class of bug that started all this.
    """

    def __init__(self, tokens: list[str] | None = None) -> None:
        self.tokens = list(tokens) if tokens is not None else list(DEFAULT_TOKENS)
        #: (prompt, system_prompt, model) per call, in order.
        self.calls: list[tuple[str, str, str | None]] = []
        #: Images seen per call. Kept beside `calls` rather than inside it so
        #: that every existing assertion about `calls` keeps its shape.
        self.images: list[list[str] | None] = []

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        images: list[str] | None = None,
    ) -> Iterator[str]:
        # `images` is on the double for the reason the contract test exists at
        # all: a fake exempt from the interface is the original bug. It kept a
        # two-argument `stream_response` for four milestones while the real
        # client grew a third, and thirteen tests failed identically without
        # anyone reading the message.
        self.calls.append((prompt, system_prompt, model))
        self.images.append(images)
        yield from self.tokens
