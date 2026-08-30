""""Write my CV" produces a CV, not a proposal with a career inside it.

Before `ArtifactKind.CV` existed the request fell through to `DOCUMENT`, which
meant the generic prose layout: a ruled masthead, a metadata grid of reference
numbers and dates, and paragraphs. Every part of that is right for a proposal
and wrong here.

**A CV is read differently, so it is laid out differently.** A report is read
in order; a CV is scanned — an eye runs down the entries looking for a title or
a date and stops where something catches. That wants a dated column beside each
entry, tight spacing inside an entry and air between them, and nothing at the
top of the page competing with the person's name. It is not a variation on the
document layout; it is another one.

The other half is rule 9, and it bites harder here than almost anywhere. A CV
is a set of claims about a person, sent to someone deciding whether to employ
them. An invented employer is not a cosmetic error — it is the kind that ends
an application when it is caught and follows someone when it is not. So the
extractor refuses rather than completes, and the tests below say so in the two
places it matters: no name, and no content.
"""

from __future__ import annotations

import json

import pytest

from artifacts.contracts import ArtifactKind
from artifacts.extract import CvEntry, Missing, cv_from
from artifacts.html import render_cv
from artifacts.service import DEFAULT_FORMAT
from runtimes.documents.runtime import _kind_from

ENTRY = CvEntry(
    role="Producer",
    organisation="Harbour Lane",
    dates="2023 — present",
    bullets=["Ran the March shoot end to end."],
)


def _cv(**over) -> str:
    fields = dict(
        name="Adaeze Okonkwo",
        headline="Film and production",
        contact=["Lagos", "adaeze@example.com"],
        summary="Twelve years in production.",
        experience=[ENTRY],
        education=[CvEntry(role="BA Film", organisation="University of Lagos", dates="2014")],
        skills=["Editing", "Colour grading"],
    )
    fields.update(over)
    return render_cv(**fields)


class TestTheRequestReachesTheKind:
    @pytest.mark.parametrize(
        "prompt",
        [
            "write my CV",
            "put together a cv for me",
            "draft a curriculum vitae",
            "turn that into a résumé",
            "make a resume from my work history",
        ],
    )
    def test_a_cv_is_asked_for_by_several_names(self, prompt):
        assert _kind_from(prompt) is ArtifactKind.CV

    def test_two_letters_do_not_match_inside_a_word(self):
        """`in` matching would have made "cv" fire on any word containing it.

        The same defect `test_intent_word_boundaries.py` records one floor
        down, where "invoice" contained "voice" and routed every invoice
        request to text-to-speech.
        """
        assert _kind_from("summarise the mcvitie report") is ArtifactKind.DOCUMENT

    def test_it_is_written_as_a_word_file(self):
        """A CV is edited more than any other document a person owns."""
        assert DEFAULT_FORMAT[ArtifactKind.CV] == "docx"


class TestTheLayoutIsNotTheDocumentLayout:
    def test_there_is_no_masthead_over_the_name(self):
        """The letterhead of a CV is the person's name."""
        assert '<header class="masthead"' not in _cv()

    def test_there_is_no_metadata_grid(self):
        """Reference numbers and validity dates belong on a proposal."""
        assert '<dl class="meta"' not in _cv()

    def test_the_name_is_the_title(self):
        assert '<h1 class="cv-name">Adaeze Okonkwo</h1>' in _cv()

    def test_each_entry_keeps_its_dates_beside_it(self):
        html = _cv()

        assert '<div class="dates">2023 — present</div>' in html
        assert '<div class="role">Producer</div>' in html

    def test_an_entry_is_never_split_across_a_page(self):
        """A role on one page and its bullets on the next reads as two jobs."""
        assert "break-inside:avoid" in _cv()

    def test_dates_are_tabular_figures(self):
        """A column of years that does not align cannot be scanned."""
        assert "font-variant-numeric:tabular-nums" in _cv()


class TestNothingEmptyIsRendered:
    def test_a_section_with_no_entries_is_omitted(self):
        """A bare "Education" heading says something untrue about the person."""
        html = _cv(education=[])

        assert "Education" not in html
        assert "Experience" in html

    def test_an_entry_with_no_dates_leaves_no_gap(self):
        """An empty dates cell reads as a date somebody removed."""
        html = _cv(
            experience=[CvEntry(role="Producer", organisation="Harbour Lane")],
            education=[],
        )

        assert '<div class="dates">' not in html
        assert '<div class="role">Producer</div>' in html

    def test_provenance_stays_out_of_the_file(self):
        """This document goes to an employer.

        `memory:55b6` at the foot of a CV is internal working on a page where
        every line is already being read as a claim about the person. Same
        default as an invoice, and for the same reason.
        """
        assert "memory:" not in _cv()
        assert "Sources" not in _cv()


class TestItRefusesRatherThanInvents:
    @staticmethod
    def _ask(payload: dict):
        return lambda prompt, system="": json.dumps(payload)

    def test_a_cv_with_no_name_is_refused(self):
        """Heading a CV with the conversation's title is the worst outcome here.

        It puts one person's name over another person's career, in a document
        whose entire purpose is to be a claim about who someone is.
        """
        result = cv_from("...", "write my CV", self._ask({"experience": [{"role": "Producer"}]}))

        assert isinstance(result, Missing)
        assert "whose CV this is" in result.sentence("a CV")

    def test_a_cv_with_nothing_in_it_is_refused(self):
        result = cv_from("...", "write my CV", self._ask({"name": "Adaeze Okonkwo"}))

        assert isinstance(result, Missing)

    def test_an_entry_with_no_role_is_dropped_rather_than_dated(self):
        """A dated blank reads as a gap the person is hiding."""
        result = cv_from(
            "...",
            "write my CV",
            self._ask(
                {
                    "name": "Adaeze Okonkwo",
                    "experience": [
                        {"role": "Producer", "dates": "2023"},
                        {"organisation": "Somewhere", "dates": "2021 - 2022"},
                    ],
                }
            ),
        )

        assert not isinstance(result, Missing)
        assert [entry.role for entry in result.experience] == ["Producer"]

    def test_a_model_that_returns_nothing_usable_refuses(self):
        result = cv_from("...", "write my CV", lambda prompt, system="": "I'm not sure.")

        assert isinstance(result, Missing)
