"""Another assistant can attach Zaram's memory as an MCP server.

Driven end to end and for real: a live Zaram on a free loopback port, a
token issued as the owner, `python -m zaram_mcp pair` redeeming it over
HTTP, and then `zaram_mcp` spawned as a subprocess and spoken to through
Zaram's **own** MCP client — the same `McpServer` that attaches a
stranger's server — so the dialect is checked by the one implementation in
this repository that has to understand it.

What is asserted is the slice-10 contract from `docs/AGENT-UX.md`: recall
with provenance, remember, correct, project scope; every call logged as
egress to the named client; and a revoked client refused on its next call
without Zaram restarting.
"""

from __future__ import annotations

import importlib
import os
import socket
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import uvicorn

from core.paired_clients import PairedClients
from runtimes.mcp.client import McpServer

BACKEND = Path(__file__).resolve().parent.parent


class _Result:
    def __init__(self, content: str, relevance: float, source: str = "brief.pdf"):
        self.record = SimpleNamespace(
            id=f"fact-{abs(hash(content)) % 10_000}",
            content=content,
            scope="global",
            origin=SimpleNamespace(value="conversation"),
            source=source,
            created_at=1.0,
        )
        self.relevance = relevance
        self.score = 0.5


class _Spine:
    def __init__(self) -> None:
        self.results: list[_Result] = []
        self.written: list[dict[str, Any]] = []
        self.corrected: list[tuple[str, str]] = []
        self._store = self

    async def retrieve(self, **kwargs: Any):
        return list(self.results)

    async def remember(self, **kwargs: Any) -> str:
        self.written.append(kwargs)
        return "fact-new"

    async def correct(self, record_id: str, content: str):
        self.corrected.append((record_id, content))
        return {"id": "fact-corrected", "corrects": record_id, "content": content}

    async def get(self, record_id: str):
        return SimpleNamespace(id=record_id, scope=None, created_at=0.0)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def live(tmp_path, monkeypatch):
    """A real Zaram on loopback with the memory stubbed and the lifespan off,
    so the kernel is never booted — what is under test is the door, not the
    rooms behind it."""
    from core.egress import get_gate
    from core.egress.log import EgressLog
    from projects.records import ProjectRecords

    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    main = importlib.import_module("main")

    monkeypatch.setattr(main, "project_records", ProjectRecords(str(tmp_path / "projects.db")))
    monkeypatch.setattr(main, "paired_clients", PairedClients(tmp_path / "clients.db"))
    spine = _Spine()
    monkeypatch.setattr(main.kernel, "memory_runtime", spine, raising=False)
    log = EgressLog(str(tmp_path / "egress.db"))
    monkeypatch.setattr(get_gate(), "_log", log, raising=False)

    port = _free_port()
    config = uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="warning", lifespan="off")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    assert server.started, "Zaram did not start on the test port"

    yield SimpleNamespace(
        url=f"http://127.0.0.1:{port}", main=main, spine=spine, log=log,
        projects=main.project_records,
    )
    server.should_exit = True
    thread.join(timeout=10)


def _owner_headers(main) -> dict:
    import core.api_secret as api_secret

    return {api_secret.HEADER: api_secret.api_secret()}


