"""An unrelated question must not cite the Spine.

Rule 2 says every recalled fact carries provenance. The converse matters just as
much and had no test: a citation the answer did not use is a false claim of
provenance. Zaram was doing exactly that — "who won the 2026 world cup" came back
with two citations about a launch rehearsal in Bristol, because the recall
threshold sat below the score every memory scores against every query.

The damage is not cosmetic. Citations are the product's central claim, and a
user who sees two irrelevant ones attached to a confident wrong answer learns
that the citations mean nothing. After that the real ones cannot help.

These tests use recorded bge-m3 scores rather than calling Ollama, so they run
offline and deterministically. The recorded values are in the docstring of
``ExecutionEngine.MIN_RECALL_SCORE``; re-measure with
``scratchpad/score_probe.py`` if the embedding model changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.execution_engine import ExecutionEngine


@dataclass
class _Result:
    """Shaped like MemoryResult, which is all the filter looks at."""

    score: float
    content: str = "a fact"


# Measured with bge-m3 against a Spine holding two launch-related facts.
RELATED_SCORES = [0.546, 0.515, 0.491, 0.436]
UNRELATED_SCORES = [0.362, 0.355, 0.339, 0.332, 0.329, 0.327, 0.321, 0.317]


class TestRelevanceThreshold:
    def test_threshold_separates_the_measured_populations(self):
        """The single assertion the fix rests on."""
        assert max(UNRELATED_SCORES) < ExecutionEngine.MIN_RECALL_SCORE, (
            f"unrelated questions score up to {max(UNRELATED_SCORES)}, which is "
            f"at or above the threshold of {ExecutionEngine.MIN_RECALL_SCORE} — "
            "they will be recalled and cited"
        )
        assert min(RELATED_SCORES) >= ExecutionEngine.MIN_RECALL_SCORE, (
            f"genuinely related questions score as low as {min(RELATED_SCORES)}, "
            f"below the threshold of {ExecutionEngine.MIN_RECALL_SCORE} — real "
            "recall will be dropped"
        )

    def test_the_old_threshold_would_fail_this(self):
        """Documents the regression rather than only preventing it.

        0.25 was the value that shipped. Every unrelated score clears it, which
        is why every question cited every memory.
        """
        assert all(s > 0.25 for s in UNRELATED_SCORES)

    def test_filter_drops_unrelated_and_keeps_related(self):
        results = [_Result(s) for s in RELATED_SCORES + UNRELATED_SCORES]
        kept = [r for r in results if r.score >= ExecutionEngine.MIN_RECALL_SCORE]

        assert len(kept) == len(RELATED_SCORES)
        assert all(r.score in RELATED_SCORES for r in kept)

    def test_nothing_is_kept_when_everything_is_unrelated(self):
        """The case from the bug report: no citations at all is the right answer."""
        results = [_Result(s) for s in UNRELATED_SCORES]
        kept = [r for r in results if r.score >= ExecutionEngine.MIN_RECALL_SCORE]

        assert kept == [], (
            "an unrelated question must produce no citations. Showing sources "
            "the answer did not use is worse than showing none."
        )

    def test_threshold_is_overridable_for_a_different_embedding_model(self, monkeypatch):
        """The number is calibrated to bge-m3 and does not transfer.

        A model with a different similarity distribution needs a different
        floor, so the value has to be reachable without editing source.
        """
        import importlib

        monkeypatch.setenv("ZARAM_MIN_RECALL_SCORE", "0.75")
        module = importlib.reload(importlib.import_module("core.execution_engine"))
        try:
            assert module.ExecutionEngine.MIN_RECALL_SCORE == 0.75
        finally:
            # Reload again without the override so the module-level constant
            # does not leak a test value into everything that runs afterwards.
            monkeypatch.delenv("ZARAM_MIN_RECALL_SCORE")
            importlib.reload(module)
