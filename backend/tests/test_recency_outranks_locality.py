"""A question about last week searches, whatever model is answering.

**The report.** Asked what was happening lately in AI with a cloud model
selected, Zaram answered from that model's training cutoff — no search step, no
sources, and nothing on screen saying nothing had been looked up. It read as
though Zaram had "switched to a cloud model to answer it".

**What was actually happening.** `search_applies_to` was a blanket switch:
search on local, skip on cloud. Nothing routes *to* cloud because a question
needs current facts — model selection happens first and search follows from it
— so the cloud model was the user's own choice. The defect was that choosing it
silently removed the search step.

The reasoning behind the switch was that a frontier model carries a bigger
store of facts, so a live result changes its answer less often. True for
general knowledge; **false for anything after a training cutoff**, which every
model has. Size does not help with what happened last week.

So recency now overrides the economy, and the economy survives for the case it
was actually reasoning about.
"""

from __future__ import annotations

import pytest

from core.planner import is_time_sensitive, search_applies_to


#: Answerable only by looking. Phrasings taken from what a person types,
#: including the vague ones — "a few months ago" is how the maintainer asked.
TIME_SENSITIVE = [
    "what is the latest happening in AI",
    "what happened in South Africa a few months ago",
    "what is in the news today",
    "who is the current president",
    "what did OpenAI announce recently",
    "what happened last week in Lagos",
    "breaking news on the election",
    "what has been released in the past few weeks",
]

#: Answerable from weights. A large model plausibly does better on these than a
#: live search would, which is the whole point of the economy.
TIMELESS = [
    "explain recursion to me",
    "what is the capital of Portugal",
    "write me a function that reverses a list",
    "what makes a good invoice",
]


@pytest.fixture(autouse=True)
def _scope_is_not_always(monkeypatch):
    """`SearchScope.ALWAYS` short-circuits everything and would make these
    tests pass without the override existing. Pinned to the default so what is
    measured is the recency rule itself."""
    from core import user_settings

    class _Scoped:
        search_scope = user_settings.SearchScope.LOCAL_ONLY

    monkeypatch.setattr(user_settings, "get_user_settings", lambda: _Scoped())


@pytest.mark.parametrize("prompt", TIME_SENSITIVE)
def test_a_cloud_model_still_searches_for_recent_things(prompt):
    """The regression, stated directly."""
    assert search_applies_to("cloud", prompt) is True, (
        f"{prompt!r} would be answered from a training cutoff with no search"
    )


@pytest.mark.parametrize("prompt", TIME_SENSITIVE)
def test_a_local_model_searches_too(prompt):
    assert search_applies_to("local", prompt) is True


@pytest.mark.parametrize("prompt", TIMELESS)
def test_the_economy_survives_for_timeless_questions(prompt):
    """The half that stops this becoming "always search".

    Searching for everything would pass every assertion above while making the
    product slower and sending questions off the machine that had no need to
    leave. On cloud, a question the model answers well from its weights still
    skips the lookup.
    """
    assert search_applies_to("cloud", prompt) is False


@pytest.mark.parametrize("prompt", TIMELESS)
def test_a_local_model_keeps_its_broader_licence(prompt):
    """Unchanged: local searches unless the scope forbids it, because a 12B
    benefits from a live result far more often."""
    assert search_applies_to("local", prompt) is True


class TestTheRecencyTestItself:
    @pytest.mark.parametrize("prompt", TIME_SENSITIVE)
    def test_it_recognises_recency(self, prompt):
        assert is_time_sensitive(prompt) is True

    @pytest.mark.parametrize("prompt", TIMELESS)
    def test_it_does_not_fire_on_timeless_questions(self, prompt):
        assert is_time_sensitive(prompt) is False

    def test_it_is_narrower_than_needs_search(self):
        """The two ask different questions and must not be merged.

        `needs_search` matches "who is" and topic words like "election" —
        plenty of which a large model answers fine from its weights. This asks
        only whether *any* model could know, which is what earns an override.
        """
        from core.query_classifier import needs_search

        prompt = "who is the founder of Microsoft"
        assert needs_search(prompt) is True
        assert is_time_sensitive(prompt) is False
