"""What a tool server is allowed to see of this process's environment.

Found 20 September 2026, reading `McpServer._child_env`: it started from
`dict(os.environ)`, so every attached server inherited the whole environment
of the backend — including **`ZARAM_API_SECRET`**, the per-launch credential
that authenticates every request to the API, `GET /memory` included. A
third-party MCP server, sloppy or hostile, was handed the key to the Spine
the moment it was attached. The 15 September fix that put the inheritance
there was right about what it added (`PATH`, `SYSTEMROOT`, without which
`npx` and Node cannot start) and did not subtract anything.

`CLAUDE.md`, custody: a tool description is third-party text, and so is the
process behind it. What crosses into it is decided the way the VRM loader
decides what an asset may reference — **an allow-list of names, never a
blocklist of patterns.** A blocklist of `SECRET|TOKEN|KEY|PASSWORD` is
guessed rather than known: `ZARAM_DATA_DIR` names none of those and tells a
server where the databases are.

Three sources, in order:

1. **What a process needs to start**, named below: the path, the system
   root, temp, home, locale, the proxy the user's network requires, and the
   cache and prefix variables the common launchers (`npx`, `uvx`, `pip`,
   `cargo`) read. Nothing in this list is a credential.
2. **What the server's own `env` block declares.** The person wrote it for
   this server; it always crosses, and it wins over the parent on a clash
   (the more specific claim, unchanged from 15 September).
3. **Nothing else.** Not `ZARAM_*`, not the cloud keys a shell may hold, not
   a variable a previous session exported for a test.

Windows environment names are case-insensitive and arrive in whatever case
the shell used (`SystemRoot`, `SYSTEMROOT`), so the comparison folds case
and the original spelling is kept — Node reads `SystemRoot` by that name.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Mapping, Optional

# fmt: off
#: Variables a child needs to *start* — locate its runtime, seed randomness,
#: find temp and home, speak the user's locale, reach the network the way the
#: user's machine reaches it. Read with the launcher in mind: `npx` needs
#: `APPDATA` for its cache and `PATHEXT` to resolve `.cmd`; `uvx` needs
#: `LOCALAPPDATA`; a Python server in a venv needs `VIRTUAL_ENV`.
PASSES: FrozenSet[str] = frozenset(name.upper() for name in (
    # the runtime and the system
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "OS",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "PROGRAMDATA",
    "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)",
    # temp and home
    "TEMP", "TMP", "TMPDIR", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "HOME",
    "APPDATA", "LOCALAPPDATA", "XDG_RUNTIME_DIR", "XDG_DATA_HOME",
    "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME",
    # who and where, as a process expects to find them
    "USER", "USERNAME", "LOGNAME", "SHELL", "COMPUTERNAME", "HOSTNAME",
    "TERM", "DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS",
    # locale and time
    "LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE", "LC_MESSAGES", "TZ",
    "PYTHONIOENCODING", "PYTHONUTF8",
    # the network, the way this machine reaches it
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "NODE_EXTRA_CA_CERTS",
    # launchers and their caches
    "VIRTUAL_ENV", "CONDA_PREFIX", "PYTHONPATH", "NODE_PATH", "NODE_OPTIONS",
    "NPM_CONFIG_CACHE", "NPM_CONFIG_PREFIX", "NPM_CONFIG_USERCONFIG",
    "UV_CACHE_DIR", "UV_PYTHON", "PIP_CACHE_DIR", "CARGO_HOME", "RUSTUP_HOME",
    "GOPATH", "GOCACHE", "JAVA_HOME", "DOTNET_ROOT",
))

#: Set on every child, asking it not to phone home.
#:
#: **This is a request, and the module is explicit about that rather than
#: quietly implying more.** A stdio server is a separate program with its own
#: sockets, and `EgressGate` intercepts what *Zaram* sends — so a server with
#: an analytics SDK in it can make a request this process never sees, and rule
#: 3 is unenforceable for that byte. No environment variable changes that.
#: What these do is turn off the SDKs that honour them, which is most of the
#: ones that get embedded by accident: PostHog, Mixpanel, Sentry, the Next.js
#: and Astro and Gatsby telemetry, `uv`, Homebrew. `DO_NOT_TRACK=1` is a small
#: cross-vendor convention rather than a standard, and it is worth sending for
#: the same reason a cookie banner gets the privacy-preserving answer: it
#: costs nothing and it is the correct one.
#:
#: **The remaining gap is stated in the interface, not papered over.**
#: `CLAUDE.md`: *never claim absolute security; state what is verifiable.* A
#: product that said "every byte is logged" while a child process had its own
#: socket would be making the one claim it cannot keep. What is true is that
#: every byte **Zaram** sends is logged, every call Zaram makes *into* a
#: server is logged, and what the server does on its own is the server's.
#:
#: Why not actually block it: an outbound firewall rule per child needs
#: administrator rights on Windows, breaks every server that legitimately
#: fetches something, and fails *open* when it cannot be applied — which is
#: the shape `electron-builder.yml` already records as the reason its payload
#: became an allow-list. A guard that silently does nothing is worse than a
#: limitation somebody can read.
#:
#: Applied **before** the server's own `env` block, so a person who
#: deliberately writes `DO_NOT_TRACK=0` for a server that needs it gets what
#: they asked for. Their block is the more specific claim, unchanged from 15
#: September.
IMPOSED: Dict[str, str] = {
    "DO_NOT_TRACK": "1",
    # The vendor-specific ones, because `DO_NOT_TRACK` is young and these are
    # what the SDKs actually read today.
    "POSTHOG_DISABLED": "1",
    "SENTRY_DSN": "",
    "NEXT_TELEMETRY_DISABLED": "1",
    "ASTRO_TELEMETRY_DISABLED": "1",
    "GATSBY_TELEMETRY_DISABLED": "1",
    "SCARF_ANALYTICS": "false",
    "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
    "HOMEBREW_NO_ANALYTICS": "1",
    "UV_NO_ANALYTICS": "1",
}
# fmt: on


def child_environment(
    parent: Mapping[str, str],
    declared: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    """The environment a tool server is spawned with.

    `parent` is this process's environment; `declared` the server's own
    `env` block from `mcp-servers.json`, or `None`. Pure, so a test can hand
    it a dictionary with a secret in it and read what came out without
    spawning anything.

    Three layers, in order: what the allow-list lets through, the telemetry
    opt-outs Zaram asks for, and the server's own block — which wins, because
    the person wrote it for this server.
    """
    child: Dict[str, str] = {}
    for name, value in parent.items():
        if name.upper() in PASSES:
            child[name] = value
    # Asked for, never enforced. See `IMPOSED`.
    child.update(IMPOSED)
    if declared:
        for name, value in declared.items():
            child[str(name)] = str(value)
    return child
