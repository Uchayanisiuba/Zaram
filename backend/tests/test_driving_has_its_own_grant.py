"""Driving the app is consented to separately from running its commands.

Driving shipped on 3 October 2026 under `runs`, with the toggle's sentence
widened to say so, and the maintainer's call the same day was that it should be
its own grant. They are right, and the reason is worth asserting rather than
only writing down.

**They are not the same risk.** Running the project's detected commands is
`npm test` and `tsc` — bounded, named, worst case a failing build. Driving the
app is pressing whatever is on the page, and the hazard is not Zaram clicking
around a toy: it is a dev build pointed at a production database, where "Delete
account" does. Somebody can reasonably want the first and not the second, and a
grant that cannot express that is a grant that gets refused whole.

It is also the shape `CLAUDE.md` already uses twice — *"permitting cloud models
does not permit mutation, and permitting file edits does not permit cloud"* —
two consents, separately given, because they answer different questions.

So the thing worth testing is not that the grant exists. It is the four
**independences**: each of the three grants is reachable alone, and none of
them implies another. A gate that passes its own test and widens on one of its
siblings is the failure the split was made to prevent.

Nothing here launches a browser. `test_zaram_can_drive_its_own_app.py` does
that against a real page; this is about the gate in front of it, which is
decided before any process starts.
"""

from __future__ import annotations

import pytest

from packs.code import (
    SERVER_ID,
    CodeRunner,
    CodeTools,
    CodeWriter,
    DrivingTools,
    drives_granted,
    runs_granted,
    set_active_root,
    writes_granted,
)
from packs.code import driving, writes
from packs.code.driving import HOW_TO_PERMIT, OPEN_IN_BROWSER
from packs.code.runners import HOW_TO_PERMIT as RUNS_HOW_TO_PERMIT
from packs.code.runners import RUN_COMMAND
from runtimes.mcp.config import ServerConfig, ServerStore, WriteMode
from runtimes.mcp.runtime import CALL, McpRuntime


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "vitest"}}', encoding="utf-8")
    return tmp_path


@pytest.fixture
def tools(repo):
    """The whole pack, wired as `bootstrapper.py` wires it.

    All three grants read from the `ContextVar`s rather than from a lambda
    fixed per test, because the question is whether *those* are independent —
    hard-coding `drives_granted=lambda: True` would assert the test's own
    plumbing.
    """
    return CodeTools(
        lambda: repo,
        writer=CodeWriter(),
        writes_granted=writes_granted,
        runner=CodeRunner(),
        runs_granted=runs_granted,
        driving=DrivingTools(),
        drives_granted=drives_granted,
    )


@pytest.fixture
def runtime(tools, tmp_path_factory):
    store = ServerStore(str(tmp_path_factory.mktemp("store") / "servers.json"))
    runtime = McpRuntime(store=store)
    runtime.register_builtin(
        ServerConfig(server_id=SERVER_ID, writes=WriteMode.HOST_UNDO), tools
    )
    return runtime


@pytest.fixture(autouse=True)
def clear_context():
    set_active_root(None)
    yield
    set_active_root(None)


class TestTheThreeGrantsAreIndependent:
    def test_nothing_is_granted_by_default(self, tools, repo):
        set_active_root(str(repo))
        granted = tools.granted_tools()
        assert not (granted & driving.TOOL_NAMES)

    def test_runs_does_not_grant_driving(self, tools, repo):
        """The one that was wrong until now."""
        set_active_root(str(repo), runs=True)
        granted = tools.granted_tools()
        assert RUN_COMMAND in granted
        assert not (granted & driving.TOOL_NAMES)

    def test_writes_does_not_grant_driving(self, tools, repo):
        set_active_root(str(repo), writes=True)
        assert not (tools.granted_tools() & driving.TOOL_NAMES)

    def test_driving_does_not_grant_runs_or_writes(self, tools, repo):
        """The direction that matters more.

        Somebody allowing Zaram to click around a dev build has not allowed it
        to run the build, and has certainly not allowed it to edit the source.
        """
        set_active_root(str(repo), drives=True)
        granted = tools.granted_tools()
        assert driving.TOOL_NAMES <= granted
        assert RUN_COMMAND not in granted
        assert not (granted & writes.TOOL_NAMES)

    def test_granted_every_driving_tool_is_allowed(self, tools, repo):
        set_active_root(str(repo), drives=True)
        assert driving.TOOL_NAMES <= tools.granted_tools()

    def test_a_grant_without_a_folder_permits_nothing(self, tools):
        """Clearing the root clears all three.

        A grant left set with no folder would be inherited by whichever
        project opened next, which is the whole reason these are request-scoped.
        """
        set_active_root(None, drives=True)
        assert drives_granted() is False
        assert not (tools.granted_tools() & driving.TOOL_NAMES)


