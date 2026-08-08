"""A recall eval harness. Recall is the moat and it was unmeasured.

Not a benchmark against LoCoMo or LongMemEval — those measure a memory *engine*
against long synthetic dialogues, and what fails first here is narrower and more
specific: whether a question about a document the user just indexed retrieves
that document and not the one next to it.

The distinction matters because of how the alpha fails. If recall is mediocre
the day-30 number will not say why: users report "it didn't feel like it knew
me", which cannot be debugged afterwards. So this measures the thing a user
would notice, on material shaped like theirs — an invoice, a brief, a contract,
a note about a different client — and fails the build when it regresses.

Two layers, because they break for different reasons and only one can run
offline:

- **The threshold, on recorded scores.** Deterministic, no Ollama, runs
  everywhere. This is what `MIN_RECALL_SCORE` is graded against.
- **The end-to-end eval, on real embeddings.** Skipped unless Ollama and bge-m3
  are reachable, because similarity over the hash fallback is arbitrary rather
  than merely worse and a green run against it would be a lie.

Why cases live here rather than being generated: retrofitting them later means
writing them against whatever happens to be indexed, which measures the corpus
instead of the retrieval.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pytest

from core.execution_engine import ExecutionEngine

# --------------------------------------------------------------------------- #
# The corpus. Deliberately confusable: two invoices, two clients, overlapping
# vocabulary. Recall that only works when documents are unrelated is not recall.
# --------------------------------------------------------------------------- #

CORPUS: dict[str, str] = {
    "century-invoice": (
        "Invoice INV-CENT-001 for Century. Issued 8 June 2026 in NGN. "
        "3D generalist services at a day rate of 250,000 naira. "
        "Payment terms: 30 days from the invoice date."
    ),
    "harbour-invoice": (
        "Invoice INV-HARB-014 for Harbour Lane Studio. Issued 2 July 2026 in NGN. "
        "Motion design at a day rate of 425,000 naira. "
        "Payment terms: 14 days from the invoice date."
    ),
    "harbour-brief": (
        "Harbour Lane Studio brief. The deliverable is a 45-second title sequence "
        "for the autumn campaign. Two rounds of revisions are included. "
        "Final delivery is 12 September 2026."
    ),
    "nda": (
        "Mutual non-disclosure agreement with Quadron Studios, signed 3 March 2026. "
        "Confidentiality survives for three years after termination."
    ),
    "note": (
        "Prefer Nigerian English spelling in anything client-facing, "
        "and never send a document without a summary paragraph at the top."
    ),
}


@dataclass(frozen=True)
class Case:
    question: str
    #: The document ids that genuinely answer it. Empty means "nothing should
    #: be recalled" — the hardest case and the one most often got wrong.
    expected: frozenset[str]
    why: str


CASES: tuple[Case, ...] = (
    Case(
        "What is Harbour Lane's day rate?",
        frozenset({"harbour-invoice"}),
        "the exact-match case; if this fails nothing else matters",
    ),
    Case(
        "When is Century's invoice due?",
        frozenset({"century-invoice"}),
        "payment terms live in a different sentence from the client name",
    ),
    Case(
        "How long is the title sequence?",
        frozenset({"harbour-brief"}),
        "the brief, not the invoice, though both say Harbour Lane",
    ),
    Case(
        "What did I agree with Quadron?",
        frozenset({"nda"}),
        "a contract question against a corpus of invoices",
    ),
    Case(
        "How should I write to clients?",
        frozenset({"note"}),
        "a preference, not a document fact — the global-vs-project boundary",
    ),
    Case(
        "Who won the 2026 World Cup?",
        frozenset(),
        "nothing in the corpus answers this, and citing anything would be a "
        "false claim of provenance. Recall must return nothing.",
    ),
    Case(
        "What is the capital of France?",
        frozenset(),
        "same, with vocabulary that shares nothing with the corpus",
    ),
)


# --------------------------------------------------------------------------- #
# Layer 1 — the threshold, offline.
# --------------------------------------------------------------------------- #

class TestThresholdIsMeasured:
    """The offline half. `test_recall_relevance.py` grades the floor against
    scores recorded in April; these are the invariants that hold regardless of
    which embedder produced them."""

    def test_recall_is_capped(self):
        """An answer citing ten sources cites nothing a user will check."""
        assert 1 <= ExecutionEngine.MAX_RECALL <= 8

    def test_the_floor_is_above_the_noise_any_embedder_produces(self):
        """Two unrelated English sentences sit around 0.3 under bge-m3.

        A floor at or below that recalls everything for every question, which
        is the regression this number was introduced to fix.
        """
        assert ExecutionEngine.MIN_RECALL_SCORE > 0.35

    def test_an_empty_query_lists_and_a_stopword_query_ranks_nothing(self):
        """Two different things that both look like "no search terms".

        An empty query is a *listing* — "everything in this session", already
        narrowed by the store's filters — and must return records. A question
        made entirely of stopwords ("what is that?") is a real question that
        cannot be ranked, and returning the whole store at a confident 0.5
        would attach citations to an answer that used none of them.

        Collapsing the two broke session filtering while fixing the stopword
        bug, which is exactly how a narrow fix becomes a wide regression.
        """
        import asyncio

        from runtimes.memory.contracts import MemoryType
        from runtimes.memory.runtime import MemoryRuntimeImpl

        async def run():
            runtime = MemoryRuntimeImpl(store_type="memory", index_type="hybrid")
            await runtime.initialize()
            await runtime.store(
                content="Session A message",
                memory_type=MemoryType.CONVERSATION,
                session_id="session-a",
            )
            listed = await runtime.retrieve(
                query="", memory_types=[MemoryType.CONVERSATION], session_id="session-a"
            )
            unrankable = await runtime.retrieve(query="what is that?")
            await runtime.shutdown()
            return listed, unrankable

        listed, unrankable = asyncio.run(run())

        assert len(listed) == 1, "an empty query must still list the session"
        assert unrankable == [], "a stopword-only question must cite nothing"

    def test_the_eval_corpus_is_deliberately_confusable(self):
        """Recall that only works on unrelated documents is not recall.

        Guards the corpus itself: someone simplifying these cases into
        obviously-distinct documents would make the suite green and the eval
        worthless.
        """
        clients = [doc for doc in CORPUS if doc.startswith("harbour")]
        assert len(clients) >= 2, "two documents must share a client name"
        assert sum("day rate" in text for text in CORPUS.values()) >= 2
        assert any(not c.expected for c in CASES), "no unanswerable case"


# --------------------------------------------------------------------------- #
# Layer 2 — end to end, on real embeddings.
# --------------------------------------------------------------------------- #

def _ollama_has_bge_m3() -> bool:
    """Checked at collection time. Loopback only — this is not egress."""
    try:
        import requests

        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        names = {m["name"] for m in response.json().get("models", [])}
    except Exception:
        return False
    return any(n.startswith("bge-m3") for n in names)


requires_embeddings = pytest.mark.skipif(
    not _ollama_has_bge_m3(),
    reason=(
        "needs Ollama with bge-m3 on 127.0.0.1:11434. Similarity over the hash "
        "fallback is arbitrary rather than merely worse, so a green run against "
        "it would be meaningless. Run: ollama pull bge-m3"
    ),
)


@pytest.fixture(scope="module")
def spine(tmp_path_factory):
    """A Spine holding the corpus, embedded for real."""
    import asyncio

    from runtimes.memory.contracts import MemoryType
    from runtimes.memory.runtime import MemoryRuntimeImpl

    db = tmp_path_factory.mktemp("recall-eval") / "spine.db"
    runtime = MemoryRuntimeImpl(
        store_type="sqlite",
        db_path=str(db),
        index_type="hybrid",
        embedding_dim=1024,
        embedding_backend="ollama",
        embedding_model="bge-m3",
    )

    async def build():
        await runtime.initialize()
        for doc_id, text in CORPUS.items():
            await runtime.remember(
                content=text,
                memory_type=MemoryType.SEMANTIC,
                metadata={"doc_id": doc_id, "origin": "user_document"},
            )
        return runtime

    loop = asyncio.new_event_loop()
    try:
        yield loop.run_until_complete(build()), loop
    finally:
        loop.run_until_complete(runtime.shutdown())
        loop.close()


def _recall(spine, question: str) -> list[tuple[str, float]]:
    runtime, loop = spine
    results = loop.run_until_complete(
        runtime.retrieve(query=question, max_results=ExecutionEngine.MAX_RECALL)
    )
    out = []
    for r in results:
        record = getattr(r, "record", None)
        metadata = (getattr(record, "metadata", None) or getattr(r, "metadata", None) or {})
        out.append((metadata.get("doc_id", "?"), float(getattr(r, "score", 0.0))))
    return out


@requires_embeddings
class TestRecallEndToEnd:
    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.question)
    def test_the_right_document_is_recalled(self, spine, case: Case):
        recalled = _recall(spine, case.question)
        kept = {
            doc for doc, score in recalled if score >= ExecutionEngine.MIN_RECALL_SCORE
        }

        if not case.expected:
            assert not kept, (
                f"{case.question!r} recalled {sorted(kept)} and should recall "
                f"nothing — {case.why}. Scores: "
                f"{[(d, round(s, 3)) for d, s in recalled]}"
            )
            return

        missing = case.expected - kept
        assert not missing, (
            f"{case.question!r} did not recall {sorted(missing)} — {case.why}. "
            f"Scores: {[(d, round(s, 3)) for d, s in recalled]}"
        )

    def test_precision_across_the_whole_set(self, spine):
        """One case passing by luck is not recall working.

        Reported as a number so a regression shows as a number rather than as
        one confusing failure.
        """
        answerable = [c for c in CASES if c.expected]
        hits = 0
        detail: list[str] = []
        for case in answerable:
            kept = {
                doc
                for doc, score in _recall(spine, case.question)
                if score >= ExecutionEngine.MIN_RECALL_SCORE
            }
            top_is_right = bool(case.expected & kept)
            hits += top_is_right
            if not top_is_right:
                detail.append(case.question)

        rate = hits / len(answerable)
        assert rate >= 0.8, (
            f"recall@{ExecutionEngine.MAX_RECALL} is {rate:.0%} "
            f"({hits}/{len(answerable)}); failing: {detail}"
        )

    def test_nothing_unrelated_survives_the_threshold(self, spine):
        """The false-positive half, measured separately.

        A citation the answer did not use is a false claim of provenance, and
        it teaches the user that citations mean nothing. After that the real
        ones cannot help.
        """
        for case in (c for c in CASES if not c.expected):
            kept = [
                (doc, round(score, 3))
                for doc, score in _recall(spine, case.question)
                if score >= ExecutionEngine.MIN_RECALL_SCORE
            ]
            assert not kept, f"{case.question!r} cited {kept}"

    def test_the_threshold_still_sits_between_the_populations(self, spine):
        """Re-measures the floor rather than trusting the recorded numbers.

        `test_recall_relevance.py` asserts the separation against scores
        recorded in April. This checks the same claim against scores produced
        now, so a change in the embedding model shows up here rather than in a
        user's answers.

        The negative population is drawn only from the *unanswerable* cases.
        `expected` means "must be recalled", not "is the only relevant
        document": a Harbour Lane brief scoring 0.49 on a question about
        Harbour Lane's day rate is the retrieval working, and counting it as a
        false positive would push the floor up until real recall broke.
        """
        related = [
            score
            for case in CASES
            for doc, score in _recall(spine, case.question)
            if doc in case.expected
        ]
        unrelated = [
            score
            for case in CASES
            if not case.expected
            for _, score in _recall(spine, case.question)
        ]

        assert related, "no related scores were produced at all"
        assert min(related) >= ExecutionEngine.MIN_RECALL_SCORE, (
            f"a genuinely related document scored {min(related):.3f}, below the "
            f"floor of {ExecutionEngine.MIN_RECALL_SCORE} — real recall is being dropped"
        )
        assert unrelated, "no negative cases — the floor is untested against noise"
        assert max(unrelated) < ExecutionEngine.MIN_RECALL_SCORE, (
            f"a document unrelated to any question scored {max(unrelated):.3f}, at "
            f"or above the floor — it will be recalled and cited"
        )

    def test_the_measured_margin_is_reported(self, spine):
        """The gap between the populations, so a narrowing one is visible.

        A pass/fail on the floor hides the trend: recall can degrade for
        several releases while still technically separating, and the first
        visible symptom would be a user saying it stopped knowing them.
        """
        related = [
            score
            for case in CASES
            for doc, score in _recall(spine, case.question)
            if doc in case.expected
        ]
        unrelated = [
            score
            for case in CASES
            if not case.expected
            for _, score in _recall(spine, case.question)
        ]
        margin = min(related) - max(unrelated)
        print(
            f"\nrecall margin: related min {min(related):.3f} - "
            f"unrelated max {max(unrelated):.3f} = {margin:+.3f} "
            f"(floor {ExecutionEngine.MIN_RECALL_SCORE})"
        )
        assert margin > 0, "the two populations overlap; no threshold separates them"


@requires_embeddings
def test_ingested_documents_are_recallable(tmp_path):
    """M7's acceptance criterion, as a test.

    Point at a folder, index it, ask a question, get the right document back.
    This is the seam — ingest and recall each work in isolation and the thing
    the user buys is the two of them together.
    """
    import asyncio

    from ingest import IngestStatus, ingest_folder
    from runtimes.memory.contracts import MemoryType
    from runtimes.memory.runtime import MemoryRuntimeImpl

    folder = tmp_path / "documents"
    folder.mkdir()
    (folder / "harbour-invoice.md").write_text(CORPUS["harbour-invoice"], encoding="utf-8")
    (folder / "century-invoice.md").write_text(CORPUS["century-invoice"], encoding="utf-8")
    (folder / "scan.pdf").write_bytes(b"%PDF-1.4\nnot a real pdf")

    pending: list[tuple[str, dict]] = []
    report = ingest_folder(
        folder, store_fact=lambda text, meta: (pending.append((text, meta)), "id")[1]
    )

    assert report.count(IngestStatus.INDEXED) == 2
    assert report.problems, "the unreadable PDF must be visible, not skipped"
    assert all(o.reason for o in report.problems)

    runtime = MemoryRuntimeImpl(
        store_type="sqlite",
        db_path=str(tmp_path / "spine.db"),
        index_type="hybrid",
        embedding_dim=1024,
        embedding_backend="ollama",
        embedding_model="bge-m3",
    )

    async def run():
        await runtime.initialize()
        for text, metadata in pending:
            await runtime.remember(
                content=text, memory_type=MemoryType.SEMANTIC, metadata=metadata
            )
        results = await runtime.retrieve(
            query="What is Harbour Lane's day rate?", max_results=3
        )
        await runtime.shutdown()
        return results

    results = asyncio.run(run())

    kept = [r for r in results if float(getattr(r, "score", 0.0)) >= ExecutionEngine.MIN_RECALL_SCORE]
    assert kept, "nothing was recalled from a folder that was just indexed"

    top = kept[0]
    record = getattr(top, "record", None)
    metadata = (getattr(record, "metadata", None) or {})
    assert metadata.get("source_name") == "harbour-invoice.md", (
        f"recalled {metadata.get('source_name')!r} for a Harbour Lane question"
    )
    assert metadata.get("origin") == "user_document", "rule 7b: origin must survive"
