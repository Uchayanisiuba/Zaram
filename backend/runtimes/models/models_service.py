# backend/runtimes/models/models_service.py
from typing import Iterator
import json
from .engines.base_engine import LLMEngine


class ModelsService:
    def __init__(self, engine: LLMEngine, knowledge_runtime=None):
        self.engine = engine
        self._knowledge_runtime = knowledge_runtime

    def generate_response(
        self, user_text: str, system_prompt: str = "", model: str | None = None
    ) -> Iterator[str]:
        """Orchestrates the prompt generation.

        ``model`` selects which model answers. It used to be absent here, so the
        engine always fell back to its own default and the caller's choice was
        silently discarded — a request naming a model that does not exist got a
        normal answer from a different one. ``None`` still means "engine
        default", which is now the provider layer's vetted selection.
        """
        full_prompt = f"{user_text}"
        for chunk in self.engine.stream_response(full_prompt, system_prompt, model):
            parsed = self._parse_sse(chunk)
            if parsed and parsed.get("type") == "token":
                yield parsed.get("content", "")
            elif parsed and parsed.get("type") == "error":
                yield f"[ERROR] {parsed.get('content', '')}"
        return

    def _parse_sse(self, chunk: str) -> dict | None:
        import json
        trimmed = chunk.strip()
        if not trimmed.startswith("data:"):
            return None
        payload = trimmed[5:].strip()
        if payload == "[DONE]":
            return {"type": "done"}
        try:
            return json.loads(payload)
        except Exception:
            return None

    def search_knowledge(self, query: str, persona: str = "zaram_prime") -> Iterator[str]:
        """Search knowledge across all providers."""
        if self._knowledge_runtime:
            response = self._knowledge_runtime.search(query, max_results=6)
            results = [r.to_dict() for r in response.results]
            print(f"[ModelsService] Knowledge search for '{query[:50]}...' returned {len(results)} results from providers: {response.providers_consulted}")
            yield json.dumps({
                "results": results,
                "total_results": len(results),
                "providers_consulted": response.providers_consulted,
                "provider_status": response.provider_status,
                "latency_ms": response.latency_ms,
            })
        else:
            from knowledge.knowledge_service import search_knowledge
            result = search_knowledge(query, persona)
            user_results = result.get('results') or []
            yield json.dumps({
                "results": user_results,
                "total_results": result.get('total_results', len(user_results)),
            })

    def analyze_image(self, prompt: str, image_base64: str, system_prompt: str = "") -> Iterator[str]:
        """Vision analysis using multimodal model."""
        full_prompt = f"{prompt}"
        for chunk in self.engine.stream_vision_response(full_prompt, images=[image_base64], system_prompt=system_prompt):
            parsed = self._parse_sse(chunk)
            if parsed and parsed.get("type") == "token":
                yield parsed.get("content", "")
            elif parsed and parsed.get("type") == "error":
                yield f"[ERROR] {parsed.get('content', '')}"
        return