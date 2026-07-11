from typing import Protocol, Iterator

class LLMEngine(Protocol):
    """Abstract interface for ANY LLM model."""
    def stream_response(self, prompt: str, model: str) -> Iterator[str]:
        """Streams text tokens from the LLM."""
        ...