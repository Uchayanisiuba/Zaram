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

    #: Used when the caller passes ``model=None``. ``None`` is the only honest
    #: value.
    #:
    #: This was ``"gemma3:latest"``, and nothing sets it from outside — unlike
    #: `OllamaEngine.default_model`, which `ModelsRuntime.initialize` assigns
    #: from the provider layer's vetted pick. So it was a hardcoded model name
    #: on a live path, which is the failure `_resolve_model` and
    #: `user_settings` were both written to end, surviving in the one adapter
    #: nobody was looking at. It stopped being theoretical when gemma3 was
    #: uninstalled: every call reaching this line would have asked Ollama for a
    #: model that is not there.
    #:
    #: Naming a different model would repeat the mistake with a fresher name.
    default_model: str | None = None

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def stream_response(self, prompt: str, system_prompt: str = "", model: str | None = None) -> Iterator[str]:
        chosen = model or self.default_model
        if not chosen:
            # Saying so beats guessing. A guessed name produces a 404 from
            # Ollama that reads as "the local model is unreachable", sending
            # whoever debugs it to look at the server rather than at the
            # caller that passed nothing.
            yield (
                f"{ERROR_PREFIX}No model was selected for this request. "
                "Choose one in Settings."
            )
            return
        try:
            payload = {
                "model": chosen,
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
                                # Names no model deliberately. This read
                                # "(qwen2.5vl:7b)", which was uninstalled on
                                # 19 August 2026 — so the advice pointed at a
                                # model the user did not have, which is worse
                                # than advice that names none. What is
                                # vision-capable here is a question the
                                # provider layer can answer and this adapter
                                # cannot.
                                yield "⚠️ The selected model does not support image input. Switch to a vision-capable model for image analysis, or remove the image and try again."
                                return
                            yield token
        except Exception as e:
            yield f"{ERROR_PREFIX}Could not reach the local model: {e}"
