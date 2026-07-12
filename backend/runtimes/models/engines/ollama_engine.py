# backend/runtimes/models/engines/ollama_engine.py
import requests
import json
from typing import Iterator
from .base_engine import LLMEngine

class OllamaEngine(LLMEngine):
    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        self.base_url = base_url
        self.default_model = "gemma3:latest"

    def stream_response(self, prompt: str, context: str = "") -> Iterator[str]:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.default_model,
            "prompt": prompt,
            "system": context,
            "stream": True
        }
        
        try:
            response = requests.post(url, json=payload, stream=True, timeout=120)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    json_data = json.loads(line)
                    if "response" in json_data:
                        yield json_data["response"]
        except Exception as e:
            yield f"⚠️ Error connecting to LLM: {str(e)}"