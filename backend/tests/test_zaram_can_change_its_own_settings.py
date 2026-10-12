"""Asking Zaram to change its own settings changes them, and says what is now true.

10 October 2026, asked for by the maintainer: *"I want users to be able to prompt
Zaram to effect changes within Zaram, tweak settings."* The tools existed and had
never worked: their handlers were `async`, the runtime ran them in a thread and got
a coroutine back, and every call returned ``success: True`` having changed nothing.
So every test here goes through the real `McpRuntime`, the path the model uses.
"""

from __future__ import annotations

import asyncio

import pytest

from core.streaming_events import StreamEvent
from core.user_settings import get_user_settings
from runtimes.mcp import policy, zaram_self
from runtimes.mcp.config import ServerConfig, ServerStore
from runtimes.mcp.policy import WriteMode
from runtimes.mcp.runtime import CALL, McpRuntime
from runtimes.mcp.zaram_self import SELF_SERVER_ID, ZaramSelfServer


@pytest.fixture
def store(tmp_path):
    s = ServerStore(tmp_path / "servers.json")
    s.save({"cua-driver": ServerConfig(server_id="cua-driver", command=["cua-driver", "mcp"], writes=WriteMode.HOST_UNDO)})
    return s


@pytest.fixture
def runtime(store):
    rt = McpRuntime(store=store)
    rt.register_builtin(
        ServerConfig(server_id=SELF_SERVER_ID, writes=WriteMode.HOST_UNDO),
        ZaramSelfServer(store_factory=lambda: store),
    )
    return rt


@pytest.fixture
def voices(monkeypatch):
    rows = [
        {"id": "af_heart", "name": "Heart", "language": "American English", "installed": True},
        {"id": "am_michael", "name": "Michael", "language": "American English", "installed": True},
        {"id": "bf_emma", "name": "Emma", "language": "British English", "installed": False},
    ]
    monkeypatch.setattr("voice.voice_manifest.catalogue", lambda **_: {"voices": rows})
    return rows


def _call(runtime, tool, confirmed=True, **arguments):
    return asyncio.run(runtime.execute(CALL, {
        "server": SELF_SERVER_ID, "tool": tool, "arguments": arguments, "confirmed": confirmed,
    }))


def test_a_call_returns_an_answer_and_not_a_coroutine(runtime):
    out = _call(runtime, "get_settings", confirmed=False)
    assert out["success"] is True
    assert isinstance(out["result"], dict), type(out["result"])
    assert "routing" in out["result"] and "computer_use" in out["result"]


def test_reading_settings_never_asks(runtime):
    for tool in ("get_settings", "list_servers"):
        assert _call(runtime, tool, confirmed=False)["success"] is True


def test_a_change_asks_the_first_time_and_then_happens(runtime):
    asked = _call(runtime, "set_routing", confirmed=False, mode="prefer_local")
    assert asked.get("needs_confirmation") is True and asked["grantable"] is True
    done = _call(runtime, "set_routing", mode="prefer_local")
    assert done["result"] == {"success": True, "routing": "prefer_local"}
    assert get_user_settings().routing_preference.value == "prefer_local"


def test_thinking_and_web_search_are_really_switched(runtime):
    _call(runtime, "set_thinking", on=False)
    assert get_user_settings().thinking is False
    _call(runtime, "set_web_search", on=True)
    assert get_user_settings().web_search is True
    _call(runtime, "set_web_search", on=False)
    assert get_user_settings().web_search is False


def test_a_voice_must_exist_and_be_on_the_machine(runtime, voices):
    assert _call(runtime, "set_voice", voice_id="am_michael")["result"] == {"success": True, "voice": "am_michael"}
    assert get_user_settings().voice == "am_michael"
    missing = _call(runtime, "set_voice", voice_id="bf_emma")["result"]
    assert missing["success"] is False and "Download" in missing["error"]
    unknown = _call(runtime, "set_voice", voice_id="nobody")["result"]
    assert unknown["success"] is False
    assert get_user_settings().voice == "am_michael", "a refused voice must not be written"


