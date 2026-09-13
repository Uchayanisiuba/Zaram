"""A correction under a reply regenerates that reply — `docs/AGENT-UX.md`, *Revise*.

What the prompt must carry: which reply, the instruction to answer the
original question again in full, and the instruction to make the change in
the files where the earlier answer changed them. What it must not do: grow
without bound, or be a second way to generate — it goes down the ordinary
plan path, which the transport test at the bottom asserts by watching what
reaches the router.
"""

from __future__ import annotations

import importlib

import pytest
from starlette.testclient import TestClient

from core.revise import MAX_REPLY_CHARS, Revision, revision_prompt


class TestThePrompt:
    def test_it_names_the_reply_the_question_and_the_correction(self):
        prompt = revision_prompt(
            Revision(question="Add subtract to calc.py", reply="I added subtract(a, b) returning a - b."),
            "it should also accept negative numbers",
        )
        assert "Add subtract to calc.py" in prompt
        assert "subtract(a, b) returning a - b" in prompt
        assert "it should also accept negative numbers" in prompt
        # In full, as the answer, and in the files.
        assert "original question in full" in prompt
        assert "make the correction in those files" in prompt

    def test_a_long_reply_is_cut_and_said_to_be(self):
        prompt = revision_prompt(Revision(question="q", reply="x" * (MAX_REPLY_CHARS + 500)), "shorter")
        assert prompt.count("x") == MAX_REPLY_CHARS
        assert "the rest was longer than fits here" in prompt

    def test_a_short_reply_is_not_said_to_be_cut(self):
        assert "longer than fits" not in revision_prompt(Revision("q", "short"), "c")


def test_the_transport_composes_it_and_sends_it_down_the_ordinary_path(monkeypatch, tmp_path):
    """`chat_router.route` receives the composed prompt, not the bare correction,
    with no new flag - a revision is one exchange like any other."""
    import json
    from unittest.mock import patch

    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    main = importlib.import_module("main")
    seen: dict = {}

    async def stream(prompt, model, system_prompt, session_id, **kwargs):
        seen["prompt"] = prompt
        seen["kwargs"] = kwargs
        yield json.dumps({"type": "done", "data": {}}) + "\n"

    with patch.object(main, "chat_router") as router:
        router.route.side_effect = stream
        response = TestClient(main.app).post("/chat", json={
            "persona": "zaram_prime",
            "text": "it should also accept negatives",
            "session_id": "s",
            "revise": {"question": "add subtract", "reply": "added subtract(a, b)"},
        })
    assert response.status_code == 200, response.text
    assert "revising an earlier answer" in seen["prompt"]
    assert "add subtract" in seen["prompt"] and "it should also accept negatives" in seen["prompt"]
    assert "revise" not in seen["kwargs"]
