"""With a coding project open, an ordinary question has the code tools offered.

Recorded in `docs/CODE-PACK.md` 3d, 7 September: "search the code for X"
classified as `filesystem.search` and "add a dark mode toggle" as conversation,
so the pack was reachable only by people who already knew to say "use the code
tools". The project decides that the tools are offered, not the phrasing — and
the intents that are about something else (a picture, a document, a search)
keep their own plans regardless.
"""

from __future__ import annotations

import pytest

from core.planner import IntentPlanner


PLAIN = [
    "add a dark mode toggle to the settings page",
    "search the code for resident_budget_bytes",
    "why does main.py crash on startup",
    "what does this project do",
]


def _ids(plan):
    return [step.capability_id for step in plan.steps]


class TestTheProjectDecides:
    @pytest.mark.parametrize("prompt", PLAIN)
    def test_open_the_tools_are_offered_first(self, prompt):
        planner = IntentPlanner()
        planner.set_code_project_open(lambda: True)

        assert _ids(planner.create_plan(prompt)) == ["mcp.list_tools", "reasoning.generate"]

    @pytest.mark.parametrize("prompt", PLAIN)
    def test_closed_nothing_changes(self, prompt):
        planner = IntentPlanner()
        planner.set_code_project_open(lambda: False)

        assert "mcp.list_tools" not in _ids(planner.create_plan(prompt))

    def test_untold_reads_as_closed(self):
        assert "mcp.list_tools" not in _ids(IntentPlanner().create_plan(PLAIN[0]))

    def test_a_drawing_is_still_a_drawing(self):
        planner = IntentPlanner()
        planner.set_code_project_open(lambda: True)
        assert _ids(planner.create_plan("draw me a picture of a lighthouse")) == ["image.generate"]

    def test_an_attached_image_is_still_answered_with_it(self):
        planner = IntentPlanner()
        planner.set_code_project_open(lambda: True)
        assert _ids(planner.create_plan("what is in this screenshot", has_images=True)) == ["reasoning.generate"]

    def test_a_broken_probe_reads_as_closed(self):
        planner = IntentPlanner()

        def boom():
            raise RuntimeError("no")

        planner.set_code_project_open(boom)
        assert "mcp.list_tools" not in _ids(planner.create_plan(PLAIN[0]))
