"""Does recall survive a Spine that has grown?

`test_recall_eval.py` measures five documents. The worry this answers is
structural: the negative side of the margin is a *maximum over the corpus*, so
every document added is another chance for something irrelevant to score high,
while the positive side does not move. In a product whose whole pitch is that
the Spine grows, a floor that only works when it is empty is not a floor.

**The two failure modes wear the same face and call for opposite spends**, so
this pulls them apart:

- **Threshold failure** — the target's relevance fell below `MIN_RECALL_SCORE`.
  A scoring problem. Better relevance fixes it; a reranker is one way.
- **Depth failure** — the target still scores well but was crowded out of the
  top `MAX_RECALL` by near-misses. A shortlist problem. No threshold change
  helps; only retrieving wider and cutting afterwards does.

Reading "1 missed" and buying a reranker without knowing which of those it was
is how a measurement becomes a purchase order for the wrong thing.

Opt-in. Indexing a hundred documents through bge-m3 takes the better part of a
minute, which does not belong in a suite that runs on every change:

    ZARAM_SCALE_EVAL=1 pytest backend/tests/test_recall_at_scale.py -s
"""

from __future__ import annotations

import asyncio
import os
import random
import time

import pytest

from core.execution_engine import ExecutionEngine
from tests.test_recall_eval import CASES, CORPUS, _ollama_has_bge_m3

FLOOR = ExecutionEngine.MIN_RECALL_SCORE
SHORTLIST = ExecutionEngine.MAX_RECALL

#: Big enough to reproduce what a hundred real documents do, small enough that
#: someone will actually run it.
CORPUS_SIZE = int(os.getenv("ZARAM_SCALE_EVAL_SIZE", "100"))

UNANSWERABLE = (
    "Who won the 2026 World Cup?",
    "What is the capital of France?",
    "How do I change a bicycle tyre?",
)

# Filler shaped like the same person's working life. Drawn from another domain
# it would make this easy in a way real life is not — the whole difficulty is
# that a freelancer's Spine is a thousand near-identical invoices.
_CLIENTS = ("Ridgeway", "Lantern House", "Ovo Media", "Blackthorn", "Maren Studio",
            "Copperfield", "Sable & Co", "Northgate", "Verity Films", "Ashwood")
_TEMPLATES = (
    "Invoice INV-{c}-{n:03d} for {C}. Issued {d} {m} 2026 in NGN. {svc} at a day "
    "rate of {r},000 naira. Payment terms: {t} days from the invoice date.",
    "{C} brief. The deliverable is a {sec}-second {svc2} for the {season} campaign. "
    "{rev} rounds of revisions are included. Final delivery is {d} {m} 2026.",
    "Mutual non-disclosure agreement with {C}, signed {d} {m} 2026. "
    "Confidentiality survives for {yr} years after termination.",
    "{C} paid invoice INV-{c}-{n:03d} on {d} {m} 2026, {late} days after the due date.",
)
_SVC = ("3D generalist services", "motion design", "compositing", "colour grading")
_SVC2 = ("title sequence", "product film", "explainer", "sizzle reel")
_MONTHS = ("January", "March", "May", "July", "September", "November")


def _filler(n: int, seed: int = 7) -> list[str]:
    rng = random.Random(seed)
    out = []
    for i in range(n):
        client = rng.choice(_CLIENTS)
        out.append(rng.choice(_TEMPLATES).format(
            c=client[:4].upper(), C=client, n=i, d=rng.randint(1, 28),
            m=rng.choice(_MONTHS), svc=rng.choice(_SVC), svc2=rng.choice(_SVC2),
            r=rng.randint(80, 900), t=rng.choice((7, 14, 30, 45)),
            sec=rng.choice((15, 30, 45, 60)), season=rng.choice(("autumn", "spring")),
            rev=rng.choice(("Two", "Three")), yr=rng.choice((2, 3, 5)),
            late=rng.randint(1, 40),
        ))
    return out


scale_only = pytest.mark.skipif(
    os.getenv("ZARAM_SCALE_EVAL") != "1" or not _ollama_has_bge_m3(),
    reason=(
        "opt-in: indexing a hundred documents through bge-m3 takes ~45s. "
        "Run with ZARAM_SCALE_EVAL=1 and Ollama serving bge-m3."
    ),
)


@pytest.fixture(scope="module")
def big_spine(tmp_path_factory):
    from runtimes.memory.contracts import MemoryType
    from runtimes.memory.runtime import MemoryRuntimeImpl

    db = tmp_path_factory.mktemp("scale") / "spine.db"
    runtime = MemoryRuntimeImpl(
        store_type="sqlite", db_path=str(db), index_type="hybrid",
        embedding_dim=1024, embedding_backend="ollama", embedding_model="bge-m3",
    )
    loop = asyncio.new_event_loop()

    async def build():
        await runtime.initialize()
        for doc_id, text in CORPUS.items():
            await runtime.remember(content=text, memory_type=MemoryType.SEMANTIC,
                                   metadata={"doc_id": doc_id})
        for i, text in enumerate(_filler(max(CORPUS_SIZE - len(CORPUS), 0))):
            await runtime.remember(content=text, memory_type=MemoryType.SEMANTIC,
                                   metadata={"doc_id": f"filler-{i}"})

    try:
        loop.run_until_complete(build())
        yield runtime, loop
    finally:
        loop.run_until_complete(runtime.shutdown())
        loop.close()


def _ranked(spine, question: str, depth: int) -> list[tuple[int, str, float]]:
    runtime, loop = spine
    results = loop.run_until_complete(runtime.retrieve(query=question, max_results=depth))
    out = []
    for i, r in enumerate(results, start=1):
        meta = getattr(r.record, "metadata", None) or {}
        relevance = r.relevance if r.relevance is not None else r.score
        out.append((i, meta.get("doc_id", "?"), float(relevance)))
    return out


