"""Generating an invoice through the real route.

`test_invoice.py` grades the arithmetic. This grades the seam: that amounts
survive the wire as strings rather than being rounded by JSON on the way in,
that a refusal comes back as an actionable 400 rather than a crash, and that
the due date reaches the document from the terms instead of being typed twice.

The wire type is the part worth guarding. JSON has one number type and it is a
double, so `"unit_price": 0.1` arrives as 0.1000000000000000055…. The Decimal
inside is useless if the value is already damaged by the time it gets there.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """A backend writing to its own artifacts database and output directory."""
    import importlib

    monkeypatch = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("invoice-api")
    monkeypatch.setenv("ZARAM_ARTIFACTS_DB", str(root / "artifacts.db"))
    monkeypatch.setenv("ZARAM_PROJECTS_DB", str(root / "projects.db"))
    monkeypatch.setenv("ZARAM_OUTPUT_DIR", str(root / "generated"))

    import main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.app) as test_client:
        test_client.zaram_main = main_module  # type: ignore[attr-defined]
        yield test_client

    monkeypatch.undo()
    importlib.reload(main_module)


def invoice_body(**overrides):
    body = {
        "title": "Invoice — Northwind Studios",
        "kind": "invoice",
        "fmt": "html",
        "number": "INV-014",
        "issued": "2026-08-10",
        "terms_days": 30,
        "currency": "₦",
        "bill_to": ["Northwind Studios", "12 Harbour Lane", "Lagos"],
        "items": [
            {"description": "Design day", "quantity": "3", "unit_price": "450.00", "unit": "day"},
            {"description": "Revisions", "quantity": "1", "unit_price": "120.50"},
        ],
    }
    body.update(overrides)
    return body


def html_of(client, artifact_id: str) -> str:
    return client.get(f"/artifacts/{artifact_id}?include_html=true").json()["html"]


class TestGenerating:
    def test_it_produces_an_invoice_artifact(self, client):
        response = client.post("/artifacts/generate", json=invoice_body())

        assert response.status_code == 200, response.text
        artifact = response.json()
        assert artifact["kind"] == "invoice"
        assert artifact["size_bytes"] > 0

    def test_the_totals_are_on_the_page(self, client):
        artifact = client.post("/artifacts/generate", json=invoice_body()).json()

        html = html_of(client, artifact["id"])
        # 3 × 450.00 = 1,350.00, plus 120.50 = 1,470.50.
        assert "₦1,350.00" in html
        assert "₦1,470.50" in html
        assert "Total due" in html

    def test_the_due_date_comes_from_the_terms(self, client):
        """One number produces both, so they cannot disagree.

        This matters beyond tidiness: M9a's reminder *is* the due date, and the
        thing a client disputes is the printed sentence. Entered separately, a
        reminder could cite a clause that does not support it.
        """
        artifact = client.post("/artifacts/generate", json=invoice_body()).json()

        html = html_of(client, artifact["id"])
        assert "2026-09-09" in html  # 10 August + 30 days
        assert "within 30 days" in html

    def test_a_stated_tax_is_computed_and_labelled_as_given(self, client):
        # Zaram sums what it is told. It does not decide that VAT applies, and
        # holds no table of rates — CLAUDE.md forbids computing tax liability.
        artifact = client.post(
            "/artifacts/generate",
            json=invoice_body(adjustments=[{"label": "VAT 7.5%", "rate": "7.5"}]),
        ).json()

        html = html_of(client, artifact["id"])
        assert "VAT 7.5%" in html
        assert "₦110.29" in html  # 7.5% of 1,470.50
        assert "₦1,580.79" in html

    def test_provenance_stays_off_the_page(self, client):
        """A client has no use for `memory:…` under the total.

        It is internal working, it reads as unfinished, and it discloses how the
        figure was reached to someone who is not owed that. Traceability lives
        on the record and in Zaram's own preview.
        """
        artifact = client.post(
            "/artifacts/generate",
            json=invoice_body(
                sources=[{"kind": "memory", "title": "Their day rate"}],
                claims=[{"id": "c1", "source_id": "memory:1", "excerpt": "450 a day"}],
            ),
        ).json()

        html = html_of(client, artifact["id"])
        assert "<h2>Sources</h2>" not in html
        # …but the record still carries it, which is where rule 2 is satisfied.
        assert artifact["claims"][0]["source_id"] == "memory:1"


class TestRefusing:
    def test_no_lines_is_a_400_that_says_why(self, client):
        response = client.post("/artifacts/generate", json=invoice_body(items=[]))

        assert response.status_code == 400
        # Actionable, and written for a person. A 500 would present a correct,
        # deliberate refusal as a crash.
        assert "at least one line" in response.json()["detail"]

    def test_a_float_amount_is_refused_rather_than_rounded(self, client):
        """The wire type is the guard, and this is what it guards against.

        A JSON number is a double. Accepting one here would not fail — it would
        produce a total nobody can reproduce by hand, on a document that goes to
        a client.
        """
        response = client.post(
            "/artifacts/generate",
            json=invoice_body(items=[{"description": "Design day", "unit_price": 450.0}]),
        )

        assert response.status_code in (400, 422)

    def test_a_malformed_issue_date_is_a_400(self, client):
        response = client.post("/artifacts/generate", json=invoice_body(issued="10/08/2026"))

        assert response.status_code == 400
