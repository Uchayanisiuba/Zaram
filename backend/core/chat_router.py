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
    ) -> AsyncGenerator:
        """Returns the correct generator based on the feature flag.

        `project_id` scopes recall and capture to one project plus global
        (rule 7i). None means no project is active, which is a real answer:
        facts captured then stay `global` rather than being assigned to a
        project nobody chose.
        """
        if USE_NEW_KERNEL:
            return self._kernel_stream(
                request_text, model, system_prompt, session_id, project_id
            )
        else:
            return self._legacy_stream(request_text, model, system_prompt)

    async def _kernel_stream(
        self,
        text: str,
        model: str,
        system_prompt: str = "",
        session_id: str = "default",
        project_id: str | None = None,
    ) -> AsyncGenerator:
        """Streams structured StreamEvent lines from the new Execution Engine.

        The engine yields plain strings for response tokens and StreamEvent
        objects for structured output such as provenance; both are forwarded.

        Iterated off the event loop — see the module docstring. The engine can
        block for a long time inside one `next()`, and while it does, the loop
        has to keep serving the endpoints that end the wait.
        """
        from core.streaming_events import StreamEvent, EventType
        try:
            yield StreamEvent.start().to_ipc() + "\n"
            async for item in iterate_in_threadpool(self.execution_engine.execute(
                text, model, system_prompt, session_id, project_id=project_id
            )):
                if isinstance(item, StreamEvent):
                    yield item.to_ipc() + "\n"
                else:
                    yield StreamEvent.token(item).to_ipc() + "\n"
            yield StreamEvent.status("complete").to_ipc() + "\n"
        except Exception as exc:
            yield StreamEvent.error(str(exc)).to_ipc() + "\n"
        yield StreamEvent.done().to_ipc() + "\n"

    async def _legacy_stream(self, text: str, model: str, system_prompt: str = "") -> AsyncGenerator:
        """Transforms legacy ConversationManager events into structured StreamEvents.

        Off the event loop for the same reason as the kernel stream. This path
        talks to Ollama, which is loopback and never reaches the confirm hook —
        but it blocks the loop for the length of every generation regardless,
        and leaving one of the two chat paths able to freeze the server is the
        kind of asymmetry that gets found by a user rather than by a test.
        """
        from core.streaming_events import StreamEvent, EventType
        import json
        try:
            yield StreamEvent.start().to_ipc() + "\n"
            async for event in iterate_in_threadpool(
                self.legacy_generator_func(text, model, system_prompt)
            ):
                if isinstance(event, dict):
                    etype = event.get("type")
                    if etype == "token":
                        yield StreamEvent.token(event.get("content", "")).to_ipc() + "\n"
                    elif etype == "audio":
                        yield StreamEvent.source("audio", event.get("url")).to_ipc() + "\n"
                    elif etype == "error":
                        yield StreamEvent.error(event.get("content", "")).to_ipc() + "\n"
                    elif etype == "llm_done":
                        yield StreamEvent.status("complete").to_ipc() + "\n"
                    elif etype == "done":
                        pass
                elif isinstance(event, str):
                    yield StreamEvent.token(event).to_ipc() + "\n"
            yield StreamEvent.done().to_ipc() + "\n"
        except Exception as exc:
            yield StreamEvent.error(str(exc)).to_ipc() + "\n"
            yield StreamEvent.done().to_ipc() + "\n"
