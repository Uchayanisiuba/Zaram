# backend/runtimes/models/engines/base_engine.py
from typing import Protocol, Iterator

class LLMEngine(Protocol):
    """The universal interface for all Language Model Engines."""
    
    def stream_response(self, prompt: str, context: str = "") -> Iterator[str]:
        """Streams text tokens from the LLM."""
        ...