"""The HTTP knowledge endpoint answers from the runtime the app actually built.

**Two instances, different capabilities, and which one answered depended on how
you arrived.** `bootstrapper._init_knowledge_runtime` builds a `KnowledgeRuntime`
with the internet runtime, the memory runtime and twelve providers, and
registers it for the capability router — so chat searched the web correctly.
`knowledge_service` held a second one, constructed as `KnowledgeRuntime()` with
no arguments: no internet runtime, no memory runtime, no providers. `POST
/knowledge/search` read that one and therefore returned zero results for every
query ever asked, and the provider-health block in `main.py` reported on an
object with nothing to report.

Nothing failed. The endpoint returned `200` with an empty list, which is
indistinguishable from "the web had nothing" — the same confusion
`search_context.reached_the_web` exists to resolve one layer up.

These assert the wiring rather than the search: a test that needed the network
to prove the endpoint is connected would be untestable offline and would pass
for the wrong reason when it did run.
"""

from __future__ import annotations

import pytest

from knowledge import knowledge_service
from knowledge.runtime import KnowledgeRuntime


@pytest.fixture(autouse=True)
def _restore_runtime():
    """Leave the module as it was found.

    The wired runtime is process-global, so a test that sets it and does not
    put it back changes what every later test in the process sees — and the
    change would be *toward* a runtime that can reach the network.
    """
    original = knowledge_service._runtime
    yield
    knowledge_service.set_runtime(original)


class TestTheFacadeCanBeWired:
    def test_it_falls_back_when_nothing_has_booted(self):
        knowledge_service.set_runtime(None)
        assert knowledge_service.get_runtime() is knowledge_service._fallback_runtime

    def test_a_wired_runtime_wins(self):
        wired = KnowledgeRuntime(internet_runtime=object(), memory_runtime=object())
        knowledge_service.set_runtime(wired)
        assert knowledge_service.get_runtime() is wired

    def test_search_reads_the_wired_runtime_not_the_global(self):
        """The defect precisely: `search_knowledge` used the module global."""

        class _Recording:
            def __init__(self):
                self.queries: list[str] = []

            def search(self, query, max_results=6, **kwargs):
                self.queries.append(query)
                from knowledge.protocol import ProviderStatus, SearchResponse

                return SearchResponse(
                    query=query,
                    results=[],
                    providers_consulted=["recording"],
                    provider_status={"recording": "ok"},
                    status=ProviderStatus.HEALTHY,
                )

        recording = _Recording()
        knowledge_service.set_runtime(recording)
        knowledge_service.search_knowledge("anything")
        assert recording.queries == ["anything"], (
            "the endpoint must reach the wired runtime, not the empty fallback"
        )


class TestTheFallbackIsGenuinelyEmpty:
    """Why this mattered: the fallback cannot answer anything."""

    def test_the_fallback_has_no_internet_runtime(self):
        assert knowledge_service._fallback_runtime._internet_runtime is None

    def test_the_fallback_has_no_providers(self):
        assert knowledge_service._fallback_runtime._providers == []


class TestTheBootstrapperHandsItOver:
    def test_init_knowledge_runtime_sets_the_facade(self):
        """Asserted against the source rather than by booting.

        A full bootstrap opens the Spine, discovers models and may reach the
        network; this needs to know one call is present and stays present.
        `CLAUDE.md`'s reachability lesson is exactly this — the component was
        complete and nothing called it — so the call site is what is pinned.
        """
        import inspect

        from core import bootstrapper

        source = inspect.getsource(
            bootstrapper.KernelBootstrapper._init_knowledge_runtime
        )
        assert "set_runtime(runtime)" in source, (
            "the bootstrapper must hand its wired runtime to knowledge_service, "
            "or POST /knowledge/search silently answers from an empty one"
        )
