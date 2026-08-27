"""Closing the window stops losing the conversation.

Checked 27 August 2026, across all seven databases: `artifacts`, `egress`,
`sources`, `outcomes`, `domains`, `domain_sources`, `obligations`,
`unresolved`, `projects`, `files`, `cache`, `memories`. **No table held a
message.** The only session state was `ExecutionEngine._session_turns`, an
in-process `OrderedDict` capped at 64 sessions of 8 turns, which dies with the
process.

Rule 7d says *"session state and long-term memory are separate stores"*. Zaram
had the second one. These tests are about the first, and about the line between
them staying where the rule puts it.
"""

from __future__ import annotations

import pytest

from conversations import (
    ASSISTANT,
    USER,
    ConversationRecords,
    UnknownConversation,
    title_from,
)


@pytest.fixture()
def store(tmp_path) -> ConversationRecords:
    return ConversationRecords(str(tmp_path / "conversations.db"))


class TestATranscriptSurvivesTheProcess:
    def test_messages_come_back_after_the_store_is_reopened(self, tmp_path):
        """The whole point, asserted first.

        A store that only works while it is open is the `OrderedDict` this
        replaces.
        """
        path = str(tmp_path / "conversations.db")
        first = ConversationRecords(path)
        conv = first.start()
        first.append(conv.id, USER, "what is my day rate for Northwind")
        first.append(conv.id, ASSISTANT, "400 a day.", model="gemma4:12b", locality="local")

        reopened = ConversationRecords(path)
        messages = reopened.messages(conv.id)

        assert [m.text for m in messages] == [
            "what is my day rate for Northwind",
            "400 a day.",
        ]

    def test_order_is_the_sequence_not_the_clock(self, store):
        """Two messages inside one clock tick must not sort arbitrarily.

        `time.time()` has coarse resolution on Windows, so a question and its
        reply written in the same request can carry an identical timestamp. A
        reply rendering above the question that produced it is the kind of bug
        nobody reproduces on demand.
        """
        conv = store.start()
        for i in range(12):
            store.append(conv.id, USER if i % 2 == 0 else ASSISTANT, f"line {i}")

        messages = store.messages(conv.id)

        assert [m.seq for m in messages] == list(range(1, 13))
        assert [m.text for m in messages] == [f"line {i}" for i in range(12)]

    def test_attribution_is_kept_per_message(self, store):
        """Which model answered, and where it ran. The `answering` event
        already carries both; without this they were thrown away."""
        conv = store.start()
        store.append(conv.id, USER, "hello")
        store.append(
            conv.id, ASSISTANT, "hi", model="claude-sonnet-4.5", locality="cloud"
        )

        reply = store.messages(conv.id)[1]

        assert reply.model == "claude-sonnet-4.5"
        assert reply.locality == "cloud"

    def test_an_unplaceable_model_records_no_locality_rather_than_local(self, store):
        """Inherited from `locality_of`, which returns `None` rather than
        guessing: *"runs on this machine" would be a confident false claim on
        the one thing the user is most likely to check.*"""
        conv = store.start()
        store.append(conv.id, USER, "hello")
        store.append(conv.id, ASSISTANT, "hi", model="something-unresolved")

        assert store.messages(conv.id)[1].locality == ""


class TestTheTitleIsTakenNeverAsked:
    """Rule 7e: never ask a question the system can answer from behaviour.

    And never spend an inference call on a label — a generated title invents
    wording the user did not use, so the list becomes searchable by everything
    except the words they remember typing.
    """

    def test_the_first_user_message_names_the_conversation(self, store):
        conv = store.start()
        store.append(conv.id, USER, "chase the Harbour Lane invoice")

        assert store.get(conv.id).title == "chase the Harbour Lane invoice"

    def test_a_long_opening_is_cut_at_a_word_boundary(self, store):
        conv = store.start()
        store.append(
            conv.id,
            USER,
            "I need to work out whether the Northwind contract lets me raise my "
            "rate before the renewal date",
        )

        title = store.get(conv.id).title

        assert title.endswith("…")
        assert not title[:-1].endswith(" ")
        # Cut on a space, so the last word is whole rather than sliced.
        assert "…" not in title[:-1]
        assert len(title) <= 61

    def test_a_reply_never_titles_a_conversation(self, store):
        """A conversation whose first stored row is an assistant message is a
        bug elsewhere. Titling it with Zaram's own words would hide that behind
        a plausible label."""
        conv = store.start()
        store.append(conv.id, ASSISTANT, "Here is what I found.")

        assert store.get(conv.id).title == ""

    def test_the_second_message_does_not_retitle(self, store):
        conv = store.start()
        store.append(conv.id, USER, "first thing")
        store.append(conv.id, ASSISTANT, "a reply")
        store.append(conv.id, USER, "second thing")

        assert store.get(conv.id).title == "first thing"

    def test_an_explicit_title_is_left_alone(self, store):
        conv = store.start(title="Imported from ChatGPT")
        store.append(conv.id, USER, "something else entirely")

        assert store.get(conv.id).title == "Imported from ChatGPT"

    def test_an_empty_message_does_not_produce_an_ellipsis_for_a_name(self):
        assert title_from("") == "Untitled"
        assert title_from("   \n  ") == "Untitled"

    def test_one_enormous_word_still_yields_a_title(self):
        """No space to cut at. Returning "…" alone would name it nothing."""
        title = title_from("a" * 200)

        assert title.startswith("aaa")
        assert len(title) == 61


