"""A reopened conversation gets back its plan, its tools and its files.

Reported 3 October 2026: *"when a Zaram session is closed the plans, tools
used, files download etc attached to the session seems to disappear ... users
should be able to go back to previous conversations and access them."*

**The measurement came before the fix, and it found a worse fault than the
one reported.** Of 50 artifacts in the maintainer's own store, none was filed
under a conversation that exists: 27 under `''`, 23 under a `session-…` id.
The column, its index, the `?conversation_id=` query and the Work surface
reading it were all present and correct, and nothing had ever written a value
that matched — the chat path passes the *session* id, minted per launch,
where the durable conversation id belongs.

So this file asserts two separate things, and the second is the one that was
invisible: that a stored reply carries what it did, and that a generated file
can be found from the conversation that produced it.

The last class is the line that must not move. `chatStore.resumeConversation`
refuses to restore citations because a citation is a live claim about the
Spine and rule 4 lets the fact underneath it be deleted. That refusal stays
right, and widening this fix into it would put stale provenance on screen.
"""

from __future__ import annotations

import json

import pytest

from conversations.records import ASSISTANT, USER, ConversationRecords
from conversations.turn_notes import MAX_CALLS, MAX_FIELD_CHARS, TurnNotes


def frame(kind: str, **data) -> str:
    return json.dumps({"type": kind, "data": data, "ts": 0, "seq": 0, "correlation_id": ""})


@pytest.fixture
def records(tmp_path):
    return ConversationRecords(str(tmp_path / "conversations.db"))


# --------------------------------------------------------------- the store


