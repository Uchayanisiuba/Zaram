# backend/core/chat_router.py
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
    def __init__(self, execution_engine, legacy_generator_func):
        self.execution_engine = execution_engine
        self.legacy_generator_func = legacy_generator_func

    def route(self, request_text: str, model: str, system_prompt: str = "") -> AsyncGenerator:
        """Returns the correct generator based on the feature flag."""
        if USE_NEW_KERNEL:
            return self._kernel_stream(request_text, model, system_prompt)
        else:
            return self.legacy_generator_func(request_text, model, system_prompt)

    async def _kernel_stream(self, text: str, model: str, system_prompt: str = "") -> AsyncGenerator:
        """Streams tokens from the new Execution Engine as SSE events."""
        import json
        try:
            for token in self.execution_engine.execute(text, model, system_prompt):
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"