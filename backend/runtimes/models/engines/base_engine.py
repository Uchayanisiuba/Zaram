# backend/runtimes/models/engines/base_engine.py
from typing import Protocol, Iterator

class LLMEngine(Protocol):
    """The universal interface for all Language Model Engines."""
    def stream_response(
        self, prompt: str, context: str = "", model: str | None = None
    ) -> Iterator[str]:
        """Streams text tokens from the LLM.

        ``model`` names which model answers; ``None`` means the engine's own
        default. The parameter was missing from this protocol while
        ``OllamaEngine`` already accepted it, which is how callers came to drop
        it without anything complaining.
        """
        ...