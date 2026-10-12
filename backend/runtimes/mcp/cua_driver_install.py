"""Installing cua-driver: the right file, checked against a hash written down here.

**Why this module exists, 10 October 2026.** The install button answered "HTTP 404" on
the first press. The URL had been built from a version number that belongs to a
different product -- `trycua/cua`'s SDK is v0.4.1 and cua-driver is v0.34.1, under the
tag `cua-driver-rs-v0.34.1` -- and an asset name nobody had looked up. It also moved a
file called `cua.exe` that is not what the archive holds, ran whatever it got, and sent
the request around the egress gate.

What the release really publishes, read from GitHub's release API on 10 October 2026
(`https://api.github.com/repos/trycua/cua/releases/tags/cua-driver-rs-v0.34.1`):
per-platform archives named `cua-driver-rs-<version>-<platform>.zip|.tar.gz`, each with
a SHA-256 the API reports as its digest and the vendor's `install.ps1` checks against
`SHA256SUMS`. The digests below are those, **pinned in source**: a hash fetched from
the same place as the file proves the download was not corrupted, and a hash written
here, in a reviewed commit, proves it is the file this commit meant. To move to a new
release, read its digests from the same API call, change `VERSION` and the table
together, and say so in the commit.

The vendor's own installer is the reference for the rest: the archive holds
`cua-driver(.exe)` (plus `cua-cursor-theme(.exe)` from 0.12.7), laid down beside each
other in one directory.

**Attaching it, read off the program itself on 10 October 2026.** `cua-driver manifest`
reports `mcp_invocation: {"args": ["mcp"]}`, and its help says `mcp` runs "direct
runtime on Windows/Linux, app-daemon proxy on macOS". So on Windows and Linux no
background `serve` is needed: `cua-driver mcp` over stdio is the whole server, and
Zaram's own client reached all 59 tools that way. On macOS the same command proxies to
the vendor's app, which the vendor's installer sets up; Zaram has not been run there.
`server_entry` is what install writes into `mcp-servers.json`.

**Telemetry is off before the first run, and stays off.** The driver "sends content-free
product telemetry by default" to `eu.i.posthog.com` -- bytes leaving the machine that
Zaram's egress gate never sees and its log never records, which is rule 3 broken by a
child process. Measured on a fresh `CUA_DRIVER_TELEMETRY_HOME`: with `DO_NOT_TRACK=1` the
driver reports `disabled (source: do_not_track)` and creates no installation id, so
every process Zaram starts gets `QUIET_ENV`, and install also runs `telemetry disable`
so the setting persists for anything else that launches it. The first version of the
install route ran `cua-driver --version` without it, which is how the driver recorded
an installation (and most likely reported one) before anyone had said it could.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

#: The id Zaram files the driver under. `policy._is_cua_server` keys its exact-name
#: rules off "cua" in this.
SERVER_ID = "cua-driver"

#: Every switch the binary reads that turns its telemetry off. `DO_NOT_TRACK` is the one
#: measured to work from the first run; the vendor's own two are set beside it so a
#: release that stops honouring one is still covered by another.
QUIET_ENV: Dict[str, str] = {
    "DO_NOT_TRACK": "1",
    "CUA_TELEMETRY_ENABLED": "false",
    "CUA_DRIVER_RS_TELEMETRY_ENABLED": "false",
}

REPO = "trycua/cua"
VERSION = "0.34.1"
TAG = f"cua-driver-rs-v{VERSION}"

#: platform label -> SHA-256 of that archive. See the module docstring for the source.
PINNED_SHA256: Dict[str, str] = {
    "windows-x86_64.zip": "a0ff8b1db0b16d6d1885c165c1a9f304a634cae53a1e7547cf4f33610283ee30",  # 29.9 MB
    "windows-arm64.zip": "b73e3e06c2c61b331a41bb6f6517260230ec8d96d234d4ed8351336e2c38e9cb",  # 28.1 MB
    "darwin-arm64.tar.gz": "83ffed8d41ef0f133976d594b02eb86dd59ef4a8721396b6e25078a59c6056d6",  # 72.3 MB
    "darwin-x86_64.tar.gz": "c485781a64b6f75ea46f63d03c5b4f646e0f1dcea2c7547805f235259193a156",  # 72.3 MB
    "linux-x86_64.tar.gz": "911481f5cfc6cb537ce0cf766a7c3a73a897a2c14c46841deed49397a4dc1834",  # 33.4 MB
    "linux-arm64.tar.gz": "6be4b56889f14fa71574f8f14e2d282b5b297449ae629e0d3af2cbebfdc56780",  # 33.1 MB
}

#: Approximate download sizes in MB, for the sentence next to the button. From the same API call.
SIZE_MB: Dict[str, float] = {
    "windows-x86_64.zip": 29.9, "windows-arm64.zip": 28.1,
    "darwin-arm64.tar.gz": 72.3, "darwin-x86_64.tar.gz": 72.3,
    "linux-x86_64.tar.gz": 33.4, "linux-arm64.tar.gz": 33.1,
}

_ARCH = {"amd64": "x86_64", "x86_64": "x86_64", "x64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}


class InstallRefused(Exception):
    """The install did not happen, and this says why in a sentence for the person."""


def platform_label(system: str, machine: str) -> Optional[str]:
    """`windows-x86_64.zip` and friends, or None for a platform the vendor does not ship."""
    system = (system or "").lower()
    arch = _ARCH.get((machine or "").lower())
    if arch is None or system not in ("windows", "darwin", "linux"):
        return None
    label = f"{system}-{arch}.{'zip' if system == 'windows' else 'tar.gz'}"
    return label if label in PINNED_SHA256 else None


def asset_name(label: str) -> str:
    return f"cua-driver-rs-{VERSION}-{label}"


def release_url(label: str) -> str:
    return f"https://github.com/{REPO}/releases/download/{TAG}/{asset_name(label)}"


def verify(data: bytes, label: str, pins: Optional[Dict[str, str]] = None) -> None:
    """Raise `InstallRefused` unless `data` is exactly the file that was pinned."""
    # `is None`, not falsy: an empty table is a table with nothing pinned, and must refuse.
    table = PINNED_SHA256 if pins is None else pins
    expected = table.get(label)
    if not expected:
        raise InstallRefused(f"There is no pinned checksum for {label}, so it was not installed.")
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise InstallRefused(
            f"The download does not match the checksum this version of Zaram expects "
            f"(expected {expected[:12]}…, got {actual[:12]}…), so nothing was installed."
        )


def _inside(root: Path, member: str) -> Path:
    target = (root / member).resolve()
    if root.resolve() not in target.parents and target != root.resolve():
        raise InstallRefused(f"The archive names a path outside itself ({member}), so it was not unpacked.")
    return target


def _unpack(data: bytes, label: str, into: Path) -> None:
    if label.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                _inside(into, name)
            archive.extractall(into)
        return
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            _inside(into, member.name)
            if member.issym() or member.islnk():
                _inside(into, str((Path(member.name).parent / member.linkname).as_posix()))
        archive.extractall(into)


def install(data: bytes, label: str, dest: Path, *, pins: Optional[Dict[str, str]] = None) -> Path:
    """Verify, unpack in a scratch folder, and lay the program down in `dest`.

    Returns the path of the driver. Nothing reaches `dest` unless the hash matched and the
    archive held the program, so a refused install leaves what was there before.
    """
    verify(data, label, pins)
    binary_name = "cua-driver.exe" if label.startswith("windows") else "cua-driver"
    with tempfile.TemporaryDirectory() as scratch:
        staging = Path(scratch)
        _unpack(data, label, staging)
        found = next((p for p in staging.rglob(binary_name) if p.is_file()), None)
        if found is None:
            raise InstallRefused(f"The archive did not contain {binary_name}, so nothing was installed.")
        dest.mkdir(parents=True, exist_ok=True)
        # Everything that sits beside the program goes with it: the vendor ships a cursor
        # theme helper and may ship libraries, and a driver without its neighbours fails
        # later and reads as a broken product.
        shutil.copytree(found.parent, dest, dirs_exist_ok=True)
    installed = dest / binary_name
    if not label.startswith("windows"):
        installed.chmod(installed.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return installed


def quiet_env(base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """The environment to launch the driver in: this process's, with telemetry off."""
    return {**(os.environ if base is None else base), **QUIET_ENV}


