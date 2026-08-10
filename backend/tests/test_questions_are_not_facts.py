"""A question must never be stored as a fact.

The Spine holds what the user told Zaram. A question tells it nothing, and
storing one has a specific, visible consequence: the next similar question
recalls it and cites it, so Zaram quotes the user's own words back at them as
though they were a source.

That is exactly what happened. Asking "who won the 2026 world cup" stored the
question; the answer then arrived with a citation pointing at the question. A
citation that leads back to the user is worse than no citation, because it looks
like corroboration and is not.

The guard existed but was conditional on recall having returned something, which
was true only while the relevance threshold was loose enough that every prompt
recalled something. Tightening the threshold — a fix — exposed it. These tests
pin the property directly so it cannot depend on unrelated tuning again.
"""

from __future__ import annotations

from core.execution_engine import ExecutionEngine


QUESTIONS = [
    "who won the 2026 world cup",
    "What can you do",
    "When is the launch?",
    "where is the rehearsal being held",
    "how do I make bread",
    "why did that fail?",
    "can you summarise this",
    "is the deadline still Friday?",
    "what's my deadline",
    "Do you remember the venue?",
]

STATEMENTS = [
    "The launch is 14 November 2027 at the Watershed in Bristol.",
    "Remember this: my deadline is Friday.",
    "My sister's name is Ada.",
    "I work at a hospital in Leeds.",
    "The API key lives in the vault, not in the repo.",
]


class TestQuestionsAreNotStored:
    def test_questions_carry_no_new_information(self):
        for q in QUESTIONS:
            assert ExecutionEngine._carries_new_information(ExecutionEngine, q) is False, (
                f"{q!r} was treated as a fact. It will be stored and later cited "
                "back to the user as a source."
            )

    def test_statements_do_carry_new_information(self):
        for s in STATEMENTS:
            assert ExecutionEngine._carries_new_information(ExecutionEngine, s) is True, (
                f"{s!r} was treated as a question, so it will never be stored "
                "and recall will never find it."
            )

    def test_a_question_mark_is_enough(self):
        assert (
            ExecutionEngine._carries_new_information(
                ExecutionEngine, "The launch is in Bristol?"
            )
            is False
        )

    def test_case_and_whitespace_do_not_matter(self):
        for variant in ("  WHO won the cup  ", "\tWhat can you do\n", "WHERE is it"):
            assert (
                ExecutionEngine._carries_new_information(ExecutionEngine, variant)
                is False
            ), f"{variant!r} slipped through on formatting alone"
