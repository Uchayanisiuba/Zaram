# backend/runtimes/models/models_service.py
from typing import Iterator
from .engines.base_engine import LLMEngine

class ModelsService:
    def __init__(self, engine: LLMEngine):
        self.engine = engine

    def generate_response(self, user_text: str, system_prompt: str = "") -> Iterator[str]:
        """Orchestrates the prompt generation."""
        full_prompt = f"{user_text}"
        return self.engine.stream_response(full_prompt, system_prompt)

    def analyze_image(self, prompt: str, image_base64: str, system_prompt: str = "") -> Iterator[str]:
        """Vision analysis using multimodal model."""
        full_prompt = f"{prompt}"
        return self.engine.stream_vision_response(full_prompt, images=[image_base64], system_prompt=system_prompt)