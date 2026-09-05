"""Semantic retrieval, the routing decision rule, and the documents runtime.

These run on a **stub embedder**, deliberately. Asserting that bge-m3 puts
"write that up as a proposal" nearest the document exemplars would be testing
the model, and it would fail on a machine where Ollama is not running — which
is most CI. What is testable here is the machinery around the model: that the
floor and the margin do what they claim, that a hash-backend embedder disables
routing rather than randomising it, and that a namespace can be dropped.

The model's own behaviour was verified by hand against real bge-m3 and is
recorded in MILESTONES, which is the right place for a measurement that depends
on a model version.
"""

from __future__ import annotations

import asyncio

import pytest

from core.retrieval import (
    Candidate,
    DimensionMismatch,
    SemanticIndex,
    SemanticIntentRouter,
    shortlist,
)
from core.retrieval.exemplars import INTENT_EXEMPLARS, INTENT_NAMESPACE


class StubEmbedder:
    """Deterministic vectors, so similarity is something the test controls.

    Each registered phrase gets an axis of its own; an unknown phrase is the
    zero vector. That makes "identical text" a cosine of 1 and "anything else"
    a cosine of 0, which is enough to exercise every decision this layer makes.
    """

    def __init__(self, vectors: dict[str, list[float]], dim: int = 4, backend="ollama"):
        self._vectors = vectors
        self._dim = dim
        self._backend = backend
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        return self._vectors.get(text, [0.0] * self._dim)

    def get_dim(self) -> int:
        return self._dim

    def health_check(self) -> dict:
        return {"status": "healthy", "backend": self._backend, "dim": self._dim}


def _basis(index: int, dim: int = 4) -> list[float]:
    vector = [0.0] * dim
    vector[index] = 1.0
    return vector


@pytest.fixture
def embedder() -> StubEmbedder:
    return StubEmbedder(
        {
            "alpha": _basis(0),
            "beta": _basis(1),
            "gamma": _basis(2),
            # Sits between alpha and beta, so neither wins by much. This is the
            # ambiguous case the margin exists for.
            "between": [0.7, 0.7, 0.0, 0.0],
        }
    )


