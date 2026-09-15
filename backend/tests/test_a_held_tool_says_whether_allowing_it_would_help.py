"""A confirmation carries whether *allowing this tool* would settle it.

The interface grew a button on the held row on 15 September 2026 — before it,
"this needs your say-so" was a dead end and the only way through was Settings.
The button must appear exactly where a grant changes the outcome, and the only
component that knows is the gate: `decide` keeps asking about destructive tools
however much has been granted, so a grant there settles nothing.

**The interface must not work this out for itself.** It would mean a second
copy of the word list, in another language, drifting from the one the gate
reads — the "one number, two places" defect this repository keeps paying for.
So the runtime says, and these tests pin what it says.
"""

from __future__ import annotations

import asyncio

import pytest

from runtimes.mcp.config import ServerConfig
from runtimes.mcp.policy import WriteMode
from runtimes.mcp.runtime import McpRuntime


@pytest.fixture()
def runtime(tmp_path, monkeypatch) -> McpRuntime:
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    rt = McpRuntime()
    # A server whose application can undo, which is the only mode where a
    # write reaches a confirmation at all — read-only refuses instead.
    rt._configs = lambda: {  # type: ignore[method-assign]
        "studio": ServerConfig(
            server_id="studio",
            command=["python", "-c", "pass"],
            writes=WriteMode.HOST_UNDO,
        )
    }
    return rt


def _confirm(runtime: McpRuntime, tool: str) -> dict:
    result = asyncio.run(
        runtime.execute("mcp.call", {"server": "studio", "tool": tool, "arguments": {}})
    )
    assert result.get("needs_confirmation"), f"{tool} did not reach a confirmation"
    return result


def test_an_ordinary_change_says_allowing_it_would_help(runtime: McpRuntime) -> None:
    assert _confirm(runtime, "set_material")["grantable"] is True


@pytest.mark.parametrize("tool", ["delete_object", "remove_layer", "purge_orphans"])
def test_a_deletion_says_it_would_not(runtime: McpRuntime, tool: str) -> None:
    """`decide` asks about these however much is granted, so the row must not
    offer a button that would change nothing — which is worse than no button,
    because the person presses it and concludes the product is broken."""
    assert _confirm(runtime, tool)["grantable"] is False


def test_the_servers_own_hint_is_believed_in_the_stricter_direction(runtime: McpRuntime) -> None:
    """A server volunteering that a tool destroys is taken at its word, the
    same way `decide` takes it — a third-party claim may make a verdict
    stricter and never looser."""
    result = asyncio.run(
        runtime.execute(
            "mcp.call",
            {
                "server": "studio",
                "tool": "apply_preset",
                "arguments": {},
                "annotations": {"destructiveHint": True},
            },
        )
    )
    assert result.get("needs_confirmation")
    assert result["grantable"] is False
