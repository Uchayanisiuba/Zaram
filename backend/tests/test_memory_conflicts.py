"""Detecting that a new fact contradicts a stored one.

The tests that matter most are the ones asserting nothing is *resolved*. A
detector that quietly picks a winner is worse than no detector, because it
destroys the record rule 4 exists to protect and does it silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from runtimes.memory.conflicts import Conflict, find_conflicts, read_assertion


@dataclass
class FakeRecord:
    """Structurally what `MemoryRecord` gives the detector, and nothing else."""

    id: str
    content: str
    scope: str = "global"
    superseded_by: Optional[str] = None


class TestReadingAssertions:
    def test_reads_a_simple_assertion(self):
        assertion = read_assertion("The target is developers")
        assert assertion is not None
        assert assertion.subject == "target"
        assert assertion.value == "developers"

    def test_ignores_articles_and_possessives_so_phrasings_match(self):
        first = read_assertion("My day rate is £600")
        second = read_assertion("The day rate is £600")
        assert first is not None and second is not None
        assert first.subject == second.subject

    def test_reads_a_preference(self):
        assertion = read_assertion("I prefer local models")
        assert assertion is not None
        assert assertion.subject == "preference"
        assert assertion.value == "local models"

    def test_a_hedged_sentence_is_not_an_assertion(self):
        """"Maybe X is Y" states nothing that can be contradicted."""
        assert read_assertion("Maybe the target is consumers") is None
        assert read_assertion("The target used to be developers") is None

    def test_most_sentences_are_not_assertions(self):
        assert read_assertion("We shipped the installer on Tuesday") is None
        assert read_assertion("") is None


class TestFindingConflicts:
    def test_finds_a_straight_contradiction(self):
        existing = [FakeRecord(id="m1", content="The target is developers")]
        conflicts = find_conflicts("The target is ordinary consumers", existing)

        assert len(conflicts) == 1
        assert conflicts[0].existing_id == "m1"
        assert conflicts[0].subject == "target"
        assert conflicts[0].existing_value == "developers"
        assert conflicts[0].incoming_value == "ordinary consumers"

    def test_the_conflict_carries_a_question_naming_both_values(self):
        conflicts = find_conflicts(
            "The target is ordinary consumers",
            [FakeRecord(id="m1", content="The target is developers")],
        )
        question = conflicts[0].question
        assert "developers" in question and "ordinary consumers" in question

    def test_the_same_statement_twice_is_not_a_conflict(self):
        existing = [FakeRecord(id="m1", content="The target is developers")]
        assert find_conflicts("The target is developers", existing) == []

    def test_a_more_detailed_restatement_is_not_a_conflict(self):
        """"net 30" and "net 30 from invoice date" are one term, twice."""
        existing = [FakeRecord(id="m1", content="Payment terms are net 30")]
        assert find_conflicts("Payment terms are net 30 from invoice date", existing) == []

    def test_different_subjects_do_not_conflict(self):
        existing = [FakeRecord(id="m1", content="The target is developers")]
        assert find_conflicts("The day rate is £600", existing) == []

    def test_a_non_assertion_conflicts_with_nothing(self):
        existing = [FakeRecord(id="m1", content="The target is developers")]
        assert find_conflicts("We shipped the installer on Tuesday", existing) == []

    def test_an_already_corrected_fact_is_not_raised_again(self):
        """It is out of recall and it is history. Asking again asks the user to
        re-decide something they already decided."""
        existing = [
            FakeRecord(id="m1", content="The target is developers", superseded_by="m2")
        ]
        assert find_conflicts("The target is consumers", existing) == []

    def test_it_reports_every_stale_fact_not_only_the_first(self):
        existing = [
            FakeRecord(id="m1", content="The target is developers"),
            FakeRecord(id="m2", content="The target is agencies"),
        ]
        conflicts = find_conflicts("The target is ordinary consumers", existing)
        assert {c.existing_id for c in conflicts} == {"m1", "m2"}


class TestScope:
    """Rule 7i. Two projects disagreeing is the normal case, not a conflict."""

    def test_facts_in_different_projects_do_not_conflict(self):
        existing = [
            FakeRecord(id="m1", content="Payment terms are net 14", scope="project:acme")
        ]
        conflicts = find_conflicts(
            "Payment terms are net 30", existing, scope="project:harbour"
        )
        assert conflicts == []

    def test_facts_in_the_same_project_do_conflict(self):
        existing = [
            FakeRecord(id="m1", content="Payment terms are net 14", scope="project:acme")
        ]
        conflicts = find_conflicts(
            "Payment terms are net 30", existing, scope="project:acme"
        )
        assert len(conflicts) == 1
        assert conflicts[0].scope == "project:acme"

    def test_a_project_fact_does_not_contradict_a_global_one(self):
        """A general preference and a project-specific choice are not rivals."""
        existing = [FakeRecord(id="m1", content="I prefer local models", scope="global")]
        conflicts = find_conflicts(
            "I prefer cloud models", existing, scope="project:harbour"
        )
        assert conflicts == []


class TestItResolvesNothing:
    def test_a_conflict_carries_no_decision(self):
        """The moment it names a winner, something starts applying that winner
        without asking."""
        conflicts = find_conflicts(
            "The target is consumers",
            [FakeRecord(id="m1", content="The target is developers")],
        )
        conflict = conflicts[0]

        assert not hasattr(conflict, "winner")
        assert not hasattr(conflict, "resolution")
        assert not hasattr(conflict, "resolved")

    def test_detection_does_not_mutate_what_it_was_given(self):
        record = FakeRecord(id="m1", content="The target is developers")
        find_conflicts("The target is consumers", [record])

        assert record.superseded_by is None
        assert record.content == "The target is developers"

    def test_the_incoming_fact_is_reported_not_stored(self):
        """Detection is a read. Storing is the caller's decision, after the
        user has answered."""
        conflicts = find_conflicts(
            "The target is consumers",
            [FakeRecord(id="m1", content="The target is developers")],
        )
        assert conflicts[0].incoming_content == "The target is consumers"
        assert isinstance(conflicts[0], Conflict)


class TestSerialisation:
    def test_a_conflict_round_trips_to_plain_data(self):
        payload = find_conflicts(
            "The target is consumers",
            [FakeRecord(id="m1", content="The target is developers")],
        )[0].to_dict()

        assert payload["existing_id"] == "m1"
        assert payload["subject"] == "target"
        assert payload["question"]
        assert "winner" not in payload
