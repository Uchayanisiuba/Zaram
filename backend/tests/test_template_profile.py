"""Reading a company's identity out of a document they already send.

The tests that matter most here are the ones asserting that nothing is adopted
without a person saying so, and that a field which cannot be read honestly
comes back as a question rather than as a plausible value. An invoice carrying
the wrong address is not a rendering bug — it is sent to a client.
"""

from __future__ import annotations

import pytest

from artifacts.letterhead import Letterhead
from artifacts.template_profile import (
    Missing,
    TemplateProposal,
    extract_template_profile,
)

#: A one-pixel PNG. Enough to be a valid image of an allowed type; the point of
#: these tests is the decision path, not the pixels.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
    "00000049454e44ae426082"
)

INVOICE = (
    "HARBOUR STUDIO\n"
    "71 Bankside, Lagos\n"
    "hello@harbour.studio\n"
    "\n"
    "INVOICE 0042\n"
    "Issued 1 March 2026\n"
    "\n"
    "Brand identity, phase two ..... NGN 1,250,000.50\n"
    "\n"
    "Payment terms are net 30.\n"
)


class TestIdentity:
    def test_reads_the_trading_name_from_the_masthead(self):
        proposal = extract_template_profile(INVOICE)
        assert proposal.name is not None
        assert proposal.name.value == "HARBOUR STUDIO"

    def test_reads_the_address_block_under_the_name(self):
        proposal = extract_template_profile(INVOICE)
        assert [line.value for line in proposal.address_lines] == [
            "71 Bankside, Lagos",
            "hello@harbour.studio",
        ]

    def test_the_masthead_stops_before_the_document_body(self):
        """"INVOICE 0042" is about the document, not the sender."""
        proposal = extract_template_profile(INVOICE)
        values = [line.value for line in proposal.address_lines]
        assert not any("INVOICE" in value for value in values)

    def test_line_items_never_become_address_lines(self):
        text = "ACME LTD\nSome Work ..... £400.00\n"
        proposal = extract_template_profile(text)
        assert [line.value for line in proposal.address_lines] == []

    def test_every_field_carries_what_it_was_read_from(self):
        """Rule 2 at onboarding: confirming "yes, that's my address" is only
        answerable if the line it came from is visible."""
        proposal = extract_template_profile(INVOICE)
        assert proposal.name is not None and proposal.name.evidence
        assert all(line.evidence for line in proposal.address_lines)
        assert proposal.terms_days is not None and proposal.terms_days.evidence


class TestConventions:
    def test_reads_net_terms(self):
        proposal = extract_template_profile(INVOICE)
        assert proposal.terms_days is not None
        assert proposal.terms_days.value == "30"

    def test_reads_within_days_terms(self):
        proposal = extract_template_profile("Payment is due within 14 days.")
        assert proposal.terms_days is not None
        assert proposal.terms_days.value == "14"

    def test_due_on_receipt_is_zero_days(self):
        proposal = extract_template_profile("Payment is due on receipt.")
        assert proposal.terms_days is not None
        assert proposal.terms_days.value == "0"

    def test_reads_the_currency_code(self):
        proposal = extract_template_profile(INVOICE)
        assert proposal.currency is not None
        assert proposal.currency.value == "NGN"

    def test_reads_a_currency_symbol(self):
        proposal = extract_template_profile("ACME LTD\n\nTotal £2,400.00\n")
        assert proposal.currency is not None
        assert proposal.currency.value == "GBP"

    def test_reads_the_numbering_scheme_and_keeps_its_width(self):
        """Stored as prefix:width:last, not as the next number — a derived
        value in storage is how two invoices end up sharing a number."""
        proposal = extract_template_profile(INVOICE)
        assert proposal.numbering is not None
        assert proposal.numbering.value == ":4:42"

    def test_a_document_stating_no_terms_proposes_none(self):
        proposal = extract_template_profile("ACME LTD\n71 Bankside\n")
        assert proposal.terms_days is None
        assert proposal.numbering is None


class TestLogo:
    def test_uses_an_embedded_image(self):
        proposal = extract_template_profile(INVOICE, images=[(PNG, "image/png")])
        assert proposal.logo is not None
        assert proposal.logo.value.startswith("data:image/png;base64,")

    def test_no_image_is_a_question_not_a_silence(self):
        proposal = extract_template_profile(INVOICE)
        assert proposal.logo is None
        missing = {item.name: item for item in proposal.missing}
        assert missing["logo"].reason is Missing.NOT_PRESENT
        assert missing["logo"].question

    def test_an_unusable_image_refuses_rather_than_approximates(self):
        """A stretched or wrong logo goes onto every invoice the user sends,
        and they find out when a client does."""
        proposal = extract_template_profile(INVOICE, images=[(b"<svg/>", "image/svg+xml")])
        assert proposal.logo is None
        missing = {item.name: item for item in proposal.missing}
        assert missing["logo"].reason is Missing.UNUSABLE
        # The refusal keeps the reason written by `logo_data_uri`, which
        # already explains why SVG is refused.
        assert "internet" in missing["logo"].question

    def test_it_skips_an_unusable_image_for_a_usable_one(self):
        proposal = extract_template_profile(
            INVOICE, images=[(b"<svg/>", "image/svg+xml"), (PNG, "image/png")]
        )
        assert proposal.logo is not None
        assert not [item for item in proposal.missing if item.name == "logo"]


