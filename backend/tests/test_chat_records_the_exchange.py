"""The chat path writes what was said into the session store.

The store landing is not the same as the store being *used*. This repository's
recorded base rate is fifteen complete, tested, unreachable subsystems, so a
transcript store with no caller would be the sixteenth — and it would look
exactly like a working feature, because the store's own tests pass either way.

These tests exercise the helpers `POST /chat` actually calls, rather than
booting the kernel: the endpoint needs a live provider layer, a planner and a
model, none of which have anything to do with whether an exchange is recorded.
`tests/test_routes_are_mounted.py` covers reachability of the route itself.
"""

from __future__ import annotations

import json

import pytest

import main
from conversations import ConversationRecords, UnknownConversation
from conversations.api import set_records


@pytest.fixture()
def store(tmp_path) -> ConversationRecords:
    records = ConversationRecords(str(tmp_path / "conversations.db"))
    set_records(records)
    return records


def _request(**kw) -> main.ChatRequest:
    return main.ChatRequest(text=kw.pop("text", "what is my day rate"), **kw)


def _token(content: str) -> str:
    return json.dumps({"type": "token", "data": {"content": content}})


class TestTheQuestionIsRecordedBeforeTheAnswerExists:
    def test_opening_a_conversation_stores_the_question(self, store):
        conversation_id, started = main._open_conversation(_request())

        assert started is True
        assert [m.text for m in store.messages(conversation_id)] == [
            "what is my day rate"
        ]

    def test_a_question_that_never_gets_an_answer_is_still_kept(self, store):
        """The reason it is recorded before generation rather than after.

        A question that produced an error is still a question they asked, and
        losing it because the model failed is the amnesia this store exists to
        end.
        """
        conversation_id, _ = main._open_conversation(_request(text="why is this slow"))

        # No reply ever arrives — the model timed out, as it did on 27 August.
        main._record_reply(conversation_id, "", main._ModelChoice("gemma4:12b", "settings"))

        messages = store.messages(conversation_id)
        assert [m.role for m in messages] == ["user"]
        assert messages[0].text == "why is this slow"

    def test_the_project_scope_travels_with_the_conversation(self, store):
        """Rule 7i. A conversation started inside a project belongs to it."""
        conversation_id, _ = main._open_conversation(_request(project_id="harbour-lane"))

        assert store.get(conversation_id).project_id == "harbour-lane"

    def test_a_named_conversation_is_continued_not_replaced(self, store):
        existing = store.start()
        store.append(existing.id, "user", "first question")

        conversation_id, started = main._open_conversation(
            _request(conversation_id=existing.id, text="second question")
        )

        assert started is False
        assert conversation_id == existing.id
        assert [m.text for m in store.messages(existing.id)] == [
            "first question",
            "second question",
        ]


class TestTheReplyIsRecordedWithWhatAnsweredIt:
    def test_the_answer_and_its_attribution_are_stored(self, store, monkeypatch):
        monkeypatch.setattr(
            main,
            "_current_inference",
            lambda m: {"model": "gemma4:12b", "locality": "local"},
        )
        conversation_id, _ = main._open_conversation(_request())

        main._record_reply(
            conversation_id, "400 a day.", main._ModelChoice("gemma4:12b", "settings")
        )

        reply = store.messages(conversation_id)[1]
        assert reply.role == "assistant"
        assert reply.text == "400 a day."
        assert reply.model == "gemma4:12b"
        assert reply.locality == "local"

    def test_an_unplaceable_model_records_no_locality_rather_than_local(
        self, store, monkeypatch
    ):
        """`locality_of` answers `None` for a model it cannot resolve, and that
        must travel as "" rather than as "local". CLAUDE.md: *"runs on this
        machine" would be a confident false claim on the one thing the user is
        most likely to check.*"""
        monkeypatch.setattr(
            main, "_current_inference", lambda m: {"model": "mystery", "locality": None}
        )
        conversation_id, _ = main._open_conversation(_request())

        main._record_reply(conversation_id, "an answer", main._ModelChoice("mystery", "request"))

        assert store.messages(conversation_id)[1].locality == ""

    def test_an_empty_reply_is_not_stored_as_silence(self, store):
        """A stream that produced no tokens has nothing anyone would look for
        later, and an empty assistant row reads as Zaram having said nothing
        when in fact it never spoke."""
        conversation_id, _ = main._open_conversation(_request())

        main._record_reply(conversation_id, "   \n ", main._ModelChoice(None, "zaram"))

        assert [m.role for m in store.messages(conversation_id)] == ["user"]


