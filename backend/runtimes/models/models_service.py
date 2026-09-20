# backend/runtimes/models/models_service.py
from typing import Iterator
import json
from .engines.base_engine import LLMEngine, accepts_tools


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
        tools: list[dict] | None = None,
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
        # Passed only when there are some, for the reason the dispatcher
        # gives about images: a dozen doubles implement this signature.
        if tools and accepts_tools(self.engine.stream_response):
            yield from self.engine.stream_response(
                full_prompt, system_prompt, model, images, tools=tools
            )
        else:
            yield from self.engine.stream_response(full_prompt, system_prompt, model, images)

    def search_knowledge(self, query: str, persona: str = "zaram_prime") -> Iterator[str]:
        """The web, for a search step.

        **`include_memory=False`, and it was the default `True` until 20
        September 2026.** The knowledge runtime fans out to the web *and*
        the Spine and cuts the union to six on a cross-provider confidence —
        a blend deciding membership, which `CLAUDE.md` records as this
        codebase's most expensive recurring bug. Seen live: a question about
        the current Blender release got DuckDuckGo answering and a result
        page read, and the model still said "the web returned nothing
        usable", because the six it was handed were mostly the manual's own
        paragraphs at a cosine of 0.4. Recall is its own step, run before
        this one, with its own citations; a search step asks for the web.
        """
        if self._knowledge_runtime:
            response = self._knowledge_runtime.search(query, max_results=6, include_memory=False)
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
