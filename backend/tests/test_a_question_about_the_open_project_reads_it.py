"""A question about the project that is open is answered from the project.

**Reported 12 October 2026, with a screenshot.** The picker read *Ride Share*,
the project had a repository at `C:\\RideShare`, and *"What are the unfinished
tasks in Ride Share?"* came back as a web search: four facts about the
Zeigarnik effect and a reply telling the person to go and look in the folder
Zaram already had open. The question reads as a search, and the search plan
came before the plan that offers the repository's tools.

Pinned here, on the keyword planner (no embedder, deterministic):

* naming the open project, or saying "this project", plans the repository's
  tools and no web search;
* asking for the web in words still gets the web;
* with no project open, nothing changes;
* a project with no repository still does not send its own name to a search
  engine -- the answer comes from recall, scoped to the project.
"""

from __future__ import annotations

import pytest

from core.open_project import (
    about_the_open_project,
    names_the_project,
    open_project_name,
    set_open_project,
)
from core.planner import IntentPlanner

QUESTION = "What are the unfinished tasks in Ride Share?"


@pytest.fixture(autouse=True)
def _search_is_on_and_no_project(monkeypatch):
    """Search switched on, so a plan that wanted it would have planned it."""
    monkeypatch.setenv("ZARAM_WEB_SEARCH", "1")
    set_open_project(None)
    yield
    set_open_project(None)


def capabilities(plan) -> list[str]:
    return [s.capability_id for s in plan.steps]


def _planner(*, repository_open: bool) -> IntentPlanner:
    planner = IntentPlanner()
    planner.set_code_project_open(lambda: repository_open)
    return planner


# ------------------------------------------------------------- the question


class TestWhatCountsAsAboutTheProject:
    def test_the_name_matches_whatever_the_spacing_and_case(self):
        for text in (QUESTION, "what's left in rideshare", "Is RIDE-SHARE finished?"):
            assert names_the_project(text, "Ride Share"), text

    def test_a_reference_points_at_it(self):
        set_open_project("Ride Share")
        for text in ("what is left to do in this project", "does the app build", "summarise our repo"):
            assert about_the_open_project(text), text

    def test_asking_for_the_web_in_words_gets_the_web(self):
        set_open_project("Ride Share")
        for text in (
            "search online for ride share prices in Lagos",
            "look up ride share regulations on the web",
            "google ride share apps",
        ):
            assert not about_the_open_project(text), text

    def test_an_unrelated_question_is_not_about_it(self):
        set_open_project("Ride Share")
        assert not about_the_open_project("who won the match last night")

    def test_no_project_open_means_nothing_is_about_one(self):
        assert open_project_name() is None
        assert not about_the_open_project(QUESTION)

    def test_a_very_short_name_does_not_match_inside_words(self):
        assert not names_the_project("I want to go home", "Go")


# ------------------------------------------------------------------ the plan


class TestThePlan:
    def test_the_reported_question_is_not_a_web_search_without_a_project(self):
        """The baseline the report started from: it does read as a search."""
        plan = _planner(repository_open=False).create_plan(QUESTION)
        assert "knowledge.search" in capabilities(plan)

    def test_with_the_project_open_it_reads_the_repository_instead(self):
        set_open_project("Ride Share")
        plan = _planner(repository_open=True).create_plan(QUESTION)

        assert capabilities(plan) == ["mcp.list_tools", "reasoning.generate"]

    def test_this_project_is_read_the_same_way(self):
        set_open_project("Ride Share")
        plan = _planner(repository_open=True).create_plan("What are the latest unfinished tasks in this project?")

        assert "knowledge.search" not in capabilities(plan)
        assert capabilities(plan)[0] == "mcp.list_tools"

    def test_the_web_asked_for_by_name_is_still_searched(self):
        set_open_project("Ride Share")
        plan = _planner(repository_open=True).create_plan("search online for the latest ride share prices in Lagos")

        assert "knowledge.search" in capabilities(plan)

    def test_a_project_with_no_repository_does_not_send_its_name_to_a_search_engine(self):
        set_open_project("Ride Share")
        plan = _planner(repository_open=False).create_plan(QUESTION)

        assert "knowledge.search" not in capabilities(plan)
        assert "reasoning.generate" in capabilities(plan)

    def test_the_classification_does_not_claim_a_search_it_will_not_run(self):
        set_open_project("Ride Share")
        classification = _planner(repository_open=True)._router.classify(QUESTION)

        assert classification.requires_search is False


# --------------------------------------------------------------- the wiring


def test_the_chat_route_records_the_open_projects_name_and_clears_it(monkeypatch):
    import main

    class _Project:
        name = "Ride Share"
        type = None
        root = ""
        writes = runs = drives = shell = False

    monkeypatch.setattr(main.project_records, "get", lambda wanted: _Project())
    main._open_code_project("p1")
    assert open_project_name() == "Ride Share"

    main._open_code_project("")
    assert open_project_name() is None


def test_the_prompt_names_the_open_project_beside_its_folder(tmp_path):
    """The real `_recall_block`, as `test_this_project_means_the_open_repository.py`
    builds it: no kernel, the method taken from the class."""
    import time

    from core.execution_engine import ExecutionEngine
    from packs.code import set_active_root

    class _Record:
        content = "something remembered about other work"
        created_at = time.time()

    class _Result:
        record = _Record()

    engine = ExecutionEngine.__new__(ExecutionEngine)
    set_open_project("Ride Share")
    set_active_root(str(tmp_path))
    try:
        block = engine._recall_block([_Result()])
    finally:
        set_active_root(None)

    assert 'The project open is called "Ride Share"' in block
    assert block.index("other work") < block.index("Ride Share") < block.index("A repository is open at")
