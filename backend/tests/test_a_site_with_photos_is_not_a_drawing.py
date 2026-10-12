"""A website whose pictures are part of it is built, not drawn.

**Reported 12 October 2026.** *"Build a luxury resort website come up with the
name, style design, source the internet for images you need and when you are
done lunch your own browser"* -- and Zaram began generating an image. The
keyword planner read "images" and planned `image.generate`; "find photos online
for it" fared no better and planned a file search. The pictures in a site are
found by the photo pack while the page is written (`packs/photos`), so for such
a request the page is the whole job.

The line is **order**: the page named first, the pictures after it, is a page
with pictures in it. A picture named first -- "generate an image for my
website" -- is a drawing *for* a page, and stays a drawing. Both are pinned.
Keyword planner, no embedder: deterministic.
"""

from __future__ import annotations

import pytest

from core.open_project import set_open_project
from core.planner import IntentPlanner

REPORTED = (
    "Build a luxury resort website come up with the name, style desing , sorce the internet "
    "for photos you need and when you arew done lunch your own browser"
)
REPORTED_SECOND_TRY = (
    "Build a luxury resort website come up with the name, style design , source the internet "
    "for images you need and when you are done lunch your own browser"
)


@pytest.fixture(autouse=True)
def _search_on_no_project(monkeypatch):
    monkeypatch.setenv("ZARAM_WEB_SEARCH", "1")
    set_open_project(None)


def capabilities(text: str, *, repository_open: bool = False, has_images: bool = False) -> list[str]:
    planner = IntentPlanner()
    planner.set_code_project_open(lambda: repository_open)
    return [s.capability_id for s in planner.create_plan(text, has_images=has_images).steps]


@pytest.mark.parametrize("text", [
    REPORTED,
    REPORTED_SECOND_TRY,
    "Build a luxury resort website, find photos online for it",
    "make a tourism website for Lagos with real photos",
    "create a landing page for my bakery with pictures of bread",
])
def test_a_site_with_pictures_in_it_is_written_not_drawn(text):
    got = capabilities(text)
    assert "image.generate" not in got, got
    assert "filesystem.search" not in got, got
    assert got == ["reasoning.generate"], got


@pytest.mark.parametrize("text", [
    "generate an image for my website",
    "make a logo for my web app",
    "draw me a logo",
    "create a picture of a sunset",
])
def test_a_picture_asked_for_first_is_still_a_drawing(text):
    assert capabilities(text) == ["image.generate"], text


def test_with_a_repository_open_the_site_is_built_with_the_project_tools():
    """A page with a project open belongs in the project's files, which the
    code tools write -- never a drawing."""
    got = capabilities(REPORTED_SECOND_TRY, repository_open=True)
    assert "image.generate" not in got
    assert got[0] == "mcp.list_tools"


def test_the_photo_guidance_still_applies_to_the_request():
    """The other half: the chat route adds the photo guidance from the same words."""
    from packs.photos.page import wants_photos

    assert wants_photos(REPORTED_SECOND_TRY)