@pytest.fixture
def attached(live):
    """Paired, spawned, connected — the way Claude Code would hold it."""
    import json
    import urllib.request

    import zaram_mcp

    request = urllib.request.Request(
        live.url + "/pairing/token", method="POST", headers=_owner_headers(live.main)
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        token = json.loads(response.read())["token"]
    paired = zaram_mcp.pair(token, "Claude Code", live.url)
    credential = paired["credential"]

    env = {**os.environ, zaram_mcp.CREDENTIAL_ENV: credential, "PYTHONIOENCODING": "utf-8"}
    server = McpServer(
        server_id="zaram",
        command=[sys.executable, "-m", "zaram_mcp", "--api", live.url],
        env=env,
        cwd=str(BACKEND),
        timeout=20.0,
    )
    server.connect()
    try:
        yield SimpleNamespace(server=server, credential=credential, client_id=paired["id"])
    finally:
        server.close()


def _text_of(result: dict) -> str:
    return "".join(block.get("text", "") for block in result.get("content", []))


class TestTheDoor:
    def test_it_lists_the_four_tools_zarams_own_client_understands(self, attached):
        names = sorted(tool.name for tool in attached.server.list_tools())
        assert names == ["correct", "projects", "recall", "remember"]
        assert attached.server.server_info.get("name") == "zaram"

    def test_recall_arrives_with_provenance(self, live, attached):
        live.spine.results = [
            _Result("Northwind's day rate is 650 and they pay net 45", 0.83, source="northwind-brief.pdf"),
            _Result("something recent and unrelated", 0.10),
        ]
        result = attached.server.call_tool("recall", {"query": "what does Northwind pay"})
        text = _text_of(result)
        assert not result.get("isError")
        assert "day rate is 650" in text
        assert "source: northwind-brief.pdf" in text
        assert "origin: conversation" in text
        assert "unrelated" not in text  # below the floor on relevance

    def test_nothing_remembered_says_so_rather_than_guessing(self, live, attached):
        live.spine.results = []
        text = _text_of(attached.server.call_tool("recall", {"query": "anything"}))
        assert "remembers nothing" in text
        assert "rather than guessing" in text

    def test_remember_and_correct_reach_the_spine(self, live, attached):
        attached.server.call_tool("remember", {"text": "Northwind moved to net 30"})
        assert live.spine.written[-1]["content"] == "Northwind moved to net 30"
        attached.server.call_tool("correct", {"fact_id": "fact-1", "text": "Northwind is on net 30"})
        assert live.spine.corrected == [("fact-1", "Northwind is on net 30")]

    def test_projects_scope_recall(self, live, attached):
        project = live.projects.create(name="Northwind site")
        listed = _text_of(attached.server.call_tool("projects", {}))
        assert project.id in listed and "Northwind site" in listed
        result = attached.server.call_tool("recall", {"query": "x", "project_id": "no-such-project"})
        assert result.get("isError") is True
        assert "no project called" in _text_of(result)


class TestCustody:
    def test_every_call_is_egress_to_the_named_client(self, live, attached):
        before = live.log.count()
        attached.server.call_tool("recall", {"query": "anything"})
        attached.server.call_tool("projects", {})
        entries = live.log.entries(limit=2)
        assert live.log.count() == before + 2
        assert {e.host for e in entries} == {"client:Claude Code"}
        assert {e.url for e in entries} == {"/memory/recall", "/projects"}
        assert all(e.kind == "client" and e.byte_count > 0 and e.body is None for e in entries)

    def test_a_revoked_client_is_refused_on_its_next_call(self, live, attached):
        import json
        import urllib.request

        assert not attached.server.call_tool("projects", {}).get("isError")
        request = urllib.request.Request(
            f"{live.url}/pairing/clients/{attached.client_id}",
            method="DELETE", headers=_owner_headers(live.main),
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert json.loads(response.read())["revoked"] == attached.client_id
        result = attached.server.call_tool("projects", {})
        assert result.get("isError") is True
        assert "refused (401)" in _text_of(result)


def test_without_a_credential_it_says_how_to_get_one(capsys):
    import zaram_mcp

    os.environ.pop(zaram_mcp.CREDENTIAL_ENV, None)
    assert zaram_mcp.main([]) == 2
    err = capsys.readouterr().err
    assert "pair <token>" in err and "Settings" in err


@pytest.mark.parametrize("url", [
    "http://zaram.example.com:8420",
    "http://127.0.0.1.evil.test:8420",
    "http://user@127.0.0.1@evil.test",
    "http://10.0.0.5:8420",
])
def test_it_refuses_to_talk_to_anything_but_this_machine(url):
    """No gate of its own, so no destination but loopback. The chokepoint
    scan lists this module as loopback-only on the strength of this."""
    import zaram_mcp

    with pytest.raises(SystemExit, match="loopback"):
        zaram_mcp.Spine("cred", url)
    with pytest.raises(SystemExit, match="loopback"):
        zaram_mcp.pair("tok", "x", url)
