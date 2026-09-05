"""Structured document blocks, through the real route.

`test_documents_have_structure.py` grades the renderer and the service, which
is the right level for those claims and is exactly why it cannot see this one.

The precedent is `test_deck_api.py`, and it is worth restating because it is
the same trap: the `kind: "deck"` branch read a field the request model did not
have, every deck request came back as a 500, and the exporter tests stayed
green because none of them went through the wire. **A capability reachable only
from Python is not a capability the product has.**

So this file grades the seam between the request body and the renderer, and
nothing the other file already covers.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import importlib

    monkeypatch = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("blocks-api")
    monkeypatch.setenv("ZARAM_ARTIFACTS_DB", str(root / "artifacts.db"))
    monkeypatch.setenv("ZARAM_PROJECTS_DB", str(root / "projects.db"))
    monkeypatch.setenv("ZARAM_OUTPUT_DIR", str(root / "generated"))

    import main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.app) as test_client:
        yield test_client

    monkeypatch.undo()
    importlib.reload(main_module)


def _html(client, **overrides):
    body = {"title": "Proposal", "kind": "document", "blocks": []}
    body.update(overrides)
    response = client.post("/artifacts/generate", json=body)
    assert response.status_code == 200, response.text
    artifact_id = response.json()["id"]

    # `html` is omitted from the generate response — it is the re-export source
    # and a list of twenty documents would carry twenty full documents. Asking
    # for it back through the route is also the stronger assertion: it proves
    # the structure survived being *stored*, not merely rendered.
    stored = client.get(f"/artifacts/{artifact_id}", params={"include_html": True})
    assert stored.status_code == 200, stored.text
    return stored.json()["html"]


class TestStructureThroughTheWire:
    def test_a_heading_block_becomes_a_heading(self, client):
        html = _html(client, blocks=[{"type": "heading", "text": "Scope of Work"}])
        assert "<h2>Scope of Work</h2>" in html

    def test_a_list_block_becomes_a_list(self, client):
        html = _html(client, blocks=[{"type": "list", "items": ["one", "two"]}])
        assert "<ul><li>one</li><li>two</li></ul>" in html

    def test_a_table_block_becomes_a_table(self, client):
        html = _html(
            client,
            blocks=[{
                "type": "table",
                "header": ["Phase", "Amount"],
                "rows": [["Build", "1,020,000"]],
                "numeric_columns": [1],
            }],
        )
        assert '<th class="num">Amount</th>' in html
        assert "<td>Build</td>" in html

    def test_a_plain_string_is_still_a_paragraph(self, client):
        assert "<p>Just prose.</p>" in _html(client, blocks=["Just prose."])

    def test_the_masthead_fields_reach_the_document(self, client):
        html = _html(
            client,
            blocks=["Prose."],
            from_name="Northwind Studios",
            kind_label="Proposal",
            meta=[{"label": "Reference", "value": "PR-014"}],
        )
        assert "Northwind Studios" in html
        assert '<div class="kind">Proposal</div>' in html
        assert "<dt>Reference</dt><dd>PR-014</dd>" in html


class TestRefusals:
    """Rule 9, arriving through the request body rather than through the model."""

    def test_an_unknown_block_type_is_refused_not_flattened(self, client):
        # Rendering a block the caller meant as a chart into a line of prose
        # produces a document that is wrong in a way its author cannot see.
        response = client.post(
            "/artifacts/generate",
            json={"title": "P", "kind": "document",
                  "blocks": [{"type": "chart", "data": [1, 2]}]},
        )
        assert response.status_code == 400
        assert "unknown block type" in response.text

    def test_a_heading_may_not_claim_level_one(self, client):
        response = client.post(
            "/artifacts/generate",
            json={"title": "P", "kind": "document",
                  "blocks": [{"type": "heading", "text": "Rival", "level": 1}]},
        )
        assert response.status_code == 400
        assert "h1 is the title" in response.text

    def test_a_block_citing_an_unknown_claim_is_still_refused(self, client):
        response = client.post(
            "/artifacts/generate",
            json={"title": "P", "kind": "document", "blocks": [{"claim_id": "nope"}]},
        )
        assert response.status_code == 400


class TestMarkdownThroughTheWire:
    """The form a model actually produces, through the real route."""

    def test_markdown_becomes_a_structured_document(self, client):
        html = _html(
            client,
            title="Proposal",
            markdown=(
                "# Proposal\n\n## Scope\n\nA **three-phase** rollout.\n\n"
                "- Discovery\n- Build\n\n| Phase | Amount |\n|---|---|\n"
                "| Build | 1,020,000 |"
            ),
        )
        assert "<h2>Scope</h2>" in html
        assert "<strong>three-phase</strong>" in html
        assert "<ul><li>Discovery</li><li>Build</li></ul>" in html
        assert "<th>Phase</th>" in html
        assert "<h2>Proposal</h2>" not in html

    def test_raw_html_in_markdown_cannot_reach_the_stored_document(self, client):
        html = _html(client, markdown="Hello <script>alert(1)</script>")
        assert "<script>" not in html

    def test_sending_both_markdown_and_blocks_is_refused(self, client):
        # A caller that sent both had two intentions, and picking one by
        # precedence silently discards the other.
        response = client.post(
            "/artifacts/generate",
            json={
                "title": "P",
                "kind": "document",
                "markdown": "## A",
                "blocks": ["B"],
            },
        )
        assert response.status_code == 400
        assert "not both" in response.text
