import json
from collections.abc import Iterator

import requests


class OllamaLLM:
    """Concrete implementation of the LLMEngine interface using Ollama."""
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def stream_response(self, prompt: str, model: str = "gemma3:latest", system_prompt: str = "") -> Iterator[str]:
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": True
            }
            if system_prompt:
                payload["system"] = system_prompt
            with requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                stream=True, timeout=120
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        json_data = json.loads(line)
                        token = json_data.get("response", "")
                        if token:
                            yield token
        except Exception as e:
            yield f"⚠️ Error connecting to LLM: {str(e)}"
