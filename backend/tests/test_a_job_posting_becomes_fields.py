"""A posting, read into fields — and the fields it refuses to invent.

The parser is the job-hunt pack's first slice and everything else stands on
it: a closing date cannot become an obligation, and a cover letter cannot name
the stack, until this works. So the claims graded here are the ones the rest
of the pack will depend on, and the sharpest of them is the negative one —
**"competitive salary" must not become a number**, because a number invented
here is laundered into a document three steps later, which is the failure rule
9 exists to prevent.

The postings below are written the way real ones are: labels on some lines and
not others, a title on the first line, a salary range in the middle of a
sentence, a deadline in whatever format the writer felt like.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from packs.jobs import Workplace, parse_posting

STUDIO = """Senior Technical Artist
Company: Northwind Interactive
Location: Manchester, UK
We are hiring a Senior Technical Artist to join our team. This is a hybrid
role, three days in the office.
You will work in Unreal Engine 5 and Maya, writing Python tools for the
animation pipeline, with some shader work in HLSL.
Salary: £60,000 - £75,000 per annum, depending on experience.
Closing date: 15 October 2026
Apply at https://northwind.example.com/careers/apply/1421
"""

VAGUE = """3D Generalist
Company: Harbour Studio
Fully remote.
Competitive salary, DOE. Great benefits and an annual bonus.
Blender and Substance Painter experience required.
"""


class TestTheFieldsItReads:
    def test_the_title_comes_off_the_first_line(self):
        assert parse_posting(STUDIO).title == "Senior Technical Artist"

    def test_labelled_fields_are_read(self):
        posting = parse_posting(STUDIO)

        assert posting.company == "Northwind Interactive"
        assert posting.location == "Manchester, UK"

    def test_seniority_is_named(self):
        assert parse_posting(STUDIO).seniority == "Senior"

    def test_the_skills_are_canonical_not_verbatim(self):
        # "Unreal Engine 5" and "UE5" are the same requirement; two spellings
        # would be two facts about one thing.
        skills = parse_posting(STUDIO).skills

        assert "Unreal Engine" in skills
        assert "Maya" in skills
        assert "Python" in skills
        assert "shaders" in skills

    def test_the_apply_link_is_preferred_over_any_other_url(self):
        assert parse_posting(STUDIO).apply_url.endswith("/apply/1421")


class TestWhereTheWorkHappens:
    """The field that decides whether an application is worth making at all."""

    def test_hybrid_is_not_read_as_remote(self):
        # A hybrid posting contains the word "remote" often enough that a
        # naive match reports it as remote — which sends somebody in another
        # country after a job requiring three days in Manchester.
        assert parse_posting(STUDIO).workplace == Workplace.HYBRID

    def test_fully_remote_is_remote(self):
        assert parse_posting(VAGUE).workplace == Workplace.REMOTE

    def test_silence_is_unknown_not_on_site(self):
        assert parse_posting("Character Artist\nCompany: Somewhere").workplace is None


class TestMoney:
    def test_a_range_is_read_with_its_currency_and_period(self):
        salary = parse_posting(STUDIO).salary

        assert salary is not None
        assert salary.currency == "GBP"
        assert salary.low == Decimal("60000")
        assert salary.high == Decimal("75000")
        assert salary.period == "year"

    def test_k_notation_is_the_same_number(self):
        salary = parse_posting("Role\nSalary: £60k - £75k per annum").salary

        assert salary is not None
        assert (salary.low, salary.high) == (Decimal("60000"), Decimal("75000"))

    def test_the_amounts_are_decimals_not_floats(self):
        # The invoice module's rule, applied here: a day rate that arrives as
        # 0.1000000000000000055 cannot be reconciled by hand.
        salary = parse_posting("Role\nRate: £550 per day").salary

        assert isinstance(salary.low, Decimal)
        assert salary.period == "day"

    def test_competitive_salary_stays_unknown(self):
        # The one that matters. A number here would reach a cover letter.
        assert parse_posting(VAGUE).salary is None

    def test_the_sentence_is_kept_as_the_evidence(self):
        salary = parse_posting(STUDIO).salary

        assert "£60,000" in salary.raw


class TestDeadlines:
    def test_a_named_month_is_read(self):
        assert parse_posting(STUDIO, today=date(2026, 9, 1)).closes == date(2026, 10, 15)

    def test_month_first_american_style_is_read(self):
        posting = parse_posting(
            "Role\nApplications close: October 15, 2026", today=date(2026, 9, 1)
        )

        assert posting.closes == date(2026, 10, 15)

    def test_an_iso_date_is_read(self):
        posting = parse_posting("Role\nDeadline: 2026-10-15", today=date(2026, 9, 1))

        assert posting.closes == date(2026, 10, 15)

    def test_a_slashed_date_is_read_day_first(self):
        # Recorded in the module docstring as a decision, not an accident:
        # 03/04/2026 is 3 April here.
        posting = parse_posting("Role\nCloses: 03/04/2026", today=date(2026, 1, 1))

        assert posting.closes == date(2026, 4, 3)

    def test_a_day_above_twelve_is_unambiguous_either_way(self):
        posting = parse_posting("Role\nCloses: 10/15/2026", today=date(2026, 1, 1))

        assert posting.closes == date(2026, 10, 15)

    def test_a_missing_year_means_the_next_one(self):
        # "Closes 15 October", read in November. The current year would be a
        # deadline already gone, which obligations would silently drop.
        posting = parse_posting("Role\nCloses: 15 October", today=date(2026, 11, 20))

        assert posting.closes == date(2027, 10, 15)

    def test_no_deadline_is_none(self):
        assert parse_posting(VAGUE).closes is None


class TestItNeverBreaksOnBadInput:
    def test_empty_text_is_an_empty_posting(self):
        posting = parse_posting("")

        assert posting.title == ""
        assert posting.salary is None

    def test_the_source_url_survives_an_empty_body(self):
        assert parse_posting("", source_url="https://example.com/x").source_url.endswith("/x")

    def test_an_impossible_date_is_refused_rather_than_raised(self):
        assert parse_posting("Role\nCloses: 31 February 2026").closes is None


class TestTheFactsItWouldStore:
    """One fact per claim, because rule 4 lets a person correct any one of
    them — and a single blob means correcting the salary deletes the date."""

    def test_each_claim_is_its_own_sentence(self):
        facts = parse_posting(STUDIO, today=date(2026, 9, 1)).facts()

        assert any("is hiring a Senior Technical Artist" in f for f in facts)
        assert any("close on 2026-10-15" in f for f in facts)
        assert any("hybrid" in f for f in facts)

    def test_nothing_unknown_is_stated(self):
        facts = parse_posting(VAGUE).facts()

        assert not any("close" in f for f in facts)
        assert not any("pay" in f for f in facts)


class TestFormatsTheFixturesAboveDidNotCover:
    """Found by probing, not by design — which is why they are here.

    The three fixtures at the top of this file were written by the same person
    who wrote the parser, so they agreed with it. Running two real-world
    shapes through it found three defects in a minute, and each one is a test
    now: a synthetic corpus that only contains what the author imagined is the
    instrument agreeing with itself.
    """

    LINKEDIN = """Technical Artist (Remote)