class TestTheStoreKeepsIt:
    def test_a_reply_round_trips_its_tools_plan_and_files(self, records):
        c = records.start()
        records.append(c.id, USER, "make me a spreadsheet of Q3")
        records.append(
            c.id,
            ASSISTANT,
            "Here it is.",
            tool_calls=[{"server": "zaram", "tool": "document.generate", "verdict": "allow"}],
            plan={"items": [{"text": "read the figures", "status": "done"}], "awaitingGo": False},
            artifact_ids=["art_7"],
        )
        back = records.messages(c.id)[-1]
        assert back.tool_calls[0]["tool"] == "document.generate"
        assert back.plan["items"][0]["text"] == "read the figures"
        assert back.artifact_ids == ("art_7",)

    def test_a_reply_with_none_of_it_stays_empty_rather_than_null(self, records):
        """Most replies are this one. The empties must be falsy without a
        caller having to tell `None` from `[]`."""
        c = records.start()
        records.append(c.id, USER, "hello")
        back = records.messages(c.id)[-1]
        assert back.tool_calls == ()
        assert back.plan is None
        assert back.artifact_ids == ()

    def test_a_transcript_written_before_this_still_opens(self, tmp_path):
        """The migration, which is the half that only runs on somebody's
        existing install and never on a fresh one.

        `CREATE TABLE IF NOT EXISTS` is silent about a table that exists and
        differs, which is how a schema change becomes `no such column` on a
        machine that is not the author's.
        """
        import sqlite3

        path = str(tmp_path / "old.db")
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE conversations (
                id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',
                project_id TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL, updated_at REAL NOT NULL
            );
            CREATE TABLE messages (
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL
                    REFERENCES conversations(id) ON DELETE CASCADE,
                seq INTEGER NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL,
                created_at REAL NOT NULL, model TEXT NOT NULL DEFAULT '',
                locality TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO conversations VALUES ('c1','older','',1,1);
            INSERT INTO messages VALUES ('m1','c1',1,'user','what did we decide',1,'','');
            """
        )
        conn.commit()
        conn.close()

        records = ConversationRecords(path)
        kept = records.messages("c1")
        assert kept[0].text == "what did we decide"
        # Nothing to recover — what that reply did was never written down —
        # but it must read as "none" rather than fail.
        assert kept[0].tool_calls == ()
        assert kept[0].plan is None

        records.append("c1", ASSISTANT, "we decided on 30 days", artifact_ids=["a1"])
        assert records.messages("c1")[-1].artifact_ids == ("a1",)

    def test_something_unserialisable_loses_the_note_not_the_reply(self, records):
        """A transcript is worth more than its annotation."""
        c = records.start()
        records.append(c.id, USER, "go")
        records.append(c.id, ASSISTANT, "done", tool_calls=[{"fn": object()}])
        back = records.messages(c.id)[-1]
        assert back.text == "done"
        assert back.tool_calls == ()


# -------------------------------------------------------------- the reading


class TestReadingTheStream:
    def test_it_picks_up_a_tool_call(self):
        notes = TurnNotes()
        notes.see(frame("tool_call", server="code", tool="read_lines", verdict="allow",
                        reason="", target="main.py:1-20", output="x"))
        assert notes.tool_calls[0]["tool"] == "read_lines"
        assert notes.tool_calls[0]["target"] == "main.py:1-20"

    def test_the_field_names_are_the_ones_the_renderer_reads(self):
        """Pinned deliberately. These cross the wire into `ChatToolCall`
        without a mapping, so a rename on either side has to break here
        rather than show an empty card."""
        notes = TurnNotes()
        notes.see(frame("tool_call", server="code", tool="run", verdict="confirm",
                        reason="needs permission", target="t", output="o",
                        diff="d", commit="abc", image="s.png", app_url="http://localhost:3000",
                        grantable=True, step_id="s1", plan_step=0))
        call = notes.tool_calls[0]
        for key in ("server", "tool", "verdict", "reason", "target", "output", "at",
                    "diff", "commit", "image", "appUrl", "grantable", "stepId", "planStep"):
            assert key in call, f"{key} missing from the stored tool call"
        assert call["appUrl"] == "http://localhost:3000"
        assert call["stepId"] == "s1"

    def test_step_zero_is_kept(self):
        """`is not None`, not truthiness. Step 0 is the first step of every
        plan and is the one most calls belong to."""
        notes = TurnNotes()
        notes.see(frame("tool_call", server="s", tool="t", verdict="allow", plan_step=0))
        assert notes.tool_calls[0]["planStep"] == 0

    def test_an_absent_field_stays_absent(self):
        """A field that is present-but-meaningless on the common case is one
        the next reader has to test twice."""
        notes = TurnNotes()
        notes.see(frame("tool_call", server="s", tool="t", verdict="allow"))
        call = notes.tool_calls[0]
        for key in ("diff", "commit", "image", "appUrl", "grantable", "planStep"):
            assert key not in call

    def test_a_step_settles_in_place_rather_than_twice(self):
        notes = TurnNotes()
        notes.see(frame("step_start", capability="search", doing="Searching the web",
                        done="Searched the web", step_id="s1", target="q"))
        notes.see(frame("step_complete", capability="search", done="Searched the web",
                        step_id="s1", success=True, seconds=1.5, detail=""))
        assert len(notes.tool_calls) == 1
        assert notes.tool_calls[0]["verdict"] == "allow"
        assert notes.tool_calls[0]["seconds"] == 1.5

    def test_a_step_that_never_finished_is_not_left_spinning(self):
        """A reopened transcript showing a spinner for a call that stopped
        weeks ago is the worst kind of wrong: it reads as live."""
        notes = TurnNotes()
        notes.see(frame("step_start", capability="search", doing="Searching",
                        done="Searched", step_id="s1"))
        assert notes.tool_calls[0]["verdict"] == "refuse"
        assert notes.tool_calls[0]["reason"] == "did not finish"

    def test_it_keeps_the_last_plan_not_every_revision(self):
        notes = TurnNotes()
        notes.see(frame("plan", items=[{"text": "one", "status": "doing"}], awaiting_go=False))
        notes.see(frame("plan", items=[{"text": "one", "status": "done"},
                                       {"text": "two", "status": "doing"}], awaiting_go=False))
        assert len(notes.plan["items"]) == 2
        assert notes.plan["items"][0]["status"] == "done"

    def test_the_engines_own_step_list_is_not_stored(self):
        """`source == "planner"` is live-only — the interface shows it while
        the reply is in flight. Storing it would put a second, differently
        worded checklist under every planned reply."""
        notes = TurnNotes()
        notes.see(frame("plan", items=[{"text": "recall", "status": "done"}],
                        awaiting_go=False, source="planner"))
        assert notes.plan is None

    def test_awaiting_go_crosses_as_camel_case(self):
        notes = TurnNotes()
        notes.see(frame("plan", items=[{"text": "x", "status": "todo"}], awaiting_go=True))
        assert notes.plan["awaitingGo"] is True

    def test_it_collects_artifact_ids_in_order_without_repeats(self):
        notes = TurnNotes()
        notes.see(frame("artifact", id="art_1", filename="a.xlsx"))
        notes.see(frame("artifact", id="art_2", filename="b.pdf"))
        notes.see(frame("artifact", id="art_1", filename="a.xlsx"))
        assert notes.artifact_ids == ["art_1", "art_2"]

    def test_a_rows_position_follows_the_text_that_had_arrived(self):
        """Where the row sits between the paragraphs."""
        notes = TurnNotes()
        notes.see(frame("tool_call", server="s", tool="first", verdict="allow"), answer_len=0)
        notes.see(frame("tool_call", server="s", tool="second", verdict="allow"), answer_len=120)
        assert notes.tool_calls[0]["at"] == 0
        assert notes.tool_calls[1]["at"] == 120

    def test_an_unreadable_frame_is_skipped_not_raised(self):
        """Bookkeeping must never be able to interrupt a reply."""
        notes = TurnNotes()
        notes.see("not json at all")
        notes.see(json.dumps(["a", "list"]))
        notes.see(json.dumps({"type": "tool_call", "data": "not a dict"}))
        assert notes.is_empty()

    def test_a_token_frame_adds_nothing(self):
        notes = TurnNotes()
        notes.see(frame("token", content="hello"))
        assert notes.is_empty()


class TestItCannotGrowWithoutBound:
    """A transcript row is read whole every time the conversation opens."""

    def test_a_long_output_is_clipped_and_says_so(self):
        notes = TurnNotes()
        notes.see(frame("tool_call", server="s", tool="t", verdict="allow",
                        output="x" * (MAX_FIELD_CHARS + 500)))
        output = notes.tool_calls[0]["output"]
        assert len(output) < MAX_FIELD_CHARS + 20
        assert output.endswith("…"), "a clipped field that just stops reads as that length"

    def test_a_long_diff_is_clipped_too(self):
        notes = TurnNotes()
        notes.see(frame("tool_call", server="s", tool="t", verdict="allow",
                        diff="y" * (MAX_FIELD_CHARS + 500)))
        assert len(notes.tool_calls[0]["diff"]) < MAX_FIELD_CHARS + 20

    def test_a_runaway_loop_stops_adding_rows(self):
        notes = TurnNotes()
        for _ in range(MAX_CALLS + 50):
            notes.see(frame("tool_call", server="s", tool="t", verdict="allow"))
        assert len(notes.tool_calls) == MAX_CALLS


# ------------------------------------------------------- the line that holds


class TestCitationsStayOut:
    """The refusal `resumeConversation` already makes, and why this does not
    widen it.

    A citation is a claim that *this* answer used *that* fact. Rule 4 lets
    the fact be corrected or deleted, so rendering yesterday's citation
    against today's Spine shows provenance that no longer holds — worse than
    showing none. A tool call, a checklist and a file are records of what
    happened, and nothing about them becomes false later.
    """

    def test_sources_are_not_collected(self):
        notes = TurnNotes()
        notes.see(frame("source", id="m1", text="the rate is 450/day", relevance=0.8))
        assert notes.is_empty()

    def test_reasoning_is_not_collected(self):
        """The model's working, never part of what it said."""
        notes = TurnNotes()
        notes.see(frame("reasoning", content="let me think about this"))
        assert notes.is_empty()

    def test_the_store_has_nowhere_to_put_one(self, records):
        """Enforced by the schema rather than by remembering. A later caller
        cannot pass sources to `append` because there is no parameter."""
        import inspect

        taken = set(inspect.signature(records.append).parameters)
        assert "sources" not in taken
        assert "citations" not in taken


# ----------------------------------------------------------------- the wire


class TestItReachesTheRenderer:
    """Against the **real** application object.

    `tests/test_routes_are_mounted.py` exists because a complete router with
    a passing test file and no `include_router` answered 404 on the running
    product while its tests stayed green. A store that round-trips and a
    route that does not serve the field look identical from the layer below.
    """

    @pytest.fixture()
    def client(self, tmp_path):
        from fastapi.testclient import TestClient

        import main
        from conversations.api import set_records

        set_records(ConversationRecords(str(tmp_path / "conversations.db")))
        return TestClient(main.app)

    def test_the_restored_transcript_carries_what_the_reply_did(self, client):
        from conversations.api import _records

        conversation_id = client.post("/conversations", json={}).json()["id"]
        records = _records()
        records.append(conversation_id, USER, "build the spreadsheet")
        records.append(
            conversation_id,
            ASSISTANT,
            "Done.",
            tool_calls=[{"server": "zaram", "tool": "document.generate",
                         "verdict": "allow", "at": 5}],
            plan={"items": [{"text": "read the figures", "status": "done"}],
                  "awaitingGo": False},
            artifact_ids=["art_9"],
        )

        body = client.get(f"/conversations/{conversation_id}").json()
        reply = body["messages"][-1]
        # camelCase on the wire: these cross into `ChatToolCall` and
        # `ChatPlan` with no mapping, so a restored message renders through
        # the same components a live one does.
        assert reply["toolCalls"][0]["tool"] == "document.generate"
        assert reply["plan"]["awaitingGo"] is False
        assert reply["artifactIds"] == ["art_9"]

    def test_a_plain_reply_sends_empties_rather_than_nulls(self, client):
        from conversations.api import _records

        conversation_id = client.post("/conversations", json={}).json()["id"]
        _records().append(conversation_id, USER, "hello")

        reply = client.get(f"/conversations/{conversation_id}").json()["messages"][0]
        assert reply["toolCalls"] == []
        assert reply["artifactIds"] == []
        assert reply["plan"] is None
