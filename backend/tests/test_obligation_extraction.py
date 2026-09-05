"""What the obligation extractor must and must not do.

The must-nots outnumber the musts here, deliberately. Missing a deadline the
document stated is a bug; *inventing* one it did not is the failure this
milestone exists to avoid, and it is the harder one to notice after the fact
because an invented obligation looks exactly like a real one in the interface.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from obligations.contracts import (
    Direction,
    ObligationKind,
    Unresolved,
)
from obligations.extract import extract_obligations


class TestAbsoluteDates:
    def test_reads_a_payment_deadline_with_its_clause(self):
        text = "Payment of £2,400.00 is due by 15 March 2026."
        result = extract_obligations(text, document_id="doc-1")

        assert len(result.obligations) == 1
        obligation = result.obligations[0]
        assert obligation.kind is ObligationKind.PAYMENT
        assert obligation.due == date(2026, 3, 15)
        assert obligation.amount == Decimal("2400.00")
        assert obligation.currency == "GBP"
        assert obligation.source_document_id == "doc-1"

    def test_carries_the_sentence_it_was_read_from(self):
        """Rule 2. An obligation with no clause is not shippable."""
        text = "Some preamble. Payment is due by 15 March 2026. More text."
        result = extract_obligations(text)

        clause = result.obligations[0].source_clause
        assert clause.text == "Payment is due by 15 March 2026."
        assert text[clause.start : clause.end] == clause.text

    def test_reads_month_first_and_day_first_alike(self):
        for phrasing in ("due by 15 March 2026", "due by March 15, 2026"):
            result = extract_obligations(f"Payment is {phrasing}.")
            assert result.obligations[0].due == date(2026, 3, 15), phrasing

    def test_reads_iso_dates(self):
        result = extract_obligations("Payment is due by 2026-03-15.")
        assert result.obligations[0].due == date(2026, 3, 15)

    def test_reads_an_unambiguous_numeric_date(self):
        """15/03 can only be day-first — no locale reads a 15th month."""
        result = extract_obligations("Payment is due by 15/03/2026.")
        assert result.obligations[0].due == date(2026, 3, 15)

    def test_expiry_and_renewal_are_distinguished_from_payment(self):
        quote = extract_obligations("This quote is valid until 30 April 2026.")
        assert quote.obligations[0].kind is ObligationKind.EXPIRY

        licence = extract_obligations(
            "The licence renews automatically on 1 June 2026 unless cancelled."
        )
        assert licence.obligations[0].kind is ObligationKind.RENEWAL

        work = extract_obligations("Final files will be delivered by 20 May 2026.")
        assert work.obligations[0].kind is ObligationKind.DELIVERABLE


class TestRelativeTerms:
    def test_net_terms_resolve_against_the_anchor(self):
        result = extract_obligations(
            "Payment terms are net 30.", anchor_date=date(2026, 3, 1)
        )
        assert result.obligations[0].due == date(2026, 3, 31)

    def test_within_days_resolves_against_the_anchor(self):
        result = extract_obligations(
            "Payment is due within 14 days of receipt.", anchor_date=date(2026, 3, 1)
        )
        assert result.obligations[0].due == date(2026, 3, 15)

    def test_due_on_receipt_is_the_anchor_itself(self):
        result = extract_obligations(
            "Payment is due on receipt.", anchor_date=date(2026, 3, 1)
        )
        assert result.obligations[0].due == date(2026, 3, 1)

    def test_a_relative_term_is_less_confident_than_an_absolute_date(self):
        """It rests on the anchor being right as well as the clause."""
        relative = extract_obligations(
            "Payment terms are net 30.", anchor_date=date(2026, 3, 1)
        ).obligations[0]
        absolute = extract_obligations(
            "Payment is due by 31 March 2026."
        ).obligations[0]
        assert relative.confidence < absolute.confidence

    def test_without_an_anchor_it_asks_rather_than_guesses(self):
        """The rule-9 case. Zaram's own clock must not set a contract term."""
        result = extract_obligations("Payment terms are net 30.")

        assert result.obligations == []
        assert len(result.unresolved) == 1
        assert result.unresolved[0].reason is Unresolved.NO_ANCHOR_DATE
        assert "30 days" in result.unresolved[0].question
        assert result.unresolved[0].source_clause.text == "Payment terms are net 30."


