"""A cosine between two embedders is a number with no meaning.

The embedder is a setting. Settings writes `router_model`, the bootstrapper
hands it to the memory runtime, and every vector already in the Spine was made
by whatever was chosen before. Nothing recorded which — so changing the model
left old vectors in one space and new queries in another, and `cosine` does not
fail on that. It returns a plausible figure, and the figure decides what the
model is allowed to see.

That is this codebase's oldest error wearing new clothes: *a score built for
one question answering another*, which `CLAUDE.md` records costing three
separate bugs before this one. The difference here is that it arrives through a
field in Settings rather than through a ranking formula.

So: every vector carries its maker, a vector from another maker is not in the
running at all, and the Spine repairs itself rather than asking.
"""

from __future__ import annotations

import asyncio

import pytest

from runtimes.memory.contracts import MemoryRecord, MemoryType
from runtimes.memory.embeddings import EmbeddingService
from runtimes.memory.index import VectorMemoryIndex
from runtimes.memory.runtime import MemoryRuntimeImpl

BGE = "ollama:bge-m3:1024"
OTHER = "ollama:embeddinggemma:768"


def record(rid: str, *, dim: int = 1024, stamp: str | None = BGE) -> MemoryRecord:
    return MemoryRecord(
        id=rid, content=rid, embedding=[0.1] * dim, embedded_by=stamp
    )


class TestTheIndexHoldsOneSpace:
    @staticmethod
    def rebuilt(*records) -> VectorMemoryIndex:
        index = VectorMemoryIndex(embedding_dim=1024, signature=BGE)
        asyncio.run(index.rebuild(list(records)))
        return index

    def test_a_vector_from_this_embedder_is_indexed(self):
        index = self.rebuilt(record("mine"))

        assert asyncio.run(index.health_check())["indexed_vectors"] == 1

    def test_a_vector_from_another_embedder_is_not(self):
        index = self.rebuilt(record("theirs", dim=768, stamp=OTHER))
        health = asyncio.run(index.health_check())

        assert health["indexed_vectors"] == 0
        assert health["vectors_from_another_embedder"] == 1

    def test_the_same_width_from_another_embedder_is_still_refused(self):
        """The dangerous case, and the reason a width check is not enough.

        Two 1024-dimension models produce vectors of the same shape and no
        relationship. Nothing raises, every comparison returns a number, and
        the recall that results is confidently wrong.
        """
        index = self.rebuilt(record("lookalike", dim=1024, stamp="ollama:mxbai:1024"))

        assert asyncio.run(index.health_check())["indexed_vectors"] == 0

    def test_a_fact_from_before_any_of_this_is_kept(self):
        """Every Spine on earth is in this state at upgrade.

        Refusing unstamped vectors would be correct and would empty the vector
        index of every existing install, which is a worse answer than a weak
        assumption that repairs itself on the next pass.
        """
        index = self.rebuilt(record("legacy", stamp=None))

        assert asyncio.run(index.health_check())["indexed_vectors"] == 1

    def test_an_unstamped_vector_of_the_wrong_width_is_not_kept(self):
        index = self.rebuilt(record("legacy-768", dim=768, stamp=None))

        assert asyncio.run(index.health_check())["indexed_vectors"] == 0

    def test_an_index_with_no_embedder_named_holds_anything(self):
        # What a test constructing this bare expects, and what the product
        # never does.
        index = VectorMemoryIndex(embedding_dim=1024)
        asyncio.run(index.rebuild([record("a"), record("b", dim=768, stamp=OTHER)]))

        assert asyncio.run(index.health_check())["indexed_vectors"] == 2


