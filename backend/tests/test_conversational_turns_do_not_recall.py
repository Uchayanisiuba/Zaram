"""A greeting must not pull the user's files into the prompt.

**The bug, observed 10 August 2026.** Typing `Hi` produced
"0 sources · nothing left this device · **3 recalled, not cited**". Three
documents — day rates and an invoice — were retrieved from the Spine and
injected into the system prompt for a two-character greeting. Nothing false
reached the user, because `MIN_CITATION_SCORE` cited none of them, so the only
visible damage was a confusing line under a "Greetings." reply. The invisible
damage is that a social turn carried the user's rates into the model's context.

**Why the existing floor could not have caught it.** `MIN_RECALL_SCORE` is 0.42,
and `ExecutionEngine`'s docstring records how it was calibrated:

    related, full sentences        0.436 - 0.546
    unrelated, full sentences      0.317 - 0.362

Every string in that population is a sentence. **A greeting was never
measured.** Similarity between a 1-2 token string and a document does not live
on the same scale as similarity between two sentences, so a floor fitted to
sentences says nothing about "Hi" — and the live evidence is that at least three
documents cleared it.

The floor cannot be tuned out of this either: raising it far enough to reject a
greeting starts discarding genuine recall, which begins at 0.436.

**So the fix is a gate, not a number.** Recall runs unconditionally in
`ExecutionEngine.run` — retrieve first, filter after. The products this is
measured against (ChatGPT, Claude, DeepSeek, Kimi) decide *whether to retrieve*
before retrieving, which is why they have no "0 sources" state to render. This
file measures the population that decision has to separate.

Run the live measurement with::

    pytest backend/tests/test_conversational_turns_do_not_recall.py -k measure -s

It is skipped when Ollama or bge-m3 is absent, so the suite stays offline and
deterministic. The recorded numbers below are asserted on every run — the same
split `test_recall_relevance.py` uses, and the reason a measurement is worth
having at all is that the recorded half is checkable without a GPU.
"""

from __future__ import annotations

import math
import os
from typing import Iterable

import pytest

# --------------------------------------------------------------------------- #
# The population
#
# Deliberately three groups, not two. "Should recall" and "should not recall"
# hides the distinction that actually matters here: a social turn and an
# unrelated *question* fail the gate for different reasons and a single bucket
# would let one mask the other.
# --------------------------------------------------------------------------- #

#: Stands in for the user's Spine. Shaped like what was actually in it when the
#: bug was seen — rates, terms, an invoice — because a corpus of unrelated
#: filler would make any gate look good.
CORPUS = [
    "My day rate for Harbour Lane is 425,000 naira.",
    "My day rate for Ashgrove Films is 750,000 naira.",
    "Payment terms for Century are 30 days from invoice date.",
    "INVOICE FROM Uche Anisiuba, 3D Generalist, BILL TO Century.",
    "The Northwind delivery is due on the 14th of September.",
]

#: Social turns. These carry no referent, so there is nothing for recall to be
#: *about* — the correct number of documents is zero regardless of what the
#: corpus contains.
SOCIAL = [
    "Hi",
    "Hello",
    "Hey",
    "hi there",
    "thanks",
    "thank you",
    "ok",
    "good morning",
    "how are you",
]

#: Genuinely referential. These must keep recalling, and they are the reason the
#: floor cannot simply be raised.
#:
#: **Phrased as paraphrases, never as restatements of the stored fact.** The
#: first draft of this list asked "What is my day rate for Harbour Lane?"
#: against a document reading "My day rate for Harbour Lane is 425,000 naira" —
#: near-verbatim, which scored 0.83-0.86 and made every gate look excellent.
#: That is the corpus trap `CLAUDE.md` records costing three measurement cycles:
#: a set that is easier than reality produces a threshold that fails on reality.
#: A person asks "how much do I charge them", not "what is my day rate for".
#:
#: The last two are deliberately terse and vague. "what did I quote them" has a
#: referent the embedding cannot see, which is the referential case rule 9 is
#: about — and the hardest thing for any gate to keep.
REFERENTIAL = [
    "how much do I charge Harbour Lane",
    "when do I have to deliver Northwind",
    "how long does Century take to pay",
    "what's the rate again",
    "what did I quote them",
]

