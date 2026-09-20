"""A search step asks for the web, not the Spine.

Seen 20 September 2026 on a live question about the current Blender
release: DuckDuckGo answered, a result page was read, and the model said
"the web returned nothing usable". The six sources it was handed were
mostly the manual's own paragraphs — `KnowledgeRuntime.search` fans out to
the web *and* memory and cuts the union to six on a cross-provider
confidence, a blend deciding membership. Recall is its own step with its own
citations; the web step must not re-run it with worse numbers.
"""

from __future__ import annotations

import json

from runtimes.models.models_service import ModelsService


class _Runtime:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def search(self, query, max_results=6, **kwargs):
        self.calls.append({"query": query, "max_results": max_results, **kwargs})

        class _Response:
            results: list = []
            providers_consulted = ["duckduckgo"]
            provider_status = {"duckduckgo": "ok"}
            latency_ms = 1.0

        return _Response()


def test_search_knowledge_leaves_memory_out():
    runtime = _Runtime()
    service = ModelsService.__new__(ModelsService)
    service._knowledge_runtime = runtime
    out = list(service.search_knowledge("current Blender release"))
    assert runtime.calls == [{"query": "current Blender release", "max_results": 6, "include_memory": False}]
    assert json.loads(out[0])["providers_consulted"] == ["duckduckgo"]