class TestTheSignature:
    def test_it_names_backend_model_and_width(self):
        service = EmbeddingService(backend="ollama", dim=1024, ollama_model="bge-m3")

        assert service.signature() == BGE

    def test_the_fallback_names_no_model(self):
        # It is not a model. Calling it one would suggest its vectors are worth
        # comparing against a real embedder's.
        assert EmbeddingService(backend="hash", dim=384).signature() == "hash:384"

    def test_the_model_decides_the_width_not_the_configuration(self, monkeypatch):
        """It used to zero-pad to whatever was configured.

        Half a vector of zeros nobody computed, compared by cosine against
        real ones — the `AdapterRAM` failure in another module: a confident
        wrong number where the honest move is to take the measurement.
        """
        import json
        import urllib.request

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return json.dumps({"embedding": [0.5] * 768}).encode()

        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Response())
        service = EmbeddingService(backend="ollama", dim=1024, ollama_model="small")

        vector = service._embed_ollama("anything")

        assert len(vector) == 768, "the vector was padded to the configured width"
        assert service.get_dim() == 768
        assert service.signature() == "ollama:small:768"


class _Embedder:
    """An embedder that answers without a model behind it."""

    _backend = "ollama"

    def __init__(self, signature: str, dim: int = 8):
        self._signature = signature
        self._dim = dim
        self.calls = 0

    def signature(self) -> str:
        return self._signature

    def get_dim(self) -> int:
        return self._dim

    def embed(self, text: str):
        self.calls += 1
        return [0.2] * self._dim

    def health_check(self):
        return {"status": "healthy"}


class TestTheSpineRepairsItself:
    @staticmethod
    def runtime() -> MemoryRuntimeImpl:
        runtime = MemoryRuntimeImpl(store_type="memory", embedding_dim=8)
        asyncio.run(runtime.initialize())
        return runtime

    def test_a_stored_fact_records_who_embedded_it(self):
        runtime = self.runtime()
        rid = asyncio.run(
            runtime.store("the rate is 700 a day", MemoryType.SEMANTIC)
        )

        stored = asyncio.run(runtime._store.get(rid))
        assert stored.embedded_by == "hash:8"

    def test_the_repair_never_runs_on_the_fallback_embedder(self):
        # Stamping hash vectors as though a model made them would make the
        # mismatch undetectable, which is worse than the mismatch.
        runtime = self.runtime()
        asyncio.run(runtime.store("a fact", MemoryType.SEMANTIC))

        assert asyncio.run(runtime.reembed_stale()) == 0

    def test_a_fact_from_another_embedder_is_embedded_again(self):
        runtime = self.runtime()
        runtime._embedder = _Embedder("ollama:new:8")
        asyncio.run(runtime._store.put(record("old", dim=8, stamp="ollama:old:8")))

        assert asyncio.run(runtime.reembed_stale()) == 1
        assert asyncio.run(runtime._store.get("old")).embedded_by == "ollama:new:8"
        assert runtime._embedder.calls == 1

    def test_an_unstamped_fact_of_the_right_width_is_stamped_not_recomputed(self):
        """The cheap half, and it is most of a first upgrade.

        The index already accepts these, so a model call would buy a stamp and
        nothing else — several thousand of them, on a machine that is also
        answering questions.
        """
        runtime = self.runtime()
        runtime._embedder = _Embedder("ollama:new:8")
        asyncio.run(runtime._store.put(record("legacy", dim=8, stamp=None)))

        assert asyncio.run(runtime.reembed_stale()) == 1
        assert asyncio.run(runtime._store.get("legacy")).embedded_by == "ollama:new:8"
        assert runtime._embedder.calls == 0, "it paid for a vector it already had"

    def test_a_repaired_fact_is_searchable_again(self):
        runtime = self.runtime()
        runtime._embedder = _Embedder("ollama:new:8")
        asyncio.run(runtime._store.put(record("old", dim=8, stamp="ollama:old:8")))
        runtime._index._vector_index._signature = "ollama:new:8"

        asyncio.run(runtime.reembed_stale())
        health = asyncio.run(runtime._index._vector_index.health_check())

        assert health["indexed_vectors"] == 1


@pytest.mark.parametrize("stamp", [None, BGE])
def test_a_record_round_trips_through_sqlite_with_its_stamp(tmp_path, stamp):
    from runtimes.memory.store import SQLiteMemoryStore

    store = SQLiteMemoryStore(db_path=str(tmp_path / "spine.db"))
    asyncio.run(store.put(record("r", stamp=stamp)))

    assert asyncio.run(store.get("r")).embedded_by == stamp
