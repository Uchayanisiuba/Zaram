"""Pinned, searchable, and grouped — what a list of fifty conversations needs.

Asked for 3 October 2026 from a screenshot of the panel beside one of
Claude's. The screenshot is the argument: a flat list by date, in which the
titles read `hello`, `hello`, `hello`, `it should also accept negatives`,
`it should also accept negatives`. Nothing there is findable.

**Titles stay as they are, and that is deliberate rather than unfixed.**
`title_from`'s own reasoning holds — a generated title spends an inference
call on a label, on the path the product's speed argument lives on, and it
invents wording the person never used, so the list becomes searchable by
everything except the words they remember typing. The answer to `hello` five
times is not a model; it is being able to search what was *said*, group by
the project it was said in, and pin the thread you keep coming back to.

So three things, and the second is the one that does the work.
"""

from __future__ import annotations

import pytest

from conversations.records import ConversationRecords


@pytest.fixture
def records(tmp_path):
    return ConversationRecords(str(tmp_path / "conversations.db"))


def conversation(records, *, project: str = "", first: str = "hello", then: str = ""):
    c = records.start(project_id=project)
    records.append(c.id, role="user", text=first)
    if then:
        records.append(c.id, role="user", text=then)
    return records.get(c.id)


class TestSearchLooksAtWhatWasSaid:
    """The half that matters. A title is the first thing somebody typed and
    is often `hello`; what they remember is something from the middle."""

    def test_it_finds_a_word_from_a_message(self, records):
        wanted = conversation(records, first="hello", then="the Keyline IK solver drifts")
        conversation(records, first="hello", then="something else entirely")
        found = records.search("Keyline IK")
        assert [c.id for c in found] == [wanted.id]

    def test_it_finds_a_word_from_a_title_too(self, records):
        wanted = conversation(records, first="audit the ride share pricing")
        assert wanted.id in {c.id for c in records.search("ride share")}

    def test_two_conversations_titled_hello_are_told_apart(self, records):
        """The screenshot, as a test."""
        a = conversation(records, first="hello", then="how do I rig a hand")
        b = conversation(records, first="hello", then="what did we decide on pricing")
        assert [c.id for c in records.search("rig a hand")] == [a.id]
        assert [c.id for c in records.search("pricing")] == [b.id]

    def test_an_empty_query_finds_nothing_rather_than_everything(self, records):
        """`%%` matches every row, which would make a cleared search box
        look like a list and behave like one — the worst kind of wrong,
        because it is indistinguishable from working."""
        conversation(records)
        assert records.search("") == []
        assert records.search("   ") == []

    def test_search_crosses_projects(self, records):
        """Somebody typing a word is looking for a conversation. Hiding
        matches outside the project they happen to have open is the empty
        result that reads as "Zaram did not keep it"."""
        wanted = conversation(records, project="keyline", first="the IK solver drifts")
        assert wanted.id in {c.id for c in records.search("IK solver")}


class TestPinningBeatsRecency:
    def test_a_pinned_conversation_leads(self, records):
        old = conversation(records, first="the long running thread")
        for n in range(5):
            conversation(records, first=f"a quick question {n}")
        records.set_pinned(old.id, True)
        assert records.list()[0].id == old.id

    def test_unpinning_puts_it_back_in_order(self, records):
        old = conversation(records, first="the long running thread")
        recent = conversation(records, first="asked just now")
        records.set_pinned(old.id, True)
        records.set_pinned(old.id, False)
        assert records.list()[0].id == recent.id

    def test_the_rest_stay_in_recency_order(self, records):
        """Pinning reorders the top, not the list."""
        first = conversation(records, first="one")
        second = conversation(records, first="two")
        third = conversation(records, first="three")
        records.set_pinned(first.id, True)
        order = [c.id for c in records.list()]
        assert order == [first.id, third.id, second.id]

    def test_pinning_something_that_is_gone_is_a_known_failure(self, records):
        from conversations.records import UnknownConversation

        with pytest.raises(UnknownConversation):
            records.set_pinned("no-such-conversation", True)

    def test_it_survives_a_reopen(self, tmp_path):
        path = str(tmp_path / "c.db")
        records = ConversationRecords(path)
        c = conversation(records)
        records.set_pinned(c.id, True)
        assert ConversationRecords(path).get(c.id).pinned is True


class TestGroupingByProjectIsAlreadyPossible:
    """`project_id` has been on the record since rule 7i, so the panel needs
    no new field to group — only to use the one that is there."""

    def test_the_list_can_be_asked_for_one_project(self, records):
        mine = conversation(records, project="keyline", first="about keyline")
        conversation(records, project="ride-share", first="about ride share")
        assert [c.id for c in records.list(project_id="keyline")] == [mine.id]

    def test_and_for_the_ones_in_no_project(self, records):
        """`None` and `""` stay different questions."""
        loose = conversation(records, project="", first="just asking")
        conversation(records, project="keyline", first="about keyline")
        assert [c.id for c in records.list(project_id="")] == [loose.id]
        assert len(records.list()) == 2


class TestADatabaseWrittenBeforeThisStillOpens:
    def test_the_column_is_added(self, tmp_path):
        import sqlite3

        path = tmp_path / "c.db"
        with sqlite3.connect(path) as conn:
            conn.execute(
                """
                CREATE TABLE conversations (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',
                    project_id TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL, updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT INTO conversations (id, title, project_id, created_at, updated_at)"
                " VALUES ('old', 'From before', '', 1.0, 1.0)"
            )
        records = ConversationRecords(str(path))
        assert records.get("old").pinned is False
        assert records.set_pinned("old", True).pinned is True
