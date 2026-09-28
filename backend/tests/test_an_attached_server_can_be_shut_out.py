"""A server can be attached, connected, healthy — and never shown to the model.

**Measured, not imagined.** On 27 September 2026 the official `comfy-mcp` was
attached to a real Zaram, connected, and offered 39 tools. Not one reached the
model: eight budget slots were already spoken for by the servers beside it.
Asked whether it could drive ComfyUI, Zaram said no — truthfully from what it
could see, and wrongly about the machine — and nothing anywhere reported that a
server had been silently dropped.

That is the failure this file guards, and it is the tool-layer version of
`CLAUDE.md`'s *"disabled capabilities are visible, not silent"*. The budget
itself is fine and deliberate; a budget that shuts a server out **without
saying so** is not.

The disclosure is on `health_check`, which Settings reads, and deliberately not
on the chat notice — `NoticeCard` returns null for `kind: "tools"`, so text
added there would be text nothing renders.
"""

from __future__ import annotations

from typing import List

import pytest

from runtimes.mcp.client import ToolDescriptor
from runtimes.mcp.config import ServerConfig, ServerStore
from runtimes.mcp.runtime import McpRuntime


class _Server:
    """A stranger's server offering however many tools the test wants."""

    def __init__(self, server_id: str, count: int) -> None:
        self.server_id = server_id
        self._count = count

    def list_tools(self) -> List[ToolDescriptor]:
        return [
            ToolDescriptor(
                server_id=self.server_id,
                name=f"tool_{index}",
                description=f"does thing {index}",
                input_schema={"type": "object", "properties": {}},
            )
            for index in range(self._count)
        ]


def _runtime(tmp_path, servers, *, budget: int) -> McpRuntime:
    store = ServerStore(tmp_path / "mcp-servers.json")
    store.save(
        {
            server_id: ServerConfig(server_id=server_id, command=["x"])
            for server_id in servers
        }
    )
    runtime = McpRuntime(store, tool_budget=budget)
    for server_id, count in servers.items():
        # Placed in the connection map directly: this is about the budget, not
        # about launching subprocesses, and a real stdio child would make the
        # test measure process startup instead.
        runtime._connections[server_id] = _Server(server_id, count)  # noqa: SLF001
    return runtime


@pytest.mark.asyncio
async def test_before_any_question_the_counts_are_unknown_not_zero(tmp_path):
    """"Nothing has happened yet" and "this server was shut out" differ.

    Reporting 0 for both would make the interface say a freshly attached server
    had been refused. Same distinction `vram_bytes` draws by returning `None`
    rather than 0 — a caller can check for unknown.
    """
    runtime = _runtime(tmp_path, {"comfyui": 39}, budget=8)
    health = await runtime.health_check()
    assert health["servers"]["comfyui"]["tools"] is None
    assert health["servers"]["comfyui"]["offered"] is None


@pytest.mark.asyncio
async def test_a_server_shut_out_by_the_budget_says_so(tmp_path):
    """The exact shape of the comfy-mcp failure, asserted.

    **Which server loses is decided by enumeration order, not by merit** — this
    test was first written assuming `comfyui` would be the one shut out and it
    was `filesystem`, because with no query there is no ranking and `theirs` is
    cut in the order the configs happened to come out. That is worth knowing
    and it is not what this file is guarding, so the assertion is on the
    property: somebody was shut out, and the report says so with their real
    tool count intact.
    """
    runtime = _runtime(tmp_path, {"filesystem": 8, "comfyui": 39}, budget=8)
    await runtime.available_tools()

    health = await runtime.health_check()
    strangers = {
        name: row for name, row in health["servers"].items() if not row["builtin"]
    }

    assert sum(row["offered"] for row in strangers.values()) == 8
    shut_out = [name for name, row in strangers.items() if row["offered"] == 0]
    assert shut_out, "a server got nothing and the report has to show it"
    for name in shut_out:
        assert strangers[name]["tools"] > 0, (
            f"{name} was trimmed to nothing, so its own count is the only thing "
            "left saying it had tools at all"
        )
    assert health["tool_budget"] == 8


@pytest.mark.asyncio
async def test_the_budget_is_reported_so_the_number_can_be_acted_on(tmp_path):
    """A shortfall with no budget beside it is a mystery rather than a fix.

    `ZARAM_TOOL_BUDGET` is what somebody would change; the interface can only
    point at it if it knows what the current value is.
    """
    runtime = _runtime(tmp_path, {"a": 3}, budget=24)
    await runtime.available_tools()
    assert (await runtime.health_check())["tool_budget"] == 24


@pytest.mark.asyncio
async def test_a_server_inside_the_budget_reports_all_of_its_tools(tmp_path):
    runtime = _runtime(tmp_path, {"small": 3}, budget=8)
    await runtime.available_tools()

    small = (await runtime.health_check())["servers"]["small"]
    assert small["tools"] == 3
    assert small["offered"] == 3


@pytest.mark.asyncio
async def test_zaram_s_own_packs_are_marked_and_never_trimmed(tmp_path):
    """The budget is for strangers, and the interface must not warn about ours.

    `available_tools` already exempts built-ins — dropping `write_file` because
    a ranker judged something closer to the question breaks the task rather
    than trimming the prompt. The report says which servers those are so
    Settings does not raise a shortfall that cannot happen.
    """
    runtime = _runtime(tmp_path, {"code": 14, "stranger": 20}, budget=4)
    runtime._builtin["code"] = object()  # noqa: SLF001 — register_builtin needs a real server
    await runtime.available_tools()

    health = await runtime.health_check()
    assert health["servers"]["code"]["builtin"] is True
    assert health["servers"]["code"]["offered"] == 14, "a pack is never trimmed"
    assert health["servers"]["stranger"]["builtin"] is False
    assert health["servers"]["stranger"]["offered"] == 4


@pytest.mark.asyncio
async def test_the_report_is_only_a_report(tmp_path):
    """Nothing routes on these numbers.

    Selection is ordering and the gate runs afterwards — this codebase's most
    expensive recurring bug is a number built for one question deciding
    another. These two exist to be read by a person, so the shortlist must be
    identical whether or not anybody asks for health.
    """
    runtime = _runtime(tmp_path, {"stranger": 20}, budget=4)
    first = await runtime.available_tools()
    await runtime.health_check()
    second = await runtime.available_tools()
    assert [t["qualified_name"] for t in first] == [t["qualified_name"] for t in second]
