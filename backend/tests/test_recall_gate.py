"""The recall gate's behaviour, without a model.

The measurement that justifies the gate lives in
``test_conversational_turns_do_not_recall.py`` and needs a live bge-m3. These
tests need nothing: they drive ``RecallGate`` with a fake embedder so the
*logic* — especially every path that must fail open — is asserted offline and
deterministically.

The split matters. A gate whose only test requires Ollama is a gate that goes
unchecked on every machine that does not have it, which is most of them.
"""

from __future__ import annotations

import math

import pytest

from core.recall_gate import RecallGate, gate_from_memory_runtime


def _unit(*values: float) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


#: A two-dimensional embedding space: axis 0 is "social", axis 1 is "task".
#: Enough to exercise every branch, and small enough to read.
SOCIAL_VECTOR = _unit(1.0, 0.0)
TASK_VECTOR = _unit(0.0, 1.0)
MIDPOINT = _unit(1.0, 1.0)


class _FakeEmbedder:
    """Maps known strings to fixed vectors and counts calls."""

    def __init__(self, mapping: dict[str, list[float]], default: list[float] | None = None):
        self._mapping = mapping
        self._default = default if default is not None else MIDPOINT
        self.calls = 0
        self.degraded = False

    def __call__(self, text: str) -> list[float]:
        self.calls += 1
        return self._mapping.get(text, self._default)


def _gate(embed, **kwargs) -> RecallGate:
    return RecallGate(
        embed=embed,
        social_exemplars=("hello there",),
        task_exemplars=("what did I agree",),
        **kwargs,
    )


def _embedder_for(query_vector: list[float]) -> _FakeEmbedder:
    return _FakeEmbedder(
        {
            "hello there": SOCIAL_VECTOR,
            "what did I agree": TASK_VECTOR,
        },
        default=query_vector,
    )


class TestTheDecision:
    def test_a_social_turn_does_not_recall(self):
        gate = _gate(_embedder_for(SOCIAL_VECTOR))
        assert gate.should_recall("Hi") is False

    def test_a_task_turn_recalls(self):
        gate = _gate(_embedder_for(TASK_VECTOR))
        assert gate.should_recall("what did I quote them") is True

    def test_a_turn_on_the_fence_recalls(self):
        """Equidistant is not social.

        The margin has to be *cleared*, not merely won. This is the case that
        rejected a bare argmax: "who won the 2026 world cup" measured +0.025
        toward social, and a rule that acts on any positive margin would have
        started suppressing recall on the strength of noise.
        """
        gate = _gate(_embedder_for(MIDPOINT))
        assert gate.should_recall("who won the 2026 world cup") is True

    def test_a_long_turn_always_recalls(self):
        """Length overrides the exemplars, deliberately.

        A paragraph carries enough content to be about something, and every
        exemplar is short — so a long input is the case they describe worst. The
        embedder is rigged to call it social; length must win anyway.
        """
        gate = _gate(_embedder_for(SOCIAL_VECTOR), max_social_chars=20)
        assert gate.should_recall("hello " * 20) is True

    def test_an_empty_turn_does_not_recall(self):
        gate = _gate(_embedder_for(SOCIAL_VECTOR))
        assert gate.should_recall("   ") is False


