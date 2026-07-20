# backend/interfaces/llm_engine.py
from typing import Protocol
from collections.abc import Iterator

class LLMEngine(Protocol):
    """Abstract interface for ANY LLM model."""
    def stream_response(self, prompt: str, model: str) -> Iterator[str]:
        """Streams text tokens from the LLM."""
        ...