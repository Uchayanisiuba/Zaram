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