class TestTheIndex:
    def test_a_query_finds_its_exemplar(self, embedder):
        index = SemanticIndex(embedder)
        index.register(Candidate(id="a", namespace="n", exemplars=["alpha"]))

        matches = index.search("alpha", namespace="n")

        assert matches[0].id == "a"
        assert matches[0].score == pytest.approx(1.0)

    def test_the_matching_exemplar_is_reported(self, embedder):
        """Routing has to be legible, and "which phrasing did it match" is the
        evidence. Without it a misroute is only fixable by trial."""
        index = SemanticIndex(embedder)
        index.register(Candidate(id="a", namespace="n", exemplars=["gamma", "alpha"]))

        assert index.search("alpha", namespace="n")[0].exemplar == "alpha"

    def test_candidates_are_scored_by_their_best_exemplar_not_their_average(
        self, embedder
    ):
        """Averaging exemplars blurs the distinctions that make retrieval work:
        a tool described three ways would score badly on all three."""
        index = SemanticIndex(embedder)
        index.register(
            Candidate(id="many", namespace="n", exemplars=["alpha", "beta", "gamma"])
        )

        assert index.search("alpha", namespace="n")[0].score == pytest.approx(1.0)

    def test_namespaces_do_not_leak(self, embedder):
        """Intents and one MCP server's tools must not compete with each other."""
        index = SemanticIndex(embedder)
        index.register(Candidate(id="a", namespace="intent", exemplars=["alpha"]))
        index.register(Candidate(id="b", namespace="tool:x", exemplars=["alpha"]))

        assert [m.id for m in index.search("alpha", namespace="intent")] == ["a"]

    def test_a_namespace_can_be_dropped(self, embedder):
        """The MCP lifecycle: a server disconnects and its tools stop being
        offered immediately. Leaving them would hand a model tools that cannot
        run, which is not an error it can recover from mid-answer."""
        index = SemanticIndex(embedder)
        index.register_all(
            [
                Candidate(id="t1", namespace="tool:x", exemplars=["alpha"]),
                Candidate(id="t2", namespace="tool:x", exemplars=["beta"]),
            ]
        )

        assert index.drop_namespace("tool:x") == 2
        assert index.search("alpha", namespace="tool:x") == []

    def test_re_registering_replaces_by_id(self, embedder):
        """A tool whose description changed between server versions is the same
        tool, not a second one."""
        index = SemanticIndex(embedder)
        index.register(Candidate(id="t", namespace="n", exemplars=["alpha"]))
        index.register(Candidate(id="t", namespace="n", exemplars=["beta"]))

        assert index.namespaces()["n"] == 1
        assert index.search("beta", namespace="n")[0].score == pytest.approx(1.0)

    def test_vectors_are_cached_across_registrations(self, embedder):
        """A reconnecting MCP server re-registers hundreds of unchanged
        descriptions. Re-embedding them all would make reconnection slow enough
        to look broken."""
        index = SemanticIndex(embedder)
        index.register(Candidate(id="a", namespace="n", exemplars=["alpha"]))
        before = embedder.calls
        index.register(Candidate(id="b", namespace="n", exemplars=["alpha"]))

        assert embedder.calls == before

    def test_mixing_dimensions_is_refused(self):
        """Cosine between a 1024-dim bge-m3 vector and a 384-dim hash vector is
        meaningless, not merely weaker — and it would look like a working system
        returning bad answers."""
        embedder = StubEmbedder({"alpha": [1.0, 0.0], "wide": [1.0, 0.0, 0.0, 0.0]})
        index = SemanticIndex(embedder)
        index.register(Candidate(id="a", namespace="n", exemplars=["alpha"]))

        with pytest.raises(DimensionMismatch):
            index.register(Candidate(id="b", namespace="n", exemplars=["wide"]))

    def test_an_empty_query_returns_nothing(self, embedder):
        index = SemanticIndex(embedder)
        index.register(Candidate(id="a", namespace="n", exemplars=["alpha"]))

        assert index.search("   ", namespace="n") == []

    def test_a_candidate_with_no_usable_exemplar_is_skipped_not_fatal(self, embedder):
        index = SemanticIndex(embedder)
        index.register(Candidate(id="empty", namespace="n", exemplars=["", "  "]))

        assert index.namespaces().get("n", 0) == 0


class TestTheRoutingDecision:
    @staticmethod
    def _router(embedder, **kwargs) -> SemanticIntentRouter:
        return SemanticIntentRouter(
            SemanticIndex(embedder),
            exemplars={"document": ["alpha"], "speech": ["beta"], "vision": ["gamma"]},
            **kwargs,
        )

    def test_a_clear_match_routes(self, embedder):
        decision = self._router(embedder).route("alpha")

        assert decision.intent == "document"
        assert decision.semantic

    def test_the_reason_names_the_exemplar(self, embedder):
        """CLAUDE.md: show routing decisions in plain language."""
        decision = self._router(embedder).route("alpha")

        assert "document" in decision.reason
        assert "alpha" in decision.reason

    def test_nothing_close_enough_becomes_conversation(self, embedder):
        """Below the floor, nothing was near anything. An ordinary answer is
        the honest outcome."""
        decision = self._router(embedder).route("unrelated text")

        assert decision.intent == "conversation"
        assert "closely enough" in decision.reason

    def test_two_intents_too_close_to_call_become_conversation(self, embedder):
        """The margin, and the case it exists for. Routing on the top score
        alone produces confident wrong answers on exactly the ambiguous
        phrasings that most need care."""
        decision = self._router(embedder).route("between")

        assert decision.intent == "conversation"
        assert "too close to call" in decision.reason
        assert decision.runner_up is not None

    def test_a_hash_backend_disables_routing_rather_than_randomising_it(self):
        """Hash vectors collide on keyword overlap and carry no semantics.
        Routing on them is arbitrary, not degraded, so the router hands back to
        the keyword classifier instead."""
        embedder = StubEmbedder({"alpha": _basis(0)}, backend="hash")
        router = self._router(embedder)

        assert router.is_semantic() is False
        assert router.route("alpha") is None

    def test_an_empty_prompt_routes_nowhere(self, embedder):
        assert self._router(embedder).route("") is None

    def test_shortlist_applies_no_floor(self, embedder):
        """The other decision rule. Excluding the right tool is the only
        failure that matters, so a marginal extra candidate is kept."""
        index = SemanticIndex(embedder)
        index.register_all(
            [
                Candidate(id="t1", namespace="tool:x", exemplars=["alpha"]),
                Candidate(id="t2", namespace="tool:x", exemplars=["beta"]),
            ]
        )

        assert len(shortlist(index, "alpha", namespace="tool:x", k=5)) == 2


