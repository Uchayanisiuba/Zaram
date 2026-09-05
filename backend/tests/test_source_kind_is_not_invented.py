"""A citation's `kind` reports where the result came from, not where it was found.

`kind` is the field the whole citation UI colours by, and it answers exactly
one question: **did this cost the user any privacy?** `chatClient.ts` says so in
as many words — "Never infer a kind here — the backend sends it, and inventing
one client-side would be the fabrication rule in a different file." That places
the obligation squarely on this side of the wire, and this file is the check.

The defect these were written from
----------------------------------
`_search_provenance_events` hardcoded ``kind="web"`` for every result of a
`knowledge.search` step. That looked correct for as long as the step could only
return web results — but a knowledge search returns the *merged* list, memory
included, and the moment the internet runtime was actually wired up, facts
recalled from the user's own Spine began arriving in the interface as web
citations with `memory:` URIs and an egress-coloured chip.

Nothing failed. The engine's own tests asserted that search results are
disclosed, which they still were, and no test asserted what they were disclosed
*as*.
"""

from __future__ import annotations

import pytest

from core.execution_engine import ExecutionEngine


@pytest.fixture
def engine():
    """A bare engine. `_source_kind` is a pure function of its argument."""
    return ExecutionEngine.__new__(ExecutionEngine)


class TestLocalResultsAreNotWeb:
    def test_a_memory_uri_is_a_memory(self, engine):
        assert engine._source_kind({"url": "memory:1a2b-3c4d", "provider": "memory"}) == "memory"

    def test_a_memory_uri_wins_over_a_misleading_provider(self, engine):
        # The URI scheme is structural; a provider name is a string somebody
        # typed. When they disagree, believe the one that cannot be a typo.
        assert engine._source_kind({"url": "memory:1a2b", "provider": "duckduckgo"}) == "memory"

    def test_a_declared_memory_type_is_enough_on_its_own(self, engine):
        assert engine._source_kind({"url": "", "type": "memory"}) == "memory"

    @pytest.mark.parametrize("provider", ["memory", "vector", "graph"])
    def test_local_retrieval_providers_are_memory(self, engine, provider):
        assert engine._source_kind({"provider": provider}) == "memory"

    @pytest.mark.parametrize("provider", ["project", "markdown", "pdf"])
    def test_local_document_providers_are_documents(self, engine, provider):
        assert engine._source_kind({"provider": provider}) == "document"


class TestUnknownIsTreatedAsHavingLeft:
    """The two errors are not symmetric, so the default is not neutral.

    Calling a memory a web source over-warns about privacy the user did not
    spend. Calling a web source a memory tells them nothing left when something
    did. Only positive evidence of being local may downgrade a result.
    """

    @pytest.mark.parametrize(
        "source",
        [
            {},
            {"provider": "some-new-search-engine"},
            {"url": "https://example.com/a", "provider": "duckduckgo"},
            {"url": "https://example.com/a", "type": "web"},
            {"provider": None, "url": None, "type": None},
        ],
    )
    def test_anything_unrecognised_is_web(self, engine, source):
        assert engine._source_kind(source) == "web"

    def test_a_real_url_is_never_downgraded_by_an_unknown_type(self, engine):
        assert engine._source_kind({"url": "https://news.example/x", "type": "wat"}) == "web"


class TestTheEventCarriesIt:
    def test_a_merged_result_list_is_labelled_per_result(self, engine):
        """The actual shape of the bug: one list, two kinds.

        A knowledge search returns memory and web results together. Labelling
        the list rather than each result is what produced web-coloured chips
        over the user's own facts.
        """
        events = engine._search_provenance_events(
            [
                {"url": "https://news.example/story", "title": "A story", "provider": "duckduckgo"},
                {"url": "memory:9f8e", "title": "Their day rate is £450", "provider": "memory"},
            ]
        )

        kinds = [event.data["kind"] for event in events]
        assert kinds == ["web", "memory"]

    def test_origin_agrees_with_kind(self, engine):
        """`origin` is rule 7b's field and must not contradict `kind`.

        They answer different questions — where it came from, and whether it
        left — but a result cannot be `origin: web` and `kind: memory`, and a
        disagreement here would show up as a citation the user cannot square
        with the egress log.
        """
        events = engine._search_provenance_events([{"url": "memory:9f8e", "provider": "memory"}])
        assert events[0].data["origin"] == events[0].data["kind"] == "memory"