class TestNothingIsAdoptedSilently:
    def test_extraction_alone_produces_no_letterhead(self):
        """The type carries the rule. A proposal is not a Letterhead, so a
        document cannot be generated from something nobody approved."""
        proposal = extract_template_profile(INVOICE, images=[(PNG, "image/png")])
        assert isinstance(proposal, TemplateProposal)
        assert not isinstance(proposal, Letterhead)

    def test_confirmation_is_what_produces_one(self):
        proposal = extract_template_profile(INVOICE, images=[(PNG, "image/png")])
        letterhead = proposal.as_letterhead()

        assert isinstance(letterhead, Letterhead)
        assert letterhead.name == "HARBOUR STUDIO"
        assert list(letterhead.lines) == ["71 Bankside, Lagos", "hello@harbour.studio"]
        assert letterhead.logo.startswith("data:image/png;base64,")
        assert not letterhead.is_empty()

    def test_an_empty_document_asks_rather_than_inventing(self):
        proposal = extract_template_profile("")
        assert proposal.name is None
        assert proposal.as_letterhead().is_empty()
        assert {item.name for item in proposal.missing} >= {"name", "logo"}
        assert all(item.question for item in proposal.missing)


class TestSerialisation:
    def test_a_proposal_round_trips_to_plain_data(self):
        payload = extract_template_profile(
            INVOICE, images=[(PNG, "image/png")]
        ).to_dict()

        assert payload["name"]["value"] == "HARBOUR STUDIO"
        assert payload["terms_days"]["value"] == "30"
        assert payload["currency"]["value"] == "NGN"
        assert len(payload["address_lines"]) == 2
        assert payload["logo"]["value"].startswith("data:")

    def test_missing_fields_serialise_with_their_question(self):
        payload = extract_template_profile(INVOICE).to_dict()
        logo = [item for item in payload["missing"] if item["name"] == "logo"][0]
        assert logo["reason"] == "not_present"
        assert logo["question"]


class TestAgainstARealGeneratedInvoice:
    """The round trip: Zaram must be able to read back a document it wrote.

    Every other test here feeds the extractor a string written to be read. This
    one runs the real invoice pipeline — the same `render_invoice` that produces
    what users send — flattens the HTML the way a parser would, and checks the
    identity comes back out.

    It is the strongest evidence available without a user's own file, and it
    guards the case that matters commercially: a company whose existing
    documents were themselves made by Zaram must not need a different code path.
    """

    @staticmethod
    def _as_text(html: str) -> str:
        """Roughly what a `.docx` or PDF parser hands back: text and newlines.

        `<style>` and `<head>` go first. A parser reads a laid-out page and
        never sees the stylesheet — leaving it in would feed the extractor a
        screenful of CSS as though it were the masthead, which is a property of
        this helper rather than of any document a user will upload.
        """
        import re

        without_head = re.sub(
            r"<(style|script|head)\b[^>]*>.*?</\1>", "\n", html, flags=re.S | re.I
        )
        with_breaks = re.sub(
            r"<(?:br|/p|/h[1-6]|/div|/li|/tr|/td)[^>]*>", "\n", without_head
        )
        stripped = re.sub(r"<[^>]+>", "", with_breaks)
        unescaped = (
            stripped.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        )
        # Collapse the run of blank lines that tag removal leaves behind, so the
        # masthead block is not separated from its own first line.
        return re.sub(r"\n[ \t]*\n+", "\n\n", unescaped)

    def _rendered(self) -> str:
        from artifacts.html import render_invoice
        from artifacts.invoice import line_item, total_of

        items = [line_item(description="Brand identity, phase two", unit_price="1250000.50")]
        return render_invoice(
            title="INVOICE 0042",
            items=items,
            totals=total_of(items),
            currency="NGN",
            terms="Payment terms are net 30.",
            letterhead=Letterhead(
                name="HARBOUR STUDIO",
                lines=("71 Bankside, Lagos", "hello@harbour.studio"),
            ),
        )

    def test_the_identity_survives_the_round_trip(self):
        proposal = extract_template_profile(self._as_text(self._rendered()))

        assert proposal.name is not None
        assert proposal.name.value == "HARBOUR STUDIO"
        assert "71 Bankside, Lagos" in [line.value for line in proposal.address_lines]

    def test_the_conventions_survive_the_round_trip(self):
        proposal = extract_template_profile(self._as_text(self._rendered()))

        assert proposal.terms_days is not None
        assert proposal.terms_days.value == "30"
        assert proposal.currency is not None
        assert proposal.currency.value == "NGN"

    def test_the_confirmed_letterhead_matches_the_one_it_was_generated_with(self):
        """The whole feature in one assertion."""
        original = Letterhead(
            name="HARBOUR STUDIO",
            lines=("71 Bankside, Lagos", "hello@harbour.studio"),
        )
        recovered = extract_template_profile(
            self._as_text(self._rendered())
        ).as_letterhead()

        assert recovered.name == original.name
        assert list(recovered.lines) == list(original.lines)


@pytest.mark.parametrize(
    "text",
    [
        "HARBOUR STUDIO\n71 Bankside, Lagos\n\nINVOICE 0042\nPayment terms are net 30.\n",
        "Harbour Studio\n71 Bankside\n\nQuote 0042\nDue within 30 days.\n",
    ],
)
def test_the_same_company_reads_the_same_way_from_different_documents(text):
    """An invoice and a quote from one business must not produce two identities,
    or every document type gets its own letterhead."""
    proposal = extract_template_profile(text)
    assert proposal.name is not None
    assert proposal.name.value.lower() == "harbour studio"
    assert proposal.terms_days is not None
    assert proposal.terms_days.value == "30"