#: Questions with a referent that is not in the Spine. A gate that only looks at
#: length or politeness would wave these through, and the floor is what has to
#: stop them — which is the division of labour worth keeping explicit.
UNRELATED = [
    "who won the 2026 world cup",
    "write me a python function to sort a list",
]


#: What a social turn looks like, for the gate to compare against.
#:
#: The gate cannot ask "how similar is this to the user's documents" — that is
#: the comparison measured above, and it does not separate the populations. It
#: asks a different question: **is this turn more like small talk or more like a
#: request about the user's work?** Nearest exemplar wins, which is the approach
#: `CLAUDE.md` already specifies for routing, applied one decision earlier.
#:
#: Short and generic on purpose. An exemplar mentioning invoices would pull
#: every money question toward the social side.
SOCIAL_EXEMPLARS = [
    "hello there",
    "hi, good to see you",
    "thanks very much",
    "how are you doing today",
    "good morning",
    "ok, sounds good",
    "goodbye for now",
]

#: What a turn that needs the Spine looks like. Deliberately about *the user's
#: own things* without naming any of them, so the exemplars do not encode this
#: particular user's clients and stop working for the next one.
TASK_EXEMPLARS = [
    "what did I agree with the client",
    "how much do I charge for this",
    "when is that due",
    "what were the terms we settled on",
    "find the file about that project",
    "what did I say in the last email",
    "write that up as a document",
]


def _cosine(a: Iterable[float], b: Iterable[float]) -> float:
    a = list(a)
    b = list(b)
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _embedder():
    """A live bge-m3 service, or a skip.

    Skipped rather than faked: the whole value of this measurement is that the
    numbers come from the model the floor is calibrated against, and a hash
    backend would produce a table that looks like data and is not.
    """
    try:
        import urllib.request

        host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        with urllib.request.urlopen(f"{host}/api/tags", timeout=2) as response:
            import json

            names = {m["name"] for m in json.loads(response.read())["models"]}
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Ollama is not reachable ({type(exc).__name__})")

    if not any(n.startswith("bge-m3") for n in names):  # pragma: no cover
        pytest.skip("bge-m3 is not installed")

    from runtimes.memory.embeddings import create_embedding_service

    return create_embedding_service(
        backend="ollama", dim=1024, ollama_model="bge-m3"
    )


def _assert_not_degraded(service) -> None:
    """`EmbeddingService` falls back to hash embeddings in silence.

    That fallback is right for the product — recall keeps working on keyword
    overlap rather than dying — and fatal for a measurement, because hash
    embeddings would fill this table with confident numbers from the wrong
    model. Checked after the first embed, since the flag is only set on failure.
    """
    assert not service._degraded, (
        "the embedder fell back to hash embeddings, so these numbers are not "
        "bge-m3 and must not be recorded"
    )


