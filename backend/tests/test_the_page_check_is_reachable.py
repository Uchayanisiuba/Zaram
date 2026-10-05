"""The page check has a caller: an endpoint the interface can reach.

`CLAUDE.md` counts nineteen tested, unreachable subsystems. This one is asked
for by the renderer after a reply that wrote a page, so the route is asserted
to exist and to hand the page to the check -- not only that the check works.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

import main as main_module


def _routes():
    return {(r.path, tuple(sorted(r.methods or ()))) for r in main_module.app.routes if hasattr(r, "methods")}


def test_the_routes_exist():
    routes = _routes()
    assert ("/preview/check", ("POST",)) in routes
    assert ("/apps/save", ("POST",)) in routes


def test_the_endpoint_hands_the_page_to_the_check_and_returns_its_verdict(monkeypatch):
    from core import page_check

    seen = {}

    def fake(document):
        seen["doc"] = document
        return page_check.PageVerdict(checked=True, ok=False, errors=["boom (line 3)"])

    monkeypatch.setattr(page_check, "check_page", fake)
    out = asyncio.run(main_module.check_preview_page(main_module.PreviewCheckBody(html="<b>hi</b>")))
    assert seen["doc"] == "<b>hi</b>"
    assert out["ok"] is False and out["checked"] is True
    assert "boom (line 3)" in out["problems"][0]


def test_an_oversized_page_is_refused_before_a_browser_is_started(monkeypatch):
    from core import page_check

    def never(_):
        raise AssertionError("a browser was started for an oversized page")

    monkeypatch.setattr(page_check, "check_page", never)
    big = "x" * (page_check.MAX_DOCUMENT_BYTES + 1)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(main_module.check_preview_page(main_module.PreviewCheckBody(html=big)))
    assert caught.value.status_code == 413


def test_an_app_save_with_a_bad_path_is_a_400_with_the_reason(tmp_path, monkeypatch):
    monkeypatch.setenv("ZARAM_OUTPUT_DIR", str(tmp_path))
    body = main_module.SaveAppBody(
        name="x", files=[main_module.SaveAppFile(path="../escape.html", content="1")]
    )
    with pytest.raises(HTTPException) as caught:
        asyncio.run(main_module.save_app_folder(body))
    assert caught.value.status_code == 400
    assert "not a path" in caught.value.detail


def test_an_app_save_writes_a_folder_under_the_output_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("ZARAM_OUTPUT_DIR", str(tmp_path))
    body = main_module.SaveAppBody(
        name="Voxel World",
        files=[
            main_module.SaveAppFile(path="index.html", content="<html></html>"),
            main_module.SaveAppFile(path="game.js", content="1"),
        ],
    )
    out = asyncio.run(main_module.save_app_folder(body))
    assert (tmp_path / "apps" / "voxel-world" / "game.js").read_text() == "1"
    assert out["path"].endswith("voxel-world")
