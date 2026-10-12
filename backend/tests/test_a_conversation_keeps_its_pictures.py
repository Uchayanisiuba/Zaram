"""A conversation keeps the pictures it was about, so its pages still show them.

An attached picture is working state and dies with the session. A page the model
wrote from it refers to it by name, so after a restart -- or when the
conversation is reopened from History -- the page was full of grey placeholders.
Now the pictures that went with a message are copied beside the conversation
(`conversations/pictures.py`) and noted on the stored message (names and ids,
never bytes).

What these tests hold to: kept on send; recorded without bytes; served only to
the conversation that owns them; removed with the conversation; bounded by a
ceiling that prunes least-recently-used first; removable on their own; given back
to a resumed session for naming and placing; and never in the Spine, which is
rule 7d (`conversations/records.py` and `pictures.py` say why).
"""

from __future__ import annotations

import ast
import io
import json
import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from conversations import ConversationRecords
from conversations import api as conversations_api
from conversations.pictures import ConversationPictures, media_type_of


def _png(colour: str = "red", size: int = 8) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (size, size), colour).save(out, format="PNG")
    return out.getvalue()


CONV = "conv_0123456789ab"
OTHER = "conv_ba9876543210"
ATT = "att_0123456789ab"
ATT2 = "att_ba9876543210"


# ---- the folder ---------------------------------------------------------------


@pytest.fixture
def folder(tmp_path):
    return ConversationPictures(str(tmp_path / "kept"))


class TestTheFolder:
    def test_a_kept_picture_comes_back_byte_for_byte(self, folder):
        data = _png("green")
        assert folder.keep(CONV, ATT, ".png", data)
        assert folder.has(CONV, ATT)
        assert folder.read(CONV, ATT) == data
        assert folder.ids(CONV) == [ATT]

    def test_another_conversation_cannot_read_it(self, folder):
        folder.keep(CONV, ATT, ".png", _png())
        assert folder.read(OTHER, ATT) is None
        assert not folder.has(OTHER, ATT)

    @pytest.mark.parametrize(
        "conversation, attachment, suffix",
        [
            ("../escape", ATT, ".png"),
            ("conv_../../x", ATT, ".png"),
            (CONV, "../../att_0123456789ab", ".png"),
            (CONV, "att_0123456789ab/../../x", ".png"),
            (CONV, ATT, "/../x"),
            (CONV, ATT, ".png/../../x"),
            ("", ATT, ".png"),
            (CONV, "", ".png"),
        ],
    )
    def test_an_id_that_is_a_path_trick_keeps_and_reads_nothing(
        self, folder, tmp_path, conversation, attachment, suffix
    ):
        assert folder.keep(conversation, attachment, suffix, _png()) is False
        assert folder.read(conversation, attachment) is None
        # Nothing was written anywhere under the temp directory but the folder.
        written = [p for p in tmp_path.rglob("*") if p.is_file()]
        assert written == []

    def test_nothing_is_kept_for_no_bytes(self, folder):
        assert folder.keep(CONV, ATT, ".png", b"") is False
        assert folder.ids(CONV) == []

    def test_removing_a_conversation_removes_only_what_this_store_wrote(self, folder, tmp_path):
        folder.keep(CONV, ATT, ".png", _png())
        folder.keep(CONV, ATT2, ".jpg", _png())
        folder.keep(OTHER, ATT, ".png", _png())
        stranger = tmp_path / "kept" / CONV / "notes.txt"
        stranger.write_text("not ours")

        files, size = folder.remove_conversation(CONV)

        assert files == 2 and size > 0
        assert folder.ids(CONV) == []
        # Another conversation is untouched, and so is a file this store did not
        # write -- which also keeps its folder, because a folder goes only when empty.
        assert folder.ids(OTHER) == [ATT]
        assert stranger.read_text() == "not ours"

    def test_removing_when_nothing_was_kept_is_not_an_error(self, folder):
        assert folder.remove_conversation(CONV) == (0, 0)
        assert folder.remove_conversation("../nope") == (0, 0)

    def test_the_default_folder_follows_the_data_directory_set_after_it_was_built(
        self, tmp_path, monkeypatch
    ):
        # `main.py` builds the store at import; a test run that moves the data
        # directory afterwards once wrote photographs into the checkout.
        built = ConversationPictures()
        monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
        assert built.keep(CONV, ATT, ".png", _png())
        assert (tmp_path / "conversation-pictures" / CONV / f"{ATT}.png").is_file()

    def test_the_media_type_is_read_from_the_bytes(self):
        assert media_type_of(_png()) == "image/png"
        assert media_type_of(b"not a picture") is None


