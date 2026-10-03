"""The policy's word lists match words, not letters inside other words.

Found 3 October 2026 by a terminal tool that asked for confirmation however
much had been granted. `_LOOKS_DESTRUCTIVE` holds `rm`, the test was
`word in tool_name`, and **`"rm" in "run_in_terminal"` is true** — *terminal*
has an r next to an m. So did `format_code`, `transform_mesh`,
`confirm_order` and `warm_cache`.

`destructive` is the one verdict a grant cannot satisfy — *"destructive stays
a question however much has been granted"* — so rule 7j's confirm-once was
broken for a whole class of ordinary tool names, silently. The symptom is a
dialog somebody has already dismissed a hundred times, which is the exact
thing 7j calls "a product nobody opens on day two".

**It is the second time in one day a word list matched inside a word.** This
morning `open_in_browser` was classified read-only because it contains
`_browse`, and a browser process launched under no grant at all. Same defect,
opposite direction, same afternoon — so both lists are tested here, not only
the one that failed.
"""

from __future__ import annotations

import pytest

from runtimes.mcp.policy import (
    Verdict,
    WriteMode,
    decide,
    looks_destructive,
    looks_read_only,
)


class TestTheLettersRM:
    """The specific failure, named so it cannot come back quietly."""

    @pytest.mark.parametrize(
        "name",
        [
            "run_in_terminal",
            "read_terminal",
            "stop_terminal",
            "format_code",
            "format_document",
            "transform_mesh",
            "confirm_order",
            "warm_cache",
            "normalise_path",
        ],
    )
    def test_a_name_that_merely_contains_rm_is_not_destructive(self, name):
        assert looks_destructive(name) is False

    @pytest.mark.parametrize("name", ["rm", "rm_tree", "rm-rf", "do_rm_now"])
    def test_rm_as_its_own_word_still_is(self, name):
        assert looks_destructive(name) is True


class TestTheLongerWordsStillCatchTheirFamily:
    """Shortening the match must not stop it working.

    `delete`, `remove`, `destroy`, `purge` and `truncate` are distinctive
    enough that a token starting with one means what it says, so they match
    by prefix. Short words do not get that, which is the whole fix.
    """

    @pytest.mark.parametrize(
        "name",
        [
            "delete_file",
            "deleteAll",
            "remove_user",
            "removeMany",
            "destroy_scene",
            "purge_cache",
            "truncate_table",
            "drop_table",
        ],
    )
    def test_it_is_destructive(self, name):
        assert looks_destructive(name) is True

    def test_a_different_stem_is_not_caught_and_that_is_acceptable(self):
        """`deletion_sweep` is not matched, and the fallback is why that is
        tolerable rather than a hole.

        Prefix matching covers `delete`, `deletes`, `deleteAll` — the same
        stem. `deletion` is a different one, so it slips the list. What
        catches it instead is `decide`'s default: anything unrecognised is
        treated as a write and asks once. The difference is *always asks*
        versus *asks until granted*, not *asks* versus *silent*, and
        lengthening the word list to chase every inflection is how a
        denylist grows forever while still failing open.
        """
        from runtimes.mcp.policy import Verdict, WriteMode, decide

        assert looks_destructive("deletion_sweep") is False
        assert (
            decide(tool_name="deletion_sweep", mode=WriteMode.HOST_UNDO).verdict
            is Verdict.CONFIRM
        )

    def test_but_a_short_word_inside_a_longer_one_is_not(self):
        """`drop` is four letters, so it must be a token of its own."""
        assert looks_destructive("dropdown_select") is False
        assert looks_destructive("backdrop_render") is False


class TestEveryNamingConventionIsReadTheSame:
    """A server author picks the spelling, and all three mean one thing."""

    @pytest.mark.parametrize(
        "name", ["delete_file", "deleteFile", "delete-file", "Delete_File"]
    )
    def test_the_same_three_words(self, name):
        assert looks_destructive(name) is True

    @pytest.mark.parametrize("name", ["list_files", "listFiles", "list-files"])
    def test_read_only_too(self, name):
        assert looks_read_only(name) is True


class TestWhatItMeansForAGrant:
    """The consequence, rather than the classifier in isolation.

    A unit test of `looks_destructive` would have passed all afternoon while
    the product asked on every call; what broke was the verdict.
    """

    def test_a_granted_terminal_tool_stops_asking(self):
        decision = decide(
            tool_name="run_in_terminal",
            mode=WriteMode.HOST_UNDO,
            granted_tools={"run_in_terminal"},
        )
        assert decision.verdict is Verdict.ALLOW

    def test_an_ungranted_one_still_asks(self):
        decision = decide(tool_name="run_in_terminal", mode=WriteMode.HOST_UNDO)
        assert decision.verdict is Verdict.CONFIRM

    def test_a_genuinely_destructive_tool_asks_even_when_granted(self):
        """Unchanged, and the reason the false positives mattered: this
        verdict is the one a grant cannot satisfy, so a tool landing in it by
        accident can never be allowed."""
        decision = decide(
            tool_name="delete_everything",
            mode=WriteMode.HOST_UNDO,
            granted_tools={"delete_everything"},
        )
        assert decision.verdict is Verdict.CONFIRM


class TestTheGuessIsStillOneDirectional:
    """Both lists may only make the verdict stricter, never looser.

    A server's own `readOnlyHint: False` is believed; nothing it can say
    makes a tool read-only.
    """

    def test_a_server_cannot_declare_itself_read_only(self):
        assert looks_read_only("list_files", {"readOnlyHint": True}) is True
        assert looks_read_only("list_files", {"readOnlyHint": False}) is False

    def test_an_unrecognised_name_is_treated_as_a_write(self):
        assert looks_read_only("frobnicate") is False
        decision = decide(tool_name="frobnicate", mode=WriteMode.HOST_UNDO)
        assert decision.verdict is Verdict.CONFIRM
