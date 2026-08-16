"""An invoice is a table of line items, not paragraphs about one.

The reported defect, in the maintainer's words: *"when asked to make an invoice,
an Excel spreadsheet or a PPT, Zaram simply creates an unformatted document of
your prompt, or a document of an error message."* All three parts were real and
all three had different causes:

* `create_invoice`, `create_spreadsheet` and `create_deck` existed, were tested,
  and were reachable only from `POST /artifacts/generate`. The conversation
  called `create_document` for every kind — so an invoice was the model's prose
  in a file named `invoice.docx`, with no table in it anywhere.
* `DECK` was not in the list of words that pick a kind, so "make me a
  PowerPoint" produced a `.docx`. The `.pptx` exporter worked throughout.
* In-band errors are text and this runtime writes text to disk, so failures
  became documents. The output directory on the maintainer's machine holds
  `error-400-client-error-bad-request-for-url-http-127-0-0-1-11.docx`.

These tests are about the wiring, so the extractor is a stub. Whether a 1.5B
model reads an answer into fields well is a separate question, measured against
real models — the same split as `test_identity.py` and
`test_identity_holds_across_models.py`.
"""

from __future__ import annotations

import json

import pytest

from artifacts.contracts import ArtifactKind
from artifacts.records import ArtifactRecords
from artifacts.service import ArtifactService
from artifacts.store import ArtifactStore
from runtimes.documents.runtime import GENERATE, DocumentsRuntime


@pytest.fixture
def runtime(tmp_path):
    service = ArtifactService(
        ArtifactRecords(str(tmp_path / "artifacts.db")), ArtifactStore(tmp_path / "out")
    )
    return DocumentsRuntime(service)


def _answering(payload: dict):
    """An extractor that returns one fixed object, as a model would."""
    return lambda prompt, system: json.dumps(payload)


INVOICE = {
    "bill_to": ["Harbour Lane Studio"],
    "currency": "£",
    "terms_days": 14,
    "items": [
        {"description": "Design work", "quantity": 3, "unit": "days", "unit_price": 400}
    ],
}


class TestAnInvoiceIsAnInvoice:
    async def test_it_is_built_from_line_items_rather_than_prose(self, runtime, tmp_path):
        runtime.set_extractor(_answering(INVOICE))

        result = await runtime.execute(
            GENERATE,
            {
                "prompt": "make me an invoice",
                "answer": "Three days of design work for Harbour Lane Studio at £400 a day.",
                "format": "html",
            },
        )

        assert result["success"], result.get("error")
        assert result["artifact"]["kind"] == ArtifactKind.INVOICE.value
        html = (tmp_path / "out" / result["artifact"]["filename"]).read_text(encoding="utf-8")
        # The shape, not the prose: a table, the rate, and a total the service
        # computed rather than the model.
        assert "<table" in html
        assert "Design work" in html
        assert "1,200" in html or "1200" in html

    async def test_the_total_is_computed_and_never_taken_from_the_model(
        self, runtime, tmp_path
    ):
        """The one number a client checks. `total_of` multiplies; a model
        producing a subtotal is a model guessing at multiplication."""
        wrong = {**INVOICE, "items": [{**INVOICE["items"][0], "unit_price": 400}]}
        runtime.set_extractor(_answering({**wrong, "subtotal": 999999}))

        result = await runtime.execute(
            GENERATE,
            {"prompt": "invoice please", "answer": "3 days at 400 for Harbour Lane.", "format": "html"},
        )

        html = (tmp_path / "out" / result["artifact"]["filename"]).read_text(encoding="utf-8")
        assert "999,999" not in html and "999999" not in html

    async def test_missing_prices_refuse_rather_than_produce_a_bill_with_a_hole(
        self, runtime
    ):
        runtime.set_extractor(
            _answering({"bill_to": ["Harbour Lane"], "items": [{"description": "Design work"}]})
        )

        result = await runtime.execute(
            GENERATE,
            {"prompt": "make me an invoice", "answer": "Some design work for Harbour Lane."},
        )

        assert result["success"] is False
        assert "line items" in result["error"]

    async def test_an_unnamed_client_refuses(self, runtime):
        runtime.set_extractor(_answering({**INVOICE, "bill_to": []}))

        result = await runtime.execute(
            GENERATE, {"prompt": "invoice", "answer": "Three days of design work at 400 a day."}
        )

        assert result["success"] is False
        assert "who it is for" in result["error"]

    async def test_no_extractor_refuses_rather_than_writing_prose(self, runtime):
        """The fallback that must not exist. Prose in a file called
        `invoice.docx` is worse than no file: the user believes they have one."""
        result = await runtime.execute(
            GENERATE, {"prompt": "make me an invoice", "answer": "Three days of design work at 400."}
        )

        assert result["success"] is False
        assert "invoice" in result["error"]