class TestTheShippedExemplars:
    def test_every_intent_maps_to_a_capability(self):
        """An exemplar naming an intent the planner cannot serve would route a
        request into nothing."""
        from core.planner import IntentRouter, IntentType

        for intent in INTENT_EXEMPLARS:
            assert IntentType(intent)
            assert intent in IntentRouter._SEMANTIC_CAPABILITIES

    def test_document_is_covered(self):
        assert "document" in INTENT_EXEMPLARS

    def test_exemplars_are_phrasings_not_category_names(self):
        """An exemplar is a thing a user would type. A list of category names
        measures how close the user came to naming the category, which is a
        different question from what they want."""
        for intent, phrasings in INTENT_EXEMPLARS.items():
            for phrase in phrasings:
                assert phrase.lower() != intent, f"{intent} lists its own name"
                assert " " in phrase.strip(), f"{intent!r} has a one-word exemplar"

    def test_they_register_without_error(self):
        embedder = StubEmbedder({}, dim=4)
        index = SemanticIndex(embedder)
        router = SemanticIntentRouter(index)

        assert index.namespaces()[INTENT_NAMESPACE] == len(INTENT_EXEMPLARS)
        assert router is not None


class TestKeywordFallbackStillWorks:
    def test_no_semantic_router_means_the_old_path(self):
        """Deleting the keywords would turn an Ollama outage into a broken
        product rather than a duller one."""
        from core.planner import IntentRouter, IntentType

        router = IntentRouter()

        assert router.classify("read that out loud").intent_type is IntentType.SPEECH

    def test_a_broken_semantic_router_does_not_fail_the_request(self):
        """Routing must never be the thing that fails a request."""
        from core.planner import IntentRouter

        class Exploding:
            def route(self, prompt):
                raise RuntimeError("index is on fire")

        router = IntentRouter(semantic_router=Exploding())

        assert router.classify("read that out loud") is not None


def _fake_extractor(reply: str):
    """An `ask` that returns fixed JSON, so structured kinds can be tested.

    `DocumentsRuntime` reads an invoice, a spreadsheet or a deck into fields by
    asking a model, and refuses outright when it has no way to ask. That
    refusal is correct and must stay — a `.docx` of prose with `invoice` in the
    filename is worse than no file, because the user believes they have one.

    It also means a runtime built without an extractor cannot make any of the
    three, which is what these tests were silently asserting when they were
    written against the prose fallback. The model is stubbed rather than
    removed: what is under test here is the runtime's routing, not a model's
    reading comprehension, and `tests/test_extraction_across_models.py` is
    where the reading itself is measured.
    """
    return lambda prompt, system: reply


