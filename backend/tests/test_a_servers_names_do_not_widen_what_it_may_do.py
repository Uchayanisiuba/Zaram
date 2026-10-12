"""A name never widens a permission, and cua-driver's names belong to cua-driver.

10 October 2026, found auditing a batch of changes that put cua-driver's tool
names into `decide` for every server, and added generic words (`config`, `state`,
`window`, `permissions`, `session`) to the list of names that run without asking.
A stranger's `set_config` or `grant_permissions` then looked like a read, and a
stranger's `get_config` was answered "reads only" ahead of its own
`destructiveHint`. `policy.py` says its guesses may only ever move a tool from
"runs freely" to "asks".
"""

from __future__ import annotations

import pytest

from runtimes.mcp.config import WriteMode
from runtimes.mcp.policy import Verdict, decide, looks_read_only


@pytest.mark.parametrize(
    "tool",
    ["set_config", "write_config", "grant_permissions", "set_permissions",
     "set_state", "clear_state", "close_window", "spawn_agent", "create_session"],
)
def test_a_generic_word_does_not_make_a_write_look_like_a_read(tool):
    assert not looks_read_only(tool)
    verdict = decide(tool_name=tool, mode=WriteMode.READ_ONLY, server_id="some-stranger")
    assert verdict.verdict is Verdict.REFUSE


@pytest.mark.parametrize("tool", ["zoom", "check_permissions", "health_report", "click", "kill_app"])
def test_cua_names_mean_nothing_on_another_server(tool):
    # `zoom` and friends are only "reads only" because cua-driver says so.
    for server in ("some-stranger", "files", ""):
        verdict = decide(tool_name=tool, mode=WriteMode.READ_ONLY, server_id=server)
        assert verdict.verdict is Verdict.REFUSE, (tool, server, verdict)


def test_cua_driver_still_reads_by_its_own_names():
    assert decide(tool_name="zoom", mode=WriteMode.READ_ONLY, server_id="cua-driver").verdict is Verdict.ALLOW


def test_a_cua_read_is_not_waved_through_over_the_servers_own_destructive_hint():
    verdict = decide(
        tool_name="get_config",
        mode=WriteMode.READ_ONLY,
        annotations={"destructiveHint": True},
        server_id="cua-driver",
    )
    assert verdict.verdict is not Verdict.ALLOW


def test_a_grant_stops_the_asking_for_a_tool_with_browser_in_its_name():
    # `browser` was a destructive word, and a grant cannot satisfy a destructive
    # verdict: open_in_browser asked again after every allow.
    verdict = decide(
        tool_name="open_in_browser",
        mode=WriteMode.HOST_UNDO,
        granted_tools={"open_in_browser"},
        not_read_only=True,
        server_id="code",
    )
    assert verdict.verdict is Verdict.ALLOW


def test_a_tool_that_kills_is_destructive_on_any_server():
    verdict = decide(
        tool_name="kill_process", mode=WriteMode.GRANTED, granted_tools={"kill_process"}, server_id="some-stranger"
    )
    assert verdict.verdict is Verdict.CONFIRM


def test_the_model_cannot_grant_itself_a_tool_under_a_grant():
    from runtimes.mcp.floors import floor_for

    floor = floor_for("zaram-self", "grant_tool", {"server_id": "code", "tool_name": "run_command"}, None)
    assert floor is not None and floor.verdict == "confirm"
    assert floor.grantable is False and floor.plan_may_cover is False
    # It says what it would grant, so the person is not approving a blank.
    assert "run_command" in floor.reason and "code" in floor.reason


def test_the_other_self_tools_and_other_servers_are_not_caught_by_it():
    from runtimes.mcp.floors import floor_for

    assert floor_for("zaram-self", "set_voice", {"voice_id": "af_bella"}, None) is None
    assert floor_for("some-stranger", "grant_tool", {}, None) is None
