"""A picture the person attaches can be used in what Zaram builds, not only looked at.

A page ("make me a portfolio site from these photos") and a document ("put my
passport photo on this form") both refer to a picture by a short name; the bytes
go in afterwards, on this machine, and never through a prompt. The window's half
of this (data: URIs in the preview and the saved page) is in
`frontend/src/lib/pagePictures.test.ts`.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import importlib
from unittest.mock import patch

import pytest
from PIL import Image
from starlette.testclient import TestClient

from artifacts.contracts import ImageBlock
from artifacts.markdown_blocks import blocks_from_markdown
from artifacts.records import ArtifactRecords
from artifacts.service import ArtifactService
from artifacts.store import ArtifactStore
from attachments import pictures
from attachments.contracts import Attachment
from attachments.store import AttachmentStore
from runtimes.documents.runtime import GENERATE, DocumentsRuntime


def _png(colour: str = "red", size: int = 8) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (size, size), colour).save(out, format="PNG")
    return out.getvalue()


def _webp() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(out, format="WEBP")
    return out.getvalue()


@pytest.fixture
def store(tmp_path):
    held = AttachmentStore(str(tmp_path / "attachments"))
    pictures.use_store(held)
    yield held
    pictures.use_store(None)


# ---- the name ---------------------------------------------------------------


class TestTheName:
    def test_a_safe_file_name_is_kept(self):
        assert pictures.page_name_for("Portrait.JPG", ".jpg", []) == "Portrait.jpg"

    def test_an_unsafe_one_becomes_a_numbered_name(self):
        # Spaces, accents and brackets would have to be repaired, and a repaired
        # name is one the person did not give.
        assert pictures.page_name_for("IMG 001 (1).jpg", ".jpg", []) == "photo-1.jpg"
        assert pictures.page_name_for("été.png", ".png", ["photo-1.png"]) == "photo-2.png"

    def test_a_name_in_use_is_not_given_twice_whatever_its_case(self):
        assert pictures.page_name_for("a.png", ".png", ["A.png"]) == "photo-1.png"

    def test_a_format_nothing_can_use_gets_no_name(self):
        assert pictures.page_name_for("passport.heic", ".heic", []) == ""

    def test_a_name_is_made_only_of_characters_safe_in_markup(self):
        for original in ["<script>.png", "a b.png", "../../x.png", 'x"y.png', "ünï.png"]:
            name = pictures.page_name_for(original, ".png", [])
            assert name.replace("-", "").replace(".", "").isalnum(), name

    def test_the_store_names_each_picture_once_and_tells_the_window(self, store):
        first, _ = store.add("s1", "IMG 1.png", _png("red"))
        second, _ = store.add("s1", "IMG 2.png", _png("green"))
        third, _ = store.add("s1", "IMG 1.png", _png("blue"))
        assert [first.page_name, second.page_name, third.page_name] == [
            "photo-1.png",
            "photo-2.png",
            "photo-3.png",
        ]
        assert first.to_dict()["page_name"] == "photo-1.png"

    def test_a_conversation_does_not_reserve_names_in_another(self, store):
        a, _ = store.add("s1", "x y.png", _png())
        b, _ = store.add("s2", "x y.png", _png())
        assert a.page_name == b.page_name == "photo-1.png"

    def test_a_document_has_no_name(self, store):
        item, _ = store.add("s1", "notes.txt", b"hello there")
        assert item.page_name == ""


# ---- what the model is told ---------------------------------------------------


class TestWhatTheModelIsTold:
    def _refs(self, store, *names):
        attached = [store.add("s1", n, _png())[0] for n in names]
        return pictures.refs_for(attached)

    def test_a_page_is_told_the_names_and_nothing_else_about_them(self, store):
        refs = self._refs(store, "IMG 1.png", "IMG 2.png")
        told = pictures.page_guidance(refs, seen=True)
        assert "photo-1.png" in told and "photo-2.png" in told
        assert "base64" not in told.replace("data: URLs", "")
        assert len(told) < 1500  # names, not pictures

    def test_bytes_never_enter_the_guidance(self, store):
        item, _ = store.add("s1", "IMG 1.png", _png("red", size=400))
        told = pictures.page_guidance(pictures.refs_for([item]), seen=True)
        assert item.data[:60] not in told
        assert "iVBOR" not in told

    def test_a_model_that_cannot_see_is_told_so(self, store):
        refs = self._refs(store, "IMG 1.png")
        assert "not shown the pictures" in pictures.page_guidance(refs, seen=False)
        assert "not shown the pictures" not in pictures.page_guidance(refs, seen=True)

    def test_a_model_that_cannot_see_still_places_the_picture(self, store):
        # Measured 11 October 2026: told to "ask rather than guess", a model
        # that cannot see asked what a hero photo showed instead of building
        # the page. It is told to place it and use a plain alt text.
        told = pictures.page_guidance(self._refs(store, "IMG 1.png"), seen=False)
        assert "Use them anyway" in told
        assert "Do not stop to ask" in told
        assert "ask rather than guess" not in told

    def test_a_format_a_browser_cannot_show_is_named_as_unusable(self, store):
        item, _ = store.add("s1", "scan.tif", _png())
        told = pictures.page_guidance(pictures.refs_for([item]), seen=True)
        assert "cannot go in a page: scan.tif" in told
        # ... though a document can carry it.
        assert "scan.tif" in pictures.document_guidance(pictures.refs_for([item]), seen=True)

    def test_nothing_attached_says_nothing(self):
        assert pictures.page_guidance([], seen=True) == ""
        assert pictures.document_guidance([], seen=True) == ""

    def test_a_document_is_told_how_to_place_one(self, store):
        told = pictures.document_guidance(self._refs(store, "IMG 1.png"), seen=True)
        assert "![passport photo](photo-1.png)" in told
        assert "never write its contents" in told


# ---- the chat route -----------------------------------------------------------


@pytest.fixture
def chat(monkeypatch, tmp_path):
    """The real route with the router replaced by one that records the prompt."""
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    main = importlib.import_module("main")
    seen: dict = {}

    async def stream(prompt, model, system_prompt, session_id, **kwargs):
        seen["system"] = system_prompt
        seen["images"] = kwargs.get("images")
        yield json.dumps({"type": "done", "data": {}}) + "\n"

    async def no_refusal(*_a, **_k):
        return None

    client = TestClient(main.app)
    session = "pictures-test-session"
    attached = []

    def attach(filename="IMG 1.png", data=None):
        response = client.post(
            "/chat/attachments",
            data={"session_id": session},
            files=[("files", (filename, data or _png(), "image/png"))],
        )
        assert response.status_code == 200, response.text
        attached.extend(response.json()["attached"])
        return response.json()["attached"][0]

    def ask(text):
        with patch.object(main, "chat_router") as router, patch.object(
            main, "_vision_refusal", no_refusal
        ), patch.object(main, "_unplaceable_model_refusal", no_refusal):
            router.route.side_effect = stream
            router.execution_engine.last_answer.return_value = ""
            response = client.post(
                "/chat",
                json={
                    "persona": "zaram_prime",
                    "text": text,
                    "session_id": session,
                    "attachment_ids": [a["id"] for a in attached],
                },
            )
        assert response.status_code == 200, response.text
        return seen["system"]

    yield attach, ask, client, session
    for item in attached:
        client.delete(f"/chat/attachments/{item['id']}")


class TestTheChatRoute:
    def test_a_page_request_with_a_picture_names_it(self, chat):
        attach, ask, _client, _session = chat
        item = attach()
        assert item["page_name"] == "photo-1.png"
        system = ask("make me a portfolio website using this photo")
        assert "photo-1.png" in system

    def test_the_pictures_themselves_are_not_in_the_prompt(self, chat):
        attach, ask, _client, _session = chat
        big = _png("red", size=300)
        attach(data=big)
        system = ask("make me a portfolio website using this photo")
        assert base64.b64encode(big).decode()[:80] not in system

    def test_a_question_that_is_not_a_page_is_not_told(self, chat):
        attach, ask, _client, _session = chat
        attach()
        assert "photo-1.png" not in ask("what colour is this")

    def test_a_page_request_with_nothing_attached_is_not_told(self, chat):
        _attach, ask, _client, _session = chat
        assert "attached these pictures" not in ask("make me a portfolio website")

    def test_the_picture_is_served_back_to_the_window_and_only_to_its_conversation(self, chat):
        attach, _ask, client, session = chat
        item = attach(data=_png("red"))
        served = client.get(f"/chat/attachments/{item['id']}/content", params={"session_id": session})
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/png"
        assert served.content == _png("red")
        other = client.get(f"/chat/attachments/{item['id']}/content", params={"session_id": "someone-else"})
        assert other.status_code == 404

    def test_a_document_is_never_served_back(self, chat):
        _attach, _ask, client, session = chat
        response = client.post(
            "/chat/attachments",
            data={"session_id": session},
            files=[("files", ("n.txt", b"private words", "text/plain"))],
        )
        item = response.json()["attached"][0]
        try:
            served = client.get(f"/chat/attachments/{item['id']}/content", params={"session_id": session})
            assert served.status_code == 404
        finally:
            client.delete(f"/chat/attachments/{item['id']}")


# ---- a document ----------------------------------------------------------------


def _held(name, data, media="image/png"):
    return {name.lower(): pictures.DocumentPicture(name, name, "att_x", data, media)}


class TestMarkdownPlacesAPicture:
    def test_a_paragraph_that_is_only_the_picture_carries_its_bytes(self):
        data = _png("red")
        placed: list[str] = []
        blocks = blocks_from_markdown(
            "## Photo\n\n![passport photo](photo-1.png)\n\nBelow it.",
            pictures=_held("photo-1.png", data),
            placed=placed,
        )
        images = [b for b in blocks if isinstance(b, ImageBlock)]
        assert len(images) == 1
        assert images[0].data == data and images[0].alt == "passport photo"
        assert placed == ["photo-1.png"]

    def test_a_path_in_front_of_the_name_is_ignored(self):
        blocks = blocks_from_markdown(
            "![x](images/PHOTO-1.png)", pictures=_held("photo-1.png", _png())
        )
        assert any(isinstance(b, ImageBlock) for b in blocks)

    def test_an_address_never_becomes_a_picture(self):
        blocks = blocks_from_markdown(
            "![x](https://evil.example/photo-1.png)", pictures=_held("photo-1.png", _png())
        )
        assert not any(isinstance(b, ImageBlock) for b in blocks)

    def test_a_name_nobody_attached_is_left_as_its_alt_text(self):
        blocks = blocks_from_markdown("![a cat](cat.png)", pictures=_held("photo-1.png", _png()))
        assert not any(isinstance(b, ImageBlock) for b in blocks)

    def test_a_picture_inside_a_sentence_is_not_placed(self):
        blocks = blocks_from_markdown(
            "See ![x](photo-1.png) here.", pictures=_held("photo-1.png", _png())
        )
        assert not any(isinstance(b, ImageBlock) for b in blocks)

    def test_without_pictures_nothing_changes(self):
        blocks = blocks_from_markdown("![x](photo-1.png)")
        assert not any(isinstance(b, ImageBlock) for b in blocks)


@pytest.fixture
def runtime(tmp_path):
    service = ArtifactService(
        ArtifactRecords(str(tmp_path / "artifacts.db")), ArtifactStore(tmp_path / "out")
    )
    return DocumentsRuntime(service)


class TestADocumentCarriesThePicture:
    def _make(self, runtime, store, answer, prompt="write a cover letter with my passport photo"):
        return asyncio.run(
            runtime.execute(
                GENERATE,
                {"prompt": prompt, "answer": answer, "session_id": "s1", "format": "html"},
            )
        )

    def test_the_attached_photo_is_in_the_file_with_its_real_bytes(self, runtime, store):
        data = _png("green", size=16)
        store.add("s1", "IMG 1.png", data)
        runtime.set_pictures(pictures.document_pictures_for_session)
        result = self._make(
            runtime, store, "# Cover letter\n\n![passport photo](photo-1.png)\n\nDear Sir,\n\n**Yours**"
        )
        assert result["success"], result
        html = open(result["artifact"]["path"], encoding="utf-8").read()
        assert base64.b64encode(data).decode() in html
        assert 'alt="passport photo"' in html

    def test_the_word_file_carries_it_too(self, runtime, store):
        import zipfile

        store.add("s1", "IMG 1.png", _png())
        runtime.set_pictures(pictures.document_pictures_for_session)
        result = asyncio.run(
            runtime.execute(
                GENERATE,
                {
                    "prompt": "write a cover letter",
                    "answer": "# Cover letter\n\n![me](photo-1.png)\n\nDear Sir,",
                    "session_id": "s1",
                    "format": "docx",
                },
            )
        )
        assert result["success"], result
        media = [n for n in zipfile.ZipFile(result["artifact"]["path"]).namelist() if "media/" in n]
        assert media, "the picture is not in the .docx"

    def test_a_picture_placed_first_does_not_become_the_title(self, runtime, store):
        store.add("s1", "IMG 1.png", _png())
        runtime.set_pictures(pictures.document_pictures_for_session)
        result = self._make(runtime, store, "![me](photo-1.png)\n\nDear Sir, here is my application.")
        assert result["success"], result
        assert "photo-1" not in result["artifact"]["filename"]

    def test_the_picture_is_recorded_as_a_source_the_person_supplied(self, runtime, store):
        store.add("s1", "IMG 1.png", _png())
        runtime.set_pictures(pictures.document_pictures_for_session)
        result = self._make(runtime, store, "# Letter\n\n![me](photo-1.png)\n\nText.")
        kinds = {(s["kind"], s["title"]) for s in result["artifact"]["sources"]}
        assert ("user_document", "IMG-1.png (picture you attached)") in kinds

    def test_a_conversations_pictures_are_not_another_conversations(self, runtime, store):
        store.add("s2", "IMG 1.png", _png())
        runtime.set_pictures(pictures.document_pictures_for_session)
        result = self._make(runtime, store, "# Letter\n\n![me](photo-1.png)\n\nText.")
        assert not [s for s in result["artifact"]["sources"] if s["kind"] == "user_document"]

    def test_a_format_a_document_cannot_hold_as_it_is_becomes_png(self, store):
        item, _ = store.add("s1", "cover.webp", _webp())
        (picture,) = pictures.document_pictures_for_session("s1")
        assert picture.media_type == "image/png"
        assert picture.data.startswith(b"\x89PNG")
        assert picture.name == item.page_name

    def test_a_spreadsheet_and_a_chart_have_nowhere_to_put_one(self, runtime):
        # An invoice, a CV and a deck take one in a field of their draft
        # (`test_a_picture_in_a_structured_document.py`); cells and a chart do not.
        assert runtime.places_pictures("write a cover letter")
        assert runtime.places_pictures("make me an invoice for Acme")
        assert runtime.places_pictures("make me a cv")
        assert not runtime.places_pictures("make me a spreadsheet of expenses")
        assert not runtime.places_pictures("draw a chart of sales")


class TestTheWritingStepIsTold:
    def _engine(self, names):
        from core.execution_engine import ExecutionEngine

        engine = ExecutionEngine.__new__(ExecutionEngine)
        engine._picture_names = names
        return engine

    def test_it_is_given_the_names_only(self, store):
        item, _ = store.add("s1", "IMG 1.png", _png())
        engine = self._engine(lambda session, request: pictures.refs_for([item]))
        told = engine._document_picture_guidance("s1", "write a letter", True)
        assert "photo-1.png" in told and item.data[:40] not in told

    def test_no_probe_no_guidance(self):
        assert self._engine(None)._document_picture_guidance("s1", "write a letter", True) == ""

    def test_a_failing_probe_does_not_fail_the_reply(self):
        def boom(*_a):
            raise RuntimeError("x")

        assert self._engine(boom)._document_picture_guidance("s1", "write a letter", True) == ""