class TestPowerPointIsAPowerPoint:
    async def test_a_deck_request_no_longer_lands_as_a_word_document(
        self, runtime
    ):
        runtime.set_extractor(
            _answering({"slides": [{"heading": "Scope", "bullets": ["Three days"]}]})
        )

        result = await runtime.execute(
            GENERATE,
            {
                "prompt": "turn that into a PowerPoint",
                # What the execution engine sets when it has carried the recent
                # exchange forward. Without it "that" is unresolved and rule 9
                # refuses — correctly, and separately from anything here.
                "context_resolved": True,
                # Long enough to clear the thin-body guard, which is rule 9
                # working: a short fluent opener is what a model with no
                # context produces.
                "answer": (
                    "The scope is three days of design work for Harbour Lane "
                    "Studio, covering layout, revisions and final artwork."
                ),
            },
        )

        assert result["success"], result.get("error")
        assert result["artifact"]["kind"] == ArtifactKind.DECK.value
        assert result["artifact"]["filename"].endswith(".pptx")


class TestASpreadsheetHasRows:
    async def test_it_is_built_from_a_header_and_rows(self, runtime, tmp_path):
        runtime.set_extractor(
            _answering({"header": ["Item", "Days"], "rows": [["Design", "3"]]})
        )

        result = await runtime.execute(
            GENERATE,
            {"prompt": "as a spreadsheet", "answer": "Design took three days.", "format": "html"},
        )

        assert result["success"], result.get("error")
        html = (tmp_path / "out" / result["artifact"]["filename"]).read_text(encoding="utf-8")
        assert "<table" in html and "Design" in html

    async def test_prose_with_no_table_in_it_refuses(self, runtime):
        runtime.set_extractor(_answering({"header": [], "rows": []}))

        result = await runtime.execute(
            GENERATE,
            {
                "prompt": "make that an excel file",
                "context_resolved": True,
                "answer": (
                    "It went quite well overall, and the client was happy with "
                    "the direction we took on the second round of revisions."
                ),
            },
        )

        assert result["success"] is False
        assert "tabular" in result["error"]


class TestAFailureIsNotADocument:
    """`error-400-client-error-bad-request-for-url-http-127-0-0-1-11.docx` is a
    real file on a real machine. So is `error-the-request-to-192-168-1-170-was-
    cancelled.docx`."""

    @pytest.mark.parametrize(
        "body",
        [
            "[ERROR] 400 Client Error: Bad Request for url: http://127.0.0.1:11434/api/generate",
            "[FALLBACK] speech.tts failed: empty_text",
            "[WARN] something went sideways in a way worth mentioning here",
        ],
    )
    async def test_an_error_reply_is_never_written_to_disk(self, runtime, tmp_path, body):
        result = await runtime.execute(
            GENERATE, {"prompt": "write that up as a document", "answer": body}
        )

        assert result["success"] is False
        assert "error" in result["error"].lower()
        assert not list((tmp_path / "out").glob("*")), "a failure was written to disk"
