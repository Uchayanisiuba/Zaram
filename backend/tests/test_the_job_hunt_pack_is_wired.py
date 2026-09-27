"""The job-hunt pack, from the tool the model calls to what it leaves behind.

`test_a_job_posting_becomes_fields.py` grades the parser, which is the right
level for that claim and exactly why it cannot see this one: a parser with no
caller is the eighteenth complete, tested, unreachable subsystem this codebase
has found. So this file grades the seam — the tool's own rules, what it files,
and what it refuses — plus the two things that must be true of the boot for it
to be reachable at all.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from packs.jobs import JobTools, RECORD_POSTING, SERVER_ID, cover_letter_blocks
from packs.jobs.letter import follow_up_blocks
from packs.jobs.posting import parse_posting

POSTING = """Senior Technical Artist
Company: Northwind Interactive
Location: Manchester, UK
This is a hybrid role. You will work in Unreal Engine 5 and Maya, writing
Python tools for the animation pipeline.
Salary: £60,000 - £75,000 per annum.
Closing date: 15 October 2026
Apply at https://northwind.example.com/careers/apply/1421
"""

TODAY = date(2026, 9, 27)


class Spine:
    """A stand-in for the Spine that records what it was told."""

    def __init__(self) -> None:
        self.facts: list[tuple[str, str]] = []

    def __call__(self, content: str, scope: str) -> None:
        self.facts.append((content, scope))


class Diary:
    def __init__(self) -> None:
        self.entries: list = []

    def __call__(self, entries):
        self.entries.extend(entries)
        return {"obligations": [f"obl_{i}" for i, _ in enumerate(entries)]}


def tools(spine=None, diary=None):
    return JobTools(
        remember=spine or Spine(),
        record_obligations=diary,
        today=lambda: TODAY,
    )


class TestTheToolSurface:
    def test_it_offers_exactly_one_verb(self):
        # A pack that grows a `submit` verb has left the scope `CLAUDE.md`
        # draws around it. One tool, and the test says which.
        assert [d.name for d in tools().list_tools()] == [RECORD_POSTING]
        assert tools().granted_tools() == {RECORD_POSTING}

    def test_the_server_has_a_name_the_bootstrapper_uses(self):
        assert SERVER_ID == "jobs"

    def test_an_unknown_tool_name_is_an_error_not_an_exception(self):
        # The loop hands errors back to the model to account for; an exception
        # would end the run.
        assert "error" in tools().call_tool("apply_for_job", {})


class TestWhatItFiles:
    def test_each_claim_becomes_its_own_fact(self):
        spine = Spine()
        result = tools(spine).record(POSTING, project_id="hunt-2026")

        assert result["success"] is True
        assert result["facts_stored"] == len(spine.facts)
        assert any("Senior Technical Artist" in f for f, _ in spine.facts)
        assert any("2026-10-15" in f for f, _ in spine.facts)

    def test_the_facts_are_scoped_to_the_hunt(self):
        # Rule 7i. A hunt's rejections must not leak into the next hunt's
        # letters, which is what a global scope would do.
        spine = Spine()
        tools(spine).record(POSTING, project_id="hunt-2026")

        assert {scope for _, scope in spine.facts} == {"project:hunt-2026"}

    def test_outside_a_project_the_scope_is_global_not_invented(self):
        spine = Spine()
        tools(spine).record(POSTING)

        assert {scope for _, scope in spine.facts} == {"global"}

    def test_the_summary_names_what_it_read(self):
        result = tools().record(POSTING)

        assert result["company"] == "Northwind Interactive"
        assert result["workplace"] == "hybrid"
        assert result["closes"] == "2026-10-15"
        assert "Unreal Engine" in result["skills"]

    def test_what_the_posting_did_not_say_is_not_stated(self):
        result = tools().record(
            "Character Artist\nCompany: Harbour Studio\n"
            + "We want a character artist for an unannounced title. Blender required. " * 3
        )

        assert result["pay"] == "not stated"
        assert result["closes"] == "not stated"


class TestTheDatesItSets:
    def test_the_closing_date_becomes_an_obligation(self):
        diary = Diary()
        tools(diary=diary).record(POSTING, project_id="hunt-2026")

        closing = [e for e in diary.entries if "close" in e.summary]
        assert closing and closing[0].due == date(2026, 10, 15)
        assert closing[0].scope == "project:hunt-2026"

    def test_a_follow_up_is_set_a_week_out(self):
        diary = Diary()
        tools(diary=diary).record(POSTING)

        follow = [e for e in diary.entries if "Follow up" in e.summary]
        assert follow and follow[0].due == TODAY + timedelta(days=7)

    def test_no_follow_up_after_the_posting_has_closed(self):
        # A reminder to chase something that is over is the noise that makes
        # somebody stop reading the list.
        diary = Diary()
        soon = POSTING.replace("15 October 2026", "30 September 2026")
        tools(diary=diary).record(soon)

        assert not [e for e in diary.entries if "Follow up" in e.summary]

    def test_nothing_is_dated_when_the_posting_gives_no_deadline(self):
        diary = Diary()
        tools(diary=diary).record(
            "3D Generalist\nCompany: Harbour Studio\n"
            + "Fully remote. Blender and Substance experience required. " * 4
        )

        assert diary.entries == []

    def test_direction_is_left_unknown(self):
        # Nobody owes anybody anything yet, and `Direction`'s own docstring
        # says guessing is the expensive kind of wrong.
        diary = Diary()
        tools(diary=diary).record(POSTING)

        assert all(e.direction.value == "unknown" for e in diary.entries)


class TestTheRefusals:
    def test_a_snippet_is_refused_rather_than_filed(self):
        result = tools().record("Senior Technical Artist at Northwind")

        assert "error" in result
        assert "too short" in result["error"]

    def test_a_posting_with_no_role_and_no_company_is_refused(self):
        # A record nothing can recognise later is worse than no record,
        # because recall will surface it and nobody will know what it means.
        result = tools().record("." + " We are hiring. Apply within. " * 10)

        assert "error" in result

    def test_a_refusal_files_nothing(self):
        spine, diary = Spine(), Diary()
        tools(spine, diary).record("too short")

        assert spine.facts == [] and diary.entries == []


class TestTheLetter:
    def test_it_is_addressed_and_referenced_from_the_posting(self):
        posting = parse_posting(POSTING, today=TODAY)
        blocks = cover_letter_blocks(
            posting, body=["I have ten years in games and film."], sender="Anisiuba Uche"
        )
        text = " ".join(str(getattr(b, "text", b)) for b in blocks)

        assert "Senior Technical Artist" in text
        assert "Dear Hiring Manager," in text
        assert "Anisiuba Uche" in text

    def test_a_letter_with_no_argument_says_so_on_the_page(self):
        # Visibly unfinished beats invented. An exception here would lose the
        # frame, which is correct.
        posting = parse_posting(POSTING, today=TODAY)
        text = " ".join(str(getattr(b, "text", b)) for b in cover_letter_blocks(posting, body=[]))

        assert "has not been written yet" in text

    def test_the_follow_up_says_when_and_what_and_stops(self):
        posting = parse_posting(POSTING, today=TODAY)
        blocks = follow_up_blocks(posting, applied_on=date(2026, 9, 20))
        text = " ".join(str(getattr(b, "text", b)) for b in blocks)

        assert "20 September" in text
        assert "Senior Technical Artist" in text
        # Short on purpose: a follow-up that restates the letter reads as a
        # second application.
        assert len(blocks) <= 7


class TestTheBootCanActuallyReachIt:
    """Registering is not reaching. Both of these were live defects."""

    def test_the_bootstrapper_can_resolve_run_sync(self):
        # `core/bootstrapper.py` referenced `run_sync` exactly once — inside
        # the draw pack's bridge — and imported it nowhere, so `draw_image`
        # raised NameError at call time while every test stayed green.
        import core.bootstrapper as bootstrapper

        assert hasattr(bootstrapper, "run_sync")

    def test_the_jobs_server_is_registered_at_boot(self):
        import inspect

        import core.bootstrapper as bootstrapper

        source = inspect.getsource(bootstrapper)
        assert "JobTools(" in source
        assert "JOBS_SERVER" in source

    def test_the_project_type_exists_so_the_pack_can_be_activated(self):
        from projects import ProjectType

        assert ProjectType("job_hunt") is ProjectType.JOB_HUNT