class TestTheListIsOrderedByActivity:
    def test_most_recently_used_comes_first(self, store):
        older = store.start()
        newer = store.start()
        store.append(older.id, USER, "older")
        store.append(newer.id, USER, "newer")
        # Touching the older one moves it, because that is what a person means
        # by "the one I was just in".
        store.append(older.id, USER, "back to the older one")

        assert [c.id for c in store.list()] == [older.id, newer.id]

    def test_renaming_is_not_activity(self, store):
        first = store.start()
        second = store.start()
        store.append(first.id, USER, "one")
        store.append(second.id, USER, "two")

        store.rename(first.id, "A better name")

        # Still second: a label change must not jump a conversation to the top.
        assert [c.id for c in store.list()] == [second.id, first.id]

    def test_the_count_is_reported(self, store):
        conv = store.start()
        store.append(conv.id, USER, "one")
        store.append(conv.id, ASSISTANT, "two")

        assert store.list()[0].message_count == 2

    def test_an_empty_conversation_counts_zero_not_one(self, store):
        """The LEFT JOIN makes this worth asserting: a naive COUNT(*) reports
        1 for a conversation with no messages at all."""
        store.start()

        assert store.list()[0].message_count == 0


class TestScopeIsRule7i:
    def test_conversations_can_be_listed_within_a_project(self, store):
        inside = store.start(project_id="harbour-lane")
        store.start(project_id="")

        assert [c.id for c in store.list(project_id="harbour-lane")] == [inside.id]

    def test_no_project_is_a_real_answer_not_a_missing_one(self, store):
        """`""` asks for the conversations belonging to no project. `None` asks
        for all of them. Collapsing the two is how "show me everything" quietly
        becomes "show me the unscoped ones"."""
        scoped = store.start(project_id="harbour-lane")
        unscoped = store.start(project_id="")

        assert [c.id for c in store.list(project_id="")] == [unscoped.id]
        assert {c.id for c in store.list()} == {scoped.id, unscoped.id}


class TestDeletionIsExactlyWhatWasAsked:
    def test_a_deleted_conversation_takes_its_messages(self, store):
        conv = store.start()
        store.append(conv.id, USER, "hello")

        store.delete(conv.id)

        with pytest.raises(UnknownConversation):
            store.messages(conv.id)

    def test_no_orphan_rows_are_left_behind(self, store):
        """Enforced by `ON DELETE CASCADE` plus `PRAGMA foreign_keys=ON`, not
        by remembering to do it in `delete` — the one path that forgets leaves
        rows pointing at a conversation that is not there."""
        import sqlite3

        conv = store.start()
        store.append(conv.id, USER, "hello")
        store.append(conv.id, ASSISTANT, "hi")
        store.delete(conv.id)

        conn = sqlite3.connect(store._path)
        try:
            remaining = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        finally:
            conn.close()

        assert remaining == 0

    def test_deleting_a_conversation_that_is_not_there_says_so(self, store):
        with pytest.raises(UnknownConversation):
            store.delete("conv_nothing")

    def test_one_conversation_does_not_take_another(self, store):
        keep = store.start()
        drop = store.start()
        store.append(keep.id, USER, "keep me")
        store.append(drop.id, USER, "drop me")

        store.delete(drop.id)

        assert [m.text for m in store.messages(keep.id)] == ["keep me"]


class TestTheStoreRefusesWhatItCannotRecord:
    def test_an_unknown_role_is_refused(self, store):
        """Two roles, and no `system`. The system prompt is composed fresh per
        request from identity, character settings and the date — storing one
        would preserve a string that becomes a lie the moment the user renames
        the assistant."""
        conv = store.start()

        with pytest.raises(ValueError):
            store.append(conv.id, "system", "You are Zaram.")

    def test_appending_to_a_conversation_that_does_not_exist_says_so(self, store):
        with pytest.raises(UnknownConversation):
            store.append("conv_nothing", USER, "hello")

    def test_an_empty_rename_is_refused(self, store):
        conv = store.start()

        with pytest.raises(ValueError):
            store.rename(conv.id, "   ")

    def test_reading_a_conversation_that_does_not_exist_says_so(self, store):
        """`messages` raises rather than returning `[]`: a caller handed an
        empty list for a bad id renders an empty transcript as though it were
        real."""
        with pytest.raises(UnknownConversation):
            store.messages("conv_nothing")