class TestRefusals:
    def test_an_ambiguous_numeric_date_is_never_guessed(self):
        """03/04/2026 is 3 April or 4 March. A month apart, and no default is
        correct — so it becomes a question, not a commitment."""
        result = extract_obligations("Payment is due by 03/04/2026.")

        assert result.obligations == []
        assert len(result.unresolved) == 1
        assert result.unresolved[0].reason is Unresolved.AMBIGUOUS_DATE

    def test_an_impossible_date_is_reported_not_swallowed(self):
        result = extract_obligations("Payment is due by 31 February 2026.")

        assert result.obligations == []
        assert result.unresolved[0].reason is Unresolved.IMPOSSIBLE_DATE

    def test_a_date_that_commits_nobody_is_not_an_obligation(self):
        """Documents are full of dates. Only the ones attached to a commitment
        cue are deadlines; the rest are history."""
        text = (
            "We met on 3 March 2026 and agreed the direction. "
            "The logo was approved on 12 April 2026."
        )
        result = extract_obligations(text)

        assert result.obligations == []
        assert result.unresolved == []

    def test_a_commitment_with_no_date_at_all_is_not_invented(self):
        result = extract_obligations("Payment is due promptly.")
        assert result.obligations == []
        assert result.unresolved == []

    def test_empty_input_yields_nothing(self):
        result = extract_obligations("")
        assert result.obligations == []
        assert result.unresolved == []


class TestDirectionAndScope:
    def test_direction_is_unknown_unless_the_caller_says(self):
        """The sentence reads identically on an invoice sent and one received.
        Guessing would tell a freelancer they owe money they are owed."""
        result = extract_obligations("Payment is due by 15 March 2026.")
        assert result.obligations[0].direction is Direction.UNKNOWN

    def test_direction_is_carried_through_when_supplied(self):
        result = extract_obligations(
            "Payment is due by 15 March 2026.", direction=Direction.OWED_TO_USER
        )
        assert result.obligations[0].direction is Direction.OWED_TO_USER

    def test_scope_defaults_to_global_and_is_carried_through(self):
        """Rule 7i."""
        assert (
            extract_obligations("Payment is due by 15 March 2026.")
            .obligations[0]
            .scope
            == "global"
        )
        scoped = extract_obligations(
            "Payment is due by 15 March 2026.", scope="project:harbour"
        )
        assert scoped.obligations[0].scope == "project:harbour"


class TestSeveralInOneDocument:
    def test_reads_each_clause_separately(self):
        text = (
            "Zaram Ltd — Invoice 0042.\n"
            "Payment of £2,400.00 is due by 15 March 2026.\n"
            "This quote is valid until 30 April 2026.\n"
            "Final assets will be delivered by 20 May 2026.\n"
        )
        result = extract_obligations(text, document_id="inv-42")

        kinds = {o.kind for o in result.obligations}
        assert kinds == {
            ObligationKind.PAYMENT,
            ObligationKind.EXPIRY,
            ObligationKind.DELIVERABLE,
        }
        assert all(o.source_document_id == "inv-42" for o in result.obligations)
        assert all(o.source_clause.text for o in result.obligations)

    def test_every_obligation_is_locatable_in_the_original_text(self):
        text = (
            "Payment of £2,400.00 is due by 15 March 2026.\n"
            "This quote is valid until 30 April 2026.\n"
        )
        result = extract_obligations(text)
        for obligation in result.obligations:
            clause = obligation.source_clause
            assert text[clause.start : clause.end] == clause.text