class TestTheRefusalNamesTheRightSwitch:
    """A refusal pointing at the wrong control is worse than a vague one.

    The person turns something on, asks again, and is refused again with the
    same sentence — and concludes the product is broken rather than that they
    pressed the wrong box.
    """

    def test_driving_points_at_the_driving_control(self, tools):
        assert tools.how_to_permit(OPEN_IN_BROWSER) == HOW_TO_PERMIT
        assert "drive the app" in HOW_TO_PERMIT

    def test_running_still_points_at_the_running_control(self, tools):
        assert tools.how_to_permit(RUN_COMMAND) == RUNS_HOW_TO_PERMIT

    def test_the_two_sentences_are_different(self):
        assert HOW_TO_PERMIT != RUNS_HOW_TO_PERMIT

    @pytest.mark.asyncio
    async def test_ungranted_a_drive_asks_and_says_where(self, runtime, repo):
        set_active_root(str(repo), runs=True)
        result = await runtime.execute(
            CALL,
            {
                "server": SERVER_ID,
                "tool": OPEN_IN_BROWSER,
                "arguments": {"url": "http://localhost:5173"},
            },
        )
        assert result["needs_confirmation"] is True
        assert HOW_TO_PERMIT in result["reason"]


class TestTheStoreHoldsIt:
    """The grant is a column, because rule 7j's remembered consent is only
    acceptable while it is visible in one place and revocable there."""

    def test_off_by_default_and_settable(self, tmp_path):
        from projects.records import ProjectRecords, ProjectType

        records = ProjectRecords(str(tmp_path / "projects.db"))
        project = records.create("App", type=ProjectType.CODING, root=str(tmp_path))
        assert project.drives is False
        assert records.set_drives(project.id, True).drives is True
        assert records.set_drives(project.id, False).drives is False

    def test_it_does_not_move_the_other_two(self, tmp_path):
        from projects.records import ProjectRecords, ProjectType

        records = ProjectRecords(str(tmp_path / "projects.db"))
        project = records.create("App", type=ProjectType.CODING, root=str(tmp_path))
        records.set_runs(project.id, True)
        after = records.set_drives(project.id, True)
        assert after.runs is True
        assert after.writes is False
        withdrawn = records.set_drives(project.id, False)
        assert withdrawn.runs is True

    def test_a_database_written_before_the_column_existed_still_opens(self, tmp_path):
        """The migration, asserted the way the `runs` one should have been.

        `CREATE TABLE IF NOT EXISTS` is silent about a table that exists and
        differs, which is how a schema change becomes `no such column` on
        somebody's machine and nowhere else.
        """
        import sqlite3

        path = tmp_path / "projects.db"
        with sqlite3.connect(path) as conn:
            conn.execute(
                """
                CREATE TABLE projects (
                    id         TEXT PRIMARY KEY,
                    name       TEXT NOT NULL,
                    type       TEXT NOT NULL DEFAULT 'general',
                    created_at REAL NOT NULL,
                    note       TEXT NOT NULL DEFAULT '',
                    root       TEXT NOT NULL DEFAULT '',
                    writes     INTEGER NOT NULL DEFAULT 0,
                    runs       INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                "INSERT INTO projects (id, name, type, created_at, note, root, writes, runs)"
                " VALUES ('old', 'Before', 'coding', 1.0, '', ?, 1, 1)",
                (str(tmp_path),),
            )

        from projects.records import ProjectRecords

        records = ProjectRecords(str(path))
        project = records.get("old")
        assert project.drives is False
        assert project.runs is True
        assert records.set_drives("old", True).drives is True


class TestTheNameGuessDoesNotWaveDrivingThrough:
    """`open_in_browser` ran under no grant, because of its own name.

    Found 3 October 2026 by printing the gate's verdict for each of the pack's
    tool names rather than trusting the grant test above, which had just gone
    green. `looks_read_only` is a substring guess over a word list — its own
    comment says *"a server author picks the names"* — and here it fired on
    Zaram's own: `open_in_browser` contains `_browser`, which contains
    `_browse`, which is in the list. So the gate classified launching a Chrome
    process as looking at something, and it ran with every grant off.

    Not a hypothetical. The probe that found it started a real browser against
    the real dev server with `drives=False` and `runs=False`.
    """

    def test_the_guess_still_gets_it_wrong_on_its_own(self):
        """The defect, asserted rather than described.

        If the word list ever changes so this passes for the right reason,
        this test fails and says to delete it — which is the correct outcome
        and better than it quietly becoming vacuous.
        """
        from runtimes.mcp.policy import looks_read_only

        assert looks_read_only(OPEN_IN_BROWSER) is True, (
            "the name guess no longer mis-reads open_in_browser; the override "
            "below may be unnecessary — check before removing it"
        )

    def test_the_pack_says_which_of_its_tools_mislead(self, tools):
        mutative = tools.mutative_tools()
        assert OPEN_IN_BROWSER in mutative
        assert driving.CLOSE_BROWSER in mutative
        # The two that genuinely only look stay out, so they keep working on a
        # machine where nothing has been granted.
        assert driving.READ_APP_PAGE not in mutative
        assert driving.READ_APP_CONSOLE not in mutative

    @pytest.mark.asyncio
    async def test_ungranted_opening_a_browser_asks(self, runtime, repo):
        set_active_root(str(repo))
        result = await runtime.execute(
            CALL,
            {
                "server": SERVER_ID,
                "tool": OPEN_IN_BROWSER,
                "arguments": {"url": "http://localhost:1"},
            },
        )
        assert result.get("needs_confirmation") is True
        assert HOW_TO_PERMIT in result["reason"]

    @pytest.mark.asyncio
    async def test_granted_it_stops_asking(self, runtime, repo):
        """**Needing the grant and asking every time are different verdicts.**

        The first fix for this reused `readOnlyHint: False`, which `decide`
        believes — and `_annotation_says_destructive` reads the same hint, so
        every driving tool became destructive and asked on every call however
        much had been granted. That is rule 7j's forty dialogs a day. This is
        the test that would have caught it.
        """
        set_active_root(str(repo), drives=True)
        for name in (OPEN_IN_BROWSER, driving.CLICK_IN_APP, driving.TYPE_IN_APP):
            result = await runtime.execute(
                CALL,
                {
                    "server": SERVER_ID,
                    "tool": name,
                    "arguments": {"url": "http://localhost:1", "ref": "e1", "text": "x"},
                },
            )
            assert not result.get("needs_confirmation"), (
                f"{name} asked again after the grant was given"
            )

    @pytest.mark.asyncio
    async def test_reading_an_open_page_needs_no_grant(self, runtime, repo):
        """It is the look `look_at_app` already performs, and it must keep
        working on a machine where nothing has been allowed — otherwise the
        read-only tier does not ship first in practice."""
        set_active_root(str(repo))
        for name in (driving.READ_APP_PAGE, driving.READ_APP_CONSOLE):
            result = await runtime.execute(
                CALL, {"server": SERVER_ID, "tool": name, "arguments": {}}
            )
            assert not result.get("needs_confirmation")
            assert not result.get("refused")

    def test_a_builtin_that_says_nothing_is_unchanged(self, tmp_path_factory):
        """Most built-ins have no `mutative_tools`, and the guess must stand
        for them exactly as it did — this is an override, not a new gate."""
        from runtimes.mcp.policy import Verdict, decide

        plain = decide(tool_name="list_things", mode=WriteMode.HOST_UNDO)
        assert plain.verdict is Verdict.ALLOW
        overridden = decide(
            tool_name="list_things", mode=WriteMode.HOST_UNDO, not_read_only=True
        )
        assert overridden.verdict is Verdict.CONFIRM

    def test_the_override_cannot_widen(self):
        """One-directional, like everything else on this path.

        There is no way to declare a tool read-only, so a mistake in
        `mutative_tools` makes the gate stricter and never looser.
        """
        from runtimes.mcp.policy import Verdict, decide

        # A genuine write, with the override off — still asks.
        assert (
            decide(tool_name="edit_file", mode=WriteMode.HOST_UNDO).verdict
            is Verdict.CONFIRM
        )
        # And destructive stays destructive whatever is granted.
        assert (
            decide(
                tool_name="delete_everything",
                mode=WriteMode.HOST_UNDO,
                granted_tools={"delete_everything"},
            ).verdict
            is Verdict.CONFIRM
        )
