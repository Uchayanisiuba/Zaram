"""A page request gets a tested starting point, edits instead of rewrites, and no tool list.

11 October 2026, from a Minecraft-style game asked for across two days that never
played. Measured on the resident Qwen3.8-27B at 2.2 bits:

* the first draft froze on `for(let z=minZ; z<=maxZ; z)` and, with that mended,
  W/A/S/D all moved sideways and the player drifted with no key held -- a page
  the load check called "Ran without errors";
* each fix rewrote all 15,000 characters to change two;
* the reply was written against a 27,000-token prompt, 16,700 of them tools it
  never used, at half the speed the same model writes with a short one.

So: a starting point that has been played (`backend/starters`), changes as
SEARCH/REPLACE edits (`core/revise.py`, `core/page_guidance.py`, the window's
`pageEdits.ts`), and no tool listing on a turn that writes a page in the chat.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from core.page_guidance import PAGE_GUIDANCE, asks_to_build_a_page
from core.revise import MAX_CODE_REPLY_CHARS, Revision, revision_prompt
from starters import STARTERS, starter_for, starter_guidance


# ---------------------------------------------------------------- which turns


@pytest.mark.parametrize("text", [
    "Build a Minecraft-style 3D game in HTML that I can play in my browser",
    "Create a simple mine Craft game that can run on my browser",
    "Creaye a Mine craft game that is ligh weight enough to run of my browser",
    "make me a snake game",
    "Write a landing page for my bakery",
    "can you pls rewrite the entire app but include the corrections made",
    "Zaram ran this page before showing it, and it did not work:\n\n- boom",
    "Change one part of the page.\n\nThe part: <div>",
])
def test_a_request_to_make_a_page_is_one(text):
    assert asks_to_build_a_page(text)


@pytest.mark.parametrize("text", [
    "can you browse the internet via your own brower and open google.com",
    "open the game in my browser",
    "search the web for game reviews",
    "who won the game last night",
    "what is on this website https://example.com",
    "Open Notepad and type: Hello from Zaram",
    "build the project and run the tests",
    "write a proposal for Acme",
])
def test_everything_else_keeps_its_tools(text):
    assert not asks_to_build_a_page(text)


def test_a_revision_is_a_page_turn_only_when_it_carries_a_page():
    page = Revision(question="make a game", reply="```html\n<!DOCTYPE html><html><body></body></html>\n```")
    prose = Revision(question="write a letter", reply="Dear Ada, ...")
    assert asks_to_build_a_page(revision_prompt(page, "faster please"))
    assert not asks_to_build_a_page(revision_prompt(prose, "shorter please"))


def _engine(code_root):
    from core.execution_engine import ExecutionEngine

    engine = ExecutionEngine.__new__(ExecutionEngine)
    engine._code_root = lambda: code_root  # noqa: SLF001 - the one seam this asks about
    return engine


def test_a_page_in_the_chat_is_offered_no_tools():
    assert _engine(None)._writes_a_page_in_the_chat("Build a minecraft game in html", "s") is True


def test_text_read_from_an_attached_picture_does_not_decide_it():
    # Measured 11 October 2026: a screenshot's words ("HTML from this page ...
    # Make a 3D racing game") sat in front of "make me a portfolio website using
    # this photo", the detector read them, and the turn was offered tools and
    # came back empty. The block is composed exactly as the chat route does it.
    from attachments.compose import CLOSING_LINE

    block = (
        "=== TEXT READ FROM PICTURES ATTACHED TO THIS MESSAGE ===\n"
        "Read on this machine by its own text recogniser; cite it as the picture's.\n\n"
        "--- text read from my-photo.png (on this machine) ---\n"
        "HTML from this page Preview Code Select Pause Restart Save\n\n"
        "Make a 3D racing game I can play in my browser.\n" + CLOSING_LINE
    )
    prompt = f"{block}\n\nMake me a simple one-page portfolio website using this photo."
    assert _engine(None)._writes_a_page_in_the_chat(prompt, "s") is True


def test_own_words_leaves_a_plain_message_alone_and_strips_only_a_closed_block():
    from attachments.compose import CLOSING_LINE, own_words

    assert own_words("build a page") == "build a page"
    closed = f"=== FILES ATTACHED TO THIS MESSAGE ===\nbody\n\nmore\n{CLOSING_LINE}\n\nwhat I typed"
    assert own_words(closed) == "what I typed"
    # A block with no closing line is not guessed at.
    unclosed = "=== FILES ATTACHED TO THIS MESSAGE ===\nbody"
    assert own_words(unclosed) == unclosed


def test_with_a_project_open_the_page_belongs_in_its_files_and_the_tools_stay():
    assert _engine("C:/proj")._writes_a_page_in_the_chat("Build a minecraft game in html", "s") is False


# ------------------------------------------------------------ starting points


def test_a_voxel_request_is_offered_the_voxel_starting_point():
    for text in ("Build a Minecraft-style game", "make a voxel sandbox", "Creaye a Mine craft game", "a blocky world I can build in"):
        assert starter_for(text) is STARTERS["voxel-world"], text


def test_other_pages_and_from_scratch_requests_are_not():
    assert starter_for("make me a snake game") is None
    assert starter_for("a landing page for my bakery") is None
    assert starter_for("Build a Minecraft game from scratch") is None
    assert starter_for("make a voxel game without a template") is None


def test_the_starting_point_is_the_tested_file_and_carries_what_was_tested():
    code = STARTERS["voxel-world"].code()
    for part in ("SETTINGS", "function collides", "function moveAxis", "function pick", "requestPointerLock", "HOTBAR"):
        assert part in code, part
    # Never relies on pointer lock: the game starts in the click handler.
    assert "playing = true" in code.split("function start()")[1].split("}")[0]


def test_the_model_is_shown_the_code_first_and_told_what_to_do_last():
    text = starter_guidance(STARTERS["voxel-world"])
    code_at = text.index("function collides")
    assert text.index("Starting from: voxel-world") > code_at
    assert "SEARCH/REPLACE" in text[code_at:]
    assert text.rstrip().endswith("shows the result.")


def test_the_window_can_fetch_a_starting_point_by_name_only():
    import main

    client = TestClient(main.app, headers={"X-Zaram-Auth": main_secret()})
    ok = client.get("/starters/voxel-world")
    assert ok.status_code == 200 and ok.json()["code"] == STARTERS["voxel-world"].code()
    assert client.get("/starters/nothing").status_code == 404
    assert client.get("/starters/..%2Fmain").status_code == 404


def main_secret() -> str:
    from core.api_secret import api_secret

    return api_secret() or ""


# ------------------------------------------------------------------- edits


def test_a_page_revision_asks_for_edits_and_shows_the_whole_page():
    page = "```html\n<!DOCTYPE html><html><body>" + "x" * 60_000 + "</body></html>\n```"
    text = revision_prompt(Revision(question="make a game", reply=page), "the floor does not hold")
    assert "SEARCH/REPLACE" in text
    assert "x" * 60_000 in text, "a 60,000-character page must reach the model whole"
    assert MAX_CODE_REPLY_CHARS >= 100_000


def test_a_prose_revision_is_unchanged():
    text = revision_prompt(Revision(question="write a letter", reply="Dear Ada"), "warmer")
    assert "SEARCH/REPLACE" not in text and "in full" in text


def test_the_page_guidance_asks_for_edits_and_never_waits_for_pointer_lock():
    assert "SEARCH/REPLACE" in PAGE_GUIDANCE
    assert "never wait for it" in PAGE_GUIDANCE
    assert "W adds forward" in PAGE_GUIDANCE
    assert "whole updated page in one" not in PAGE_GUIDANCE
