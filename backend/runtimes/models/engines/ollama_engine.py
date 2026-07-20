# backend/runtimes/models/engines/ollama_engine.py
import requests
import json
from typing import Iterator
from .base_engine import LLMEngine

class OllamaEngine(LLMEngine):
    def __init__(self, base_url: str = "http://127.0.0.1:11434"):
        self.base_url = base_url
        self.default_model = "gemma3:latest"

    def stream_response(self, prompt: str, context: str = "", model: str | None = None) -> Iterator[str]:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model or self.default_model,
            "prompt": prompt,
            "system": context,
            "stream": True
        }
        print(f"[STAGE-9][LLM] OllamaEngine.stream_response called: model={payload['model']}, prompt='{prompt[:50]}...'")
        try:
            response = requests.post(url, json=payload, stream=True, timeout=120)
            response.raise_for_status()
            print(f"[STAGE-9][LLM] Ollama responded, streaming tokens...")
            token_count = 0
            for line in response.iter_lines():
                if line:
                    json_data = json.loads(line)
                    if "response" in json_data:
                        token_count += 1
                        yield json_data["response"]
            print(f"[STAGE-9][LLM] Done streaming. Total tokens: {token_count}")
        except Exception as e:
            print(f"[STAGE-9][LLM] Error: {e}")
            yield f"⚠️ Error connecting to LLM: {str(e)}"

    def stream_vision_response(self, prompt: str, images: list[str], system_prompt: str = "") -> Iterator[str]:
        url = f"{self.base_url}/api/generate"
        clean_images = [img for img in (images or []) if img and img.strip()]
        if not clean_images:
            yield "⚠️ No valid image provided for vision analysis. Attach or capture an image before analyzing."
            return
        payload = {
            "model": "qwen2.5vl:7b",
            "prompt": prompt,
            "images": clean_images,
            "system": system_prompt,
            "stream": True
        }
        print(f"[STAGE-9][Vision] OllamaEngine.stream_vision_response called: model=qwen2.5vl:7b, prompt='{prompt[:50]}...', images={len(clean_images)}")
        try:
            response = requests.post(url, json=payload, stream=True, timeout=120)
            response.raise_for_status()
            print(f"[STAGE-9][Vision] Ollama responded, streaming tokens...")
            token_count = 0
            for line in response.iter_lines():
                if line:
                    json_data = json.loads(line)
                    if "response" in json_data:
                        text = json_data["response"]
                        if "does not support image input" in text or "doesn't support image input" in text:
                            yield ("⚠️ The vision model rejected the image input. Ensure the image is a valid PNG/JPEG "
                                   "and that the 'qwen2.5vl:7b' model is pulled (run: ollama pull qwen2.5vl:7b).")
                            return
                        token_count += 1
                        yield text
            print(f"[STAGE-9][Vision] Done streaming. Total tokens: {token_count}")
        except Exception as e:
            print(f"[STAGE-9][Vision] Error: {e}")
            yield f"⚠️ Error connecting to Vision LLM: {str(e)}"