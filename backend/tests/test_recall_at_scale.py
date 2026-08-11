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
#: Deliverables for the filler briefs — deliberately *not* including "title
#: sequence".
#:
#: It used to. One of the eval questions is "How long is the title sequence?"
#: and its expected answer is a brief carrying a duration, so a filler template
#: that emitted "a 45-second title sequence for the autumn campaign" produced
#: ~64 documents per thousand that answered the question exactly as well as the
#: target did, for different clients. The eval then reported the target ranking
#: 54th as a recall miss, three times, and it was nothing of the sort.
#:
#: These are still the same *shape* of document — a client brief with a
#: deliverable, a duration and a date — which is what makes them useful
#: distractors. They simply no longer answer the question being graded.
#: `TestTheCorpusIsFitToMeasureWith` enforces the distinction.
_SVC2 = ("product film", "explainer", "sizzle reel", "brand ident")
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


def _engine_shortlist(spine, question: str) -> list[tuple[str, float]]:
    """Exactly what `ExecutionEngine._recall` hands the model.

    Retrieve `RECALL_CANDIDATES`, drop everything under the floor, sort by
    relevance, cut to `MAX_RECALL`.

    Written as a mirror of the engine rather than as a general ranking view
    because the earlier tests here measured the raw order retrieval returns —
    which is the *blend* — and then asserted things about the shortlist. Those
    are two different lists, and the tests kept diagnosing the ordering as a
    depth problem because they never looked at the list the product builds.
    That is this repo's own "test the seams, not the components" note, in the
    file that exists to measure the seam.
    """
    runtime, loop = spine
    results = loop.run_until_complete(
        runtime.retrieve(query=question, max_results=ExecutionEngine.RECALL_CANDIDATES)
    )
    kept = sorted(
        (r for r in results
         if (r.relevance if r.relevance is not None else r.score) >= FLOOR),
        key=lambda r: r.relevance if r.relevance is not None else r.score,
        reverse=True,
    )[: ExecutionEngine.MAX_RECALL]

    out = []
    for r in kept:
        meta = getattr(r.record, "metadata", None) or {}
        rel = r.relevance if r.relevance is not None else r.score
        out.append((meta.get("doc_id", "?"), float(rel)))
    return out


def _ranked_both(spine, question: str, depth: int) -> list[tuple[int, str, float, float]]:
    """As `_ranked`, but carrying the ranking blend alongside the relevance.

    The two numbers answer different questions — `relevance` is the cosine the
    citation floor is graded against, `score` is the ordering blend — and the
    position a document ends up in is decided by the second. Reporting only the
    first makes a blend-driven displacement look like a scoring failure.
    """
    runtime, loop = spine
    results = loop.run_until_complete(runtime.retrieve(query=question, max_results=depth))
    out = []
    for i, r in enumerate(results, start=1):
        meta = getattr(r.record, "metadata", None) or {}
        relevance = r.relevance if r.relevance is not None else r.score
        out.append((i, meta.get("doc_id", "?"), float(relevance), float(r.score)))
    return out


class TestTheCorpusIsFitToMeasureWith:
    """Does the filler accidentally answer the questions?

    Not opt-in and needs no Ollama: it is arithmetic on the generator, and it
    guards every number the rest of this file prints.

    This exists because the eval spent three measurement cycles reporting "4 of
    5 recalled" and inviting a reranker, when the fifth was unrecallable by
    construction. `_filler` draws from `_SVC2`, which contains *"title
    sequence"*, and emits it in a brief template that also carries a duration —
    so a thousand-document corpus holds ~64 documents that answer *"How long is
    the title sequence?"* exactly as well as the expected one does, for
    different clients. The question names no client. Ranking the expected
    document 54th out of 65 equally valid answers is **correct retrieval**, and
    counting it as a miss measures the generator rather than the product.

    A corpus whose distractors are indistinguishable from its targets cannot
    grade anything. Near-miss filler is the point; accidentally-correct filler
    is a broken instrument.
    """

    def test_no_filler_document_answers_an_eval_question_as_well_as_its_target(self):
        collisions = {}
        docs = _filler(1000)

        for case in CASES:
            if not case.expected:
                continue
            # The content words that make this question answerable at all.
            terms = {w for w in case.question.lower().strip("?").split() if len(w) > 4}
            if not terms:
                continue
            hits = [d for d in docs if all(t in d.lower() for t in terms)]
            if hits:
                collisions[case.question] = len(hits)

        for question, n in collisions.items():
            print(f"\n  {n} filler documents answer {question!r} as well as the target")

        assert not collisions, (
            f"the filler answers its own eval questions: {collisions}. Any miss "
            f"reported for these is a property of `_filler`, not of recall — "
            f"fix the generator to be deliberately *near*-miss before reading "
            f"the recall numbers in this file."
        )