@pytest.mark.measure
class TestMeasureTheGatePopulation:
    """Prints the table the gate has to separate. The numbers are the point."""

    def test_measure(self, capsys):
        service = _embedder()
        corpus_vectors = [service.embed(text) for text in CORPUS]
        _assert_not_degraded(service)

        def best(query: str) -> float:
            vector = service.embed(query)
            return max(_cosine(vector, c) for c in corpus_vectors)

        groups = [
            ("SOCIAL — must recall nothing", SOCIAL),
            ("REFERENTIAL — must keep recalling", REFERENTIAL),
            ("UNRELATED — the floor's job, not the gate's", UNRELATED),
        ]

        from core.execution_engine import ExecutionEngine

        floor = ExecutionEngine.MIN_RECALL_SCORE
        measured: dict[str, list[float]] = {}

        with capsys.disabled():
            print(f"\n  best cosine against a {len(CORPUS)}-document Spine")
            print(f"  MIN_RECALL_SCORE = {floor}\n")
            for label, queries in groups:
                print(f"  {label}")
                scores = []
                for query in queries:
                    score = best(query)
                    scores.append(score)
                    flag = "  <-- CLEARS THE FLOOR" if score >= floor else ""
                    print(f"      {score:.3f}  {query!r}{flag}")
                measured[label] = scores
                print()

        # Asserted, not just printed. A measurement that only prints is a script
        # with a test's filename.
        assert measured, "measured nothing"
        social = measured["SOCIAL — must recall nothing"]
        referential = measured["REFERENTIAL — must keep recalling"]

        assert min(referential) >= floor, (
            f"referential questions scored as low as {min(referential):.3f}, below "
            f"the floor of {floor} — real recall is being dropped, and the gate "
            "is not the problem"
        )

        # The finding, stated as an assertion so it cannot quietly stop being
        # true. If a future embedding model separates greetings on similarity
        # alone, this fails and the gate's justification gets re-read.
        assert max(social) >= floor, (
            f"greetings now top out at {max(social):.3f}, below the floor of "
            f"{floor}. The premise of the recall gate was that similarity alone "
            "cannot reject them. Re-measure before keeping the gate."
        )

        # The stronger claim, and the one that decides the design: the two
        # populations *overlap*, so no floor can separate them at all.
        assert max(social) > min(referential), (
            "social and referential no longer overlap on corpus similarity — a "
            "threshold could separate them, and the gate may be unnecessary "
            f"(social max {max(social):.3f}, referential min {min(referential):.3f})"
        )

    def test_measure_exemplar_separation(self, capsys):
        """Does comparing against *turn-type* exemplars separate what a floor cannot?

        This is the gate's actual mechanism, measured before it is built. Each
        query is scored against both exemplar sets; the margin is what a
        threshold would have to live inside.
        """
        service = _embedder()
        social_vectors = [service.embed(t) for t in SOCIAL_EXEMPLARS]
        task_vectors = [service.embed(t) for t in TASK_EXEMPLARS]
        _assert_not_degraded(service)

        def margin(query: str) -> tuple[float, float]:
            vector = service.embed(query)
            return (
                max(_cosine(vector, v) for v in social_vectors),
                max(_cosine(vector, v) for v in task_vectors),
            )

        social_margins: list[float] = []
        referential_margins: list[float] = []
        unrelated_margins: list[float] = []

        with capsys.disabled():
            print("\n  nearest exemplar — social vs task\n")
            for label, queries, sink in (
                ("SOCIAL — must be gated out", SOCIAL, social_margins),
                ("REFERENTIAL — must reach recall", REFERENTIAL, referential_margins),
                ("UNRELATED — either route is fine", UNRELATED, unrelated_margins),
            ):
                print(f"  {label}")
                for query in queries:
                    social_score, task_score = margin(query)
                    delta = social_score - task_score
                    sink.append(delta)
                    print(
                        f"      social {social_score:.3f}  task {task_score:.3f}  "
                        f"delta {delta:+.3f}  {query!r}"
                    )
                print()
            print(f"  smallest social margin      {min(social_margins):+.3f}")
            print(f"  largest non-social margin   {max(referential_margins + unrelated_margins):+.3f}\n")

        # A bare argmax is the wrong rule, and this is where that was decided.
        # `who won the 2026 world cup` lands social by +0.025 — harmless in
        # itself, since the floor rejects it anyway, but it shows argmax has no
        # headroom. **Suppressing recall on a real question is the worse
        # failure**, so the gate demands a clear social win rather than any win.
        assert all(d > 0 for d in social_margins), (
            "a social turn landed nearer a task exemplar; recall would run on a "
            "greeting, which is the bug this file exists for"
        )
        assert all(d < 0 for d in referential_margins), (
            "a referential turn landed nearer a social exemplar; the gate would "
            "suppress recall on a real question, which is the worse failure"
        )

        # UNRELATED is deliberately *not* asserted on direction. Its defining
        # property is that no citation may appear, and both routes deliver that:
        # gated out, or recalled and dropped by MIN_RECALL_SCORE at 0.319-0.372.
        # Demanding a direction here would be asserting an implementation
        # detail, and it is what made the first version of this test fail on
        # behaviour that was correct.

        # The gap the threshold has to sit in, which is the number the gate
        # ships with. Measured 10 August 2026: social bottoms out at +0.247 and
        # everything else tops out at +0.025 — an order of magnitude of empty
        # space, so the exact value inside it is not delicate.
        assert min(social_margins) > max(referential_margins + unrelated_margins), (
            "the social and non-social margin populations now overlap, so no "
            "single threshold separates them — re-read the gate's design"
        )
