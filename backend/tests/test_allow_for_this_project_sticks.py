"""*Allow for this project* has to settle the tool it was offered for.

Reported by the maintainer, 11 October 2026, with a screenshot: during a coding
project the permission card for `start_app_stack` offered **Deny · Allow for
this conversation · Allow for this project · Always**. Pressing *Allow for this
project* — repeatedly — changed nothing; the card came back every time, and only
*Allow for this conversation* made it stop.

**Two mappings answered one question and disagreed.** `CodeTools.grant_scope`
sent every tool in `apps.TOOL_NAMES` to the `runs` switch, so the card offered
that switch and the press turned it on. `CodeTools.granted_tools`, which is what
the gate reads once the switch is on, named three app tools by hand —
`start_app`, `stop_app`, `look_at_app` — and had never been widened when the
stack tools arrived. `start_app_stack` was therefore *offered* a grant that
*could not* settle it, which is the button-that-changes-nothing this codebase
already refuses elsewhere. A conversation grant is by tool name, which is why
that rung alone worked.

The test that would have caught it is not about one tool, because the next tool
added to a pack would fail the same way. So the contract is asserted over every
tool the pack lists: **whatever `grant_scope` sends to a switch, that switch
being on must be enough.**
"""

from __future__ import annotations

import pytest

from packs.code import (
    SERVER_ID,
    AppTools,
    CodeRunner,
    CodeTools,
    CodeWriter,
    DrivingTools,
    TerminalTools,
    drives_granted,
    runs_granted,
    set_active_root,
    shell_granted,
    writes_granted,
)
from packs.code import apps
from packs.code.apps import START_APP_STACK, STOP_APP_STACK
from runtimes.mcp.config import ServerConfig, ServerStore, WriteMode
from runtimes.mcp.policy import Verdict, decide, looks_destructive, looks_outbound
from runtimes.mcp.runtime import CALL, McpRuntime

SWITCHES = ("writes", "runs", "drives", "shell")


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"scripts": {"dev": "vite", "test": "vitest"}}', encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def tools(repo, tmp_path_factory):
    """The whole pack, wired as `bootstrapper.py` wires it: the grants are
    read from the request's `ContextVar`s, not from a lambda the test fixes."""
    return CodeTools(
        lambda: repo,
        writer=CodeWriter(),
        writes_granted=writes_granted,
        runner=CodeRunner(),
        runs_granted=runs_granted,
        app=AppTools(screens_dir=tmp_path_factory.mktemp("screens")),
        driving=DrivingTools(),
        drives_granted=drives_granted,
        shell=TerminalTools(),
        shell_granted=shell_granted,
    )


@pytest.fixture
def runtime(tools, tmp_path_factory):
    store = ServerStore(str(tmp_path_factory.mktemp("store") / "servers.json"))
    runtime = McpRuntime(store=store)
    runtime.register_builtin(ServerConfig(server_id=SERVER_ID, writes=WriteMode.HOST_UNDO), tools)
    return runtime


@pytest.fixture(autouse=True)
def clear_context():
    set_active_root(None)
    yield
    set_active_root(None)


def _verdict(tools, name, granted):
    return decide(
        server_id=SERVER_ID,
        tool_name=name,
        mode=WriteMode.HOST_UNDO,
        granted_tools=granted,
        not_read_only=name in tools.mutative_tools(),
    ).verdict


class TestTheSwitchTheCardOffersIsEnough:
    def test_the_stack_tools_are_granted_by_the_runs_switch(self, tools, repo):
        """The reported tool, and its sibling that was missed the same way."""
        set_active_root(str(repo), runs=True)
        granted = tools.granted_tools()
        assert {START_APP_STACK, STOP_APP_STACK} <= granted

    def test_every_app_tool_is_covered_not_a_list_of_three(self, tools, repo):
        set_active_root(str(repo), runs=True)
        assert apps.TOOL_NAMES <= tools.granted_tools()

    @pytest.mark.parametrize("switch", SWITCHES)
    def test_the_switch_named_for_a_tool_settles_it(self, tools, repo, switch):
        """The contract, over every tool the pack lists.

        For each switch: turn on only that one, and every tool `grant_scope`
        maps to it must come back allowed — unless it is a destructive or an
        outbound name, which no grant settles and which the card does not
        offer one for (`grantable`).
        """
        set_active_root(str(repo), **{switch: True})
        granted = tools.granted_tools()
        covered = [t.name for t in tools.list_tools() if tools.grant_scope(t.name) == switch]
        assert covered, f"no tool maps to {switch}"
        for name in covered:
            if looks_destructive(name) or looks_outbound(name):
                continue
            assert _verdict(tools, name, granted) is Verdict.ALLOW, (
                f"{name} is offered the {switch} switch, which is on, and still asks"
            )

    def test_the_runs_switch_does_not_reach_a_wider_one(self, tools, repo):
        """Widening the app tools' grant must not widen it past `runs`."""
        from packs.code import driving, terminal, writes

        set_active_root(str(repo), runs=True)
        granted = tools.granted_tools()
        assert not (granted & driving.TOOL_NAMES)
        assert not (granted & terminal.TOOL_NAMES)
        assert not (granted & writes.TOOL_NAMES)


