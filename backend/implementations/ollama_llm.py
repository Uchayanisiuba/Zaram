import json
from collections.abc import Iterator

import requests

from runtimes.models.engines.base_engine import ERROR_PREFIX


class OllamaLLM:
    """The voice path's Ollama client, conforming to `LLMEngine`.

    This duplicates `runtimes/models/engines/ollama_engine.OllamaEngine` and
    should collapse into it — two Ollama adapters is the drift that produced
    four `stream_response` signatures in the first place. Until then it at
    least satisfies the same contract, which is what
    `test_llm_engine_contract.py` holds it to.
    """

    #: Used when the caller passes ``model=None``.
    default_model = "gemma3:latest"

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def stream_response(self, prompt: str, system_prompt: str = "", model: str | None = None) -> Iterator[str]:
        try:
            payload = {
                "model": model or self.default_model,
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
                accumulated = ""
                for line in response.iter_lines():
                    if line:
                        json_data = json.loads(line)
                        token = json_data.get("response", "")
                        if token:
                            accumulated += token
                            if "does not support image input" in accumulated or "doesn't support image input" in accumulated:
                                yield "⚠️ The selected model does not support image input. Switch to a vision-capable model (qwen2.5vl:7b) for image analysis, or remove the image and try again."
                                return
                            yield token
        except Exception as e:
            yield f"{ERROR_PREFIX}Could not reach the local model: {e}"
