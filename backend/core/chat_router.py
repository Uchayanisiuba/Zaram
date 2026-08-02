import os
from dotenv import load_dotenv
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
    ) -> AsyncGenerator:
        """Returns the correct generator based on the feature flag."""
        if USE_NEW_KERNEL:
            return self._kernel_stream(request_text, model, system_prompt, session_id)
        else:
            return self._legacy_stream(request_text, model, system_prompt)

    async def _kernel_stream(
        self,
        text: str,
        model: str,
        system_prompt: str = "",
        session_id: str = "default",
    ) -> AsyncGenerator:
        """Streams structured StreamEvent lines from the new Execution Engine.

        The engine yields plain strings for response tokens and StreamEvent
        objects for structured output such as provenance; both are forwarded.
        """
        from core.streaming_events import StreamEvent, EventType
        try:
            yield StreamEvent.start().to_ipc() + "\n"
            for item in self.execution_engine.execute(text, model, system_prompt, session_id):
                if isinstance(item, StreamEvent):
                    yield item.to_ipc() + "\n"
                else:
                    yield StreamEvent.token(item).to_ipc() + "\n"
            yield StreamEvent.status("complete").to_ipc() + "\n"
        except Exception as exc:
            yield StreamEvent.error(str(exc)).to_ipc() + "\n"
        yield StreamEvent.done().to_ipc() + "\n"

    async def _legacy_stream(self, text: str, model: str, system_prompt: str = "") -> AsyncGenerator:
        """Transforms legacy ConversationManager events into structured StreamEvents."""
        from core.streaming_events import StreamEvent, EventType
        import json
        try:
            yield StreamEvent.start().to_ipc() + "\n"
            for event in self.legacy_generator_func(text, model, system_prompt):
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