Ubisoft  Lagos, Nigeria (Remote)  2 weeks ago  Over 200 applicants

About the job
You will build tools in Python for Maya and Unreal Engine.
Pay range: $90,000/yr - $120,000/yr
"""

    PROSE = """Freelance 3D Animator needed for a six-week project starting in November.
The rate is 400 GBP per day and the work is fully remote. We use Blender.
Closing date: the 9th of November
"""

    def test_a_range_survives_a_period_suffix_on_each_half(self):
        # "$90,000/yr - $120,000/yr". The obvious regex reads 90,000 and stops
        # at the "/yr", reporting no upper bound — a range silently halved.
        salary = parse_posting(self.LINKEDIN).salary

        assert (salary.low, salary.high) == (Decimal("90000"), Decimal("120000"))
        assert salary.currency == "USD"
        assert salary.period == "year"

    def test_a_currency_written_as_a_code_is_read(self):
        # "400 GBP per day" — how pay is written in most of the world that
        # does not use a symbol, including the maintainer's own market.
        salary = parse_posting(self.PROSE).salary

        assert salary is not None
        assert salary.currency == "GBP"
        assert salary.low == Decimal("400")
        assert salary.period == "day"

    def test_a_title_that_is_really_a_sentence_is_trimmed(self):
        # Storing the whole sentence puts it in the subject line of a letter.
        assert parse_posting(self.PROSE).title == "Freelance 3D Animator"

    def test_a_date_written_with_of_is_read(self):
        posting = parse_posting(self.PROSE, today=date(2026, 9, 27))

        assert posting.closes == date(2026, 11, 9)


class TestTheEvidenceString:
    """`raw` is read back as prose, so it is trimmed like prose.

    It reaches a fact — "Northwind states the pay as …" — and from there a
    document. "states the pay as Salary: £60,000 per annum.." is the label and
    the line's punctuation leaking into a sentence somebody sends.
    """

    def test_the_label_is_not_part_of_the_figure(self):
        salary = parse_posting("Role\nSalary: £60,000 - £75,000 per annum.").salary

        assert salary.raw == "£60,000 - £75,000 per annum"

    def test_only_the_sentence_holding_the_figure_is_kept(self):
        posting = parse_posting(
            "Role\nWe are a small studio. The rate is £550 per day. Apply soon."
        )

        assert posting.salary.raw == "The rate is £550 per day"

    def test_the_fact_reads_as_a_sentence(self):
        facts = parse_posting("Role\nCompany: Northwind\nSalary: £550 per day.").facts()
        pay = [f for f in facts if "pay" in f]

        assert pay == ["Northwind states the pay as £550 per day."]
