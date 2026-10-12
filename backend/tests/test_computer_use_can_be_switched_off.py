"""Computer use can be switched off without being removed.

10 October 2026, asked for by the maintainer: "do I have a toggle on and off for
computer use?" The only off was Remove, which forgot every grant and pin, and
switching back on meant downloading the driver again. Off now keeps all of that, and
means nothing about the server reaches the model or runs: its tools are not listed, a
call is refused with a sentence, its process is stopped, and the model is told the
capability is switched off so it can say so (a disabled capability is visible, not
silent).
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from runtimes.mcp import api
from runtimes.mcp.client import ToolDescriptor
from runtimes.mcp.config import ServerConfig, ServerStore
from runtimes.mcp.policy import WriteMode
from runtimes.mcp.runtime import CALL, LIST_TOOLS, McpRuntime


class _Driver:
    """A stand-in for the driver's process. Records whether it was stopped."""

    def __init__(self):
        self.closed = False
        self.calls = []

    def list_tools(self):
        return [ToolDescriptor(server_id="cua-driver", name=n, description=n) for n in ("click", "list_windows")]

    def call_tool(self, name, arguments):
        self.calls.append(name)
        return {"content": [{"type": "text", "text": "done"}]}

    def close(self):
        self.closed = True


@pytest.fixture
def setup(tmp_path, monkeypatch):
    store = ServerStore(tmp_path / "servers.json")
    store.save({
        "cua-driver": ServerConfig(
            server_id="cua-driver", command=["cua-driver", "mcp"], writes=WriteMode.HOST_UNDO,
            granted_tools={"click"}, pinned_tools={"click"},
        )
    })
    runtime = McpRuntime(store=store)
    driver = _Driver()
    runtime._connections["cua-driver"] = driver
    monkeypatch.setattr(api, "_store", lambda: store)
    monkeypatch.setattr(api, "_MCP_RUNTIME", runtime)
    app = FastAPI()
    app.include_router(api.router)
    return runtime, store, driver, TestClient(app)


def _tools(runtime, query="click on the start button"):
    return [t["name"] for t in asyncio.run(runtime.execute(LIST_TOOLS, {"query": query}))["tools"]]


def test_on_by_default_and_the_file_does_not_change_shape(setup):
    runtime, store, _driver, _client = setup
    assert store.load()["cua-driver"].enabled is True
    assert "enabled" not in store.load()["cua-driver"].to_json()
    assert "click" in _tools(runtime)


def test_switching_off_withdraws_the_tools_and_stops_the_process(setup):
    runtime, store, driver, client = setup
    response = client.put("/tools/servers/cua-driver/enabled", json={"enabled": False})
    assert response.status_code == 200 and response.json()["enabled"] is False
    assert driver.closed, "off must be true the moment the switch says it"
    assert _tools(runtime) == []
    assert store.load()["cua-driver"].to_json()["enabled"] is False


def test_a_call_to_a_switched_off_server_is_refused_whatever_was_granted(setup):
    runtime, store, driver, _client = setup
    store.set_enabled("cua-driver", False)
    result = asyncio.run(runtime.execute(CALL, {"server": "cua-driver", "tool": "click", "arguments": {}}))
    assert result["success"] is False and result["refused"] is True
    assert "switched off" in result["reason"]
    assert driver.calls == []


def test_off_keeps_the_grants_and_pins_so_on_is_instant(setup):
    runtime, store, _driver, client = setup
    client.put("/tools/servers/cua-driver/enabled", json={"enabled": False})
    client.put("/tools/servers/cua-driver/enabled", json={"enabled": True})
    cfg = store.load()["cua-driver"]
    assert cfg.enabled is True and cfg.granted_tools == {"click"} and cfg.pinned_tools == {"click"}


def test_the_model_is_told_it_is_off(setup):
    runtime, store, _driver, _client = setup
    store.set_enabled("cua-driver", False)
    briefing = asyncio.run(runtime.execute(LIST_TOOLS, {"query": "take a screenshot"}))["briefing"]
    assert "switched off" in briefing and "Settings" in briefing


def test_the_model_is_told_what_it_is_on_for(setup):
    """On, it drives the person's own browser. A model that was never told so
    answered "I don't have a browser of my own" right after opening one."""
    runtime, _store, _driver, _client = setup
    briefing = asyncio.run(runtime.execute(LIST_TOOLS, {"query": "open google.com"}))["briefing"]
    assert "Computer use is on" in briefing
    assert "browser they already have" in briefing
    assert "look before you say what happened" in briefing
    assert "switched off" not in briefing


def test_switching_it_off_replaces_the_on_briefing_rather_than_adding_to_it(setup):
    runtime, store, _driver, _client = setup
    store.set_enabled("cua-driver", False)
    briefing = asyncio.run(runtime.execute(LIST_TOOLS, {"query": "open google.com"}))["briefing"]
    assert "Computer use is on" not in briefing and "switched off" in briefing


def test_the_health_check_says_off_without_starting_anything(setup):
    runtime, store, driver, _client = setup
    store.set_enabled("cua-driver", False)
    runtime._connections.pop("cua-driver")
    health = asyncio.run(runtime._check_cua_driver_health("cua-driver"))
    assert health["status"] == "off"
    assert "cua-driver" not in runtime._connections


def test_an_unknown_server_is_a_404(setup):
    _runtime, _store, _driver, client = setup
    assert client.put("/tools/servers/nobody/enabled", json={"enabled": False}).status_code == 404


def test_the_listing_says_whether_each_server_is_on(setup):
    _runtime, store, _driver, client = setup
    store.set_enabled("cua-driver", False)
    [row] = client.get("/tools/servers").json()["servers"]
    assert row["enabled"] is False