class TestTheCeiling:
    """The ceiling prunes whole conversations, least recently used first."""

    def _age(self, folder_path, conversation, age_seconds):
        stamp = time.time() - age_seconds
        for path in (Path(folder_path) / conversation).iterdir():
            os.utime(path, (stamp, stamp))

    def test_the_default_ceiling_is_a_gigabyte(self):
        from conversations import pictures

        assert pictures.MAX_TOTAL_BYTES == 1024 * 1024 * 1024

    def test_the_oldest_conversation_loses_its_pictures_first(self, tmp_path):
        root = tmp_path / "kept"
        folder = ConversationPictures(str(root), max_total_bytes=250)
        blob = b"\x89PNG\r\n\x1a\n" + b"x" * 92  # 100 bytes
        folder.keep(CONV, ATT, ".png", blob)
        self._age(root, CONV, 3000)
        folder.keep(OTHER, ATT, ".png", blob)
        self._age(root, OTHER, 2000)
        assert folder.total_bytes() == 200

        third = "conv_aaaaaaaaaaaa"
        folder.keep(third, ATT, ".png", blob)  # 300 > 250

        assert folder.ids(CONV) == []  # the oldest went, whole
        assert folder.ids(OTHER) == [ATT]
        assert folder.ids(third) == [ATT]
        assert folder.total_bytes() <= 250

    def test_a_conversation_in_use_outlasts_an_older_one_it_was_kept_after(self, tmp_path):
        root = tmp_path / "kept"
        folder = ConversationPictures(str(root), max_total_bytes=250)
        blob = b"\x89PNG\r\n\x1a\n" + b"x" * 92
        folder.keep(CONV, ATT, ".png", blob)
        self._age(root, CONV, 3000)
        folder.keep(OTHER, ATT, ".png", blob)
        self._age(root, OTHER, 2000)
        # The older one is opened and its picture shown: that is use.
        assert folder.read(CONV, ATT) == blob

        folder.keep("conv_aaaaaaaaaaaa", ATT, ".png", blob)

        assert folder.ids(OTHER) == []
        assert folder.ids(CONV) == [ATT]

    def test_the_conversation_being_written_to_is_never_the_one_pruned_for_others(self, tmp_path):
        folder = ConversationPictures(str(tmp_path / "kept"), max_total_bytes=150)
        blob = b"\x89PNG\r\n\x1a\n" + b"x" * 92
        folder.keep(CONV, ATT, ".png", blob)
        folder.keep(CONV, ATT2, ".png", blob)  # alone, and over: its oldest goes
        assert folder.ids(CONV) == [ATT2]


# ---- the store ------------------------------------------------------------------


class TestTheMessageRecordsThePicture:
    def test_a_message_carries_its_pictures_without_their_bytes(self, tmp_path):
        records = ConversationRecords(str(tmp_path / "c.db"))
        conversation = records.start()
        meta = {"id": ATT, "name": "me.png", "kind": "image", "page_name": "me.png", "suffix": ".png"}
        records.append(conversation.id, "user", "a site from this", attachments=[meta])

        stored = records.messages(conversation.id)[0]

        assert stored.attachments == (meta,)
        raw = (tmp_path / "c.db").read_bytes()
        assert b"\x89PNG" not in raw

    def test_a_database_from_before_this_opens_and_gains_the_default(self, tmp_path):
        path = tmp_path / "old.db"
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE conversations (id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '', "
                "project_id TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, "
                "updated_at REAL NOT NULL, pinned INTEGER NOT NULL DEFAULT 0)"
            )
            conn.execute(
                "CREATE TABLE messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, "
                "seq INTEGER NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL, created_at REAL NOT NULL, "
                "model TEXT NOT NULL DEFAULT '', locality TEXT NOT NULL DEFAULT '')"
            )
            conn.execute("INSERT INTO conversations VALUES ('conv_x','t','',1,1,0)")
            conn.execute("INSERT INTO messages VALUES ('m1','conv_x',1,'user','hello',1,'','')")

        records = ConversationRecords(str(path))

        assert records.messages("conv_x")[0].attachments == ()


# ---- the real app ---------------------------------------------------------------


