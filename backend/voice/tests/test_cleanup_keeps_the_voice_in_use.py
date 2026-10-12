"""The voice cache cleanup deletes only what it was asked to, and keeps the voice in use.

10 October 2026, found auditing a batch of changes. The route read `keep_voice` and
`dry_run` as query parameters while every caller sent a JSON body, so a request for a
preview was ignored and the defaults applied: delete, and keep `am_michael`. That is
the shipped default voice, and the wrong one to keep for anybody who chose another.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from voice.cleanup import resolve_keep_voice

MAIN = Path(__file__).resolve().parents[2] / "main.py"


def test_what_was_asked_is_kept():
    assert resolve_keep_voice("af_bella", "am_adam", "am_michael") == "af_bella"


def test_otherwise_the_voice_in_use_is_kept():
    assert resolve_keep_voice("", "am_adam", "am_michael") == "am_adam"
    assert resolve_keep_voice(None, "  am_adam ", "am_michael") == "am_adam"


def test_otherwise_the_shipped_default_is_kept():
    assert resolve_keep_voice(None, "", "am_michael") == "am_michael"


def test_with_nothing_to_keep_it_refuses_rather_than_keep_nothing():
    with pytest.raises(ValueError):
        resolve_keep_voice(None, "", "")


def _class(name: str) -> ast.ClassDef:
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == name)


def test_the_request_is_a_dry_run_unless_it_says_otherwise():
    fields = {
        n.target.id: n.value
        for n in _class("VoiceCacheCleanupBody").body
        if isinstance(n, ast.AnnAssign) and n.value is not None
    }
    assert isinstance(fields["dry_run"], ast.Constant) and fields["dry_run"].value is True


def test_the_route_reads_a_body_and_names_no_voice():
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    route = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "voice_cache_cleanup")
    assert [a.arg for a in route.args.args] == ["body"], "a query parameter is what no caller sent"
    assert "am_michael" not in ast.get_source_segment(MAIN.read_text(encoding="utf-8"), route)
