"""Working state stays out of the Spine — rule 7d, asserted.

**Where these strings come from.** Not imagination: they were read out of the
maintainer's own `GET /memory` on 16 August. The Spine held

    "Say the single word: hello"
    "Say the single word: ping"
    "Reply with exactly the word: alive"
    "WHars your name"
    "In three or four full sentences, explain what makes a good invoice."

sitting beside genuine facts like "My day rate for Harbour Lane is 425,000
naira." None of the five is a question, which is why they survived: the door
check was a **blocklist** — store unless it looks like a question, an
instruction opener or a greeting — and a blocklist fails open. Anything phrased
unusually was kept for ever.

Rule 7d says conversation is ephemeral and entering the Spine is a decision the
system makes. The cost of getting it wrong is the one the rule predicts and the
one the maintainer reported: stored prompts come back as recall and as
citations, so Zaram appears to raise questions the user asked days ago.

The check now requires **positive evidence that a message asserts something**,
which fails closed. The two lists below are the whole contract: what must never
be stored, and what must never be lost. A change that trades one for the other
fails here rather than in somebody's Spine.
"""

from __future__ import annotations

import pytest

from core.execution_engine import ExecutionEngine


@pytest.fixture(scope="module")
def carries():
    """The predicate, without building an engine.

    `_carries_new_information` touches only class constants, and constructing a
    real `ExecutionEngine` would drag in a registry, an event bus and a memory
    runtime to test a string function.
    """

    class _Probe(ExecutionEngine):
        def __init__(self):  # noqa: D107 - deliberately does nothing
            pass

    return _Probe()._carries_new_information


@pytest.fixture(scope="module")
def fact_from():
    """The extractor, built the same way and for the same reason."""

    class _Probe(ExecutionEngine):
        def __init__(self):  # noqa: D107 - deliberately does nothing
            pass

    return _Probe()._fact_from


#: Read out of the real Spine, plus the two question forms that started it.
TRAFFIC = [
    "Say the single word: hello",
    "Say the single word: ping",
    "Reply with exactly the word: alive",
    "WHars your name",
    "In three or four full sentences, explain what makes a good invoice.",
    "Its not can uyou do some research based on real time information and a",
    "who won the osun state election",
    "what happened in south africa a few months ago",
    "can you summarise that for me",
    "make me an invoice for Harbour Lane",
    "thanks",
]

#: The other half. A check that stores nothing passes the list above perfectly.
FACTS = [
    "My day rate for Harbour Lane is 425,000 naira.",
    "My day rate for Ashgrove Films is 750,000 naira.",
    "Remember: the Northwind contract renews in March.",
    "The deadline is Friday.",
    "Harbour Lane pays late.",
    "I charge 500 per day for rush work.",
    "Our payment terms are 30 days.",
    "The retainer is 200,000 a month.",
]


@pytest.mark.parametrize("prompt", TRAFFIC)
def test_traffic_never_enters_the_spine(carries, prompt):
    assert carries(prompt) is False, (
        f"{prompt!r} would be stored as a durable fact and cited back later"
    )


@pytest.mark.parametrize("prompt", FACTS)
def test_a_stated_fact_is_kept(carries, prompt):
    """The half that stops the fix becoming "store nothing".

    Without this, rejecting everything would pass every assertion above while
    quietly removing the product's reason to exist.
    """
    assert carries(prompt) is True, f"{prompt!r} is a fact and was dropped"


def test_an_explicit_remember_always_wins(carries):
    """The user overriding the heuristic outranks it, in the one direction
    that is safe: they asked for it deliberately."""
    assert carries("Remember: Ashgrove always pays on the 30th.") is True


def test_the_asymmetry_is_deliberate(carries):
    """A miss and a false positive do not cost the same.

    A missed fact costs the user saying it again. A stored instruction is a
    permanent record that only a human deleting it by hand removes — and until
    they do, it is recalled and cited. So a phrasing this cannot read is
    dropped rather than kept, and that choice is written down as a test so it
    is not quietly reversed by someone improving recall.
    """
    ambiguous = "the thing we discussed on Tuesday"
    assert carries(ambiguous) is False


class TestWhatIsStoredIsTheFactAndNotTheMessage:
    """Getting in the door is one decision; what gets written is another.

    The door check above decides whether a message contains a fact. It says
    nothing about *which part* of it is one — and until 3 September 2026
    `_remember` stored the whole message, so a real fact arrived in the Spine
    wrapped in a greeting and a request:

        "Hey, quick one — my day rate is 450 now. Can you redo the invoice?"

    All of that was recalled and cited later, which is the same visible failure
    rule 7d names, one size smaller: Zaram quoting the user's own asides back
    at them as though they were sources.

    The extractor uses `_ASSERTION_RE` — the *same* evidence the door used,
    applied per sentence. A second matcher tuned separately would eventually
    disagree with the first, and a message could be admitted by one and emptied
    by the other.
    """

    def test_the_request_after_a_fact_is_left_out(self, fact_from):
        """The half that was doing the damage: the ask.

        **A sentence is the unit, and the limit that comes with that is stated
        rather than papered over.** "Hey, quick one" shares its sentence with
        the fact — an em-dash is not a sentence boundary — so it rides along.
        Splitting on dashes as well would trim it, and would also cut
        `Ashgrove — 30th, every month` in half, which is a whole fact and is
        asserted below. A greeting stored beside a rate is untidy; a fact
        stored in two pieces is wrong.
        """
        got = fact_from(
            "Hey, quick one — my day rate is 450 now. Can you redo the invoice?"
        )
        assert got == "Hey, quick one — my day rate is 450 now."
        assert "redo the invoice" not in got

    def test_an_explicit_opener_is_not_stored_as_part_of_the_fact(self, fact_from):
        """"Remember:" is an instruction to Zaram, not something about the work."""
        assert fact_from("Remember: the Northwind contract renews in March.") == (
            "the Northwind contract renews in March."
        )
        assert fact_from("Don't forget the deadline is Friday.") == (
            "the deadline is Friday."
        )

    def test_a_message_that_is_only_a_fact_is_unchanged(self, fact_from):
        for prompt in FACTS:
            if prompt.lower().startswith("remember"):
                continue  # covered above; the opener is deliberately removed
            assert fact_from(prompt) == prompt

    def test_a_second_line_that_asks_for_something_is_dropped(self, fact_from):
        got = fact_from("The deadline is Friday.\nCan you draft the email?")
        assert got == "The deadline is Friday."

    def test_two_facts_in_one_message_both_survive(self, fact_from):
        got = fact_from(
            "My day rate is 450. Harbour Lane pays late. Anyway, thanks for the help."
        )
        assert got == "My day rate is 450. Harbour Lane pays late."

    def test_it_never_returns_nothing(self, fact_from):
        """The failure that would be silent, so it is the one pinned hardest.

        Returning empty for a message the door check already admitted is a
        deletion nobody asked for and nobody sees. Keeping too much is the
        failure this method reduces, and the user can see and correct that one.
        """
        awkward = "Ashgrove — 30th, every month, without fail"
        assert fact_from(awkward) == awkward
        assert fact_from("Remember") == "Remember"
        assert fact_from("   ") == ""
