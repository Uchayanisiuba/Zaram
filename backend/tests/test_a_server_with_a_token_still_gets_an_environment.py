"""A server configured with an `env` block is spawned with that block **on top
of** Zaram's environment, never instead of it.

Found 15 September 2026 by attaching the first server that needs a credential.
`Popen(env=...)` replaces the environment, so `env: {GITHUB_PERSONAL_ACCESS_TOKEN: …}`
produced a child with one variable: no `PATH`, so `npx` could not find `node`;
no `SYSTEMROOT`, so Node's OpenSSL could not seed its random source on Windows
and aborted with `Assertion failed: ncrypto::CSPRNG(nullptr, 0)`. Every bundled
server has no `env` block, inherited everything, and worked — which is exactly
why every server with a token was unstartable and nothing said so.

The child here is Python rather than a real MCP server: the contract is about
what the child *receives*, and a fake that prints its environment measures that
directly without a network or a package download.
"""

from __future__ import annotations

import json
import os
import sys
import textwrap

from runtimes.mcp.client import McpServer

_ECHO_ENV = textwrap.dedent(
    """
    import json, os, sys
    print(json.dumps({k: os.environ.get(k) for k in ("PATH", "SYSTEMROOT", "SystemRoot", "ZARAM_TEST_TOKEN", "ZARAM_TEST_OVERRIDE")}))
    sys.stdout.flush()
    """
)


def _child_environment(env):
    server = McpServer("echo", [sys.executable, "-c", _ECHO_ENV], env=env, timeout=10)
    server._start()
    # The client's reader thread owns stdout and parses each line into the
    # reply queue; read from there rather than racing it for the pipe.
    seen = server._replies.get(timeout=10)
    assert server._process
    server._process.wait(timeout=10)
    return seen


def test_a_declared_env_is_added_to_the_process_environment_not_substituted_for_it(monkeypatch):
    monkeypatch.setenv("ZARAM_TEST_OVERRIDE", "from-zaram")
    seen = _child_environment({"ZARAM_TEST_TOKEN": "secret-123", "ZARAM_TEST_OVERRIDE": "from-server"})

    # The server's own variables arrive.
    assert seen["ZARAM_TEST_TOKEN"] == "secret-123"
    # And win over Zaram's on a clash: the block is the more specific claim.
    assert seen["ZARAM_TEST_OVERRIDE"] == "from-server"
    # But Zaram's environment is still there underneath — PATH is what lets
    # `npx` find `node` at all.
    assert seen["PATH"], "PATH did not reach the child"
    if os.name == "nt":
        # Windows: without SystemRoot, Node aborts before reading stdin.
        assert seen["SYSTEMROOT"] or seen["SystemRoot"], "SystemRoot did not reach the child"


def test_a_server_without_an_env_block_inherits_everything(monkeypatch):
    monkeypatch.setenv("ZARAM_TEST_OVERRIDE", "inherited")
    seen = _child_environment(None)
    assert seen["ZARAM_TEST_OVERRIDE"] == "inherited"
    assert seen["PATH"]
