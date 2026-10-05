"""`scripts/compare_thinking.py` -- the parts that do not need a model.

It is the instrument that decides a default, so its folding and its summary are
tested: an instrument that miscounts decides wrongly with a straight face.
"""

from __future__ import annotations

import json

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from compare_thinking import first_page, read_stream, summarise  # noqa: E402


def line(kind, **data):
    return json.dumps({"type": kind, "data": data})


def test_a_stream_folds_into_reply_thinking_and_errors():
    out = read_stream(
        [
            line("reasoning", content="abc"),
            line("reasoning", content="de"),
            line("token", content="Here: "),
            line("token", content="```html\n<p>x</p>\n```"),
            "",
            "not json",
            line("error", message="boom"),
        ]
    )
    assert out["reasoning_chars"] == 5
    assert out["reply"].startswith("Here: ```html")
    assert out["errors"] == ["boom"]


def test_the_first_page_is_found_and_an_empty_block_is_not_a_page():
    assert first_page("a\n```html\n<b>1</b>\n```\n```html\n<i>2</i>\n```").strip() == "<b>1</b>"
    assert first_page("```html\n  \n```") is None
    assert first_page("no code") is None
    assert first_page("```html index.html\n<p>x") == "<p>x"  # a block still being written


def test_the_summary_counts_what_it_says():
    rows = [
        {"page": True, "checked": True, "ok": True, "hung": False, "seconds": 10, "reasoning_chars": 100},
        {"page": True, "checked": True, "ok": False, "hung": True, "seconds": 30, "reasoning_chars": 300},
        {"page": False, "seconds": 20, "reasoning_chars": 200},
        {"page": True, "checked": False, "ok": None, "seconds": 40, "reasoning_chars": 0},
    ]
    s = summarise(rows)
    assert s["runs"] == 4 and s["wrote_a_page"] == 3 and s["checked"] == 2
    assert s["clean"] == 1 and s["hung"] == 1
    assert s["median_seconds"] == 25.0
    assert s["median_thinking_chars"] == 150
    # A page that could not be run is not counted as clean.
    assert s["clean"] < s["wrote_a_page"]