#: Enough of an invoice to build one — two line items and who they are for.
#: Totals are deliberately absent: `total_of` computes them, because a language
#: model producing a subtotal is a language model guessing at multiplication.
INVOICE_JSON = (
    '{"bill_to": ["Northwind Studios"], "currency": "NGN", "terms_days": 30, '
    '"items": [{"description": "Design work", "quantity": 3, '
    '"unit_price": 85000, "unit": "day"}]}'
)

TABLE_JSON = '{"header": ["Item", "Amount"], "rows": [["Design work", "255000"]]}'


class TestTheDocumentsRuntime:
    @pytest.fixture
    def runtime(self, tmp_path):
        from artifacts.records import ArtifactRecords
        from artifacts.service import ArtifactService
        from artifacts.store import ArtifactStore
        from runtimes.documents.runtime import DocumentsRuntime

        service = ArtifactService(
            ArtifactRecords(str(tmp_path / "a.db")), ArtifactStore(tmp_path / "out")
        )
        runtime = DocumentsRuntime(service)
        asyncio.run(runtime.initialize())
        return runtime

    @pytest.fixture
    def invoicing(self, runtime):
        """The same runtime, able to read an answer into invoice fields."""
        runtime.set_extractor(_fake_extractor(INVOICE_JSON))
        return runtime

    @pytest.fixture
    def tabulating(self, runtime):
        runtime.set_extractor(_fake_extractor(TABLE_JSON))
        return runtime

    @staticmethod
    def _run(runtime, data):
        from runtimes.documents.runtime import GENERATE

        return asyncio.run(runtime.execute(GENERATE, data))

    def test_it_writes_the_answer_not_the_request(self, runtime):
        """Generating from the prompt would write up the user's own question.

        Checked against the stored HTML rather than the .docx bytes: a .docx is
        a zip, so a substring search over the file finds nothing either way and
        would pass for the wrong reason. HTML is the source of truth the file
        was rendered from, which is the thing actually worth asserting.
        """
        result = self._run(
            runtime,
            {
                "prompt": "write that up as a proposal",
                "answer": "The terms are 30 days.",
                # Referential prompt, so rule 9 requires the engine to say it
                # resolved the reference. This test is about what gets written,
                # not about the refusal.
                "context_resolved": True,
            },
        )

        assert result["success"]
        stored = runtime._service.records.get(result["artifact"]["id"])
        assert "30 days" in stored.html
        assert "write that up as a proposal" not in stored.html

    def test_the_card_says_whether_the_file_is_there(self, runtime):
        """`exists` was missing here while the /artifacts listing had it, so a
        card for a file written a second earlier said "file not found"."""
        result = self._run(
            runtime,
            {"prompt": "write it up", "answer": "Body.", "context_resolved": True},
        )

        assert result["artifact"]["exists"] is True
        assert result["artifact"]["download_url"].endswith("/download")

    def test_a_referential_request_with_no_resolved_context_is_refused(self, runtime):
        """Rule 9: generation must fail rather than invent.

        This is the Project Phoenix case, reproduced. "Write that up" carries no
        content of its own, so with nothing resolved the model wrote a fluent,
        confident proposal for a client that had never been mentioned. Every
        component was working. A wrong chat reply is corrected next turn; a
        wrong document is sent to a client.
        """
        result = self._run(
            runtime,
            {
                "prompt": "write that up as a proposal",
                "answer": (
                    "Project Phoenix: Optimized Resource Allocation Strategy. This "
                    "proposal outlines a revised strategy designed to maximise "
                    "operational efficiency across the current infrastructure."
                ),
                "context_resolved": False,
            },
        )

        assert not result["success"]
        assert "guessing" in result["error"]

    def test_the_same_request_succeeds_once_context_is_resolved(self, runtime):
        """The refusal must not be a blanket ban on referential phrasing — that
        would break the feature it exists to protect."""
        result = self._run(
            runtime,
            {
                "prompt": "write that up as a proposal",
                "answer": "Northwind pay on 30-day terms and their rate is 85,000.",
                "context_resolved": True,
            },
        )

        assert result["success"]

    def test_a_self_describing_request_needs_no_context(self, invoicing):
        """"Draft an invoice for the Northwind job at 85,000 a day" contains its
        own subject. Refusing it would be the rule misfiring."""
        result = self._run(
            invoicing,
            {
                "prompt": "draft an invoice for the Northwind job at 85,000 a day",
                "answer": "Invoice for Northwind Studios. Day rate 85,000 naira, "
                "payable within 30 days of issue.",
            },
        )

        assert result["success"]

    def test_nothing_to_write_up_is_refused_with_a_reason(self, runtime):
        result = self._run(runtime, {"prompt": "write that up", "answer": ""})

        assert not result["success"]
        assert "Ask the question first" in result["error"]

    def test_a_chart_is_refused_rather_than_quietly_becoming_a_document(self, runtime):
        """A chart is a claim about numbers and this runtime has prose.
        Inventing figures to plot would be worse than refusing; so would
        handing back a document nobody asked for."""
        result = self._run(runtime, {"prompt": "chart the revenue", "answer": "Prose."})

        assert not result["success"]
        assert "needs the figures as data" in result["error"]

    def test_the_requested_kind_picks_the_format(self, tabulating):
        result = self._run(
            tabulating, {"prompt": "make me a spreadsheet", "answer": "Some rows."}
        )

        assert result["artifact"]["filename"].endswith(".xlsx")

    def test_a_structured_kind_refuses_rather_than_writing_prose(self, runtime):
        """No extractor, so no invoice — and no `.docx` pretending to be one.

        This is the defect the structured path was built to end: "make me an
        invoice" produced a document of the model's paragraphs with `invoice`
        in the filename and no table anywhere in it. A prose fallback would
        restore it, so the refusal is asserted rather than merely intended.
        """
        result = self._run(
            runtime,
            {"prompt": "draft an invoice for the Northwind job", "answer": "Some prose."},
        )

        assert not result["success"]
        assert "artifact" not in result
        assert "an invoice" in result["error"]

    def test_markdown_does_not_reach_the_document(self, runtime):
        """The model reaches for `**bold**` by habit. Left alone those are
        literal asterisks in a file the user sends a client."""
        from runtimes.documents.runtime import _plain

        assert _plain("**Bold heading**") == "Bold heading"
        assert _plain("## Heading") == "Heading"

    def test_the_title_is_not_printed_twice(self, runtime):
        """The title comes from the answer's first line and is rendered as the
        h1, so keeping it in the body prints it twice — and a model that
        repeats its own heading printed it three times."""
        from runtimes.documents.runtime import _blocks, _title_from

        body = "**A Proposal**\nOpening sentence.\n\nSecond paragraph."
        title = _title_from("write it up", body)

        blocks = _blocks(body, [], title)

        assert title == "A Proposal"
        assert not any(str(b).strip().lower() == title.lower() for b in blocks)
        assert any("Opening sentence." in str(b) for b in blocks)

    def test_claims_survive_into_the_artifact(self, runtime):
        result = self._run(
            runtime,
            {
                "prompt": "write it up",
                "answer": "Northwind pay on 30-day terms.",
                "context_resolved": True,
                "claims": [
                    {
                        "id": "c1",
                        "source_id": "memory:55b6",
                        "excerpt": "Northwind pay on 30-day terms.",
                        "source_excerpt": "Clause 4.2.",
                    }
                ],
            },
        )

        assert len(result["artifact"]["claims"]) == 1

    def test_an_unknown_capability_is_refused(self, runtime):
        assert not asyncio.run(runtime.execute("document.destroy", {}))["success"]

    def test_health_reports_which_formats_work_here(self, runtime):
        """Disabled capabilities are visible, not silent."""
        health = asyncio.run(runtime.health_check())

        assert health["formats"]["docx"]["available"] is True
        assert "pdf" in health["formats"]
