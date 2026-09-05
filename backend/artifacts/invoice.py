"""What an invoice is made of, and the arithmetic that totals it.

Separate from `html.py` so the sums can be tested without rendering anything.
A wrong number on an invoice is the most expensive output this product can
produce — it goes to a client, it is acted on, and unlike a chat reply there is
no next turn in which to correct it.

Three rules hold this module together.

**Money is `Decimal`, never `float`.** `0.1 + 0.2` is `0.30000000000000004`,
and an invoice for three items at £0.10 that totals £0.30000000000000004 is not
a rounding curiosity, it is a document that cannot be reconciled. Inputs are
accepted as strings and integers and converted exactly; a `float` is refused at
the door rather than quietly absorbed, because by the time it arrives the
precision is already gone and nothing here can recover it.

**Zaram does the arithmetic; it never decides what applies.** CLAUDE.md is
explicit — records and drafts, not filings and advice; never compute tax
liability. So an adjustment like "VAT 7.5%" is computed *because the user said
it applies*, at the rate the user gave. Zaram does not know whether that user
should be charging VAT, does not infer it from anything, and has no table of
rates. Summing what someone tells you is bookkeeping; deciding it is advice.

**An incomplete invoice is refused, not filled in.** Rule 9, at the point it
does the most damage. A line with no price is not zero, and an invoice with no
lines is not a £0 invoice — both are a caller that does not have the
information, and inventing the missing half produces a confident, plausible,
wrong document that leaves the building.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import List, Optional, Sequence, Union

#: What a caller may hand us for a number. `float` is deliberately absent.
Money = Union[str, int, Decimal]

_CENTS = Decimal("0.01")


class InvoiceIncomplete(ValueError):
    """The invoice cannot be produced from what was supplied.

    Rule 9: generation must fail rather than invent. Raised in preference to
    defaulting anything, because every default here is a number a client will
    be asked to pay.
    """


def to_decimal(value: Money, *, field_name: str) -> Decimal:
    """Exact conversion, or a refusal that names the field.

    `float` is rejected rather than converted. `Decimal(0.1)` is
    `0.1000000000000000055511151231257827021181583404541015625` — accepting one
    would not fail, it would silently produce a total nobody can reproduce by
    hand, which is the failure mode an invoice must not have.
    """
    if isinstance(value, float):
        raise InvoiceIncomplete(
            f"{field_name} was given as a float, which cannot represent money "
            "exactly. Send it as a string, e.g. \"1250.00\"."
        )
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise InvoiceIncomplete(f"{field_name} is not a number: {value!r}") from None


def money(value: Decimal) -> Decimal:
    """Round to two places, half-up — the way an invoice is read aloud.

    Banker's rounding is Python's default and is wrong here: it is a statistical
    convention, and a client checking the arithmetic by hand rounds 0.005 up.
    """
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LineItem:
    """One billable line. Quantity times unit price, and nothing implicit."""

    description: str
    quantity: Decimal
    unit_price: Decimal
    #: "day", "hour", "unit" — shown beside the quantity. Optional and cosmetic.
    unit: str = ""

    @property
    def amount(self) -> Decimal:
        """Rounded per line, not at the end.

        This is what the reader can check: each row's amount is what its own
        quantity and rate produce. Carrying full precision to the bottom and
        rounding once makes the column not add up to the total shown beside it,
        and "the arithmetic is wrong" is what the client concludes.
        """
        return money(self.quantity * self.unit_price)


@dataclass(frozen=True)
class Adjustment:
    """A named amount added after the subtotal — tax, discount, deposit.

    Either a `rate` (a percentage of the subtotal) or a flat `amount`, never
    both. `label` is required and free text: Zaram does not know whether this is
    VAT, GST, a retainer or a discount, and does not need to. It is the user's
    word for it, printed as given.
    """

    label: str
    rate: Optional[Decimal] = None
    amount: Optional[Decimal] = None

    def applied_to(self, subtotal: Decimal) -> Decimal:
        """Computed against the subtotal, never against a running total.

        Two adjustments therefore cannot compound. That is a decision, not an
        omission: compounding is a jurisdiction-specific rule about which taxes
        stack, and inferring one would be exactly the advice this product
        refuses to give. A user who needs a compounded figure states it as an
        amount.
        """
        if self.amount is not None:
            return money(self.amount)
        if self.rate is not None:
            return money(subtotal * self.rate / Decimal(100))
        raise InvoiceIncomplete(
            f"adjustment {self.label!r} has neither a rate nor an amount"
        )


@dataclass(frozen=True)
class Totals:
    subtotal: Decimal
    #: Label and computed amount, in the order they were supplied.
    adjustments: List[tuple[str, Decimal]] = field(default_factory=list)
    total: Decimal = Decimal("0")


def total_of(
    items: Sequence[LineItem], adjustments: Sequence[Adjustment] = ()
) -> Totals:
    """Subtotal, each adjustment, and the number the client pays."""
    if not items:
        raise InvoiceIncomplete(
            "An invoice needs at least one line. An invoice with no lines is a "
            "caller that does not know what is being billed, not a zero invoice."
        )

    subtotal = money(sum((item.amount for item in items), Decimal("0")))
    applied = [(a.label, a.applied_to(subtotal)) for a in adjustments]
    return Totals(
        subtotal=subtotal,
        adjustments=applied,
        total=money(subtotal + sum((amount for _, amount in applied), Decimal("0"))),
    )


def line_item(
    *,
    description: str,
    quantity: Money = 1,
    unit_price: Money,
    unit: str = "",
) -> LineItem:
    """Build a line, refusing anything that would have to be guessed at."""
    if not (description or "").strip():
        raise InvoiceIncomplete("a line item needs a description")
    return LineItem(
        description=description.strip(),
        quantity=to_decimal(quantity, field_name=f"quantity for {description!r}"),
        unit_price=to_decimal(unit_price, field_name=f"unit price for {description!r}"),
        unit=unit.strip(),
    )


def due_date(issued: date, terms_days: int) -> date:
    """When payment is due. **This is the obligation.**

    The one derived date in the whole document, and the seed for M9a: the
    reminder is not a separate thing the user sets up, it is this number, which
    already exists on the record and traces to the terms line printed on the
    page. An obligation the user typed twice is one they can disagree with
    themselves about.
    """
    if terms_days < 0:
        raise InvoiceIncomplete(
            f"payment terms cannot be negative ({terms_days} days)"
        )
    return issued + timedelta(days=terms_days)


def format_money(amount: Decimal, currency: str) -> str:
    """`₦1,250.00`. Grouped, two places, currency exactly as given.

    No symbol table and no conversion. Zaram does not know that "NGN" should be
    rendered "₦", does not know today's rate, and must never appear to: a
    converted figure on an invoice is a number the user did not agree to.
    """
    text = f"{money(amount):,.2f}"
    prefix = (currency or "").strip()
    if not prefix:
        return text
    # A bare symbol butts against the number; a code needs a space. Deciding by
    # whether it is alphabetic keeps both "₦1,250.00" and "USD 1,250.00" right
    # without a list of currencies to maintain.
    return f"{prefix} {text}" if prefix.isalpha() else f"{prefix}{text}"