@pytest.fixture
def world(tmp_path, monkeypatch):
    """The real app with the transcript and the picture folder in a temp directory."""
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    import main

    previous = (
        conversations_api._RECORDS,
        conversations_api._PICTURES,
        conversations_api._ON_PICTURES_REMOVED,
    )
    records = ConversationRecords(str(tmp_path / "conversations.db"))
    conversations_api.set_records(records)
    kept = ConversationPictures(str(tmp_path / "kept"))
    conversations_api.set_pictures(kept, on_removed=main.attachment_store.detach_pictures)

    client = TestClient(main.app)
    seen: dict = {"systems": []}

    async def stream(prompt, model, system_prompt, session_id, **kwargs):
        seen["systems"].append(system_prompt)
        yield json.dumps({"type": "done", "data": {}}) + "\n"

    async def no_refusal(*_a, **_k):
        return None

    attached_sessions: list[tuple[str, str]] = []

    def attach(session, filename="IMG 1.png", data=None, content_type="image/png"):
        response = client.post(
            "/chat/attachments",
            data={"session_id": session},
            files=[("files", (filename, data if data is not None else _png(), content_type))],
        )
        assert response.status_code == 200, response.text
        item = response.json()["attached"][0]
        attached_sessions.append((session, item["id"]))
        return item

    def ask(session, text, ids=(), conversation_id=""):
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
                    "attachment_ids": list(ids),
                    "conversation_id": conversation_id,
                },
            )
        assert response.status_code == 200, response.text
        found = ""
        for line in response.text.splitlines():
            try:
                frame = json.loads(line)
            except ValueError:
                continue
            if frame.get("type") == "conversation":
                found = frame["data"]["conversation_id"]
        return found or conversation_id

    class World:
        pass

    w = World()
    w.main, w.client, w.records, w.kept = main, client, records, kept
    w.attach, w.ask, w.seen, w.root = attach, ask, seen, tmp_path / "kept"
    yield w
    for session, identifier in attached_sessions:
        client.delete(f"/chat/attachments/{identifier}")
    # Pictures restored into a session are not ones the test attached; the
    # store is process-wide, so leave no session behind for the next test.
    for session in ("s1", "s2", "old-session", "new-session"):
        main.attachment_store.clear_session(session)
    conversations_api._RECORDS, conversations_api._PICTURES, conversations_api._ON_PICTURES_REMOVED = previous


PAGE = "make me a portfolio website using this photo"


class TestPicturesAreKeptOnSend:
    def test_the_picture_is_copied_beside_the_conversation(self, world):
        item = world.attach("s1", data=_png("red"))
        conversation = world.ask("s1", PAGE, [item["id"]])

        assert world.kept.read(conversation, item["id"]) == _png("red")

    def test_the_stored_message_names_it_and_holds_no_bytes(self, world, tmp_path):
        item = world.attach("s1", "portrait.png", data=_png("blue"))
        conversation = world.ask("s1", PAGE, [item["id"]])

        body = world.client.get(f"/conversations/{conversation}").json()
        user = [m for m in body["messages"] if m["role"] == "user"][0]

        assert user["attachments"] == [
            {
                "id": item["id"],
                "name": "portrait.png",
                "kind": "image",
                "page_name": "portrait.png",
                "suffix": ".png",
            }
        ]
        assert b"\x89PNG" not in (tmp_path / "conversations.db").read_bytes()
        assert _png("blue").hex() not in json.dumps(body)

    def test_a_follow_up_does_not_record_the_same_picture_again(self, world):
        item = world.attach("s1")
        conversation = world.ask("s1", PAGE, [item["id"]])
        world.ask("s1", "make the heading bigger", [item["id"]], conversation)

        users = [m for m in world.records.messages(conversation) if m.role == "user"]
        assert [len(m.attachments) for m in users] == [1, 0]
        assert world.kept.ids(conversation) == [item["id"]]

    def test_a_document_is_never_kept(self, world):
        response = world.client.post(
            "/chat/attachments",
            data={"session_id": "s1"},
            files=[("files", ("contract.txt", b"private words", "text/plain"))],
        )
        doc = response.json()["attached"][0]
        try:
            conversation = world.ask("s1", "summarise this", [doc["id"]])
            assert world.kept.ids(conversation) == []
            user = world.records.messages(conversation)[0]
            assert user.attachments == ()
        finally:
            world.client.delete(f"/chat/attachments/{doc['id']}")

    def test_a_format_no_page_can_use_is_not_kept(self, world):
        # heic gets no page name, so nothing could ever refer to it.
        item = world.attach("s1", "shot.heic", data=b"\x00\x00\x00\x18ftypheic" + b"0" * 40, content_type="image/heic")
        conversation = world.ask("s1", "what is this", [item["id"]])
        assert world.kept.ids(conversation) == []


