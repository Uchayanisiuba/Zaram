"""Routing a chat request to the engine that answers it.

**Both streams below drive a synchronous generator from an async one, and that
seam is load-bearing.** The engine, the providers and the egress gate are all
ordinary blocking code. Iterated with a plain ``for`` inside an ``async def``,
every one of their blocking steps runs on the event loop thread — which means
the server cannot answer anything else until the token arrives.

That was survivable while every step was fast and local. It stopped being
survivable the moment the egress gate learned to ask: the confirm hook blocks
until a person answers, the person answers through ``/egress/pending``, and a
frozen event loop cannot serve the endpoint that would release it. Observed
rather than reasoned about — the whole backend, ``/health`` included, went
unresponsive for the full confirmation timeout, and the log then recorded the
timeout as though the user had refused.

So the sync generator is iterated in a worker thread. `iterate_in_threadpool`
runs each ``__next__`` off the loop, which costs one pooled thread per active
stream and keeps the process answering while a question is on screen.
"""

import os
from dotenv import load_dotenv
from starlette.concurrency import iterate_in_threadpool
from typing import AsyncGenerator, Any

load_dotenv()
USE_NEW_KERNEL = os.getenv("USE_NEW_KERNEL", "false").lower() == "true"


class ChatRouter:
    """
    Routes chat requests to either the new Execution Engine or the Legacy path.
    This isolates the Strangler Fig feature flag from the FastAPI layer.
    """
    def __init__(self, execution_engine, event_bus, legacy_generator_func):
        self.execution_engine = execution_engine
        self.event_bus = event_bus
        self.legacy_generator_func = legacy_generator_func

    def route(
        self,
        request_text: str,
        model: str,
        system_prompt: str = "",
        session_id: str = "default",
        project_id: str | None = None,
        only_ids: frozenset[str] | None = None,
        images: list[str] | None = None,
    ) -> AsyncGenerator:
        """Returns the correct generator based on the feature flag.

        `project_id` scopes recall and capture to one project plus global
        (rule 7i). None means no project is active, which is a real answer:
        facts captured then stay `global` rather than being assigned to a
        project nobody chose.

        `only_ids` narrows recall to a knowledge domain, already resolved to
        fact ids by the API layer — a separate axis from scope, since one is
        about whose work a fact belongs to and the other about which library
        the user chose to read from. ``None`` is unrestricted; an **empty set
        is not**, and means a domain holding nothing. Never test it for
        truthiness anywhere along this chain.
        """
        if USE_NEW_KERNEL:
            return self._kernel_stream(
                request_text, model, system_prompt, session_id, project_id,
                only_ids, images,
            )
        else:
            # The legacy path has no image plumbing and is not getting any.
            # Dropping them silently would answer about a picture nobody
            # looked at, so it refuses instead - see `_legacy_stream`.
            return self._legacy_stream(request_text, model, system_prompt, images)

    async def _kernel_stream(
        self,
        text: str,
        model: str,
        system_prompt: str = "",
        session_id: str = "default",
        project_id: str | None = None,
        only_ids: frozenset[str] | None = None,
        images: list[str] | None = None,
    ) -> AsyncGenerator:
        """Streams structured StreamEvent lines from the new Execution Engine.

        The engine yields plain strings for response tokens and StreamEvent
        objects for structured output such as provenance; both are forwarded.

        Iterated off the event loop — see the module docstring. The engine can
        block for a long time inside one `next()`, and while it does, the loop
        has to keep serving the endpoints that end the wait.
        """
        from core.reasoning import ReasoningSplitter
        from core.streaming_events import StreamEvent, EventType
        # One splitter per reply. Reusing one across replies would carry an
        # unclosed <think> from a truncated answer into the next question, and
        # that answer would vanish into the thinking panel.
        splitter = ReasoningSplitter()
        try:
            yield StreamEvent.start().to_ipc() + "\n"
            async for item in iterate_in_threadpool(self.execution_engine.execute(
                text, model, system_prompt, session_id,
                project_id=project_id, only_ids=only_ids, images=images,
            )):
                if isinstance(item, StreamEvent):
                    yield item.to_ipc() + "\n"
                else:
                    for line in _token_events(splitter, item):
                        yield line
            for line in _flush_events(splitter):
                yield line
            yield StreamEvent.status("complete").to_ipc() + "\n"
        except Exception as exc:
            yield StreamEvent.error(str(exc)).to_ipc() + "\n"
        yield StreamEvent.done().to_ipc() + "\n"

    async def _legacy_stream(
        self,
        text: str,
        model: str,
        system_prompt: str = "",
        images: list[str] | None = None,
    ) -> AsyncGenerator:
        """Transforms legacy ConversationManager events into structured StreamEvents.

        Off the event loop for the same reason as the kernel stream. This path
        talks to Ollama, which is loopback and never reaches the confirm hook —
        but it blocks the loop for the length of every generation regardless,
        and leaving one of the two chat paths able to freeze the server is the
        kind of asymmetry that gets found by a user rather than by a test.

        **It refuses images rather than ignoring them.** There is no plumbing
        here and none is being added — but a path that quietly dropped the
        attachment would answer with confident prose about a picture nobody
        looked at, which is precisely rule 9's failure. Saying so costs one
        branch; the alternative is indistinguishable from a correct answer.
        """
        from core.streaming_events import StreamEvent

        if images:
            yield StreamEvent.error(
                "This build's legacy chat path cannot read images. Remove the "
                "attachment to ask about the text, or enable the kernel path."
            ).to_ipc() + "\n"
            yield StreamEvent.done().to_ipc() + "\n"
            return
        from core.reasoning import ReasoningSplitter
        from core.streaming_events import StreamEvent, EventType
        import json
        splitter = ReasoningSplitter()
        try:
            yield StreamEvent.start().to_ipc() + "\n"
            async for event in iterate_in_threadpool(
                self.legacy_generator_func(text, model, system_prompt)
            ):
                if isinstance(event, dict):
                    etype = event.get("type")
                    if etype == "token":
                        for line in _token_events(splitter, event.get("content", "")):
                            yield line
                    elif etype == "audio":
                        yield StreamEvent.source("audio", event.get("url")).to_ipc() + "\n"
                    elif etype == "error":
                        yield StreamEvent.error(event.get("content", "")).to_ipc() + "\n"
                    elif etype == "llm_done":
                        yield StreamEvent.status("complete").to_ipc() + "\n"
                    elif etype == "done":
                        pass
                elif isinstance(event, str):
                    for line in _token_events(splitter, event):
                        yield line
            for line in _flush_events(splitter):
                yield line
            yield StreamEvent.done().to_ipc() + "\n"
        except Exception as exc:
            yield StreamEvent.error(str(exc)).to_ipc() + "\n"
            yield StreamEvent.done().to_ipc() + "\n"


def _token_events(splitter, text: str):
    """Yield the NDJSON lines one model token becomes, thinking split out.

    One helper, every caller. `docs/SPEECH.md` records what the alternative
    costs: marker stripping lived in three copies, and the one that had been
    missed was the one that spoke.
    """
    from core.reasoning import REASONING as _REASONING
    from core.streaming_events import StreamEvent

    for kind, chunk in splitter.feed(text):
        event = StreamEvent.reasoning(chunk) if kind == _REASONING else StreamEvent.token(chunk)
        yield event.to_ipc() + "\n"


def _flush_events(splitter):
    """Whatever the splitter still holds at end of stream. Never dropped."""
    from core.reasoning import REASONING as _REASONING
    from core.streaming_events import StreamEvent

    for kind, chunk in splitter.flush():
        event = StreamEvent.reasoning(chunk) if kind == _REASONING else StreamEvent.token(chunk)
        yield event.to_ipc() + "\n"
