"""A tool its own server declares granted is not then refused by the gate.

Found 4 October 2026 by asking the resident model for an SVG: it called
`draw_image` and was told *"this server is read-only because nothing here can
undo it."* `DrawTools.granted_tools` names the tool; the server was registered
with the default mode, which is read-only; and `decide` refuses a read-only
server's write **before** it reads the grants. So `draw_image` was refused on
every call since it was written -- and so were `record_job_posting` and
`check_eligibility`, which shipped in alpha.3.

The tests for all three passed, because every one of them called the tool's
code directly. None went through the policy. This file does, with the real
boot, over **every tool every built-in grants**, so the next pack registered
the same way cannot be unreachable by the same route.
"""

from __future__ import annotations

import pytest

from runtimes.mcp.config import ServerConfig, WriteMode
from runtimes.mcp.policy import Verdict, decide
from runtimes.mcp.runtime import McpRuntime


class _Granting:
    """A built-in that grants one tool and offers another it does not."""

    def __init__(self, grants):
        self._grants = set(grants)

    def granted_tools(self):
        return set(self._grants)

    def list_tools(self):
        return []

    def connect(self):
        pass

    def close(self):
        pass


def _runtime(tmp_path, server, mode=WriteMode.READ_ONLY, server_id="pack"):
    runtime = McpRuntime(config_path=str(tmp_path / "mcp.json")) if _takes_config() else McpRuntime()
    runtime.register_builtin(ServerConfig(server_id=server_id, writes=mode), server)
    return runtime


def _takes_config():
    import inspect

    return "config_path" in inspect.signature(McpRuntime.__init__).parameters


class TestTheEffectiveMode:
    def test_a_built_in_grant_counts_under_a_read_only_server(self, tmp_path):
        runtime = _runtime(tmp_path, _Granting({"make_thing"}))
        cfg = runtime._configs()["pack"]
        assert runtime._effective_mode("pack", "make_thing", cfg) is WriteMode.GRANTED

    def test_a_tool_the_server_did_not_grant_stays_read_only(self, tmp_path):
        runtime = _runtime(tmp_path, _Granting({"make_thing"}))
        cfg = runtime._configs()["pack"]
        assert runtime._effective_mode("pack", "other_thing", cfg) is WriteMode.READ_ONLY

    def test_an_attached_servers_grant_is_not_a_built_in_grant(self, tmp_path):
        """Narrow to Zaram's own servers. A stranger's server is read-only
        until its owner says it has an undo, whatever it claims about itself."""
        runtime = _runtime(tmp_path, _Granting(set()))
        stranger = ServerConfig(server_id="stranger", writes=WriteMode.READ_ONLY)
        assert runtime._effective_mode("stranger", "make_thing", stranger) is WriteMode.READ_ONLY

    def test_a_server_already_allowed_to_write_is_left_as_it_is(self, tmp_path):
        runtime = _runtime(tmp_path, _Granting({"make_thing"}), mode=WriteMode.HOST_UNDO)
        cfg = runtime._configs()["pack"]
        assert runtime._effective_mode("pack", "make_thing", cfg) is WriteMode.HOST_UNDO


class TestItIsNotAFreePass:
    """`GRANTED` runs without asking -- except for the two things that can never
    be taken back, which still ask however a built-in answers."""

    @pytest.mark.parametrize("tool", ["delete_everything", "purge_cache", "remove_file"])
    def test_a_destructive_tool_still_confirms(self, tool):
        assert decide(tool_name=tool, mode=WriteMode.GRANTED, granted_tools={tool}).verdict is Verdict.CONFIRM

    @pytest.mark.parametrize("tool", ["send_message", "publish_post", "reply_all"])
    def test_a_send_still_confirms(self, tool):
        assert decide(tool_name=tool, mode=WriteMode.GRANTED, granted_tools={tool}).verdict is Verdict.CONFIRM

    def test_an_ordinary_generative_tool_runs(self):
        assert decide(tool_name="draw_image", mode=WriteMode.GRANTED, granted_tools={"draw_image"}).verdict is Verdict.ALLOW


@pytest.mark.asyncio
async def test_every_tool_a_built_in_grants_can_actually_run():
    """Over the real boot, through the real gate.

    The audit that found the bug, kept as a test. For each built-in server and
    each tool it lists: if the server declares the tool granted, the policy must
    not refuse it. A refusal here is a tool that is registered, tested, offered
    to the model, and unreachable.
    """
    import os

    from core.bootstrapper import KernelBootstrapper
    from packs.code import set_active_root

    kernel = KernelBootstrapper()
    await kernel.boot()
    try:
        mcp = kernel.mcp_runtime
        set_active_root(os.getcwd())
        refused = []
        checked = 0
        for server_id, cfg in mcp._builtin.items():
            server = mcp._builtin_server(server_id)
            granted = mcp._builtin_grants(server_id)
            for tool in server.list_tools():
                if tool.name not in granted:
                    continue
                checked += 1
                verdict = decide(
                    tool_name=tool.name,
                    mode=mcp._effective_mode(server_id, tool.name, cfg),
                    granted_tools=cfg.granted_tools | granted,
                    not_read_only=mcp._builtin_says_not_read_only(server_id, tool.name),
                ).verdict
                if verdict is Verdict.REFUSE:
                    refused.append(f"{server_id}.{tool.name}")
        assert checked >= 4, "the audit saw almost nothing; it is not auditing"
        assert refused == [], f"granted by their own server and refused by the gate: {refused}"
    finally:
        set_active_root(None)
        await kernel.shutdown()
