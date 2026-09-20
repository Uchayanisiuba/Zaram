"""The person's own attached servers start under the allow-list environment — measured, `-m measure`.

`runtimes/mcp/child_env.py` (20 September 2026) replaced `dict(os.environ)`
with an allow-list of what a process needs to start, so a stranger's server
no longer receives `ZARAM_API_SECRET`. The unit test asserts that at the
process boundary against a fake; it cannot say whether `npx`, `uvx` and a
venv `.exe` still find everything *they* need, and a launcher that fails to
start is exactly the failure a green suite hides — the 15 September fix
existed because `Popen(env=...)` with one variable produced a child with no
`PATH` and Node aborted before reading stdin.

So this reads a real `mcp-servers.json` — named by `ZARAM_REAL_SERVERS`,
never the data directory, which `conftest.py` isolates for a reason — and
spawns every stdio server in it with `McpServer`'s own environment, which is
the allow-list. Each must complete the handshake and answer `tools/list`.
Nothing is asked of any tool; the servers are started and closed.

Runs only with ``-m measure`` and only when the variable names a file: it
starts whatever the person has attached, which on the maintainer's machine
is Blender (needs Blender up to do anything, but starts without it), a mail
server, and several `npx` packages that fetch on first run.

    ZARAM_REAL_SERVERS=C:/Zaram/backend/mcp-servers.json \
      pytest tests/test_the_real_servers_start_under_the_allow_list.py -m measure -s
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from runtimes.mcp.client import McpServer
from runtimes.mcp.config import ServerStore

pytestmark = pytest.mark.measure


def _named_file():
    named = (os.getenv("ZARAM_REAL_SERVERS") or "").strip()
    return Path(named) if named else None


def _stdio_servers():
    """Collected at import so each server is its own test row; skipped, not
    failed, when nothing is named — a measurement nobody asked for is not a
    defect."""
    path = _named_file()
    if not path or not path.is_file():
        return {}
    return {cfg.server_id: cfg for cfg in ServerStore(path).load().values() if cfg.reachable}


_SERVERS = _stdio_servers()


@pytest.mark.parametrize("server_id", sorted(_SERVERS) or ["(none named)"])
def test_the_server_starts_and_lists_its_tools(server_id):
    if server_id not in _SERVERS:
        pytest.skip("set ZARAM_REAL_SERVERS to the mcp-servers.json to spawn")
    cfg = _SERVERS[server_id]
    # 90 s: an `npx -y` package fetches on first run, and `uvx` builds a venv.
    server = McpServer(cfg.server_id, cfg.command, env=cfg.env or None, timeout=90.0)
    try:
        server.connect()
        tools = server.list_tools()
    except Exception as exc:  # noqa: BLE001 - the tail is the diagnosis
        tail = "\n".join(server.stderr_tail[-8:])
        pytest.fail(f"{cfg.server_id}: {cfg.command} did not start under the allow-list: {exc}\n{tail}")
    finally:
        server.close()
    print(f"\n{cfg.server_id}: {server.era} {server.protocol_version} — {len(tools)} tools")
    assert server.era in ("modern", "legacy")
