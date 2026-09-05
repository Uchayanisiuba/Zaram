"""One Spine, whichever model answers.

This is the product's central claim and it had no test. `CLAUDE.md`'s current
milestone states it as a demonstration — *"ask model A something, ask model B
about it later, get a cited answer, delete the fact, watch the answer change"* —
and the pieces were each covered separately: `test_provenance_invariant.py`
proves recall reaches *the* model, `test_memory_supersession.py` proves a
corrected fact stops being recalled, `test_engine_routing.py` proves a model
name reaches the right engine. Nothing asserted the property that joins them,
which is the one a user would call *memory*: **a fact learned while one
provider was answering is recalled when a different provider answers.**

Two providers here rather than two model names, because the interesting failure
is not a string. `RoutedEngine` sends local and cloud to different objects, and
recall lives in `system_prompt`, which each engine then handles in its own code
— `OllamaEngine` puts it in a `system` field, `OpenAICompatibleEngine` builds a
message array. A regression that dropped it on one side would leave the other
green.

**Where the boundary of the claim actually is**, asserted below rather than
described:

* The stored fact carries no provider or model identity, and recall does not
  filter on session — so nothing about the second turn can make it unreachable.
* What is remembered is **what the user said**, never what a model answered
  (rule 7d, and `_remember`'s own docstring on why). Model B inherits model A's
  *input*, not its output.
* Correction propagates across providers too, or rule 4 would hold only for
  whichever model happened to be selected when the user fixed something.

The real thing was run as well — two live models on this machine, TabbyAPI and
Ollama, recorded in `docs/MILESTONES.md`. A double cannot tell you that a 27B
model reads the recall block and answers from it; it can tell you the block
arrives, which is the half that regresses silently.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from core.contracts import Capability, RuntimeMetadata, RuntimeState
from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.registry import RuntimeRegistry
from core.streaming_events import EventType, StreamEvent
from runtimes.memory import create_memory_runtime
from runtimes.models.engines.routed_engine import RoutedEngine
from runtimes.models.models_service import ModelsService

#: The names are arbitrary; the locality is not. `RoutedEngine` asks
#: `is_remote`, never the string, so these could be swapped without moving the
#: behaviour they select.
CLOUD_MODEL = "a-cloud-model"
LOCAL_MODEL = "a-local-model"

FACT = "My day rate for Harbour Lane is 425,000 naira and they pay 30 days late."
QUESTION = "What is my day rate for Harbour Lane?"
UNRELATED = "who won the 2026 world cup"

#: The relevance floor this fixture runs at, and it is **not** the shipped one.
#:
#: `MIN_RECALL_SCORE` is 0.42, measured against bge-m3, and its own comment says
#: the number is not transferable between embedding models — which is why the
#: backend can override it. This fixture embeds with the `hash` backend so the
#: suite does not need Ollama, and that backend's numbers live elsewhere.
#:
#: **Measured on the quantity that is actually thresholded**, which is
#: `MemoryResult.relevance` out of the hybrid retriever — not the embedding
#: cosine. The first version of this comment quoted the cosine (+0.064 for the
#: matching question) and was the "score built for ranking is not a score for
#: deciding" mistake in miniature: under the hash backend the cosine carries
#: almost nothing and `_keyword_match` carries the retrieval.
#:
#:     FACT, asked by QUESTION     relevance 0.40
#:     FACT, asked by UNRELATED    no candidate returned at all
#:
#: So 0.35 — under the one and above nothing, and close enough to the shipped
#: 0.42 to be recognisable as the same kind of number.
#: `test_an_unrelated_question_recalls_nothing` is what holds this honest;
#: without it the file could pass against a fixture that admitted everything.
#:
#: What this file claims is that a fact crosses from one provider to another.
#: What the floor should be is a different question, owned by
#: `test_recall_relevance.py` and `test_recall_at_scale.py` against the real
#: embedder. Do not read either number here as evidence about the other.
HASH_EMBEDDER_FLOOR = 0.35


class RecordingEngine:
    """An `LLMEngine` that answers nothing and remembers how it was asked."""

    def __init__(self, name: str) -> None:
        self.name = name
        #: (prompt, system_prompt, model) per call, in order.
        self.calls: list[tuple[str, str, str | None]] = []
        self.default_model: str | None = None

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        images: list[str] | None = None,
    ) -> Iterator[str]:
        self.calls.append((prompt, system_prompt, model))
        yield f"answered by {self.name}"

    @property
    def last_system_prompt(self) -> str:
        assert self.calls, f"{self.name} was never called"
        return self.calls[-1][1]


class _ModelsRuntime:
    """Wraps a real `ModelsService` so the registry can resolve it."""

    def __init__(self, service: ModelsService) -> None:
        self._service = service

    def get_runtime_id(self):
        return "models"

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id="models",
            version="1.0.0",
            capabilities=[Capability(id="reasoning.generate", runtime_id="models")],
        )

    def get_service(self):
        return self._service

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def get_state(self):
        return RuntimeState.READY

    def health_check(self):
        return {"state": "ready"}


class TwoProviders:
    """The engine under test, with a real Spine and two distinct providers."""

    def __init__(self) -> None:
        self.local = RecordingEngine("local")
        self.cloud = RecordingEngine("cloud")
        routed = RoutedEngine(
            local=self.local,
            cloud=self.cloud,
            is_remote=lambda model: model == CLOUD_MODEL,
        )
        registry = RuntimeRegistry(EventBus())
        registry.register(_ModelsRuntime(ModelsService(routed)))
        # A real memory runtime, not a double: capture, embedding, retrieval
        # and the relevance floor are what this test is about, and a fake
        # returning fixed records would assert the wiring while skipping the
        # thing being claimed.
        self.memory = create_memory_runtime(
            store_type="memory",
            index_type="hybrid",
            embedding_dim=128,
            embedding_backend="hash",
        )
        asyncio.run(self.memory.initialize())
        registry.register(self.memory)
        self.engine = ExecutionEngine(registry, EventBus())
        # See HASH_EMBEDDER_FLOOR: the shipped floors are calibrated for bge-m3
        # and mean nothing against a hash embedder. Set on the instance so the
        # class attribute — the shipped value — is left alone for every other
        # test in the run.
        self.engine.MIN_RECALL_SCORE = HASH_EMBEDDER_FLOOR
        self.engine.MIN_CITATION_SCORE = HASH_EMBEDDER_FLOOR

    def ask(self, prompt: str, model: str, session_id: str) -> list[StreamEvent]:
        """Run one turn and return the source events it emitted."""
        sources: list[StreamEvent] = []
        for item in self.engine.execute(prompt, model, "", session_id):
            if isinstance(item, StreamEvent) and item.type == EventType.SOURCE:
                sources.append(item)
        return sources

    def stored(self) -> list:
        return asyncio.run(self.memory._store.all_records())


@pytest.fixture
def zaram() -> TwoProviders:
    return TwoProviders()


class TestTheFactCrossesTheProvider:
    def test_told_to_the_local_model_recalled_by_the_cloud_one(self, zaram):
        """The claim, in the direction that costs the most.

        Local to cloud is the expensive direction: the recalled fact leaves the
        machine, which is why `OpenAICompatibleEngine` hands the whole body to
        the egress gate rather than owning a client. It is also the direction a
        user means when they say the memory is theirs rather than a provider's.
        """
        zaram.ask(FACT, LOCAL_MODEL, session_id="first")
        assert not zaram.cloud.calls, "the cloud provider answered the first turn"

        zaram.ask(QUESTION, CLOUD_MODEL, session_id="second")

        assert "425,000 naira" in zaram.cloud.last_system_prompt, (
            "a fact stated while the local model answered did not reach the "
            "cloud model — the Spine is not shared across providers"
        )

    def test_told_to_the_cloud_model_recalled_by_the_local_one(self, zaram):
        """And back the other way, which is the one users notice.

        Asserted separately rather than parametrised: the two directions run
        through different engine code, so a symmetrical test could only catch a
        failure common to both.
        """
        zaram.ask(FACT, CLOUD_MODEL, session_id="first")
        zaram.ask(QUESTION, LOCAL_MODEL, session_id="second")

        assert "425,000 naira" in zaram.local.last_system_prompt

    def test_the_second_provider_is_the_one_that_answers(self, zaram):
        """Recall must not quietly re-route the question to the first model."""
        zaram.ask(FACT, LOCAL_MODEL, session_id="first")
        before = len(zaram.local.calls)

        zaram.ask(QUESTION, CLOUD_MODEL, session_id="second")

        assert len(zaram.local.calls) == before, (
            "the local engine was called for a cloud model's turn"
        )
        assert zaram.cloud.calls[-1][2] == CLOUD_MODEL

    def test_the_same_record_is_cited_to_both(self, zaram):
        """One fact, one id, two providers — not two copies that agree today.

        Rule 2 is the half that makes the memory checkable: the user can open
        the citation and see the fact, whichever model the answer came from.
        """
        zaram.ask(FACT, LOCAL_MODEL, session_id="first")

        to_cloud = zaram.ask(QUESTION, CLOUD_MODEL, session_id="second")
        to_local = zaram.ask(QUESTION, LOCAL_MODEL, session_id="third")

        def cited(sources):
            return {s.data.get("url") for s in sources if s.data.get("cited")}

        assert cited(to_cloud), "the cloud turn cited nothing"
        assert cited(to_cloud) == cited(to_local)

    def test_an_unrelated_question_recalls_nothing(self, zaram):
        """The fixture's own honesty check — see `HASH_EMBEDDER_FLOOR`.

        Without this, every assertion above would still pass against a floor
        low enough to admit anything at all, and the file would be measuring
        nothing but its own permissiveness.
        """
        zaram.ask(FACT, LOCAL_MODEL, session_id="first")

        sources = zaram.ask(UNRELATED, CLOUD_MODEL, session_id="second")

        assert sources == []
        assert "425,000 naira" not in zaram.cloud.last_system_prompt

    def test_a_new_session_does_not_lose_the_fact(self, zaram):
        """Session state and the Spine are separate stores (rule 7d).

        Every turn in this file uses a different session id deliberately, so
        what carries the fact across is the Spine rather than a conversation
        buffer that happens to still be alive in this process.

        **What this does not guard**, checked by breaking it rather than
        assumed: changing `_recall`'s `session_id=None` to pass the session
        through leaves all ten tests green, because session membership is a
        *ranking* signal in `MemoryRankerImpl` and never a filter. So this
        asserts the outcome — the fact survives a new session — and not the
        argument that currently produces it.
        """
        zaram.ask(FACT, LOCAL_MODEL, session_id="one")
        sources = zaram.ask(
            QUESTION, CLOUD_MODEL, session_id="a-completely-different-session"
        )

        assert sources, "nothing was recalled once the session changed"


class TestWhatIsRememberedIsTheUsersWordsNotTheModelsAnswer:
    def test_the_answer_is_not_stored_as_a_fact(self, zaram):
        """Rule 7d, and the boundary of the cross-model claim.

        Model B inherits what the *user* told model A. It does not inherit what
        model A said back — `_remember` stores the prompt precisely so Zaram
        stops quoting its own replies as sources.
        """
        zaram.ask(FACT, LOCAL_MODEL, session_id="first")

        contents = [r.content for r in zaram.stored()]
        assert any("425,000 naira" in c for c in contents)
        assert not any("answered by local" in c for c in contents)

    def test_the_record_names_no_provider(self, zaram):
        """Nothing in a stored fact says which model was answering.

        This is what makes the property structural rather than incidental: a
        record carrying a model invites a filter, and a filter is how memory
        would come to belong to a provider.
        """
        zaram.ask(FACT, LOCAL_MODEL, session_id="first")
        record = next(r for r in zaram.stored() if "425,000 naira" in r.content)

        assert not hasattr(record, "model")
        assert LOCAL_MODEL not in str(record.metadata)
        assert LOCAL_MODEL not in str(record.tags)


class TestCorrectionCrossesTheProviderToo:
    def test_a_deleted_fact_stops_reaching_the_other_model(self, zaram):
        """Rule 4 across providers: the answer changes for whoever answers.

        A correction loop holding only for the model selected when the user
        made it would be worse than none, because the fact would come back
        under a different name.
        """
        zaram.ask(FACT, LOCAL_MODEL, session_id="first")
        record = next(r for r in zaram.stored() if "425,000 naira" in r.content)

        assert asyncio.run(zaram.memory.forget(record.id)) is True

        sources = zaram.ask(QUESTION, CLOUD_MODEL, session_id="second")

        assert "425,000 naira" not in zaram.cloud.last_system_prompt
        assert sources == []

    def test_a_corrected_fact_reaches_the_other_model_in_its_new_form(self, zaram):
        """Supersession, seen from the far side of a model switch."""
        zaram.ask(FACT, LOCAL_MODEL, session_id="first")
        record = next(r for r in zaram.stored() if "425,000 naira" in r.content)

        asyncio.run(zaram.memory.correct(
            record.id,
            "My day rate for Harbour Lane is 600,000 naira and they pay 30 days late.",
        ))

        zaram.ask(QUESTION, CLOUD_MODEL, session_id="second")
        prompt = zaram.cloud.last_system_prompt

        assert "600,000 naira" in prompt
        assert "425,000 naira" not in prompt, (
            "the superseded figure was still recalled — the user corrected it "
            "under one model and the other kept the old answer"
        )