@scale_only
class TestMarginAtScale:
    def test_the_margin_survives_the_corpus(self, big_spine):
        """The headline number, at `CORPUS_SIZE` rather than five."""
        related, unrelated = [], []
        for case in CASES:
            question, expected = case.question, case.expected
            for _, doc, rel in _ranked(big_spine, question, SHORTLIST):
                if doc in expected:
                    related.append(rel)
        for question in UNANSWERABLE:
            for _, _, rel in _ranked(big_spine, question, SHORTLIST):
                unrelated.append(rel)

        margin = min(related) - max(unrelated)
        print(f"\n[{CORPUS_SIZE} docs] related_min {min(related):.3f} - "
              f"unrelated_max {max(unrelated):.3f} = {margin:+.3f} (floor {FLOOR})")

        assert margin > 0, (
            f"at {CORPUS_SIZE} documents the populations overlap; no threshold "
            f"separates them and a reranker is not optional"
        )

    def test_a_missed_target_is_diagnosed_not_just_counted(self, big_spine):
        """Names *why* each miss happened, because the fix differs.

        This is the test that decides the reranker question. A depth failure is
        fixed by retrieving wider and cutting afterwards, which costs nothing; a
        threshold failure is a scoring problem and is what a cross-encoder is
        actually for.
        """
        displaced, below_floor, fine = [], [], []

        answerable = [c for c in CASES if c.expected]
        for case in answerable:
            # The unanswerable cases are excluded rather than counted as
            # misses: they have no target by design, and "the target is not in
            # the top 100" is the correct outcome for them. Counting them here
            # reported two threshold failures that did not exist, which would
            # have argued for a reranker on the strength of the eval working.
            question, expected = case.question, case.expected
            deep = _ranked(big_spine, question, 100)
            target = next((t for t in deep if t[1] in expected), None)
            top = {doc for _, doc, _ in deep[:SHORTLIST]}

            if target is None:
                below_floor.append((question, "not in the top 100 at all", 0.0))
                continue

            rank, doc, relevance = target
            if expected & top:
                fine.append((question, rank, relevance))
            elif relevance >= FLOOR:
                displaced.append((question, rank, relevance))
            else:
                below_floor.append((question, rank, relevance))

        print(f"\n[{CORPUS_SIZE} docs] recalled in top-{SHORTLIST}: "
              f"{len(fine)}/{len(answerable)} answerable targets")
        for q, rank, rel in displaced:
            print(f"  DISPLACED   rank {rank}, relevance {rel:.3f} (above floor): {q!r}")
        for q, rank, rel in below_floor:
            print(f"  BELOW FLOOR rank {rank}, relevance {rel:.3f}: {q!r}")

        assert not below_floor, (
            f"a target fell below the relevance floor at {CORPUS_SIZE} documents: "
            f"{below_floor}. That is a *scoring* failure — the case a reranker "
            f"exists for — not something a wider shortlist fixes."
        )

    def test_a_wider_shortlist_recovers_anything_displaced(self, big_spine):
        """If misses are displacement, retrieving wider fixes them for free.

        Establishes the cheap remedy before anything is bought: retrieve deep,
        cut to `MAX_RECALL` after. If this passes while the top-k misses, the
        answer to the reranker question is "retrieve wider first".
        """
        recovered = []
        for case in (c for c in CASES if c.expected):
            question, expected = case.question, case.expected
            deep = {doc for _, doc, rel in _ranked(big_spine, question, 50) if rel >= FLOOR}
            missing = expected - deep
            if missing:
                recovered.append((question, sorted(missing)))

        assert not recovered, (
            f"a wider shortlist still misses {recovered} — so the problem is not "
            f"depth, and retrieving more will not fix it"
        )

    def test_false_citations_are_counted(self, big_spine):
        """Unrelated documents crossing the floor, reported as a number.

        Not asserted to zero. At a hundred near-identical invoices some filler
        genuinely does sit near a stray question, and the honest response is to
        watch the count rather than pretend a single global threshold can be
        perfect. It is asserted to stay a small minority, because a majority
        would mean the floor has stopped meaning anything.
        """
        total, false_cites = 0, []
        for question in UNANSWERABLE:
            for _, doc, rel in _ranked(big_spine, question, SHORTLIST):
                total += 1
                if rel >= FLOOR:
                    false_cites.append((question, doc, round(rel, 3)))

        rate = len(false_cites) / max(total, 1)
        print(f"\n[{CORPUS_SIZE} docs] false citations: {len(false_cites)}/{total} "
              f"({rate:.0%}) at floor {FLOOR}")
        for q, doc, rel in false_cites[:6]:
            print(f"  {rel}  {doc} <- {q!r}")

        assert rate < 0.5, (
            f"{rate:.0%} of what comes back for an unanswerable question would be "
            f"cited. The floor has stopped separating anything."
        )

    def test_recall_latency_is_recorded(self, big_spine):
        """The vector index is a linear scan in Python. Watch it.

        Not a pass/fail on a millisecond count — that is a machine property —
        but a number in the output, because retrieval that takes a second is a
        product problem long before it is a correctness one.
        """
        started = time.perf_counter()
        for case in CASES:
            _ranked(big_spine, case.question, SHORTLIST)
        per_query = (time.perf_counter() - started) / len(CASES) * 1000

        print(f"\n[{CORPUS_SIZE} docs] mean recall latency: {per_query:.0f} ms")
        assert per_query < 10_000, "recall has become unusable, not merely slow"