def test_list_voices_works_and_names_what_needs_downloading(runtime, voices):
    out = _call(runtime, "list_voices", confirmed=False)["result"]
    assert any(v.startswith("am_michael") for v in out["on_this_machine"])
    assert out["need_downloading"] == ["bf_emma"]


def test_computer_use_is_switched_without_being_removed(runtime, store):
    out = _call(runtime, "set_computer_use", on=False)["result"]
    assert out == {"success": True, "computer_use": "off"}
    assert store.load()["cua-driver"].enabled is False
    _call(runtime, "set_computer_use", on=True)
    assert store.load()["cua-driver"].enabled is True


def test_computer_use_that_is_not_installed_says_where_it_is_installed(tmp_path):
    empty = ServerStore(tmp_path / "none.json")
    rt = McpRuntime(store=empty)
    rt.register_builtin(ServerConfig(server_id=SELF_SERVER_ID, writes=WriteMode.HOST_UNDO), ZaramSelfServer(store_factory=lambda: empty))
    out = _call(rt, "set_computer_use", on=True)["result"]
    assert out["success"] is False and "Install cua-driver" in out["error"]


def test_the_window_changes_come_back_as_an_instruction(runtime):
    assert _call(runtime, "set_indicator", renderer="avatar")["result"]["apply"] == {"renderer": "avatar"}
    assert _call(runtime, "open_place", place="settings")["result"]["apply"] == {"open": "settings"}
    nowhere = _call(runtime, "open_place", place="canvas")["result"]
    assert nowhere["success"] is False and "apply" not in nowhere


def test_the_event_carries_the_instruction_only_when_there_is_one():
    with_apply = StreamEvent.tool_call("zaram-self", "set_indicator", "allow", apply={"renderer": "orb"})
    assert with_apply.data["apply"] == {"renderer": "orb"}
    assert "apply" not in StreamEvent.tool_call("cua-driver", "click", "allow").data


# ------------------------------------------------------------------ the gate


@pytest.mark.parametrize("tool", sorted(zaram_self.ALWAYS_ASK))
def test_widening_tools_ask_every_time_whatever_was_allowed(runtime, store, tool):
    """A model must not widen its own permissions, or send questions out, off
    one card the person allowed once."""
    store.grant(SELF_SERVER_ID, tool) if SELF_SERVER_ID in store.load() else None
    runtime.allow_for_session("s", SELF_SERVER_ID, tool)
    arguments = {"server_id": "cua-driver", "tool_name": "click"} if tool == "grant_tool" else {"on": True}
    out = asyncio.run(runtime.execute(CALL, {"server": SELF_SERVER_ID, "tool": tool, "arguments": arguments, "session": "s"}))
    assert out.get("needs_confirmation") is True
    assert out["grantable"] is False, "the card must not offer 'always' for this"


def test_grant_tool_only_grants_on_an_attached_server(runtime, store):
    assert _call(runtime, "grant_tool", server_id="nobody", tool_name="x")["result"]["success"] is False
    assert _call(runtime, "grant_tool", server_id="cua-driver", tool_name="click")["result"]["success"] is True
    assert "click" in store.load()["cua-driver"].granted_tools
    _call(runtime, "revoke_tool", server_id="cua-driver", tool_name="click")
    assert "click" not in store.load()["cua-driver"].granted_tools


def test_the_gate_and_the_server_agree_on_what_always_asks():
    assert policy._SELF_ALWAYS_ASK == zaram_self.ALWAYS_ASK


def test_nothing_here_changes_what_may_leave_the_computer():
    """The kill switch, per-site rules and keys are the person's, in Settings ->
    Privacy. Asserted on the tool list so a later tool cannot slip one in."""
    names = {t.name for t in ZaramSelfServer().list_tools()}
    assert not any(word in name for name in names for word in ("kill", "egress", "policy", "key", "rule", "privacy"))