@scale_only
class TestRankingIsStable:
    """Does asking the same question twice give the same answer?

    This exists because two tests in `TestMarginAtScale` disagreed about the
    rank of one document — 7 in one, 2 in the next — against the same corpus in
    the same run. Only one of them can be right, and a shortlist that reorders
    between identical queries makes every other measurement in this file a
    reading of whatever happened to run before it.
    """

    def test_the_same_question_ranks_the_same_every_time(self, big_spine):
        """Retrieval must not be changed by having been run.

        `retrieve` calls `record_access`, and `access_count` carries weight in
        the ranking blend. If that feedback reaches the ordering, recall becomes
        self-reinforcing: whatever came back last time comes back more easily
        next time, regardless of what was asked. On a Spine that grows for
        years, that is a memory which gradually narrows to its own history.

        Measured on the *target's* rank across repeats, not on the top ten.
        The first version of this test compared two consecutive top-10 slices
        and passed, while two other tests in this file disagreed about the same
        document's position by five places. It was asserting stability where
        the score gaps are widest — true, and about nothing anyone was worried
        about. The instability lives at the shortlist boundary, among
        near-identical invoices whose scores differ in the third decimal, so
        that is where it has to be looked for.
        """
        question = "How long is the title sequence?"
        expected = next(c.expected for c in CASES if c.question == question)

        observed: list[tuple[int, float]] = []
        for _ in range(6):
            deep = _ranked(big_spine, question, 100)
            target = next((t for t in deep if t[1] in expected), None)
            assert target is not None, f"{expected} vanished from the top 100 entirely"
            observed.append((target[0], round(target[2], 4)))

        ranks = [r for r, _ in observed]
        relevances = {rel for _, rel in observed}
        print(f"\n[{CORPUS_SIZE} docs] same question asked 6×, "
              f"target ranks: {ranks}, relevance {sorted(relevances)}")

        assert len(relevances) == 1, (
            f"the same document scored differently against the same query on "
            f"repeat asks: {sorted(relevances)}. Relevance is supposed to be a "
            f"cosine between two fixed vectors."
        )
        assert len(set(ranks)) == 1, (
            f"the same document moved between ranks {ranks} on identical "
            f"queries while its relevance never changed. Retrieval is mutating "
            f"the state it orders on — see record_access and the access weight "
            f"in MemoryRankerImpl. Every other measurement in this file is a "
            f"reading of whatever happened to run before it."
        )

    def test_position_is_decided_by_relevance_not_by_the_blend(self, big_spine):
        """Where a document lands must follow from how relevant it is.

        The citation floor was already moved off the ranking blend and onto
        `relevance`, because a fact could clear it on recency alone. The *cut*
        is the same argument one step later: `MAX_RECALL` slices a list ordered
        by the blend, so a document with the highest relevance in the corpus can
        still be cut by five documents that are less relevant and more recently
        touched. A floor on relevance does not help a document that never
        reaches the floor's list.
        """
        offenders = []
        for case in (c for c in CASES if c.expected):
            deep = _ranked_both(big_spine, case.question, 100)
            target = next((t for t in deep if t[1] in case.expected), None)
            if target is None:
                continue
            rank, doc, relevance, _score = target

            # How many documents ahead of it are *less relevant* than it is.
            # Those are the ones the blend promoted past it.
            ahead = [t for t in deep[: rank - 1] if t[2] < relevance]

            # Ordering by the blend inside the shortlist is deliberate and
            # correct — a pinned, recent, frequently-used fact should be shown
            # first among equally relevant ones. What must not happen is a
            # document being *excluded* on the blend. So the test is membership
            # of the engine's shortlist, not ordinal position in the raw list.
            shortlist = {d for d, _ in _engine_shortlist(big_spine, case.question)}
            if ahead and not (case.expected & shortlist):
                offenders.append((case.question, doc, rank, relevance, len(ahead)))

        print(f"\n[{CORPUS_SIZE} docs] blend-driven exclusion:")
        for q, doc, rank, rel, n in offenders:
            print(f"  {doc} (relevance {rel:.3f}) missing from the shortlist, "
                  f"{n} less-relevant documents ranked above it: {q!r}")
        if not offenders:
            print("  none — the blend orders the shortlist but no longer picks it")

        assert not offenders, (
            f"{len(offenders)} target(s) were kept out of the shortlist by "
            f"documents they out-score on relevance. This is not a depth "
            f"problem and a wider shortlist does not fix it: {offenders}"
        )


