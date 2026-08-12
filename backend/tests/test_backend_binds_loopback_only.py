# backend/tests/test_backend_binds_loopback_only.py
"""The API is reachable from this machine and from nowhere else.

`main.py` bound `0.0.0.0` — every network interface — and
`electron/backend/backendLauncher.js` launches the packaged app through exactly
that path. There is no authentication on any endpoint. So the shipped product
would have published, to whatever network the user happened to be on:

* `GET /memory` — the entire Spine
* `GET /egress` — every request that has ever left, with its literal text
* `PUT /egress/policy` — enough to set a host to `allow` and defeat the gate
* `POST /egress/pending/{id}` — enough to approve a send the user never saw

On a café or hotel network that is every promise the product makes, broken by
one string. Windows Firewall prompts on first run and blocks inbound on
networks marked public, which is a real mitigation and is exactly one
click-through from gone — an OS firewall dialog is not where this boundary
belongs.

The scan below is deliberately broader than the one line that was wrong.
Binding is the kind of thing that gets re-added by a debugging session and left
behind, and it is invisible when it happens: everything keeps working, and it
keeps working for other people too.
"""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]

#: `host="..."` and `--host ...` as they appear in real launch code.
HOST_ASSIGNMENT = re.compile(r"""host\s*=\s*["']([^"']+)["']""")
HOST_FLAG = re.compile(r"""--host["'\s,]+["']?([0-9a-zA-Z.:_-]+)""")

#: Directories that are not ours, or are not launch code.
SKIP_DIRS = {
    "venv", ".venv", "__pycache__", "node_modules", "tests",
    "audio", "audio_cache", "audio_clips", "audio_output",
    "image_output", "temp", "uploads", "generated",
}


def is_loopback(host: str) -> bool:
    """Loopback names and addresses only. Anything unparseable is not."""
    lowered = host.strip().lower()
    if lowered in {"localhost"} or lowered.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(lowered).is_loopback
    except ValueError:
        return False


def python_sources() -> list[Path]:
    found = []
    for path in BACKEND.rglob("*.py"):
        if SKIP_DIRS & set(path.relative_to(BACKEND).parts):
            continue
        found.append(path)
    return found


def test_the_listen_host_is_loopback():
    """The constant the entrypoint actually uses."""
    import main

    assert is_loopback(main.LISTEN_HOST), (
        f"the backend would listen on {main.LISTEN_HOST!r}, which is reachable "
        "from other machines — and no endpoint requires authentication"
    )


def test_the_entrypoint_uses_the_constant():
    """A literal slipped back into `uvicorn.run` would not be caught above."""
    source = (BACKEND / "main.py").read_text(encoding="utf-8")
    run_call = re.search(r"uvicorn\.run\((.*?)\)", source, re.DOTALL)

    assert run_call, "could not find the uvicorn.run call in main.py"
    assert "LISTEN_HOST" in run_call.group(1), (
        "main.py calls uvicorn.run with a literal host rather than LISTEN_HOST, "
        "so the constant and the binding can disagree"
    )


def test_no_shipped_module_binds_a_routable_address():
    """Anywhere in the backend, not just the entrypoint.

    A second server started for a debugging session is the likely way this
    comes back, and it would come back somewhere this file has to look for it
    rather than somewhere anyone would think to check.
    """
    offenders: list[str] = []

    for path in python_sources():
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in (HOST_ASSIGNMENT, HOST_FLAG):
            for match in pattern.finditer(text):
                host = match.group(1)
                # Templates and env lookups are resolved elsewhere; only
                # literal addresses are decidable here.
                if any(c in host for c in "{}$%"):
                    continue
                if not re.match(r"^[0-9a-zA-Z.:_-]+$", host):
                    continue
                # A bare hostname is somebody's outbound URL, not a bind.
                if not (host[0].isdigit() or host in {"localhost", "::"} or ":" in host):
                    continue
                if is_loopback(host):
                    continue
                line = text[: match.start()].count("\n") + 1
                offenders.append(f"{path.relative_to(BACKEND)}:{line} binds {host!r}")

    assert not offenders, (
        "these would accept connections from other machines, and nothing in "
        "this API asks who is calling:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    "host,loopback",
    [
        ("127.0.0.1", True),
        ("localhost", True),
        ("::1", True),
        ("127.0.0.5", True),
        ("0.0.0.0", False),
        ("::", False),
        ("192.168.1.170", False),
        ("127.0.0.1.evil.com", False),
    ],
)
def test_the_loopback_check_itself(host, loopback):
    """Including the string-prefix trap: `127.0.0.1.evil.com` is not loopback,
    and a `startswith("127.")` test would say it is."""
    assert is_loopback(host) is loopback
