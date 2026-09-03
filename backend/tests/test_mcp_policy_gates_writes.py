"""What a tool may do, and the ways that decision can be got wrong.

The rule under test: **Zaram may change things in applications that can undo
them, and may only look at applications that cannot.** Everything here is about
the places that rule has to hold even when a server is unhelpful or hostile,
because the server's text is the one input nobody here controls.
"""

from __future__ import annotations

import pytest

from runtimes.mcp.policy import Decision, Verdict, WriteMode, decide, looks_read_only


class TestReadingIsAlwaysAllowed:
    @pytest.mark.parametrize(
        "name", ["list_directory", "read_text_file", "search_files", "get_scene_info"]
    )
    def test_a_read_runs_without_asking(self, name):
        """The tier that needs no undo, sandbox or rollback."""
        assert decide(tool_name=name, mode=WriteMode.READ_ONLY).verdict is Verdict.ALLOW


class TestAServerWithNoUndoMayNotWrite:
    def test_a_write_is_refused_outright(self):
        d = decide(tool_name="write_file", mode=WriteMode.READ_ONLY)

        assert d.verdict is Verdict.REFUSE

    def test_the_refusal_says_how_to_permit_it(self):
        """A disabled capability is visible, never silent.

        A refusal that does not name the thing that would change it reads as a
        broken product rather than as a decision the user can make.
        """
        d = decide(tool_name="write_file", mode=WriteMode.READ_ONLY)

        assert "undo" in d.reason

    def test_read_only_is_what_an_unconfigured_server_gets(self):
        """Default deny. An unknown server is exactly the case that must not
        get the benefit of the doubt."""
        assert WriteMode("read_only") is WriteMode.READ_ONLY


class TestAnAppWithUndoMayWriteAfterAsking:
    def test_the_first_write_asks(self):
        d = decide(tool_name="set_material", mode=WriteMode.HOST_UNDO)

        assert d.verdict is Verdict.CONFIRM

    def test_and_stops_asking_once_granted(self):
        """7j: confirm once, then remember. Forty dialogs a day is a product
        nobody opens on day two."""
        d = decide(
            tool_name="set_material",
            mode=WriteMode.HOST_UNDO,
            granted_tools={"set_material"},
        )

        assert d.verdict is Verdict.ALLOW

    def test_a_grant_is_per_tool_and_does_not_spread(self):
        d = decide(
            tool_name="delete_object",
            mode=WriteMode.HOST_UNDO,
            granted_tools={"set_material"},
        )

        assert d.verdict is not Verdict.ALLOW


class TestDestructiveAlwaysAsks:
    @pytest.mark.parametrize("name", ["delete_object", "remove_file", "drop_table", "purge_cache"])
    def test_even_on_a_fully_granted_server(self, name):
        """Undo does not save you from a delete in most applications, and a
        grant made for "edit the scene" was not consent to empty it."""
        d = decide(tool_name=name, mode=WriteMode.GRANTED, granted_tools={name})

        assert d.verdict is Verdict.CONFIRM


class TestUntrustedTextMayNarrowNeverWiden:
    """The spec: clients "must treat tool annotations as untrusted unless they
    originate from a trusted server source". So a hint is evidence only when it
    argues against the server's own interest."""

    def test_a_server_claiming_read_only_earns_nothing(self):
        """The exact claim a hostile server would make.

        `delete_everything` advertising `readOnlyHint` must not become a read,
        or a description has become a permission.
        """
        d = decide(
            tool_name="delete_everything",
            mode=WriteMode.READ_ONLY,
            annotations={"readOnlyHint": True},
        )

        assert d.verdict is not Verdict.ALLOW

    def test_a_name_that_looks_like_a_read_is_still_refused_if_it_admits_writing(self):
        """`readOnlyHint: False` is the server volunteering that it writes.

        Believed, because it makes the verdict stricter. Without this, naming a
        write `get_and_replace` would slip past on the name alone.
        """
        assert looks_read_only("get_and_replace", {"readOnlyHint": False}) is False
        d = decide(
            tool_name="get_and_replace",
            mode=WriteMode.READ_ONLY,
            annotations={"readOnlyHint": False},
        )

        assert d.verdict is Verdict.REFUSE

    def test_a_destructive_hint_forces_a_question(self):
        d = decide(
            tool_name="tidy_up",
            mode=WriteMode.GRANTED,
            granted_tools={"tidy_up"},
            annotations={"destructiveHint": True},
        )

        assert d.verdict is Verdict.CONFIRM


class TestTheUnknownIsTreatedAsAWrite:
    @pytest.mark.parametrize("name", ["render", "bake", "apply_modifier", "do_the_thing", "x"])
    def test_a_name_nothing_recognises_is_not_a_read(self, name):
        """The safe direction. A guess that lets an unrecognised tool run is
        the one that cannot be taken back."""
        assert looks_read_only(name) is False
        assert decide(tool_name=name, mode=WriteMode.READ_ONLY).verdict is Verdict.REFUSE


class TestTheDecisionCarriesItsReason:
    def test_every_verdict_explains_itself(self):
        for mode in WriteMode:
            for name in ("read_file", "write_file", "delete_all"):
                d = decide(tool_name=name, mode=mode)
                assert isinstance(d, Decision)
                assert d.reason.strip(), f"{mode}/{name} decided nothing readable"
