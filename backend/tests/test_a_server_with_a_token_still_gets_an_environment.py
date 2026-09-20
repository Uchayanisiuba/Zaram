"""A tool server is spawned with what it needs to start, its own `env` block,
and **nothing else** — not Zaram's credential, not the shell's keys.

Two findings, five days apart, and the second undid half of the first.

**15 September 2026.** Attaching the first server that needs a credential:
`Popen(env=...)` replaces the environment, so `env: {GITHUB_PERSONAL_ACCESS_TOKEN: …}`
produced a child with one variable — no `PATH`, so `npx` could not find
`node`; no `SYSTEMROOT`, so Node's OpenSSL could not seed its random source
on Windows and aborted with `Assertion failed: ncrypto::CSPRNG(nullptr, 0)`.
The fix was to inherit everything and lay the block on top.

**20 September 2026.** Reading that fix: *everything* included
`ZARAM_API_SECRET`, the per-launch credential that authenticates every
request to the API — `GET /memory` included. Every attached server, sloppy
or hostile, was handed the key to the Spine the moment it started. Nothing
in the suite asserted what a child did *not* receive.

`runtimes/mcp/child_env.py` is the answer to both: an allow-list of what a
process needs to start, plus the block, and nothing else. The pure function
is tested with a dictionary; the spawn is tested with a child that prints
its environment, so the contract is about what the child *receives*.
"""

from __future__ import annotations

import json
import os
import sys
import textwrap

from runtimes.mcp.child_env import PASSES, child_environment
from runtimes.mcp.client import McpServer

_ECHO_ENV = textwrap.dedent(
    """
    import json, os, sys
    print(json.dumps(dict(os.environ)))
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


class TestThePureFunction:
    def test_the_credential_never_crosses(self):
        parent = {"PATH": "/bin", "ZARAM_API_SECRET": "s3", "ZARAM_DATA_DIR": "/d", "OPENAI_API_KEY": "k"}
        child = child_environment(parent, None)
        assert child == {"PATH": "/bin"}

    def test_the_block_always_crosses_and_wins(self):
        parent = {"PATH": "/bin", "TOKEN_FROM_SHELL": "no", "HOME": "/h"}
        child = child_environment(parent, {"GITHUB_TOKEN": "gh", "HOME": "/server"})
        assert child == {"PATH": "/bin", "HOME": "/server", "GITHUB_TOKEN": "gh"}

    def test_names_are_matched_without_case_and_kept_as_spelled(self):
        # Windows hands `SystemRoot` in that spelling and Node reads it by
        # that name; the comparison folds, the key does not.
        child = child_environment({"SystemRoot": r"C:\Windows", "systemdrive": "C:"}, None)
        assert child == {"SystemRoot": r"C:\Windows", "systemdrive": "C:"}

    def test_nothing_on_the_list_is_a_credential(self):
        for name in PASSES:
            for word in ("SECRET", "TOKEN", "PASSWORD", "PASSWD", "CREDENTIAL", "API_KEY"):
                assert word not in name, name


class TestTheSpawn:
    def test_a_declared_env_is_added_and_the_process_can_still_start(self, monkeypatch):
        monkeypatch.setenv("ZARAM_TEST_OVERRIDE", "from-zaram")
        seen = _child_environment({"ZARAM_TEST_TOKEN": "secret-123", "ZARAM_TEST_OVERRIDE": "from-server"})

        # The server's own variables arrive, and win over Zaram's on a clash.
        assert seen["ZARAM_TEST_TOKEN"] == "secret-123"
        assert seen["ZARAM_TEST_OVERRIDE"] == "from-server"
        # And enough of Zaram's environment to start: PATH is what lets `npx`
        # find `node` at all; without SystemRoot, Node aborts on Windows.
        assert seen["PATH"], "PATH did not reach the child"
        if os.name == "nt":
            assert seen.get("SYSTEMROOT") or seen.get("SystemRoot"), "SystemRoot did not reach the child"

    def test_zarams_credential_does_not_reach_a_server(self, monkeypatch):
        # The 20 September finding, asserted at the process boundary.
        monkeypatch.setenv("ZARAM_API_SECRET", "the-key-to-the-spine")
        monkeypatch.setenv("ZARAM_DATA_DIR", "somewhere")
        monkeypatch.setenv("SOME_PROVIDER_API_KEY", "paid-for")

        for declared in (None, {"ITS_OWN": "1"}):
            seen = _child_environment(declared)
            assert "ZARAM_API_SECRET" not in seen
            assert "ZARAM_DATA_DIR" not in seen
            assert "SOME_PROVIDER_API_KEY" not in seen
            assert seen["PATH"]