class TestServing:
    def test_the_conversation_serves_its_picture(self, world):
        item = world.attach("s1", data=_png("red"))
        conversation = world.ask("s1", PAGE, [item["id"]])

        served = world.client.get(f"/conversations/{conversation}/pictures/{item['id']}")

        assert served.status_code == 200
        assert served.headers["content-type"] == "image/png"
        assert served.headers["cache-control"] == "no-store"
        assert served.content == _png("red")

    def test_another_conversation_cannot_have_it(self, world):
        item = world.attach("s1")
        conversation = world.ask("s1", PAGE, [item["id"]])
        stranger = world.records.start().id

        assert world.client.get(f"/conversations/{stranger}/pictures/{item['id']}").status_code == 404
        assert world.client.get(f"/conversations/{conversation}/pictures/{item['id']}").status_code == 200

    def test_an_unknown_conversation_and_a_path_trick_both_answer_404(self, world):
        item = world.attach("s1")
        conversation = world.ask("s1", PAGE, [item['id']])

        assert world.client.get(f"/conversations/conv_000000000000/pictures/{item['id']}").status_code == 404
        for trick in ("..%2F..%2Fconversations.db", "att_0123456789ab%2F..%2F..%2Fx", "x"):
            assert world.client.get(f"/conversations/{conversation}/pictures/{trick}").status_code in (404, 422)


class TestDeletion:
    def test_deleting_the_conversation_removes_its_pictures(self, world):
        item = world.attach("s1")
        conversation = world.ask("s1", PAGE, [item["id"]])
        assert (world.root / conversation).is_dir()

        response = world.client.delete(f"/conversations/{conversation}")

        assert response.status_code == 200
        assert not (world.root / conversation).exists()
        assert world.kept.read(conversation, item["id"]) is None
        # And the live session lets go of its copy too.
        live = world.client.get(f"/chat/attachments/{item['id']}/content", params={"session_id": "s1"})
        assert live.status_code == 404

    def test_the_delete_sentence_says_the_pictures_went(self, world):
        item = world.attach("s1")
        conversation = world.ask("s1", PAGE, [item["id"]])
        note = world.client.delete(f"/conversations/{conversation}").json()["note"]
        assert "pictures" in note


class TestRemovingJustThePictures:
    def test_the_conversation_stays_and_its_pictures_go(self, world):
        item = world.attach("s1")
        conversation = world.ask("s1", PAGE, [item["id"]])

        response = world.client.delete(f"/conversations/{conversation}/pictures")

        assert response.status_code == 200
        assert response.json()["removed"] == 1
        assert response.json()["bytes"] > 0
        assert world.client.get(f"/conversations/{conversation}").status_code == 200
        assert world.client.get(f"/conversations/{conversation}/pictures/{item['id']}").status_code == 404
        # The working copy is gone as well, so the picture is not still showing
        # on a page the person just removed it from.
        live = world.client.get(f"/chat/attachments/{item['id']}/content", params={"session_id": "s1"})
        assert live.status_code == 404

    def test_a_conversation_that_does_not_exist_is_a_404(self, world):
        assert world.client.delete("/conversations/conv_000000000000/pictures").status_code == 404


class TestTheCeilingThroughTheApp:
    def test_a_ceiling_that_is_passed_prunes_the_older_conversation(self, world):
        small = _png("red", size=8)
        world.kept._max = len(small) + len(small) // 2  # room for one and a half
        first = world.attach("s1", data=small)
        older = world.ask("s1", PAGE, [first["id"]])
        os.utime(world.root / older / next((world.root / older).iterdir()).name, (1, 1))
        second = world.attach("s2", data=_png("blue", size=8))
        newer = world.ask("s2", PAGE, [second["id"]])

        assert world.kept.ids(older) == []
        assert world.kept.ids(newer) == [second["id"]]
        # The conversation is intact; only the pictures went, and the window
        # shows the placeholder because the kept copy answers 404.
        assert world.client.get(f"/conversations/{older}").status_code == 200
        assert world.client.get(f"/conversations/{older}/pictures/{first['id']}").status_code == 404


