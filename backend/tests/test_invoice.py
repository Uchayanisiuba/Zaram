"""The arithmetic on an invoice, and what it refuses to guess.

This is the output with the shortest path to real consequences: it goes to a
client, it is paid or disputed, and there is no next turn in which to correct
it. So the sums are tested directly rather than through the renderer, and the
refusals are tested as hard as the successes — rule 9 lands here more than
anywhere else in the product.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from artifacts.invoice import (
    Adjustment,
    InvoiceIncomplete,
    due_date,
    format_money,
    line_item,
    total_of,
)


def day(description="Design day", quantity="1", unit_price="450.00"):
    return line_item(description=description, quantity=quantity, unit_price=unit_price)


class TestTheSums:
    def test_a_line_is_quantity_times_rate(self):
        item = line_item(description="Design day", quantity="3", unit_price="450.00")
        assert item.amount == Decimal("1350.00")

    def test_money_does_not_drift(self):
        """The reason `Decimal` is not an aesthetic preference.

        In binary floating point 0.1 + 0.1 + 0.1 is 0.30000000000000004. An
        invoice that totals that is not a rounding curiosity — it is a document
        that cannot be reconciled against the column above it.
        """
        items = [line_item(description=f"Item {i}", unit_price="0.10") for i in range(3)]

        assert total_of(items).total == Decimal("0.30")

    def test_a_float_is_refused_rather_than_converted(self):
        # By the time a float arrives the precision is already gone. Accepting
        # it would not fail, it would produce a total nobody can reproduce.
        with pytest.raises(InvoiceIncomplete, match="float"):
            line_item(description="Design day", unit_price=450.0)

    def test_lines_round_before_they_are_summed(self):
        """Each row's amount is what its own quantity and rate produce.

        Carrying full precision to the bottom and rounding once makes the
        printed column not add up to the printed total, and "your arithmetic is
        wrong" is what the client concludes — correctly, from what they can see.
        """
        items = [
            line_item(description="Hour", quantity="1", unit_price="0.005"),
            line_item(description="Hour", quantity="1", unit_price="0.005"),
        ]

        # 0.005 rounds half-up to 0.01 per line, so the total is 0.02 — not the
        # 0.01 that summing first and rounding once would produce.
        assert [i.amount for i in items] == [Decimal("0.01"), Decimal("0.01")]
        assert total_of(items).total == Decimal("0.02")

    def test_half_up_not_bankers(self):
        # Python's default is banker's rounding, a statistical convention. A
        # client checking by hand rounds 0.005 up.
        item = line_item(description="Thing", quantity="1", unit_price="2.005")
        assert item.amount == Decimal("2.01")


class TestAdjustments:
    def test_a_rate_is_applied_to_the_subtotal(self):
        totals = total_of([day(unit_price="1000.00")], [Adjustment("VAT 7.5%", rate=Decimal("7.5"))])

        assert totals.subtotal == Decimal("1000.00")
        assert totals.adjustments == [("VAT 7.5%", Decimal("75.00"))]
        assert totals.total == Decimal("1075.00")

    def test_a_flat_amount_is_taken_as_given(self):
        totals = total_of([day(unit_price="1000.00")], [Adjustment("Deposit held", amount=Decimal("-250"))])

        assert totals.total == Decimal("750.00")

    def test_adjustments_do_not_compound(self):
        """Both are computed against the subtotal, never a running total.

        A decision, not an omission: whether one tax stacks on another is a
        jurisdiction-specific rule, and inferring one is the tax advice this
        product refuses to give. A user who needs a compounded figure states it
        as an amount.
        """
        totals = total_of(
            [day(unit_price="100.00")],
            [Adjustment("A 10%", rate=Decimal("10")), Adjustment("B 10%", rate=Decimal("10"))],
        )

        assert [a for _, a in totals.adjustments] == [Decimal("10.00"), Decimal("10.00")]
        assert totals.total == Decimal("120.00")

    def test_an_adjustment_with_neither_rate_nor_amount_is_refused(self):
        with pytest.raises(InvoiceIncomplete, match="neither a rate nor an amount"):
            total_of([day()], [Adjustment("Mystery")])


class TestRefusing:
    def test_an_invoice_with_no_lines_is_not_a_zero_invoice(self):
        """Rule 9 at the point it does the most damage.

        No lines means the caller does not know what is being billed. Producing
        a £0 invoice from that is a confident, plausible, wrong document — and
        unlike a wrong chat reply, it leaves the building.
        """
        with pytest.raises(InvoiceIncomplete, match="at least one line"):
            total_of([])

    def test_a_line_with_no_price_is_refused(self):
        with pytest.raises(InvoiceIncomplete):
            line_item(description="Design day", unit_price="")

    def test_a_line_with_no_description_is_refused(self):
        # An unlabelled charge is the line a client queries, and Zaram cannot
        # answer the query.
        with pytest.raises(InvoiceIncomplete, match="description"):
            line_item(description="   ", unit_price="450.00")

    def test_negative_terms_are_refused(self):
        with pytest.raises(InvoiceIncomplete, match="negative"):
            due_date(date(2026, 8, 10), -5)


class TestTheDueDate:
    def test_it_is_derived_from_the_terms(self):
        assert due_date(date(2026, 8, 10), 30) == date(2026, 9, 9)

    def test_due_on_receipt_is_the_issue_date(self):
        assert due_date(date(2026, 8, 10), 0) == date(2026, 8, 10)


class TestFormatting:
    def test_a_symbol_butts_against_the_number(self):
        assert format_money(Decimal("1250"), "₦") == "₦1,250.00"

    def test_a_code_is_spaced(self):
        assert format_money(Decimal("1250"), "USD") == "USD 1,250.00"

    def test_no_currency_is_a_bare_number(self):
        # Not defaulted to a symbol. Zaram does not know what currency this is
        # and must not appear to.
        assert format_money(Decimal("1250"), "") == "1,250.00"

    def test_thousands_are_grouped_and_places_are_fixed(self):
        assert format_money(Decimal("1234567.5"), "") == "1,234,567.50"