class TestThroughTheRuntime:
    """The gate itself, with the request's project carried the way the chat
    route carries it."""

    async def _call(self, runtime, name, session=""):
        return await runtime.execute(
            CALL,
            {"server": SERVER_ID, "tool": name, "arguments": {"runners": []}, "session": session},
        )

    @pytest.mark.asyncio
    async def test_without_the_switch_the_stack_asks_and_names_it(self, runtime, repo):
        set_active_root(str(repo))
        result = await self._call(runtime, START_APP_STACK)
        assert result["needs_confirmation"] is True
        assert result["grant_scope"] == "runs"
        assert result["grantable"] is True
        # The card reads this to withhold "Always", which a built-in cannot keep.
        assert result["builtin"] is True

    @pytest.mark.asyncio
    async def test_an_attached_server_is_not_called_a_built_in(self, tmp_path):
        """The other half: an attached server keeps its "Always"."""
        store = ServerStore(str(tmp_path / "servers.json"))
        runtime = McpRuntime(store=store)
        runtime.register_builtin(ServerConfig(server_id=SERVER_ID), object())
        assert (SERVER_ID in runtime._builtin) is True
        assert ("weather" in runtime._builtin) is False

    @pytest.mark.asyncio
    async def test_after_allow_for_this_project_the_next_call_does_not_ask(self, runtime, repo):
        """The reported bug, end to end: the press is the switch, and the
        next identical call goes through."""
        set_active_root(str(repo))
        assert (await self._call(runtime, START_APP_STACK))["needs_confirmation"] is True

        set_active_root(str(repo), runs=True)  # what PATCH /projects/{id} {runs: true} does
        for name in (START_APP_STACK, STOP_APP_STACK):
            result = await self._call(runtime, name)
            assert not result.get("needs_confirmation"), f"{name} asked again after the grant"

    @pytest.mark.asyncio
    async def test_another_project_is_still_asked(self, runtime, repo, tmp_path_factory):
        """A project grant is per project (the maintainer's own decision)."""
        other = tmp_path_factory.mktemp("other")
        set_active_root(str(repo), runs=True)
        assert not (await self._call(runtime, START_APP_STACK)).get("needs_confirmation")

        set_active_root(str(other))
        assert (await self._call(runtime, START_APP_STACK))["needs_confirmation"] is True

    @pytest.mark.asyncio
    async def test_a_conversation_grant_is_unaffected(self, runtime, repo):
        set_active_root(str(repo))
        runtime.allow_for_session("s1", SERVER_ID, START_APP_STACK)
        assert not (await self._call(runtime, START_APP_STACK, "s1")).get("needs_confirmation")
        # Another conversation in the same project still asks.
        assert (await self._call(runtime, START_APP_STACK, "s2"))["needs_confirmation"] is True
        # And the grant was for that tool, not its sibling.
        assert (await self._call(runtime, STOP_APP_STACK, "s1"))["needs_confirmation"] is True


class TestAlwaysIsNotOfferedWhereItCannotBeKept:
    """*Always* for a built-in tool posts to `/tools/servers/{id}/grant`, which
    answers 404 for any server not attached by the user — a built-in is never
    in `mcp-servers.json`. And a by-name grant on a project-scoped tool would
    not be the per-project consent the maintainer decided on: the pack's tools
    do not re-check the switch, the gate is the only check. So the route says
    why, rather than a bare 404 the card reads as "did not save"."""

    def test_the_route_explains_a_built_in(self, tools, tmp_path, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from runtimes.mcp import api

        store = ServerStore(str(tmp_path / "servers.json"))
        runtime = McpRuntime(store=store)
        runtime.register_builtin(ServerConfig(server_id=SERVER_ID, writes=WriteMode.HOST_UNDO), tools)
        monkeypatch.setattr(api, "_MCP_RUNTIME", runtime)
        monkeypatch.setattr(api, "_store", lambda: store)
        app = FastAPI()
        app.include_router(api.router)
        client = TestClient(app)

        response = client.post(f"/tools/servers/{SERVER_ID}/grant", json={"tool": START_APP_STACK})
        assert response.status_code == 409
        assert "project" in response.json()["detail"]
        # Nothing was written anywhere.
        assert store.load() == {}