class TestOnlyTheAnswerIsAccumulated:
    def test_tokens_are_collected(self):
        answer: list[str] = []
        for chunk in (_token("400 "), _token("a "), _token("day.")):
            main._collect_answer(chunk, answer)

        assert "".join(answer) == "400 a day."

    def test_reasoning_is_not_part_of_the_transcript(self):
        """`ReasoningSplitter` already keeps a model's working out of
        `streamingText` and out of speech. Storing it here would put an
        internal monologue in the transcript as though it were the answer, and
        a later session would read it back as what Zaram said."""
        answer: list[str] = []
        main._collect_answer(
            json.dumps({"type": "reasoning", "data": {"content": "Let me think..."}}), answer
        )
        main._collect_answer(_token("400 a day."), answer)

        assert "".join(answer) == "400 a day."

    def test_other_events_are_ignored(self):
        answer: list[str] = []
        for frame in (
            json.dumps({"type": "answering", "data": {"model": "gemma4:12b"}}),
            json.dumps({"type": "source", "data": {"title": "a fact"}}),
            json.dumps({"type": "notice", "data": {"content": "read 3 of 41 sections"}}),
            json.dumps({"type": "done", "data": {}}),
        ):
            main._collect_answer(frame, answer)

        assert answer == []

    def test_a_frame_this_layer_cannot_parse_never_breaks_the_stream(self):
        """Bookkeeping must not interfere with the reply. A frame that fails to
        parse here is still a frame the client receives."""
        answer: list[str] = []

        main._collect_answer("not json at all", answer)
        main._collect_answer("", answer)
        main._collect_answer(_token("fine"), answer)

        assert answer == ["fine"]


class TestBookkeepingNeverCostsTheAnswer:
    """A transcript is bookkeeping; the reply is the product."""

    def test_no_store_means_the_exchange_is_not_recorded_rather_than_refused(
        self, monkeypatch
    ):
        monkeypatch.setattr(main, "_conversation_store", lambda: None)

        conversation_id, started = main._open_conversation(_request())

        assert (conversation_id, started) == ("", False)

    def test_a_conversation_id_that_does_not_exist_is_not_silently_replaced(self, store):
        """Opening a fresh conversation under a different id would leave the
        client writing into a transcript it can never find again. Better to
        record nothing and say so in the log."""
        conversation_id, started = main._open_conversation(
            _request(conversation_id="conv_nothing")
        )

        assert (conversation_id, started) == ("", False)
        with pytest.raises(UnknownConversation):
            store.get("conv_nothing")

    def test_a_store_that_raises_does_not_reach_the_user(self, store, monkeypatch):
        class Exploding:
            def get(self, *a, **k):
                raise RuntimeError("disk is full")

            def start(self, *a, **k):
                raise RuntimeError("disk is full")

            def append(self, *a, **k):
                raise RuntimeError("disk is full")

        monkeypatch.setattr(main, "_conversation_store", lambda: Exploding())

        assert main._open_conversation(_request()) == ("", False)
        # And recording a reply into nothing is a no-op rather than a raise.
        main._record_reply("", "an answer", main._ModelChoice(None, "zaram"))

    def test_the_title_lookup_degrades_to_empty(self, monkeypatch):
        monkeypatch.setattr(main, "_conversation_store", lambda: None)

        assert main._conversation_title("conv_1") == ""


class TestTheStoreIsTheOneTheRouteUses:
    """Without this, every test above could be exercising a store the endpoint
    never touches — which is the shape that produced fifteen unreachable
    subsystems in this repository."""

    def test_the_helper_reads_the_module_the_router_writes(self, store):
        assert main._conversation_store() is store