class TestAResumedSessionGetsThePicturesBack:
    def test_a_follow_up_after_a_restart_still_knows_the_names(self, world):
        item = world.attach("old-session", "portrait.png")
        conversation = world.ask("old-session", PAGE, [item["id"]])
        # A restart: this session holds nothing, and the request names no id.
        assert world.main.attachment_store.for_session("new-session") == []

        world.ask("new-session", "make me a portfolio website again with the photo bigger", [], conversation)

        system = world.seen["systems"][-1]
        assert "portrait.png" in system
        # Not shown to the model this time, and the guidance says so.
        assert "not shown the pictures" in system

    def test_the_second_follow_up_still_knows_them(self, world):
        item = world.attach("old-session", "portrait.png")
        conversation = world.ask("old-session", PAGE, [item["id"]])
        world.ask("new-session", "make me a portfolio website again with the photo bigger", [], conversation)

        world.ask("new-session", "make me a portfolio website again but darker", [], conversation)

        assert "portrait.png" in world.seen["systems"][-1]

    def test_a_document_can_place_it(self, world):
        from attachments.pictures import document_pictures_for_session

        item = world.attach("old-session", "portrait.png", data=_png("red"))
        conversation = world.ask("old-session", PAGE, [item["id"]])
        world.ask("new-session", "thanks", [], conversation)

        placed = document_pictures_for_session("new-session")

        assert [p.name for p in placed] == ["portrait.png"]
        assert placed[0].data == _png("red")

    def test_restoring_does_not_record_or_keep_it_a_second_time(self, world):
        item = world.attach("old-session", "portrait.png")
        conversation = world.ask("old-session", PAGE, [item["id"]])
        world.ask("new-session", "make me a portfolio website again with the photo bigger", [], conversation)
        world.ask("new-session", "and the heading", [], conversation)

        users = [m for m in world.records.messages(conversation) if m.role == "user"]
        assert [len(m.attachments) for m in users] == [1, 0, 0]
        assert world.kept.ids(conversation) == [item["id"]]

    def test_the_restored_picture_keeps_the_name_the_page_already_uses(self, world):
        item = world.attach("old-session", "portrait.png")
        conversation = world.ask("old-session", PAGE, [item["id"]])
        world.ask("new-session", "thanks", [], conversation)

        held = world.main.attachment_store.for_session("new-session")

        assert [a.page_name for a in held] == ["portrait.png"]
        assert held[0].kept_as == item["id"]
        assert held[0].id != item["id"]

    def test_a_picture_the_new_session_attached_wins_a_name_clash(self, world):
        item = world.attach("old-session", "portrait.png", data=_png("red"))
        conversation = world.ask("old-session", PAGE, [item["id"]])
        fresh = world.attach("new-session", "portrait.png", data=_png("blue"))
        assert fresh["page_name"] == "portrait.png"

        world.ask("new-session", PAGE, [fresh["id"]], conversation)

        names = [a.page_name for a in world.main.attachment_store.for_session("new-session")]
        assert names == ["portrait.png"]

    def test_a_live_conversation_does_not_get_a_removed_picture_back(self, world):
        item = world.attach("s1", "portrait.png")
        conversation = world.ask("s1", PAGE, [item["id"]])
        world.client.delete(f"/chat/attachments/{item['id']}")  # the person detached it
        world.ask("s1", "make me a portfolio website again with a bigger heading", [], conversation)

        assert world.main.attachment_store.for_session("s1") == []
        assert "portrait.png" not in world.seen["systems"][-1]


class TestNothingReachesTheSpine:
    def test_the_module_imports_nothing_that_could_index_or_send(self):
        source = (Path(__file__).resolve().parents[1] / "conversations" / "pictures.py").read_text(
            encoding="utf-8"
        )
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "urllib", "socket", "aiohttp", "ingest", "memory", "runtimes", "core"}
        # `core.paths` is the one allowed reach into core: where the data lives.
        assert (imported & forbidden) <= {"core"}
        assert "from core.paths import data_dir" in source
        assert "from core import" not in source

    def test_sending_a_picture_adds_no_source_to_knowledge(self, world):
        before = world.client.get("/ingest/sources").json()
        item = world.attach("s1")
        world.ask("s1", PAGE, [item["id"]])
        after = world.client.get("/ingest/sources").json()
        assert after == before

    def test_the_export_says_where_the_pictures_are(self, world):
        import io as _io
        import zipfile

        response = world.client.get("/export")
        assert response.status_code == 200
        with zipfile.ZipFile(_io.BytesIO(response.content)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
        assert any("Pictures kept with conversations" in line for line in manifest["not_included"])
