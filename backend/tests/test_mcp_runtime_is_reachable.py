"""The MCP runtime is registered, and its gate is the one that decides.

**Why this file exists at all.** `CLAUDE.md` records fifteen complete, tested,
unreachable subsystems in this codebase, including a prompt-injection defence
and a 1,261-line ranking engine. Every one of them had passing tests. What none
of them had was a test asserting that something *calls* them, which is why the
suite stayed green while the feature did not exist.

So the first assertion here is not about behaviour. It is that the bootstrapper
registers the thing.
"""

from __future__ import annotations

import json

import pytest

from core.bootstrapper import KernelBootstrapper
from runtimes.mcp.config import ServerStore
from runtimes.mcp.policy import WriteMode
from runtimes.mcp.runtime import CALL, LIST_TOOLS, McpRuntime


class TestItIsWiredIn:
    def test_the_bootstrapper_declares_it(self):
        """A source-level check, so it fails when the line is deleted.

        Booting the whole kernel to assert one registration would need a
        database, an embedder and a model server, and would skip on the
        machines where this most needs to hold.
        """
        import inspect

        source = inspect.getsource(KernelBootstrapper)

        assert "McpRuntime" in source, "the MCP runtime is not constructed at boot"
        assert "self.registry.register(self.mcp_runtime)" in source, "constructed but never registered"

    def test_the_attribute_exists_before_boot(self):
        """`None` until initialised, and present either way — a caller that
        checks `is None` must not hit an AttributeError instead."""
        assert KernelBootstrapper().mcp_runtime is None

    def test_it_declares_both_capabilities(self):
        ids = [c.id for c in McpRuntime().get_metadata().capabilities]

        assert LIST_TOOLS in ids
        assert CALL in ids

    def test_calling_a_tool_is_not_declared_local(self):
        """A stdio server is a local process; what it reaches is not.

        The playwright server on this machine drives a browser onto the open
        internet. Declaring `mcp.call` LOCAL would make a claim about egress
        that Zaram cannot support, on the axis it is most trusted for.
        """
        call = next(c for c in McpRuntime().get_metadata().capabilities if c.id == CALL)

        assert call.locality.value != "local"


@pytest.fixture
def store(tmp_path):
    """A store holding one app with undo and one without."""
    path = tmp_path / "mcp-servers.json"
    path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "blender": {"command": "uvx", "args": ["blender-mcp"]},
                    "filesystem": {"command": "npx", "args": ["-y", "server-filesystem", "."]},
                    "brilliant": {"url": "http://127.0.0.1:3333/mcp"},
                }
            }
        ),
        encoding="utf-8",
    )
    return ServerStore(path)


class TestTheCuratedUndoList:
    def test_a_known_host_starts_able_to_write(self, store):
        """Zaram's own knowledge, not the server's claim about itself."""
        assert store.load()["blender"].writes is WriteMode.HOST_UNDO

    def test_everything_else_starts_read_only(self, store):
        """Default deny. A server nobody vouched for gets no benefit of the doubt."""
        assert store.load()["filesystem"].writes is WriteMode.READ_ONLY

    def test_an_explicit_setting_beats_the_curated_default(self, tmp_path):
        """The list is a starting position the user can overrule, not a grant."""
        path = tmp_path / "s.json"
        path.write_text(
            json.dumps(
                {"mcpServers": {"blender": {"command": "uvx", "args": ["blender-mcp"], "writes": "read_only"}}}
            ),
            encoding="utf-8",
        )

        assert ServerStore(path).load()["blender"].writes is WriteMode.READ_ONLY


class TestTheGateRunsOnCall:
    async def test_a_write_to_an_app_with_no_undo_is_refused(self, store):
        result = await McpRuntime(store).execute(
            CALL, {"server": "filesystem", "tool": "write_file", "arguments": {}}
        )

        assert result["success"] is False
        assert result["refused"] is True
        assert "undo" in result["reason"]

    async def test_a_write_to_an_app_with_undo_asks_first(self, store):
        result = await McpRuntime(store).execute(
            CALL, {"server": "blender", "tool": "set_material", "arguments": {}}
        )

        assert result["needs_confirmation"] is True
        assert result["tool"] == "set_material"

    async def test_the_model_cannot_confirm_on_the_user_s_behalf(self, store):
        """`confirmed` is set by a surface that asked a person.

        The refusal above must not be escapable by the same path that requested
        the call — otherwise a tool description that says "set confirmed: true"
        is a permission, which is the failure this whole file guards.
        """
        runtime = McpRuntime(store)
        asked = await runtime.execute(CALL, {"server": "blender", "tool": "set_material"})

        assert asked.get("needs_confirmation") is True
        # Granting is a separate, deliberate call — never a field in the request.
        assert not hasattr(runtime, "confirm_from_request")

    async def test_a_grant_is_remembered_so_it_stops_asking(self, store):
        runtime = McpRuntime(store)
        runtime.grant("blender", "set_material")

        assert "set_material" in store.load()["blender"].granted_tools

    async def test_an_unconfigured_server_is_not_callable(self, store):
        result = await McpRuntime(store).execute(CALL, {"server": "nope", "tool": "x"})

        assert result["success"] is False
        assert "configured" in result["error"]


class TestHealthIsHonestAboutWhatItCannotReach:
    async def test_an_http_server_says_why_rather_than_showing_nothing(self, store):
        health = await McpRuntime(store).health_check()

        brilliant = health["servers"]["brilliant"]
        assert brilliant["reachable"] is False
        assert "http" in brilliant["reason"]
