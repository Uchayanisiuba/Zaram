# backend/implementations/ollama_llm.py
import requests
import json
from collections.abc import Iterator

class OllamaLLM:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def stream_response(self, prompt: str, model: str) -> Iterator[str]:
        try:
            with requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": True},
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
            print(f"❌ Ollama LLM Error: {e}")
            yield f"️ Error connecting to LLM: {str(e)}"