class TestARealisticDocument:
    """One document shaped like something a freelancer actually receives.

    Every unit above passes on a single tidy sentence. This is the probe that a
    whole document — masthead, line items, a number with a decimal point, a
    term rather than a date, and a date nobody can read — comes out as three
    commitments and one question rather than as silence.
    """

    TEXT = (
        "HARBOUR STUDIO\n"
        "71 Bankside, Lagos\n"
        "\n"
        "INVOICE 0042\n"
        "Issued 1 March 2026\n"
        "\n"
        "Brand identity, phase two ..... NGN 1,250,000.50\n"
        "Retainer, March ............... NGN 400,000.00\n"
        "\n"
        "Payment terms are net 30.\n"
        "Final assets will be delivered by 20 May 2026.\n"
        "The rate quoted above is valid until 03/04/2026.\n"
        "Thanks for your business — we met on 12 February 2026 to agree scope.\n"
    )

    def test_reads_the_commitments_and_asks_about_the_rest(self):
        result = extract_obligations(
            self.TEXT,
            document_id="inv-0042",
            anchor_date=date(2026, 3, 1),
            scope="project:harbour",
            direction=Direction.OWED_TO_USER,
        )

        by_kind = {o.kind: o for o in result.obligations}
        assert by_kind[ObligationKind.PAYMENT].due == date(2026, 3, 31)
        assert by_kind[ObligationKind.DELIVERABLE].due == date(2026, 5, 20)

        # The ambiguous expiry became a question, not a date.
        assert ObligationKind.EXPIRY not in by_kind
        assert [u.reason for u in result.unresolved] == [Unresolved.AMBIGUOUS_DATE]

    def test_the_decimal_amount_survives(self):
        """The bug this document exists to keep fixed: a period inside
        `1,250,000.50` must not end the sentence."""
        result = extract_obligations(self.TEXT, anchor_date=date(2026, 3, 1))
        clauses = [o.source_clause.text for o in result.obligations]
        assert any("net 30" in c for c in clauses)

    def test_the_meeting_is_not_a_deadline(self):
        result = extract_obligations(self.TEXT, anchor_date=date(2026, 3, 1))
        assert all("we met" not in o.source_clause.text for o in result.obligations)

    def test_scope_and_direction_reach_every_obligation(self):
        result = extract_obligations(
            self.TEXT,
            anchor_date=date(2026, 3, 1),
            scope="project:harbour",
            direction=Direction.OWED_TO_USER,
        )
        assert all(o.scope == "project:harbour" for o in result.obligations)
        assert all(o.direction is Direction.OWED_TO_USER for o in result.obligations)
        assert all(u.scope == "project:harbour" for u in result.unresolved)


class TestSerialisation:
    def test_an_obligation_round_trips_to_plain_data(self):
        result = extract_obligations(
            "Payment of £2,400.00 is due by 15 March 2026.", document_id="doc-1"
        )
        payload = result.obligations[0].to_dict()

        assert payload["due"] == "2026-03-15"
        assert payload["amount"] == "2400.00"
        assert payload["kind"] == "payment"
        assert payload["source_clause"]["text"]

    def test_an_unresolved_obligation_carries_its_question(self):
        payload = extract_obligations("Payment terms are net 30.").unresolved[0].to_dict()
        assert payload["reason"] == "no_anchor_date"
        assert payload["question"]
        assert payload["source_clause"]["text"]


def test_no_obligation_can_be_built_without_a_clause():
    """The type system carries the rule: `source_clause` has no default, so a
    commitment cannot be constructed by forgetting to supply its evidence."""
    from obligations.contracts import Obligation

    with pytest.raises(TypeError):
        Obligation(  # type: ignore[call-arg]
            id="x",
            kind=ObligationKind.PAYMENT,
            summary="Payment due",
            due=date(2026, 3, 15),
        )