def run_driver(binary: Path, *args: str, timeout: float = 30.0, run: Optional[Callable[..., Any]] = None):
    """Run one driver subcommand with telemetry off. The only way Zaram should start it."""
    run = run or subprocess.run
    return run([str(binary), *args], capture_output=True, text=True, timeout=timeout, env=quiet_env())


def disable_telemetry(binary: Path, *, run: Optional[Callable[..., Any]] = None) -> bool:
    """Persist "telemetry off" in the driver's own settings, for launches Zaram does not make."""
    try:
        return run_driver(binary, "telemetry", "disable", run=run).returncode == 0
    except Exception:  # noqa: BLE001 - QUIET_ENV still covers every launch Zaram makes
        return False


#: The desktop tools kept in front of the model from the start: find and open an app,
#: see its windows and what is in them, and act on them. **First-party knowledge, like
#: `KNOWN_HOSTS`, and visibility only**: a pin decides what the model can see and never
#: what it may do -- every one of these still goes through `policy._cua_decision`, and
#: the ones that change something ask first. Settings shows the set and the person can
#: change it.
#:
#: Why it exists, measured 10 October 2026: nothing in the app calls
#: `McpRuntime.set_ranker`, so a server's tools reach the model in the order the server
#: lists them, cut to the budget -- for cua-driver that is `bring_to_front` and seven
#: `browser_*` tools, and "click on the Start button" arrived with no click, no window
#: list and no screenshot. Every name here is in cua-driver 0.34.1's `list-tools`.
DEFAULT_PINS = (
    "list_apps", "launch_app", "list_windows", "get_window_state", "get_desktop_state",
    "click", "type_text", "press_key", "hotkey", "scroll",
)


def server_entry(binary: Path) -> Dict[str, Any]:
    """The `mcp-servers.json` block for the installed driver: stdio, telemetry off."""
    return {
        "command": str(binary),
        "args": ["mcp"],
        "env": dict(QUIET_ENV),
        "pinnedTools": list(DEFAULT_PINS),
    }


def download_and_install(
    fetch: Callable[[str], bytes], system: str, machine: str, dest: Path, *, pins: Optional[Dict[str, str]] = None
) -> Tuple[Path, str]:
    """Fetch through `fetch` (the egress gate), check, install. Returns (path, label)."""
    label = platform_label(system, machine)
    if label is None:
        raise InstallRefused(f"cua-driver has no build for {system} on {machine}.")
    data = fetch(release_url(label))
    return install(data, label, dest, pins=pins), label
