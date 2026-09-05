""""Write mine like this one" — the attached file as a shape, not as text.

Attaching a document already worked for *content*: `compose` parses it, sizes
it against the model's window and puts it in front of the question. What it did
not carry was the thing a person means when they attach an example — its
**structure**. So "draft my proposal in the same format as this one" reached a
model that could see the reference's sentences and had been told nothing about
its sections.

Two properties, and the second is the one that makes this safe:

* The outline is read from the **whole file**, never from the excerpt.
  Selection ranks passages by overlap with the question and is free to drop the
  headings the outline is made of, so an outline taken after budgeting would
  describe whichever three sections happened to match the wording.
* The reference supplies a **shape, not sentences**. Without that instruction a
  model asked to write one "like this" returns the reference with the names
  changed — which is somebody else's document with the user's name on it, and
  on a CV or a contract that is the worst thing this feature could produce.

Heading detection is inference, because plain text has no heading markup, and
it is written to fail towards *fewer* headings. A missed heading makes a
thinner exemplar; an invented one becomes a section in the generated document
that its author never had.
"""

from __future__ import annotations

import pytest

from attachments.compose import compose
from attachments.contracts import Attachment, AttachmentKind
from attachments.exemplar import REFERENCE_NOTE, outline_of, structure_line

PROPOSAL = """Production proposal

Scope of work

Harbour Lane has asked for a two-day shoot in March. This sets out what is
included and what it costs.

What is included

Two shooting days on location, ten hours each.

Fees

All figures in naira, exclusive of tax.

Terms

Half falls due on acceptance and the balance on delivery.
"""


def _attachment(text: str, name: str = "proposal.docx") -> Attachment:
    return Attachment(
        id="att-1",
        session_id="s",
        name=name,
        suffix=".docx",
        path="",
        text=text,
        parser="office",
        kind=AttachmentKind.DOCUMENT.value,
    )


class TestTheOutlineIsTheStructure:
    def test_the_sections_are_read_in_order(self):
        assert outline_of(PROPOSAL) == [
            "Production proposal",
            "Scope of work",
            "What is included",
            "Fees",
            "Terms",
        ]

    def test_markdown_headings_are_read(self):
        text = "# Summary\n\nWords here.\n\n## Fees\n\nMore words.\n"

        assert outline_of(text) == ["Summary", "Fees"]

    def test_numbering_is_kept(self):
        """"3.1 Payment" and "Payment" are different facts about the reference."""
        text = "1. Scope\n\nWords.\n\n3.1 Payment\n\nMore words.\n"

        assert outline_of(text) == ["1. Scope", "3.1 Payment"]

    def test_a_running_header_is_not_forty_sections(self):
        """A PDF repeats its header on every page; forty copies is not a shape."""
        text = "".join("Harbour Lane Ltd\n\nSome body text here.\n\n" for _ in range(40))

        assert outline_of(text).count("Harbour Lane Ltd") == 1


class TestItRefusesToInventStructure:
    def test_prose_produces_no_outline(self):
        """A wall of text has no shape, and saying so beats guessing one."""
        text = (
            "This is an ordinary letter with no headings in it at all. It runs "
            "on for a while, as letters do, and it says several things.\n\n"
            "It has a second paragraph, which is also just prose and is not a "
            "section of anything."
        )

        assert outline_of(text) == []

    def test_a_sentence_is_not_a_heading(self):
        """Terminal punctuation is the signal, a colon included.

        A colon introduces what follows it rather than naming a section, and
        admitting those is how an outline fills with the first line of every
        paragraph.
        """
        assert outline_of("Please note:\n\nSomething follows.\n") == []
        assert outline_of("We agreed the following.\n\nText.\n") == []

    def test_a_short_line_inside_a_paragraph_is_not_a_heading(self):
        """An address line, a name in a list — short, unpunctuated, not a section."""
        text = "Adaeze Okonkwo\n14 Bourdillon Road\nIkoyi, Lagos\n\nBody text.\n"

        assert "14 Bourdillon Road" not in outline_of(text)

    def test_an_empty_outline_produces_no_line(self):
        assert structure_line([]) == ""


class TestTheShapeReachesThePrompt:
    def test_the_structure_is_named_under_the_file(self):
        composition = compose([_attachment(PROPOSAL)], "write mine like this")

        assert "Its sections, in order: Production proposal · Scope of work" in (
            composition.block
        )

    def test_the_model_is_told_to_copy_the_shape_and_not_the_words(self):
        composition = compose([_attachment(PROPOSAL)], "write mine like this")

        assert REFERENCE_NOTE in composition.block
        assert "Never copy its sentences" in composition.block

    def test_a_file_with_no_shape_carries_no_instruction(self):
        """An instruction to follow a structure, under a file that has none,
        is an instruction to invent one."""
        composition = compose(
            [_attachment("Just some prose, at length, with no headings anywhere.")],
            "what does this say",
        )

        assert REFERENCE_NOTE not in composition.block
        assert "Its sections, in order" not in composition.block

    def test_the_outline_survives_a_document_too_long_to_read_whole(self):
        """The property that makes this worth having on a real file.

        `compose` selects passages by overlap with the question, so on a long
        reference the headings can be dropped from the excerpt entirely. The
        outline is taken from the full text before any of that happens — and
        this asserts it on a document big enough that the budget really bites.
        """
        filler = "\n\n".join(
            f"Paragraph {i} about scheduling, crews and equipment hire."
            for i in range(400)
        )
        # The question's rare terms appear once, deep in the filler and nowhere
        # near a heading — so selection has every reason to return that
        # paragraph and none of the sections. Without that the test passes
        # against an outline read from the excerpt, which is the thing it is
        # supposed to rule out. Checked by making exactly that change: it went
        # green, and the fixture was rewritten rather than the assertion.
        long_reference = (
            PROPOSAL
            + "\n\n"
            + filler
            + "\n\nThe zebra permit for the Ikoyi bridge was granted in February.\n"
        )

        composition = compose(
            [_attachment(long_reference)], "what about the zebra permit", budget_chars=900
        )

        assert composition.mode == "excerpt", "the fixture is not long enough to excerpt"

        # The excerpt itself, with the structure line taken back out — it names
        # the headings by definition, so leaving it in would make the next
        # assertion vacuous.
        excerpt = "\n".join(
            line
            for line in composition.block.splitlines()
            if not line.startswith("Its sections, in order:")
        )

        # The headings really are gone from what was read...
        assert "Scope of work" not in excerpt
        # ...and the shape survives anyway.
        assert "Its sections, in order: Production proposal · Scope of work" in (
            composition.block
        )

    def test_an_image_carries_no_outline(self):
        """A picture has no text to read a shape out of."""
        picture = Attachment(
            id="att-2",
            session_id="s",
            name="shot.png",
            suffix=".png",
            path="",
            text="",
            parser="image",
            kind=AttachmentKind.IMAGE.value,
        )

        composition = compose([picture], "what is this")

        assert composition.block == ""
