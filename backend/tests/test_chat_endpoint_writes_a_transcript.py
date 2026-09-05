"""`POST /chat` really writes to the store — asserted through the endpoint.

**This file exists because its absence cost a live `NameError`.**

The persistence helpers were built with sixteen passing tests
(`test_chat_records_the_exchange.py`), and every one of them called
`_open_conversation`, `_collect_answer` and `_record_reply` directly. An edit
then landed `_record_reply(conversation_id, ...)` into the endpoint *without*
the line that defines `conversation_id`, and the whole chat path raised::

    NameError: name 'conversation_id' is not defined

Not one of the sixteen noticed, because none of them went through `/chat`. What
caught it was `test_alpha10c_acceptance.py`, which posts to the endpoint for an
unrelated reason and happened to walk the same ground.

That is the repository's own rule pointing the other way. "Assume unreachable
until the caller is seen" is usually about dead code; here the code was live and
the *caller* was the untested part. Testing the parts and not the wiring leaves
exactly this gap, and a green suite says nothing about it.

So: one test that posts a message and reads the transcript back out.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main as main_module
from conversations import ConversationRecords
from conversations.api import set_records


@pytest.fixture()
def store(tmp_path) -> ConversationRecords:
    records = ConversationRecords(str(tmp_path / "conversations.db"))
    set_records(records)
    return records


@pytest.fixture()
def client() -> TestClient:
    return TestClient(main_module.app)


def _reply(*tokens: str):
    """A chat_router stand-in that emits the IPC frames the endpoint reads."""

    async def stream(*args, **kwargs):
        for token in tokens:
            yield json.dumps({"type": "token", "data": {"content": token}}) + "\n"
        yield json.dumps({"type": "done", "data": {}}) + "\n"

    return stream


def _post(client, **body):
    with patch.object(main_module, "chat_router") as router:
        router.route.return_value = body.pop("_stream")()
        return client.post("/chat", json={"persona": "zaram_prime", **body})


class TestTheEndpointRecordsTheExchange:
    def test_a_message_and_its_reply_land_in_the_store(self, client, store):
        response = _post(
            client,
            text="what is my day rate for Northwind",
            _stream=_reply("400 ", "a day."),
        )

        assert response.status_code == 200

        conversations = store.list()
        assert len(conversations) == 1, "the endpoint did not open a conversation"

        messages = store.messages(conversations[0].id)
        assert [(m.role, m.text) for m in messages] == [
            ("user", "what is my day rate for Northwind"),
            ("assistant", "400 a day."),
        ]

    def test_the_conversation_id_is_announced_before_the_answer(self, client, store):
        """The client needs the id it did not send, and needs it early enough
        that an interrupted stream still leaves something reopenable."""
        response = _post(client, text="hello", _stream=_reply("hi"))

        types = []
        for line in response.text.splitlines():
            if not line.strip():
                continue
            try:
                types.append(json.loads(line).get("type"))
            except Exception:
                continue

        assert "conversation" in types
        assert types.index("conversation") < types.index("token")

    def test_the_announced_id_is_the_one_that_was_written(self, client, store):
        response = _post(client, text="hello", _stream=_reply("hi"))

        announced = next(
            json.loads(line)["data"]["conversation_id"]
            for line in response.text.splitlines()
            if line.strip() and json.loads(line).get("type") == "conversation"
        )

        assert [m.text for m in store.messages(announced)] == ["hello", "hi"]

    def test_a_second_message_continues_the_same_transcript(self, client, store):
        """Without this every message is its own one-line thread — a store with
        a caller that cannot use it, which looks exactly like a working
        feature."""
        first = _post(client, text="first question", _stream=_reply("first answer"))
        conversation_id = next(
            json.loads(line)["data"]["conversation_id"]
            for line in first.text.splitlines()
            if line.strip() and json.loads(line).get("type") == "conversation"
        )

        _post(
            client,
            text="second question",
            conversation_id=conversation_id,
            _stream=_reply("second answer"),
        )

        assert len(store.list()) == 1
        assert [m.text for m in store.messages(conversation_id)] == [
            "first question",
            "first answer",
            "second question",
            "second answer",
        ]

    def test_the_project_scope_reaches_the_transcript(self, client, store):
        """Rule 7i, through the wire rather than through the helper."""
        _post(
            client,
            text="chase the invoice",
            project_id="harbour-lane",
            _stream=_reply("done"),
        )

        assert store.list()[0].project_id == "harbour-lane"

    def test_the_title_is_the_question(self, client, store):
        _post(client, text="chase the Harbour Lane invoice", _stream=_reply("ok"))

        assert store.list()[0].title == "chase the Harbour Lane invoice"


class TestBookkeepingNeverCostsTheReply:
    def test_a_store_that_fails_does_not_fail_the_answer(self, client, store, monkeypatch):
        """A transcript is bookkeeping; the reply is the product. This is the
        assertion that would have failed loudest for the `NameError`, since a
        broken persistence path took the whole endpoint down with it."""

        class Exploding:
            def start(self, *a, **k):
                raise RuntimeError("disk is full")

            def get(self, *a, **k):
                raise RuntimeError("disk is full")

            def append(self, *a, **k):
                raise RuntimeError("disk is full")

        monkeypatch.setattr(main_module, "_conversation_store", lambda: Exploding())

        response = _post(client, text="hello", _stream=_reply("hi there"))

        assert response.status_code == 200
        assert "hi there" in response.text


class _Engine:
    """The two members `_seed_turns_from_transcript` touches.

    A stand-in because these tests do not boot the kernel — `execution_engine`
    is None without it, and booting one per test costs 20 s and proves nothing
    about rehydration. `seed_session_turns`'s own rules (existing turns win, the
    cap, the LRU) are asserted against the real `ExecutionEngine` in
    `test_session_seeding.py`.
    """

    MAX_SESSION_TURNS = 8

    def __init__(self) -> None:
        self.seeded: dict[str, list] = {}

    def seed_session_turns(self, session_id, pairs):
        if not session_id or not pairs:
            return
        if self.seeded.get(session_id):
            return
        self.seeded[session_id] = list(pairs)


@pytest.fixture()
def engine(monkeypatch) -> _Engine:
    stub = _Engine()
    monkeypatch.setattr(main_module.kernel, "execution_engine", stub, raising=False)
    return stub


class TestAResumedConversationGetsItsTurnsBack:
    """**The gap stored transcripts exist to close.**

    `ExecutionEngine._session_turns` is in-process and dies with it. That is
    rule 7d's ephemeral half and it is right — false starts must not reach the
    Spine — but until transcripts were stored it also meant reopening a
    conversation handed the model nothing, so "write that up as a proposal"
    resolved against an empty buffer. Rule 9's referential failure, arriving
    after a restart rather than on a first message.
    """

    def test_prior_turns_are_seeded_into_a_fresh_session(self, client, store, engine):
        conversation = store.start()
        store.append(conversation.id, "user", "the Northwind rate is 400 a day")
        store.append(conversation.id, "assistant", "Noted — 400 a day for Northwind.")

        _post(
            client,
            text="write that up as a proposal",
            conversation_id=conversation.id,
            session_id="restarted",
            _stream=_reply("Here is the proposal."),
        )

        seeded = engine.seeded.get("restarted", [])
        assert seeded, "a resumed conversation arrived with an empty turn buffer"
        assert seeded[0] == (
            "the Northwind rate is 400 a day",
            "Noted — 400 a day for Northwind.",
        )

    def test_this_request_s_own_question_is_not_a_prior_turn(self, client, store, engine):
        """Left in, the buffer would answer "what is 'that'" with the sentence
        containing "that"."""
        conversation = store.start()
        store.append(conversation.id, "user", "first question")
        store.append(conversation.id, "assistant", "first answer")

        _post(
            client,
            text="write that up",
            conversation_id=conversation.id,
            session_id="s2",
            _stream=_reply("ok"),
        )

        assert all("write that up" not in pair[0] for pair in engine.seeded.get("s2", []))

    def test_an_answer_whose_question_was_dropped_is_not_paired_forward(
        self, client, store, engine
    ):
        """`fit` already refuses to start a transcript on a reply. This asserts
        the pairing does not undo that by attaching an orphaned answer to
        whatever happens to precede it."""
        conversation = store.start()
        store.append(conversation.id, "assistant", "an answer with no question")
        store.append(conversation.id, "user", "a real question")
        store.append(conversation.id, "assistant", "a real answer")

        _post(
            client,
            text="follow up",
            conversation_id=conversation.id,
            session_id="s3",
            _stream=_reply("ok"),
        )

        assert engine.seeded.get("s3") == [("a real question", "a real answer")]

    def test_a_brand_new_conversation_is_not_rehydrated(self, client, store, engine):
        """Nothing prior exists, so asking the store would be a query with a
        known answer."""
        _post(client, text="hello", session_id="fresh", _stream=_reply("hi"))

        assert not engine.seeded.get("fresh")

    def test_a_transcript_that_cannot_be_read_costs_a_weaker_reply_only(
        self, client, store, engine, monkeypatch
    ):
        conversation = store.start()
        store.append(conversation.id, "user", "q")
        store.append(conversation.id, "assistant", "a")

        class Exploding:
            def get(self, *a, **k):
                return None

            def append(self, *a, **k):
                return None

            def messages(self, *a, **k):
                raise RuntimeError("unreadable")

        monkeypatch.setattr(main_module, "_conversation_store", lambda: Exploding())

        response = _post(
            client,
            text="follow up",
            conversation_id=conversation.id,
            session_id="s4",
            _stream=_reply("still answered"),
        )

        assert response.status_code == 200
        assert "still answered" in response.text
