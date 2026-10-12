"""A site request reaches the model with the photo instructions; a game does not.

`packs/photos` decides when a page wants real photographs and phrases what the
model is told. Its own tests prove the decision and the wording; this proves the
chat route actually puts it in front of the model -- the step a complete,
tested module can miss while every one of its tests passes -- and that the
photo routes are mounted on the running app.
"""

from __future__ import annotations

import importlib
import json
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from packs.photos.page import PHOTO_GUIDANCE


@pytest.fixture
def ask(monkeypatch, tmp_path):
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    main = importlib.import_module("main")
    seen: dict = {}

    async def stream(prompt, model, system_prompt, session_id, **kwargs):
        seen["system"] = system_prompt
        yield json.dumps({"type": "done", "data": {}}) + "\n"

    async def no_refusal(*_a, **_k):
        return None

    client = TestClient(main.app)

    def send(text, revise=None):
        body = {"persona": "zaram_prime", "text": text, "session_id": "photo-guidance"}
        if revise is not None:
            body["revise"] = revise
        with patch.object(main, "chat_router") as router, patch.object(
            main, "_vision_refusal", no_refusal
        ), patch.object(main, "_unplaceable_model_refusal", no_refusal):
            router.route.side_effect = stream
            router.execution_engine.last_answer.return_value = ""
            response = client.post("/chat", json=body)
        assert response.status_code == 200, response.text
        return seen["system"]

    return send


def test_a_tourism_site_is_told_to_describe_its_photos(ask):
    assert PHOTO_GUIDANCE in ask("Build a tourism website for Lagos with a gallery")


def test_a_game_built_from_a_tested_starter_is_not(ask):
    assert PHOTO_GUIDANCE not in ask("Make a Minecraft-style 3D game in HTML")


def test_any_other_page_is_offered_photos_and_the_model_decides(ask):
    """12 October 2026: offered on every page Zaram builds, not on a keyword
    guess about the subject. The guidance itself says a game or a tool usually
    needs none, and nothing is searched unless the page names a photo."""
    system = ask("Make a snake game in HTML")
    assert PHOTO_GUIDANCE in system
    assert "game, a tool" in PHOTO_GUIDANCE and "write none" in PHOTO_GUIDANCE


def test_a_drawn_picture_in_a_page_is_answered_honestly():
    assert "found, never drawn" in PHOTO_GUIDANCE


def test_a_question_is_not(ask):
    assert PHOTO_GUIDANCE not in ask("What is the capital of Nigeria?")


def test_changing_a_page_that_uses_photos_keeps_them(ask):
    system = ask(
        "make the header taller",
        revise={
            "question": "make the header taller",
            "reply": '```html\n<!doctype html><html><body><img src="photo:Lagos beach"></body></html>\n```',
        },
    )
    assert PHOTO_GUIDANCE in system


#: Mounting is asserted by asking, in `test_routes_are_mounted.py` -- this
#: FastAPI keeps an included router as one entry, so reading `app.routes` for
#: its paths would fail against a correctly mounted router.
