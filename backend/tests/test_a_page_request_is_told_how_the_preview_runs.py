"""A model asked for a page is told what the preview can run.

5 October 2026: a "Block World" the resident model wrote could never be played
-- a three.js file that no longer exists, a start click swallowed by its own
overlay, a player who fell through the ground. `core/page_guidance.py` says
how to avoid each, and only when a page is what was asked for.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.page_guidance import PAGE_GUIDANCE, wants_page_guidance

FRONTEND_LIBRARIES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "previewLibraries.ts"


@pytest.mark.parametrize(
    "text",
    [
        "Create a 3d MineCraft game that can run on my browser",
        "build me a landing page in HTML",
        "make a three.js scene with a spinning cube",
        "write a snake game",
        "a website for my photography",
    ],
)
def test_a_page_request_gets_it(text):
    assert wants_page_guidance(text)


@pytest.mark.parametrize(
    "text",
    ["what do I owe this month", "summarise this contract", "hi", "", "the gamekeeper's invoice"],
)
def test_nothing_else_does(text):
    assert not wants_page_guidance(text)


def test_it_names_the_offline_addons_the_preview_actually_serves():
    # One list in two languages. If the preview stops serving an addon, a model
    # told it is available writes a page that cannot load it.
    served = re.findall(r"'((?:controls|math)/\w+)\.js'", FRONTEND_LIBRARIES.read_text(encoding="utf-8"))
    assert served, "could not read the preview's addon list"
    for path in served:
        assert path in PAGE_GUIDANCE, f"{path} is served offline and the model is not told"
    told = set(re.findall(r"\b((?:controls|math)/\w+)\b", PAGE_GUIDANCE))
    assert told == set(served)


def test_it_asks_for_urls_that_work_online_as_well_as_offline():
    # No pinned version: the saved file resolves the current release online,
    # and the preview serves its own copy for the same URL.
    assert "https://cdn.jsdelivr.net/npm/three/build/three.module.js" in PAGE_GUIDANCE
    assert "https://cdn.jsdelivr.net/npm/three/examples/jsm/" in PAGE_GUIDANCE
    assert "three@" not in PAGE_GUIDANCE
    assert "build/three.min.js; it no longer exists" in PAGE_GUIDANCE


def test_it_names_the_two_mistakes_that_made_the_game_unplayable():
    assert "put the listener on the start screen" in PAGE_GUIDANCE
    assert "smaller than one block" in PAGE_GUIDANCE


def test_it_names_no_model():
    # `CLAUDE.md`: build for the set of models, never for one.
    assert not re.search(r"qwen|gemma|llama|claude|gpt|mistral", PAGE_GUIDANCE, re.IGNORECASE)


def test_a_follow_up_to_a_page_gets_it_too():
    # "the floor collision doesn't work" names no page; the reply before it was one.
    page = "Here it is:\n```html\n<!doctype html><canvas></canvas>\n```"
    assert wants_page_guidance("the floor collision doesn't work", page)
    assert not wants_page_guidance("the floor collision doesn't work", "Your invoice is due Friday.")


def test_a_change_comes_back_as_edits_the_window_applies():
    # 5 October: loose changed lines nobody could run. 11 October: the whole page
    # again cost twenty minutes a change, so changes are SEARCH/REPLACE edits that
    # the window applies -- the person still gets the whole page to run.
    assert "SEARCH/REPLACE" in PAGE_GUIDANCE
    assert "the person still gets the whole page" in PAGE_GUIDANCE


def test_the_engine_reports_the_last_answer_of_a_session():
    from core.execution_engine import ExecutionEngine

    engine = ExecutionEngine.__new__(ExecutionEngine)
    engine._session_turns = {"s1": [("make a game", "```html\n<p>1</p>\n```")]}
    assert engine.last_answer("s1").startswith("```html")
    assert engine.last_answer("other") == ""


def test_it_asks_for_every_loop_to_be_re_read():
    # 5 October 2026: a page froze because `for(let i=0;i<16;i)` lost its `++`,
    # twenty-three times over. Any model can slip; the preview now refuses to
    # run such a page unasked, and this asks the model not to write one.
    assert "each `for` must change its counter" in PAGE_GUIDANCE


def test_it_describes_a_multi_file_app_without_a_project():
    # The maintainer asked for apps of several files with no project behind them.
    # The guidance has to tell the model how to label them, and that nothing
    # needs installing.
    from core.page_guidance import PAGE_GUIDANCE

    assert "Name each file on its fence line" in PAGE_GUIDANCE
    assert "```js src/world.js" in PAGE_GUIDANCE
    assert "no project, terminal or install step" in PAGE_GUIDANCE
    assert "Name the file on the line above each block" in PAGE_GUIDANCE


def test_it_asks_for_the_first_screen_before_heavy_work():
    # Voxel World built 361 chunks in one loop: ~6.6 s of blank page on the
    # maintainer's machine, before any menu.
    from core.page_guidance import PAGE_GUIDANCE

    assert "Draw the first screen" in PAGE_GUIDANCE
    assert "small pieces across frames" in PAGE_GUIDANCE


def test_it_tells_a_game_to_wait_for_the_player_and_not_to_replay_missed_time():
    # A snake game the resident model wrote set off at once and had hit the wall
    # before the first arrow key reached it. The page check passed it, because
    # nothing threw.
    from core.page_guidance import PAGE_GUIDANCE

    assert "A game waits for the player" in PAGE_GUIDANCE
    assert "do not move anything until the first key press or click" in PAGE_GUIDANCE
    assert "Never advance a game by the time since the page loaded" in PAGE_GUIDANCE
    assert "at most one move per frame" in PAGE_GUIDANCE


def test_it_tells_a_game_to_start_slow():
    # The same snake game started at a speed nobody could steer, then got faster.
    from core.page_guidance import PAGE_GUIDANCE

    assert "A game starts slow and gets harder" in PAGE_GUIDANCE
    assert "one move every 300 to 400 ms" in PAGE_GUIDANCE
    assert "has a floor" in PAGE_GUIDANCE