class TestItFailsOpen:
    """Every path that cannot measure must still recall.

    Not symmetric failures: recalling on a greeting costs milliseconds and a
    line of UI, while suppressing recall on a real question is a silently wrong
    answer with no way for the user to know it happened.
    """

    def test_no_embedder_recalls(self):
        assert RecallGate(embed=None).should_recall("Hi") is True

    def test_an_embedder_that_raises_recalls(self):
        def boom(_text: str):
            raise RuntimeError("ollama is down")

        assert _gate(boom).should_recall("Hi") is True

    def test_a_degraded_embedder_recalls(self):
        """Hash-fallback embeddings must not be allowed to suppress anything.

        `EmbeddingService` silently falls back to hashing when Ollama is
        unreachable — right for the product, since keyword recall keeps working,
        and fatal here: the margin would be computed from a different model and
        would still look like a number.
        """
        embedder = _embedder_for(SOCIAL_VECTOR)
        gate = _gate(embedder, is_degraded=lambda: True)
        assert gate.should_recall("Hi") is True

    def test_a_zero_vector_recalls(self):
        gate = _gate(_embedder_for([0.0, 0.0]))
        assert gate.should_recall("Hi") is True

    def test_an_unknown_margin_is_none_not_zero(self):
        """`None` and `0.0` mean different things and only one may gate.

        Zero is "measured, and balanced". None is "no trustworthy measurement".
        Collapsing them is how a fail-open turns into a fail-closed later.
        """
        assert RecallGate(embed=None).social_margin("Hi") is None
        assert _gate(_embedder_for(MIDPOINT)).social_margin("Hi") == pytest.approx(0.0)


class TestItIsCheap:
    def test_exemplars_are_embedded_once(self):
        """Steady state is one embedding per turn, not nine.

        The exemplars are fixed, so re-embedding them per turn would multiply
        the gate's cost by the number of exemplars — turning a 10-30ms check
        into something worth arguing about.
        """
        embedder = _embedder_for(TASK_VECTOR)
        gate = _gate(embedder)

        gate.should_recall("first question about my rates")
        after_first = embedder.calls
        gate.should_recall("second question about my rates")

        # Two exemplars plus one query on the first call; one query after.
        assert after_first == 3
        assert embedder.calls - after_first == 1


class TestBuildingItFromTheRuntime:
    def test_a_runtime_without_an_embedder_recalls_everything(self):
        """The behaviour that shipped before this file existed.

        A gate that cannot measure is not an error state — it is the old
        product, which is the correct thing to degrade to.
        """
        class _Bare:
            pass

        assert gate_from_memory_runtime(_Bare()).should_recall("Hi") is True

    def test_it_reuses_the_runtime_s_own_embedder(self):
        """Rather than constructing a second one.

        Two embedders can disagree about what an embedding is — different
        model, different dimension, different degraded state — and a gate
        disagreeing with recall about that would be invisible.
        """
        class _Service:
            def __init__(self):
                self._degraded = False
                self.seen: list[str] = []

            def embed(self, text: str):
                self.seen.append(text)
                return SOCIAL_VECTOR if "hello" in text or text == "Hi" else TASK_VECTOR

        class _Runtime:
            def __init__(self, service):
                self._embedding_service = service

        service = _Service()
        gate = gate_from_memory_runtime(_Runtime(service))
        gate.should_recall("Hi")

        assert service.seen, "the gate did not use the runtime's embedder"

    def test_it_finds_the_real_memory_runtime_s_embedder(self):
        """Against the real class, not a fake with an invented attribute.

        **This is the test that was missing, and its absence shipped an inert
        gate.** Every other test here builds a stand-in exposing
        `_embedding_service`; `MemoryRuntime` calls it `_embedder`. So the probe
        found nothing, the gate failed open on every turn, `Hi` kept recalling
        three documents — and fourteen unit tests passed, because the fixtures
        asserted the spelling the code was looking for rather than the one that
        exists.

        A hash backend is enough: this asserts *wiring*, not similarity, and
        needs no Ollama.
        """
        from runtimes.memory.runtime import create_memory_runtime

        runtime = create_memory_runtime(
            store_type="memory", index_type="simple", embedding_dim=8
        )
        gate = gate_from_memory_runtime(runtime)

        assert gate._embed is not None, (
            "the gate could not find MemoryRuntime's embedder, so it will fail "
            "open on every turn and silently do nothing"
        )
        # And it is genuinely callable, not merely present.
        assert gate.social_margin("Hi") is not None

    def test_a_degraded_runtime_embedder_is_honoured(self):
        class _Service:
            _degraded = True

            def embed(self, text: str):
                return SOCIAL_VECTOR

        class _Runtime:
            def __init__(self):
                self._embedding_service = _Service()

        assert gate_from_memory_runtime(_Runtime()).should_recall("Hi") is True
