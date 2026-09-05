"""Asking for slides through the real route.

`test_export_pptx.py` grades the exporter: that headings are slide boundaries,
so any document Zaram has already generated can be shown as a deck. It calls
`render_deck` directly, which is the right level for that claim and is also
exactly why it could not see this one.

**The route branch for `kind: "deck"` read a field the request model did not
have.** Every deck request raised `AttributeError`, was caught by the endpoint's
last-resort handler and came back as a 500 — while the exporter tests stayed
green, because none of them went through the wire. A capability reachable only
from Python is not a capability the product has.

So this grades the seam, and nothing the other file already covers.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """A backend writing to its own artifacts database and output directory."""
    import importlib

    monkeypatch = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("deck-api")
    monkeypatch.setenv("ZARAM_ARTIFACTS_DB", str(root / "artifacts.db"))
    monkeypatch.setenv("ZARAM_PROJECTS_DB", str(root / "projects.db"))
    monkeypatch.setenv("ZARAM_OUTPUT_DIR", str(root / "generated"))

    import main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.app) as test_client:
        yield test_client

    monkeypatch.undo()
    importlib.reload(main_module)


def deck_body(**overrides):
    body = {
        "title": "Northwind — Q3",
        "kind": "deck",
        "slides": [
            {"heading": "What we agreed", "bullets": ["Three design days", "Revisions included"]},
            {"heading": "Next", "bullets": []},
        ],
    }
    body.update(overrides)
    return body


class TestGenerating:
    def test_a_deck_request_produces_a_deck(self, client):
        """The regression. This came back 500 before `slides` reached the model."""
        response = client.post("/artifacts/generate", json=deck_body())

        assert response.status_code == 200, response.text
        artifact = response.json()
        assert artifact["kind"] == "deck"
        assert artifact["size_bytes"] > 0

    def test_the_default_format_is_pptx(self, client):
        """The reason the kind exists at all.

        A deck is not a separate pipeline — it is a document whose headings are
        slides. What `kind: "deck"` buys is that the file written by default is
        the one the user meant, without them naming a format.
        """
        artifact = client.post("/artifacts/generate", json=deck_body()).json()

        assert artifact["filename"].endswith(".pptx")

    def test_the_slides_reach_the_file(self, client):
        """Through the route, opened as PowerPoint would open it."""
        pptx = pytest.importorskip("pptx")

        artifact = client.post("/artifacts/generate", json=deck_body()).json()
        downloaded = client.get(f"/artifacts/{artifact['id']}/download")
        assert downloaded.status_code == 200

        titles = [
            slide.shapes.title.text
            for slide in pptx.Presentation(io.BytesIO(downloaded.content)).slides
        ]
        assert "What we agreed" in titles
        # A heading with no bullets is a section marker and stays a slide.
        assert "Next" in titles

    def test_the_outline_is_what_gets_previewed(self, client):
        """One `<h2>` per slide — the same HTML any document has.

        Worth asserting through the route because it is the claim that keeps
        this from being a second authoring path: if the preview were a private
        deck format, the exporter's headings-are-slides property would be a
        coincidence rather than the design.
        """
        artifact = client.post("/artifacts/generate", json=deck_body(fmt="html")).json()

        html = client.get(f"/artifacts/{artifact['id']}?include_html=true").json()["html"]
        assert "<h2>What we agreed</h2>" in html
        assert "<li>Three design days</li>" in html
