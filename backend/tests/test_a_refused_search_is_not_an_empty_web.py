""""No results" and "never asked" are different sentences.

**Measured on this machine, 30 August 2026.** Web search was turned on from the
offer in the conversation, `duckduckgo.com` had no egress rule, default-deny
refused the request, and the reply carried:

    Web search ran but returned no results, so this answer comes only from
    what the model already knows.

Every clause of that was false except the last. The web returned nothing
because it was never asked, and the sentence describes a problem the user does
not have — so there is nothing they can do about the one they do.

`result_count` cannot tell the two apart: a refusal and an empty web both
arrive as an empty list. `reached_the_web` asks the other question — did
anything leave this machine — off the `provider_status` the knowledge runtime
already fills in per connector.

**Three states, and the third is why this is not a boolean.** An unreadable
payload returns `None` and the engine says nothing at all, because "Zaram could
not reach the web" is a claim, and a claim built on a payload we could not
parse is a guess wearing a disclosure's clothes.
"""

from __future__ import annotations

import json

import pytest

from core.search_context import reached_the_web, result_count


def _payload(status: dict | None, results: list | None = None) -> str:
    body: dict = {"results": results if results is not None else [], "total_results": 0}
    if status is not None:
        body["provider_status"] = status
    return json.dumps(body)


class TestWhetherAnythingLeftTheMachine:
    def test_a_web_connector_that_answered_counts_as_reached(self):
        assert reached_the_web(_payload({"duckduckgo": "ok"})) is True

    def test_a_web_connector_that_errored_did_not_reach_it(self):
        """What a refusal looks like: the runtime catches it and records error."""
        assert reached_the_web(_payload({"internet": "error"})) is False

    def test_local_connectors_alone_are_not_the_web(self):
        """Memory and the graph answer from disk. They are not a search."""
        assert reached_the_web(_payload({"memory": "ok", "graph": "ok"})) is False

    def test_a_new_web_connector_counts_without_being_listed(self):
        """The local set is the closed one, deliberately.

        A connector nobody added to a list is treated as web, so forgetting
        produces "we reached the web" about something local — cautious in the
        direction that matters, since the other error is telling a user their
        question stayed on the machine when it did not.
        """
        assert reached_the_web(_payload({"some_new_engine": "ok"})) is True

    def test_an_unreadable_payload_says_nothing(self):
        assert reached_the_web("not json at all") is None
        assert reached_the_web(_payload(None)) is None
        assert reached_the_web(json.dumps({"provider_status": "not a dict"})) is None


class TestTheTwoQuestionsStayApart:
    def test_zero_results_does_not_imply_the_web_was_asked(self):
        """The defect, stated as the property that was missing.

        Both numbers come off the same payload and they answer different
        questions — which is this repository's most expensive recurring
        mistake, in its smallest form.
        """
        refused = _payload({"internet": "error"})

        assert result_count(refused) == 0
        assert reached_the_web(refused) is False

    def test_an_empty_web_is_still_an_empty_web(self):
        empty = _payload({"duckduckgo": "ok"})

        assert result_count(empty) == 0
        assert reached_the_web(empty) is True

    def test_results_and_reach_are_read_independently(self):
        """A search can reach the web and return something; nothing here
        couples the two, and coupling them is how the defect returns."""
        found = _payload({"duckduckgo": "ok"}, results=[{"title": "a page"}])

        assert result_count(found) == 1
        assert reached_the_web(found) is True
