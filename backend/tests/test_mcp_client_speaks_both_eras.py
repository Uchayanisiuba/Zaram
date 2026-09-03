"""The MCP client against servers of both eras, and against a real one.

**Why a fake server rather than a mocked transport.** A mock of `_request`
would assert that this file's own idea of the protocol is self-consistent,
which is the assertion-free test `CLAUDE.md` warns about wearing a costume.
These spawn a real subprocess and speak real newline-delimited JSON-RPC over a
real pipe, so what is exercised is the framing, the id matching, the threading
and the fallback — the parts that actually break.

The era fallback is the thing worth testing hardest. Read from the 2026-07-28
specification: a legacy server "may respond to unknown requests with
implementation-defined errors or fail to respond entirely, so fallback logic
must not rely on a single specific error code." So there are three legacy
signatures here — a method-not-found error, an unrelated error code, and
silence — and all three must land in the same place.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import textwrap

import pytest

from runtimes.mcp.client import SUPPORTED_VERSIONS, McpServer

# --------------------------------------------------------------------- fakes

#: A server whose era and behaviour are chosen by argv, so one script covers
#: every case and the differences between them stay visible in one place.
_FAKE = textwrap.dedent(
    '''
    import json, sys

    mode = sys.argv[1]

    def send(payload):
        sys.stdout.write(json.dumps(payload) + "\\n")
        sys.stdout.flush()

    if mode == "noisy":
        # Not JSON. A real server did this; the client must skip it, not die.
        sys.stdout.write("starting up...\\n")
        sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        method, mid = msg.get("method"), msg.get("id")

        if method == "notifications/initialized":
            continue

        if method == "server/discover":
            if mode == "modern":
                send({"jsonrpc": "2.0", "id": mid, "result": {
                    "serverInfo": {"name": "fake-modern", "version": "1.0"},
                    "supportedVersions": ["2026-07-28", "2025-11-25"]}})
            elif mode == "modern_old_version":
                send({"jsonrpc": "2.0", "id": mid, "error": {
                    "code": -32022, "message": "Unsupported protocol version",
                    "data": {"supported": ["2025-11-25"], "requested": "2026-07-28"}}})
            elif mode == "legacy_unrelated_error":
                send({"jsonrpc": "2.0", "id": mid, "error": {
                    "code": -32603, "message": "Internal error"}})
            elif mode == "silent":
                pass  # never answers the probe
            else:
                send({"jsonrpc": "2.0", "id": mid, "error": {
                    "code": -32601, "message": "Method not found"}})
            continue

        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2025-06-18",
                "serverInfo": {"name": "fake-legacy", "version": "1.0"},
                "capabilities": {"tools": {}}}})
            continue

        if method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [
                {"name": "add", "description": "Add two numbers.",
                 "inputSchema": {"type": "object"}},
                {"name": "", "description": "nameless, must be dropped"}]}})
            continue

        if method == "tools/call":
            params = msg.get("params") or {}
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": "called " + str(params.get("name"))}],
                "meta_seen": "_meta" in params}})
            continue

        send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "no"}})
    '''
)


@pytest.fixture
def fake(tmp_path):
    script = tmp_path / "fake_mcp_server.py"
    script.write_text(_FAKE, encoding="utf-8")

    started = []

    def _start(mode: str) -> McpServer:
        server = McpServer(
            server_id=f"fake-{mode}",
            command=[sys.executable, str(script), mode],
            timeout=10.0,
        )
        server.connect()
        started.append(server)
        return server

    yield _start
    for server in started:
        server.close()


# --------------------------------------------------------------------- tests


class TestEraDetection:
    def test_a_modern_server_is_recognised_from_its_discovery_result(self, fake):
        server = fake("modern")

        assert server.era == "modern"
        assert server.protocol_version == "2026-07-28"
        assert server.server_info.get("name") == "fake-modern"

    def test_a_modern_server_on_an_older_version_is_still_modern(self, fake):
        """-32022 names what the server has, so it is a negotiation, not a fallback."""
        server = fake("modern_old_version")

        assert server.era == "modern"
        assert server.protocol_version == "2025-11-25"

    def test_method_not_found_means_legacy(self, fake):
        server = fake("legacy")

        assert server.era == "legacy"
        assert server.protocol_version == "2025-06-18"
        assert server.server_info.get("name") == "fake-legacy"

    def test_an_unrelated_error_code_also_means_legacy(self, fake):
        """The spec forbids resting the decision on one code, and this is why.

        A server that answers the probe with -32603 is not saying anything
        about its era; it is failing. Treating only -32601 as legacy would
        strand it.
        """
        server = fake("legacy_unrelated_error")

        assert server.era == "legacy"

    def test_silence_means_legacy(self, fake):
        """The other signature the spec names: "fail to respond entirely"."""
        server = fake("silent")

        assert server.era == "legacy"


class TestTools:
    def test_it_lists_tools_and_drops_a_nameless_one(self, fake):
        tools = fake("legacy").list_tools()

        assert [t.name for t in tools] == ["add"]
        assert tools[0].description == "Add two numbers."
        assert tools[0].qualified_name == "fake-legacy:add"

    def test_a_call_reaches_the_server(self, fake):
        result = fake("legacy").call_tool("add", {"a": 1, "b": 2})

        assert result["content"][0]["text"] == "called add"

    def test_only_a_modern_server_is_sent_per_request_metadata(self, fake):
        """`_meta` on a legacy request is a protocol error waiting to happen."""
        assert fake("modern").call_tool("add")["meta_seen"] is True
        assert fake("legacy").call_tool("add")["meta_seen"] is False

    def test_non_json_on_stdout_is_skipped_rather_than_fatal(self, fake):
        """The spec says stdout carries messages only. Servers break that."""
        assert fake("noisy").era == "legacy"
        assert [t.name for t in fake("noisy").list_tools()] == ["add"]


class TestQualifiedNames:
    def test_two_servers_offering_the_same_tool_stay_distinguishable(self, fake):
        a, b = fake("legacy"), fake("modern")
        # Same tool name from both; only the qualified name separates them.
        assert a.list_tools()[0].name == b.list_tools()[0].name
        assert a.list_tools()[0].qualified_name != b.list_tools()[0].qualified_name


# ---------------------------------------------------------------- live probe

#: A real MCP server, fetched by npx. Marked `measure` for the same reason the
#: Ollama reasoning test is: every fake above would also pass against a client
#: that had the protocol subtly wrong, because the fakes were written from the
#: same reading of the spec as the client. Only a server somebody else wrote
#: can find that.
@pytest.mark.measure
class TestAgainstARealServer:
    @pytest.fixture(scope="class")
    def real(self, tmp_path_factory):
        if not shutil.which("npx"):
            pytest.skip("npx not installed; needed to fetch a real MCP server")

        root = tmp_path_factory.mktemp("mcp_root")
        (root / "hello.txt").write_text("Zaram was here", encoding="utf-8")

        server = McpServer(
            server_id="filesystem",
            command=[
                "npx", "-y", "@modelcontextprotocol/server-filesystem", str(root),
            ],
            # First run downloads the package.
            timeout=120.0,
        )
        try:
            server.connect()
        except Exception as exc:  # noqa: BLE001
            server.close()
            pytest.skip(f"could not start a real MCP server ({exc}); needs network")
        yield server, root
        server.close()

    def test_it_connects_and_names_its_era(self, real):
        server, _ = real

        assert server.era in {"legacy", "modern"}
        assert server.protocol_version in SUPPORTED_VERSIONS or server.era == "legacy"

    def test_it_lists_real_tools(self, real):
        server, _ = real
        tools = server.list_tools()

        assert tools, f"no tools; stderr: {server.stderr_tail}"
        assert all(t.server_id == "filesystem" for t in tools)

    def test_it_attaches_to_whatever_servers_this_machine_has_configured(self):
        """The developer's own `.mcp.json`, connected to for real.

        A different question from the fixture above, and the more useful one:
        that server is one Zaram chose, and these are servers somebody else
        configured for another client entirely. If a stdio server works in
        Claude Code it must work here, because the protocol is the product —
        so this fails the moment that stops being true.

        Skips rather than fails when the file is absent: it describes this
        machine, not the contract.
        """
        config = pathlib.Path(__file__).resolve().parents[2] / ".mcp.json"
        if not config.exists():
            pytest.skip("no .mcp.json on this machine")

        servers = (json.loads(config.read_text(encoding="utf-8")).get("mcpServers") or {})
        stdio = {n: s for n, s in servers.items() if s.get("command")}
        if not stdio:
            pytest.skip("no stdio servers configured (an http/sse server needs the SDK)")

        for name, spec in stdio.items():
            server = McpServer(name, [spec["command"], *(spec.get("args") or [])], timeout=90.0)
            try:
                server.connect()
                tools = server.list_tools()
                assert server.era in {"legacy", "modern"}
                assert tools, f"{name} offered no tools; stderr: {server.stderr_tail}"
            finally:
                server.close()

    def test_it_calls_a_real_tool_and_reads_a_real_file(self, real):
        server, root = real
        names = {t.name for t in server.list_tools()}
        tool = next((n for n in ("read_text_file", "read_file") if n in names), None)
        if tool is None:
            pytest.skip(f"this server offers no read tool; has {sorted(names)}")

        result = server.call_tool(tool, {"path": str(root / "hello.txt")})

        assert "Zaram was here" in json.dumps(result), result
