"""Ingesting a document produces commitments you can read back.

`test_obligation_extraction.py` grades the extractor, which is the right level
for that claim and is exactly why it could not see this one: **the whole
`obligations` package was imported by nothing but that file.** Twenty-eight
green tests over a parser that ran for no one — the eighteenth complete,
tested, unreachable subsystem in this repository, and the documented shape.

So this file grades the seam. It puts a real file on a real disk, runs the real
ingest, and asks the store what it has. Nothing here mocks the extractor, and
the one thing it does substitute — the Spine — is substituted because indexing
is a separate capability, which is the point of the split in
`IngestService.attach_obligations`.

The defect this found on the way is worth recording. `_COMMITMENT` gates every
sentence before a date in it is read as a deadline, and

    "Payment terms: 30 days from the invoice date."

carries none of `due`, `by`, `within` or `net` — so it was dropped at that gate
with **no obligation and no unresolved question**. Classified as a payment, its
thirty days parsed, and then discarded silently. That is the most common clause
on a real invoice, and it is the exact sentence `test_recall_eval.py` uses as
its sample invoice: the repository's own canonical example was the one the
extractor could not read. `TestTheClauseThatWasBeingDropped` holds that shut.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ingest.records import IngestRecords
from ingest.service_api import IngestService
from obligations.contracts import Direction, ObligationKind, ObligationStatus
from obligations.extract import extract_obligations
from obligations.records import ObligationRecords

INVOICE = (
    "Invoice INV-HARB-014 for Harbour Lane Studio.\n"
    "Issued 2 July 2026 in NGN.\n"
    "Motion design at a day rate of 425,000 naira.\n"
    "Payment terms: 30 days from the invoice date.\n"
    "Final delivery is 12 September 2026.\n"
)


@pytest.fixture
def store(tmp_path) -> ObligationRecords:
    return ObligationRecords(str(tmp_path / "obligations.db"))


@pytest.fixture
def service(tmp_path, store) -> IngestService:
    return IngestService(
        IngestRecords(str(tmp_path / "ingest.db")),
        memory_runtime=None,
        obligations=store,
    )


def _folder(tmp_path, name: str = "invoice.txt", text: str = INVOICE) -> Path:
    root = tmp_path / "docs"
    root.mkdir(exist_ok=True)
    (root / name).write_text(text, encoding="utf-8")
    return root


class TestTheClauseThatWasBeingDropped:
    """The commonest payment clause on a real invoice, silently discarded."""

    def test_payment_terms_produce_a_commitment(self):
        result = extract_obligations(
            "Payment terms: 30 days from the invoice date.",
            anchor_date=date(2026, 7, 2),
        )
        assert [o.kind for o in result.obligations] == [ObligationKind.PAYMENT]
        assert result.obligations[0].due == date(2026, 8, 1)

    def test_it_is_not_dropped_when_there_is_no_anchor_either(self):
        # Without an anchor it must become a *question*, not nothing. Dropping
        # it loses a real deadline the user is exposed to.
        result = extract_obligations("Payment terms: 30 days from the invoice date.")
        assert not result.obligations
        assert len(result.unresolved) == 1
        assert result.unresolved[0].kind is ObligationKind.PAYMENT

    def test_the_gate_still_refuses_a_date_that_commits_nobody(self):
        # The reason `_COMMITMENT` exists. Widening it to admit the clause
        # above must not admit these.
        for sentence in (
            "We met on 3 March 2026.",
            "The logo was approved on 12 April 2026.",
        ):
            result = extract_obligations(sentence, anchor_date=date(2026, 7, 2))
            assert not result.obligations, sentence
            assert not result.unresolved, sentence


class TestIngestReachesTheStore:
    def test_a_folder_ingest_records_its_commitments(self, service, store, tmp_path):
        service.scan(str(_folder(tmp_path)))
        stored = store.open_obligations()
        assert stored, "ingest produced no obligations at all"
        assert ObligationKind.DELIVERABLE.value in {o["kind"] for o in stored}

    def test_every_stored_obligation_carries_its_clause(self, service, store, tmp_path):
        # Rule 2, and the rule this package was written to obey: never a
        # commitment without the sentence it was read from.
        service.scan(str(_folder(tmp_path)))
        stored = store.open_obligations()
        # The emptiness check is not decoration. Written without it, this
        # passed with the ingest seam disabled — iterating nothing and
        # asserting nothing, reporting coverage it did not have. Caught by
        # disabling the seam and reading which tests *survived*.
        assert stored
        for item in stored:
            assert item["source_clause"]["text"].strip()

    def test_the_document_is_named(self, service, store, tmp_path):
        service.scan(str(_folder(tmp_path)))
        stored = store.open_obligations()
        assert stored
        for item in stored:
            assert item["source_document_id"].endswith("invoice.txt")

    def test_an_undated_relative_term_becomes_a_question(self, service, store, tmp_path):
        # The ingest layer has no issue date — the parsers return text, not
        # fields — so "30 days from the invoice date" must be asked about
        # rather than anchored to today.
        service.scan(str(_folder(tmp_path)))
        questions = store.open_questions()
        assert questions, "the payment clause produced neither a date nor a question"
        assert any(q["kind"] == ObligationKind.PAYMENT.value for q in questions)
        assert all(q["question"].strip() for q in questions)

    def test_re_ingesting_the_same_file_does_not_duplicate(self, service, store, tmp_path):
        root = _folder(tmp_path)
        service.scan(str(root))
        first = len(store.all_obligations())
        service.scan(str(root))
        assert len(store.all_obligations()) == first

    def test_ingest_without_an_obligations_store_still_works(self, tmp_path):
        # Indexing and reading commitments are separate capabilities. A build
        # with one and not the other does the half it can.
        service = IngestService(
            IngestRecords(str(tmp_path / "i.db")), memory_runtime=None, obligations=None
        )
        report = service.scan(str(_folder(tmp_path)))
        assert report is not None


class TestNothingIsInvented:
    """CLAUDE.md: never silently create a commitment."""

    def test_direction_is_not_guessed(self, service, store, tmp_path):
        # "Payment is due within 30 days" reads identically on an invoice the
        # user sent and one they received. Guessing tells a freelancer they owe
        # money they are in fact owed.
        service.scan(str(_folder(tmp_path)))
        stored = store.open_obligations()
        assert stored
        for item in stored:
            assert item["direction"] == Direction.UNKNOWN.value

    def test_a_document_with_no_commitments_produces_none(self, service, store, tmp_path):
        _folder(tmp_path, "notes.txt", "Met the client. The office is on Marina.\n")
        service.scan(str(tmp_path / "docs"))
        assert store.open_obligations() == []


class TestCorrectionSurvives:
    """Rule 4, and the reason a dismissal is stored rather than deleted."""

    def test_a_dismissed_obligation_does_not_come_back_on_re_ingest(
        self, service, store, tmp_path
    ):
        root = _folder(tmp_path)
        service.scan(str(root))
        first = store.open_obligations()[0]
        assert store.dismiss(first["id"])

        service.scan(str(root))
        live = [o["id"] for o in store.open_obligations()]
        assert first["id"] not in live, "dismissing it did not stick across a re-ingest"

    def test_a_correction_supersedes_rather_than_mutates(self, service, store, tmp_path):
        service.scan(str(_folder(tmp_path)))
        original = store.open_obligations()[0]

        corrected = store.correct(original["id"], due=date(2026, 10, 1))
        assert corrected is not None
        assert corrected["due"] == "2026-10-01"

        # The old belief is still on disk and is out of the live set.
        assert store.get(original["id"])["superseded_by"] == corrected["id"]
        assert original["id"] not in {o["id"] for o in store.open_obligations()}

    def test_a_correction_keeps_the_source_clause(self, service, store, tmp_path):
        # A correction says Zaram read the sentence wrongly, not that the
        # sentence was different.
        service.scan(str(_folder(tmp_path)))
        original = store.open_obligations()[0]
        corrected = store.correct(original["id"], due=date(2026, 10, 1))
        assert corrected["source_clause"] == original["source_clause"]

    def test_a_corrected_obligation_is_no_longer_an_extractor_guess(
        self, service, store, tmp_path
    ):
        service.scan(str(_folder(tmp_path)))
        original = store.open_obligations()[0]
        corrected = store.correct(original["id"], due=date(2026, 10, 1))
        assert corrected["confidence"] == 1.0

    def test_answering_a_question_produces_a_dated_commitment(
        self, service, store, tmp_path
    ):
        service.scan(str(_folder(tmp_path)))
        question = next(
            q for q in store.open_questions() if q["kind"] == ObligationKind.PAYMENT.value
        )
        created = store.answer_question(question["id"], anchor=date(2026, 7, 2))
        assert created is not None
        assert created["due"] == "2026-08-01"
        assert created["status"] == ObligationStatus.OPEN.value
        # And the question is closed rather than asked again.
        assert question["id"] not in {q["id"] for q in store.open_questions()}