@scale_only
class TestMarginAtScale:
    def test_the_margin_survives_the_corpus(self, big_spine):
        """The headline number, at `CORPUS_SIZE` rather than five.

        **Both populations are read at full corpus depth, not at `SHORTLIST`.**
        The margin asks whether the *relevance* populations separate — a
        property of scoring, which has nothing to do with how many rows the
        shortlist holds.

        The bias this removes is already documented and already fixed *at the
        other end*: `docs/RERANKER.md` records that the `+0.179` still sitting
        in `execution_engine.py` was inflated because the document scoring 0.517
        was excluded from the shortlist entirely and so never entered the sample
        the minimum was taken over. Selection by relevance fixed that, and
        +0.106 is the baseline.

        What was left is that **the measurement still depended on the fix.**
        Reading `related` at shortlist depth only gives an honest answer while
        selection is behaving; the day a target is crowded out again, the metric
        reports a *better* margin — loudest praise exactly when a user stops
        getting their answer. A number that can only be trusted when the thing
        it measures is working is not an instrument.

        The unrelated side had the mirror of it. Results arrive ordered by the
        ranking blend, so the most relevant unrelated document need not be in
        the first six — `max(unrelated)` was a maximum over whatever the blend
        promoted, not over the corpus.

        Measured both ways at 10 and 100 documents: identical numbers, because
        the bias is currently inactive. That is the point — it is inactive, not
        absent.
        """
        related, unrelated = [], []
        for case in CASES:
            for _, doc, rel in _ranked(big_spine, case.question, CORPUS_SIZE):
                if doc in case.expected:
                    related.append(rel)
        for question in UNANSWERABLE:
            for _, _, rel in _ranked(big_spine, question, CORPUS_SIZE):
                unrelated.append(rel)

        margin = min(related) - max(unrelated)
        print(f"\n[{CORPUS_SIZE} docs] related_min {min(related):.3f} - "
              f"unrelated_max {max(unrelated):.3f} = {margin:+.3f} (floor {FLOOR}) "
              f"— full-depth, {len(related)} targets vs {len(unrelated)} unrelated")

        assert margin > 0, (
            f"at {CORPUS_SIZE} documents the populations overlap; no threshold "
            f"separates them and a reranker is not optional"
        )

    def test_every_target_contributes_to_the_margin_however_it_ranked(self, big_spine):
        """The guard on the metric above, and it is worth its own name.

        If the margin is ever measured at shortlist depth again, a crowded-out
        target silently leaves the population and the number *improves*. That
        failure is invisible in the margin itself — it looks like a better
        result — so it cannot be caught by asserting on the margin.

        What can be asserted is the population: every answerable case must
        contribute exactly one relevance, whatever rank its target reached. A
        count that drops means a target was dropped, and the next margin printed
        is measuring a smaller and flattering set.
        """
        answerable = [c for c in CASES if c.expected]
        contributed = []
        for case in answerable:
            found = [rel for _, doc, rel in _ranked(big_spine, case.question, CORPUS_SIZE)
                     if doc in case.expected]
            contributed.append((case.question, len(found)))

        missing = [q for q, n in contributed if n == 0]
        print(f"\n[{CORPUS_SIZE} docs] margin population: "
              f"{len(answerable) - len(missing)}/{len(answerable)} targets found at full depth")

        assert not missing, (
            f"{len(missing)} target(s) never appeared at any depth, so they "
            f"contribute nothing to the margin and the printed number is taken "
            f"over the targets that happened to survive: {missing}"
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
            # The list the product actually gives the model, not the first
            # `SHORTLIST` of the raw blend-ordered results. Those differ, and
            # reading the second while reasoning about the first is what made
            # an ordering defect look like a depth defect for a whole cycle.
            top = {doc for doc, _ in _engine_shortlist(big_spine, question)}

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

        # Displacement is asserted, not merely printed. It was printed and not
        # asserted for one measurement cycle, which is how "1 missed, rank 7"
        # was read as a finding to note rather than a failure to fix.
        assert not displaced, (
            f"a target scored above the floor and was still crowded out of the "
            f"top {SHORTLIST}: {displaced}. That is a *depth* failure. Raise "
            f"MAX_RECALL past the ranks reported by "
            f"test_the_shortlist_covers_the_deepest_target."
        )

    def test_the_shortlist_covers_the_deepest_target(self, big_spine):
        """Where MAX_RECALL's value comes from.

        The cut is a product constant, so it is measured rather than chosen:
        this reports the rank each answerable target actually lands at, and the
        deepest of them is the number the shortlist has to clear.

        It reports rather than merely asserting, because the headroom matters as
        much as the pass. A shortlist sitting exactly on the deepest target is
        one near-identical invoice away from dropping it, and that is visible
        here and nowhere else.
        """
        ranks: list[tuple[int, str]] = []
        for case in (c for c in CASES if c.expected):
            # Ranked by relevance, because relevance is what selection uses.
            deep = sorted(_ranked(big_spine, case.question, 100),
                          key=lambda t: t[2], reverse=True)
            position = next(
                (i for i, t in enumerate(deep, start=1) if t[1] in case.expected),
                None,
            )
            if position is not None:
                ranks.append((position, case.question))

        assert ranks, "no answerable target was found at all — the corpus is wrong"

        deepest, worst_question = max(ranks)
        print(f"\n[{CORPUS_SIZE} docs] target ranks by relevance: "
              f"{sorted(r for r, _ in ranks)} — deepest {deepest} "
              f"({worst_question!r}), shortlist {SHORTLIST}, "
              f"headroom {SHORTLIST - deepest}")

        assert SHORTLIST >= deepest, (
            f"MAX_RECALL is {SHORTLIST} and a target sits at relevance rank "
            f"{deepest} ({worst_question!r}). The shortlist cuts off a document "
            f"that scored well enough to cite."
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
