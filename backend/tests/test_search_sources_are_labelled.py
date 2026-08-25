"""A source says where it came from, and a memory id is never called a URL.

`knowledge.search` fans out across providers and returns web results and Spine
records in **one list**. Every result carries `provider` and `type`.
`format_search_results` read only `title`, `url`, `snippet` and `published` —
dropping the one field that distinguishes them — and printed the lot under a
header saying `=== INTERNET SEARCH RESULTS ===`, followed by the instruction
*"If the sources conflict with your training data, ALWAYS trust the live
sources."*

Measured against a live question about the day's news, five of six "internet
search results" were the user's own Spine records: a stored conversation turn,
a spreadsheet dump, and three near-duplicates of the same old prompt. The one
genuine web result ranked last of the six.

The fixtures below are those payload shapes, taken from that run.

Three things it broke, and the order is the severity:

* **Rule 2.** A `memory:` id was printed on a line reading `URL:`. Cite that
  and the user is shown a web address that does not exist and cannot be
  checked — a false claim of provenance, which is worse than none.
* **Rule 7d.** A stored conversation turn was presented as a research source,
  alongside three copies of itself. That is the duplicate-citation failure 7d
  was written from, reaching the model rather than the screen.
* **The instruction was wrong for most of the block.** Telling a model to
  prefer the user's own remembered remark over its knowledge of the world is
  not what "trust the live sources" was for.

This is the same defect shape as the seam that made the search fix necessary:
the distinguishing information was present one layer up and thrown away at the
boundary.
"""

from __future__ import annotations

from core.query_classifier import SEARCH_MARKER, needs_search
from core.search_context import Origin, format_search_results, origin_of, search_prompt

QUERY = "What are the top technology news headlines today?"

#: A real DuckDuckGo result from the run.
WEB = {
    "title": "Today Headlines-16 AUGUST 2026 - YouTube",
    "url": "https://www.youtube.com/watch?v=9WtmNXcA0U0",
    "snippet": "For the latest Tamil News Today, stay connected with NEWS TAMIL.",
    "provider": "duckduckgo",
    "type": "web",
    "metadata": {"source": "ddg_html"},
}

#: A stored conversation turn — the user's own past message, retrieved as a
#: source. This is the one that matters most.
CONVERSATION = {
    "title": "This is a recent event dont you have websearch on",
    "url": "memory:fd591a18-0b13-4df5-96e2-872120cab66e",
    "snippet": "This is a recent event dont you have websearch on",
    "provider": "memory",
    "type": "memory",
    "metadata": {"memory_type": "conversation", "match_reason": "vector"},
}

#: A fact drawn from something the user actually gave Zaram.
RECORD = {
    "title": "Northwind Studios pay on 30-day terms",
    "url": "memory:6c96bd30-5569-466e-9867-fa74073b40b0",
    "snippet": "Northwind Studios pay on 30-day terms. Day rate 85,000 naira.",
    "provider": "memory",
    "type": "semantic",
    "metadata": {"memory_type": "semantic"},
}


def _block(*results):
    return format_search_results(QUERY, {"results": list(results)})


class TestOriginIsReadFromThePayload:
    def test_a_duckduckgo_result_is_web(self):
        assert origin_of(WEB) is Origin.WEB

    def test_a_stored_conversation_turn_is_a_conversation(self):
        assert origin_of(CONVERSATION) is Origin.CONVERSATION

    def test_a_saved_fact_is_a_record(self):
        assert origin_of(RECORD) is Origin.RECORD

    def test_an_http_url_is_web_even_without_a_type(self):
        assert origin_of({"url": "https://example.com/a"}) is Origin.WEB

    def test_an_unrecognised_source_is_not_called_web(self):
        # The direction of this default is the point. Calling a web page a
        # local record understates a source; calling a local record a web page
        # is a false claim of provenance.
        assert origin_of({"title": "who knows"}) is not Origin.WEB


class TestAMemoryIsNeverPresentedAsAWebPage:
    def test_a_memory_reference_is_not_printed_as_a_url(self):
        block = _block(CONVERSATION)
        assert "URL: memory:" not in block
        assert "Reference: memory:fd591a18-0b13-4df5-96e2-872120cab66e" in block

    def test_a_real_url_is_still_printed_as_a_url(self):
        assert "URL: https://www.youtube.com/watch?v=9WtmNXcA0U0" in _block(WEB)

    def test_each_source_carries_its_origin(self):
        block = _block(WEB, CONVERSATION, RECORD)
        assert f"Source 1 — {Origin.WEB.value}:" in block
        assert f"Source 2 — {Origin.CONVERSATION.value}:" in block
        assert f"Source 3 — {Origin.RECORD.value}:" in block

    def test_a_mixed_block_says_how_much_of_it_is_not_the_web(self):
        block = _block(WEB, CONVERSATION, RECORD)
        assert "2 of these 3 sources came from this user's own stored material" in block

    def test_an_all_web_block_says_nothing_extra(self):
        assert "own stored material" not in _block(WEB)


class TestTheInstructionsMatchWhatIsInTheBlock:
    def test_the_blanket_trust_instruction_is_gone(self):
        # It said "ALWAYS trust the live sources" over the user's own notes.
        for block in (_block(WEB), _block(CONVERSATION), _block(WEB, CONVERSATION)):
            assert "ALWAYS trust the live sources" not in block

    def test_web_recency_is_claimed_only_where_there_is_a_web_source(self):
        assert "trust the web source" in _block(WEB)
        assert "trust the web source" not in _block(CONVERSATION, RECORD)

    def test_the_cutoff_instructions_appear_only_with_a_web_source(self):
        # "Do NOT say you don't have real-time access" over a block of stored
        # records tells the model to imply currency it does not have.
        assert "real-time access" in _block(WEB)
        assert "real-time access" not in _block(CONVERSATION, RECORD)

    def test_local_material_is_scoped_to_what_it_can_answer(self):
        block = _block(RECORD)
        assert "authoritative about the user" in block
        assert "not current news" in block

    def test_a_block_with_no_web_source_says_the_web_gave_nothing(self):
        block = _block(CONVERSATION, RECORD)
        assert "The web returned nothing usable here" in block

    def test_that_notice_is_absent_when_the_web_did_return_something(self):
        assert "returned nothing usable" not in _block(WEB, CONVERSATION)


class TestTheContractTheRestOfTheSystemRelieson:
    """Things that must not move, because other modules key off them."""

    def test_the_sentinel_is_unchanged(self):
        # `needs_search` suppresses a second search when it sees this, and
        # `planner` splits the user's question out on it. Rewording the marker
        # to be more honest would have broken both — which is why the honesty
        # was added beside it instead.
        block = _block(WEB, CONVERSATION)
        assert block.startswith(SEARCH_MARKER)
        assert needs_search(block) is False

    def test_the_question_is_still_last(self):
        # A model reads the last instruction most reliably.
        assert _block(WEB, CONVERSATION).rstrip().endswith(QUERY)

    def test_no_results_still_degrades_to_the_bare_question(self):
        assert search_prompt(QUERY, '{"results": []}') == QUERY

    def test_unparseable_output_still_degrades_to_the_bare_question(self):
        assert search_prompt(QUERY, "[FALLBACK] knowledge.search failed") == QUERY
