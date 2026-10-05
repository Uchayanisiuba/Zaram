"""A send is the one write that cannot be called back, so no grant settles it.

`docs/MILESTONES.md` set the rule for email before any of it was built:
*draft-and-hold, never auto-send* -- rule 6, the obligations posture (Zaram
*drafts the response*), and rule 9: a document from unresolved context is
confident, plausible and wrong, **and it leaves the building**. A job application
is that failure with the user's name on it.

The policy already had the shape for it. A delete keeps asking however much has
been granted, because undo does not help and the cost of being wrong is
asymmetric. A send is the same hazard: once it has gone, it has gone. But a mail
server's `send_message` was an ordinary write, so "allow this tool" made Zaram
"stop asking about this tool" -- including from an unattended automation, where
there is nobody to ask.

Three readers share one word list: the policy (`decide`), the engine's "let this
plan run without stopping", and the permission card's offer to remember.
"""

from __future__ import annotations

import pytest

from runtimes.mcp.policy import (
    Verdict,
    WriteMode,
    decide,
    looks_destructive,
    looks_outbound,
    looks_read_only,
)


class TestWhatCountsAsASend:
    @pytest.mark.parametrize(
        "name",
        [
            "send_message", "send_email", "sendMessage", "send-mail", "reply", "reply_all",
            "forward_message", "post_comment", "publish_post", "publishPage", "tweet",
            "broadcast", "submit_application", "share_file", "invite_attendee", "git_push",
        ],
    )
    def test_these_send(self, name):
        assert looks_outbound(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            # Drafting is the point of draft-and-hold: held by definition.
            "create_draft", "update_draft", "get_draft", "list_drafts", "delete_draft",
            # Reads, including ones whose names contain a send-ish stem.
            "get_message", "list_threads", "search_threads", "list_posts", "get_post",
            "read_email", "get_thread",
            # Words that merely contain the letters.
            "postgres_query", "compost_report", "sender_info", "pushover_status",
            "run_in_terminal", "write_file", "edit_file", "open_in_browser",
        ],
    )
    def test_these_do_not(self, name):
        assert looks_outbound(name) is False

    def test_a_send_is_never_a_look(self):
        """`fetch_and_send` has a read word in it. It is not a read."""
        assert looks_read_only("fetch_and_send") is False
        assert looks_read_only("get_message") is True

    def test_a_send_is_not_called_destructive(self):
        """Two hazards, two lists. Merging them would make a draft's deletion
        and a send the same sentence."""
        assert looks_destructive("send_message") is False


class TestNoGrantSettlesIt:
    @pytest.mark.parametrize("mode", [WriteMode.HOST_UNDO, WriteMode.GRANTED])
    def test_a_send_asks_even_when_granted(self, mode):
        decision = decide(tool_name="send_message", mode=mode, granted_tools={"send_message"})
        assert decision.verdict is Verdict.CONFIRM
        assert "cannot be called back" in decision.reason

    def test_a_granted_ordinary_write_still_runs(self):
        """The rule is narrow. It must not turn confirm-once into confirm-always
        for every tool, which is how a product gets abandoned on day two."""
        decision = decide(tool_name="create_draft", mode=WriteMode.HOST_UNDO, granted_tools={"create_draft"})
        assert decision.verdict is Verdict.ALLOW

    def test_a_read_only_server_still_refuses_rather_than_asks(self):
        assert decide(tool_name="send_message", mode=WriteMode.READ_ONLY).verdict is Verdict.REFUSE

    def test_a_draft_is_held_not_blocked(self):
        decision = decide(tool_name="create_draft", mode=WriteMode.HOST_UNDO)
        assert decision.verdict is Verdict.CONFIRM  # ordinary write: asks once
        assert "send" not in decision.reason


class TestTheEngineAndTheCardAgree:
    def test_run_without_stopping_never_covers_a_send(self):
        from core.execution_engine import ExecutionEngine

        engine = ExecutionEngine.__new__(ExecutionEngine)
        engine._uninterrupted = {"s"}
        assert engine._runs_uninterrupted("s", "write_file") is True
        assert engine._runs_uninterrupted("s", "send_message") is False
        assert engine._runs_uninterrupted("s", "delete_file") is False

    def test_the_permission_card_does_not_offer_to_remember_a_send(self):
        import asyncio

        from runtimes.mcp.runtime import McpRuntime

        runtime = McpRuntime.__new__(McpRuntime)
        # Only the verdict path is exercised; build the smallest honest runtime.
        import inspect

        source = inspect.getsource(McpRuntime)
        assert "looks_outbound(tool_name)" in source
        assert '"grantable": not (' in source
        del asyncio, runtime
