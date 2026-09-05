"""Which installed models can read an answer into invoice fields.

`test_structured_documents.py` asserts the wiring with a stubbed extractor —
given fields, the right document is built. This asks the other half of the
question, which no stub can answer: **can the model the user actually has read
prose into those fields at all?**

It matters because the failure is silent in the good direction. When extraction
fails Zaram refuses, which is correct and is also indistinguishable, from the
user's chair, from the feature not working. So the number that decides whether
this is finished is *how many of the installed models can do it*, and that has
to be measured rather than assumed — the first live run refused on
`qwen2.5-coder:1.5b`, which was the model selected in Settings at the time.

Off by default for the same reason as the identity measurement: it loads every
chat model in turn. Enable deliberately::

    $env:ZARAM_LIVE_MODELS='1'; .venv\\Scripts\\python.exe -m pytest \\
        backend/tests/test_extraction_across_models.py -v

**A skip here is a finding, not a pass.** A model that cannot do this is a model
that cannot make an invoice from a conversation, and the skip reason says so in
those words.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import pytest

from artifacts.extract import Missing, invoice_from

OLLAMA = "http://127.0.0.1:11434"

#: An answer of the shape the conversation actually produces, with everything an
#: invoice needs stated in it and nothing pre-structured. Prose on purpose:
#: extraction that only works on a table is extraction that only works when it
#: was not needed.
ANSWER = (
    "Here's the summary for Harbour Lane Studio. You spent three days on the "
    "design work at a rate of 400 per day, which comes to 1,200 in total. "
    "The agreed terms are payment within 14 days of the invoice date."
)

REQUEST = "Make me an invoice for that"


def _installed_chat_models() -> list[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=2) as response:
            payload = json.loads(response.read())
    except (urllib.error.URLError, OSError, ValueError):
        return []
    names = [m.get("name", "") for m in payload.get("models", [])]
    return [n for n in names if n and "embed" not in n and "bge" not in n]


def _ask_via(model: str):
    def ask(prompt: str, system: str) -> str:
        body = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "keep_alive": "30s",
                # Extraction is a reading, not a composition. Sampling adds
                # nothing and costs valid JSON.
                "options": {"temperature": 0},
            }
        ).encode()
        request = urllib.request.Request(
            f"{OLLAMA}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read()).get("response", "")

    return ask


live_only = pytest.mark.skipif(
    os.environ.get("ZARAM_LIVE_MODELS") != "1",
    reason="loads every installed model; set ZARAM_LIVE_MODELS=1 to run",
)


@live_only
@pytest.mark.parametrize("model", _installed_chat_models() or ["none-installed"])
def test_the_model_can_read_an_answer_into_invoice_fields(model: str):
    if model == "none-installed":
        pytest.skip("no Ollama chat models installed")

    draft = invoice_from(ANSWER, REQUEST, _ask_via(model))

    if isinstance(draft, Missing):
        pytest.skip(
            f"{model} cannot extract invoice fields from prose "
            f"(missing: {draft.fields or 'produced no usable JSON'}). "
            f"Zaram refuses rather than inventing, so this model can answer "
            f"questions but cannot make an invoice from a conversation."
        )

    assert draft.bill_to, f"{model} lost the client"
    assert "harbour" in " ".join(draft.bill_to).lower(), draft.bill_to
    assert len(draft.items) == 1, f"{model} produced {len(draft.items)} lines: {draft.items}"

    item = draft.items[0]
    # The two numbers a client checks. Read as text, never as floats — see
    # `_amount` for why money and binary floats do not mix.
    assert float(item["quantity"]) == 3, item
    assert float(item["unit_price"]) == 400, item
    # The total is computed by `total_of`, so a model restating 1,200 must not
    # have smuggled it in as a fourth line item.
    assert "1200" not in str(item["unit_price"]).replace(",", "")
