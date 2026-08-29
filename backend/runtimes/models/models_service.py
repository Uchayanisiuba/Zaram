# backend/runtimes/models/models_service.py
from typing import Iterator
import json
from .engines.base_engine import LLMEngine


class ModelsService:
    def __init__(self, engine: LLMEngine, knowledge_runtime=None):
        self.engine = engine
        self._knowledge_runtime = knowledge_runtime

    def generate_response(
        self,
        user_text: str,
        system_prompt: str = "",
        model: str | None = None,
        images: list[str] | None = None,
    ) -> Iterator[str]:
        """Orchestrates the prompt generation.

        ``model`` selects which model answers. It used to be absent here, so the
        engine always fell back to its own default and the caller's choice was
        silently discarded — a request naming a model that does not exist got a
        normal answer from a different one. ``None`` still means "engine
        default", which is now the provider layer's vetted selection.
        """
        full_prompt = f"{user_text}"
        # The engine yields plain text tokens (`LLMEngine`), errors included as
        # a chunk prefixed with ERROR_PREFIX. This used to parse SSE frames the
        # engine had just built, so both sides had to agree on a wire format
        # that never went over a wire.
        yield from self.engine.stream_response(full_prompt, system_prompt, model, images)

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
