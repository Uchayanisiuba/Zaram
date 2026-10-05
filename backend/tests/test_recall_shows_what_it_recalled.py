"""*Recalled 6 facts* — which six, and why so often six.

Asked 5 October 2026: *"Zaram keeps saying recalling 6 facts — is it really
recalling, why is it always six, are they relevant, why can't the user expand
and see them?"*

Measured the same day on the maintainer's Spine (428 facts) for *"Create a 3d
Minecraft game that can run on my browser"*: 27 facts cleared the 0.42 floor,
so the cap of 6 decided; the top match (0.53) was an unrelated line from a
Ride Share conversation; and **three of the six slots were the identical
ping-pong code Zaram had written earlier**. Six is `MAX_RECALL`, and on a real
corpus the floor admits enough that the cap is what usually binds.

Two things are fixed here and one is not:

* the row says *which* facts, with the similarity they were chosen on and
  where each came from, so the number can be checked;
* a fact stored several times takes one slot, not three.

**Not fixed: the floor.** 0.42 was calibrated on a small corpus where
unrelated questions scored at most 0.362; on the real Spine short
conversational lines score ~0.5 against almost anything. Moving it is a
measurement job against `test_recall_at_scale.py` and the eval, not an edit.
"""

from __future__ import annotations

from core.execution_engine import ExecutionEngine, _recall_listing
from runtimes.memory.contracts import MemoryResult


class _Record:
    def __init__(self, content: str, origin: str = "conversation") -> None:
        self.content = content
        self.origin = origin


def _result(content: str, relevance: float, origin: str = "conversation") -> MemoryResult:
    return MemoryResult(record=_Record(content, origin), score=0.9, relevance=relevance)  # type: ignore[arg-type]


class _Gate:
    def should_recall(self, prompt: str) -> bool:
        return True


class _Memory:
    def __init__(self, results):
        self._results = results

    async def retrieve(self, **_):
        return list(self._results)


def _engine(results) -> ExecutionEngine:
    engine = ExecutionEngine.__new__(ExecutionEngine)
    engine._memory_runtime = lambda: _Memory(results)  # type: ignore[method-assign]
    engine._recall_gate = lambda runtime: _Gate()  # type: ignore[method-assign]
    engine._publish = lambda *a, **k: None  # type: ignore[method-assign]
    return engine


class TestADuplicateTakesOneSlot:
    def test_three_copies_of_one_fact_are_one(self):
        ping = "Code Zaram wrote for: Create a ping pong game using HTML <!DOCTYPE html>"
        results = [
            _result(ping, 0.519, "generated"),
            _result(ping, 0.519, "generated"),
            _result(ping.replace(" ", "  "), 0.519, "generated"),
            *[_result(f"fact {i}", 0.50 - i / 100) for i in range(8)],
        ]

        kept = _engine(results)._recall("make a browser game", "s1")

        contents = [r.record.content for r in kept]
        assert len(kept) == ExecutionEngine.MAX_RECALL
        assert sum(1 for c in contents if "ping pong" in c) == 1
        # The slots freed went to the next most relevant, in order.
        assert contents[1:] == [f"fact {i}" for i in range(5)]

    def test_the_floor_still_applies_first(self):
        kept = _engine([_result("near", 0.6), _result("far", 0.2)])._recall("q", "s1")
        assert [r.record.content for r in kept] == ["near"]


class TestTheRowSaysWhichFacts:
    def test_each_fact_with_its_similarity_and_origin(self):
        text = _recall_listing([
            _result("The launch is 9 September in Bristol.", 0.527),
            _result("Invoice terms: 30 days.", 0.48, "user_document"),
            _result("Code Zaram wrote for: tetris", 0.51, "generated"),
        ])
        assert text.splitlines() == [
            "0.53  a conversation · The launch is 9 September in Bristol.",
            "0.48  your document · Invoice terms: 30 days.",
            "0.51  Zaram wrote it · Code Zaram wrote for: tetris",
        ]

    def test_a_long_fact_is_cut_and_a_multiline_one_is_one_line(self):
        line = _recall_listing([_result("word " * 100 + "\nsecond line", 0.5)])
        assert "\n" not in line
        assert line.endswith("…")
        assert len(line) < 140
