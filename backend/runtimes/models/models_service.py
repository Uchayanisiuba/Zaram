# backend/runtimes/models/models_service.py
from typing import Iterator
from .engines.base_engine import LLMEngine

class ModelsService:
    def __init__(self, engine: LLMEngine):
        self.engine = engine

    def generate_response(self, user_text: str, personality_context: str = "") -> Iterator[str]:
        """Orchestrates the prompt generation."""
        # Business logic: Combine context and user text
        full_prompt = f"{user_text}"
        return self.engine.stream_response(full_prompt, personality_context)