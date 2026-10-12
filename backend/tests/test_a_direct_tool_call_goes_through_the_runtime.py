"""`POST /tools/call` is the runtime's answer, not a second opinion of its own.

10 October 2026: the route called `McpRuntime.call_tool`, which does not exist, so
every direct call from Settings or the ambient panel was a 500; and its own grant
check treated a pin as permission and was skipped when no session id was sent.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from runtimes.mcp import api


class _Runtime:
    """Records what it is asked and answers like a runtime that wants a Go."""

    _builtin = {"cua-driver": object()}

    def __init__(self, answer):
        self.answer = answer
        self.asked = []

    async def execute(self, capability_id, input_data):
        self.asked.append((capability_id, dict(input_data)))
        return self.answer


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(api.router)
    holder = {}

    def attach(answer):
        runtime = _Runtime(answer)
        monkeypatch.setattr(api, "_MCP_RUNTIME", runtime)
        monkeypatch.setattr(api, "_store", lambda: type("S", (), {"load": staticmethod(lambda: {})})())
        holder["runtime"] = runtime
        return TestClient(app), runtime

    return attach


def test_a_call_is_handed_to_the_runtime_unconfirmed(client):
    http, runtime = client({"success": True, "result": {"ok": 1}})
    body = http.post("/tools/call", json={"server": "cua-driver", "tool": "zoom", "arguments": {"x": 1}}).json()
    assert body["success"] is True and body["needsConfirmation"] is False
    capability, data = runtime.asked[0]
    assert capability == "mcp.call"
    assert data["server"] == "cua-driver" and data["tool"] == "zoom"
    assert "confirmed" not in data  # nothing on this route has asked anyone


def test_a_call_that_needs_a_go_says_so_and_does_not_run(client):
    http, _ = client({"success": False, "needs_confirmation": True, "server": "cua-driver", "tool": "click"})
    body = http.post("/tools/call", json={"server": "cua-driver", "tool": "click"}).json()
    assert body["success"] is False and body["needsConfirmation"] is True


def test_an_unknown_server_is_a_404_before_anything_runs(client):
    http, runtime = client({"success": True})
    assert http.post("/tools/call", json={"server": "nobody", "tool": "x"}).status_code == 404
    assert runtime.asked == []
