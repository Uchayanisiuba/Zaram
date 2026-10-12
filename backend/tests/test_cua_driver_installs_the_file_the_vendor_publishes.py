"""cua-driver is fetched from the release the vendor really publishes, and checked.

10 October 2026. The install button answered `HTTP 404` on its first press. The URL
joined `trycua/cua`'s SDK version (0.4.1) to an asset name that does not exist; the
driver is v0.34.1 under the tag `cua-driver-rs-v0.34.1`. These tests run on in-memory
archives and a pin override, so nothing here touches the network, and what they hold
down is the shape that would have caught it: the URL names a real tag and file, a
download is refused unless its hash is the pinned one, and an archive cannot write
outside the folder it is unpacked into.
"""

from __future__ import annotations

import hashlib
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from runtimes.mcp import cua_driver_install as cua


def _zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _pin(data: bytes, label: str = "windows-x86_64.zip") -> dict[str, str]:
    return {label: hashlib.sha256(data).hexdigest()}


def test_the_url_names_the_driver_release_and_a_real_asset():
    url = cua.release_url("windows-x86_64.zip")
    assert url == (
        "https://github.com/trycua/cua/releases/download/"
        "cua-driver-rs-v0.34.1/cua-driver-rs-0.34.1-windows-x86_64.zip"
    )
    # The mistake that 404'd: the SDK's version, and a name the release never had.
    assert "cua-cli" not in url and "/v0.4." not in url


@pytest.mark.parametrize(
    "system,machine,label",
    [
        ("Windows", "AMD64", "windows-x86_64.zip"),
        ("Windows", "ARM64", "windows-arm64.zip"),
        ("Darwin", "arm64", "darwin-arm64.tar.gz"),
        ("Darwin", "x86_64", "darwin-x86_64.tar.gz"),
        ("Linux", "x86_64", "linux-x86_64.tar.gz"),
        ("Linux", "aarch64", "linux-arm64.tar.gz"),
    ],
)
def test_each_platform_the_vendor_ships_maps_to_a_pinned_archive(system, machine, label):
    assert cua.platform_label(system, machine) == label
    assert len(cua.PINNED_SHA256[label]) == 64 and cua.SIZE_MB[label] > 0


def test_a_platform_the_vendor_does_not_ship_is_not_guessed():
    assert cua.platform_label("Windows", "x86") is None
    assert cua.platform_label("FreeBSD", "x86_64") is None


def test_every_pin_is_a_sha256_and_every_platform_has_a_size():
    assert set(cua.PINNED_SHA256) == set(cua.SIZE_MB)
    assert all(len(h) == 64 and int(h, 16) >= 0 for h in cua.PINNED_SHA256.values())


def test_a_download_that_is_not_the_pinned_file_is_refused_and_nothing_is_written(tmp_path):
    good = _zip({"cua-driver.exe": b"MZ real"})
    tampered = _zip({"cua-driver.exe": b"MZ something else"})
    dest = tmp_path / "bin"
    with pytest.raises(cua.InstallRefused, match="does not match"):
        cua.install(tampered, "windows-x86_64.zip", dest, pins=_pin(good))
    assert not dest.exists()


def test_a_platform_with_no_pin_is_refused():
    with pytest.raises(cua.InstallRefused, match="no pinned checksum"):
        cua.verify(b"x", "windows-x86_64.zip", pins={})


def test_the_program_and_its_neighbours_are_laid_down_together(tmp_path):
    data = _zip({
        "cua-driver-rs-0.34.1-windows-x86_64/cua-driver.exe": b"MZ driver",
        "cua-driver-rs-0.34.1-windows-x86_64/cua-cursor-theme.exe": b"MZ theme",
        "cua-driver-rs-0.34.1-windows-x86_64/README.txt": b"hello",
    })
    dest = tmp_path / "bin"
    path = cua.install(data, "windows-x86_64.zip", dest, pins=_pin(data))
    assert path == dest / "cua-driver.exe" and path.read_bytes() == b"MZ driver"
    assert (dest / "cua-cursor-theme.exe").read_bytes() == b"MZ theme"


def test_an_archive_without_the_program_is_an_error_not_an_empty_success(tmp_path):
    data = _zip({"something-else.exe": b"MZ"})
    with pytest.raises(cua.InstallRefused, match="did not contain cua-driver.exe"):
        cua.install(data, "windows-x86_64.zip", tmp_path / "bin", pins=_pin(data))
    assert not (tmp_path / "bin").exists()


def test_an_archive_cannot_write_outside_the_folder_it_is_unpacked_into(tmp_path):
    data = _zip({"../escaped.txt": b"x", "cua-driver.exe": b"MZ"})
    with pytest.raises(cua.InstallRefused, match="outside itself"):
        cua.install(data, "windows-x86_64.zip", tmp_path / "bin", pins=_pin(data))
    assert not (tmp_path / "escaped.txt").exists()


def test_a_tar_archive_installs_and_is_made_executable(tmp_path):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo("pkg/cua-driver")
        payload = b"#!/bin/sh\n"
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    data = buffer.getvalue()
    path = cua.install(data, "linux-x86_64.tar.gz", tmp_path / "bin", pins=_pin(data, "linux-x86_64.tar.gz"))
    assert path.name == "cua-driver" and path.read_bytes() == b"#!/bin/sh\n"


def test_download_and_install_asks_only_for_the_url_it_names(tmp_path):
    data = _zip({"cua-driver.exe": b"MZ"})
    asked: list[str] = []

    def fetch(url: str) -> bytes:
        asked.append(url)
        return data

    path, label = cua.download_and_install(fetch, "Windows", "AMD64", tmp_path / "bin", pins=_pin(data))
    assert asked == [cua.release_url("windows-x86_64.zip")] and label == "windows-x86_64.zip"
    assert path.exists()


def test_an_unsupported_platform_asks_the_network_for_nothing(tmp_path):
    def fetch(url: str) -> bytes:  # pragma: no cover - must not be called
        raise AssertionError("the network was asked")

    with pytest.raises(cua.InstallRefused, match="no build"):
        cua.download_and_install(fetch, "FreeBSD", "x86_64", tmp_path / "bin")


def test_the_route_goes_through_the_gate_and_not_around_it():
    source = (Path(__file__).resolve().parents[1] / "runtimes" / "mcp" / "api.py").read_text(encoding="utf-8")
    assert "urlretrieve" not in source and "urllib.request" not in source
    assert 'get_gate().request(url' in source


# --- the button, against a gate that has never been told about github.com --------------
#
# 10 October 2026, second report: after the 404 was fixed the same button answered "Zaram
# blocked a request to github.com: no policy exists for this destination". The route asked
# the gate with no grant, and default deny is the right answer for a host nobody named --
# but a person pressing Install under a sentence that says "downloads from github.com" has
# named it (rule 7j). These run the real route against a real gate with no rules at all,
# which is exactly the machine that failed; the earlier tests mocked `fetch` and could not.


@pytest.fixture
def fresh_gate(tmp_path):
    from core.egress import EgressGate, set_gate
    from core.egress.log import EgressLog
    from core.egress.policy import EgressPolicy

    policy = EgressPolicy(str(tmp_path / "policy.json"))
    gate = EgressGate(EgressLog(str(tmp_path / "egress.db")), policy)
    set_gate(gate)
    yield gate, policy
    set_gate(None)


class _Response:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _press_install(monkeypatch, tmp_path, data: bytes):
    import asyncio
    import urllib.request

    from runtimes.mcp import api

    requested: list[str] = []

    def urlopen(req, timeout=None):
        requested.append(req.full_url)
        return _Response(data)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(api, "CUADRIVER_INSTALL_DIR", tmp_path / "bin")
    # Install now files the server; never in the real data folder from a test.
    from runtimes.mcp.config import ServerStore

    monkeypatch.setattr(api, "_store", lambda: ServerStore(tmp_path / "mcp-servers.json"))
    launched: list = []

    def fake_run(argv, **kwargs):
        launched.append((argv, kwargs.get("env") or {}))

        class Done:
            returncode = 0
            stdout = ""
            stderr = ""

        return Done()

    monkeypatch.setattr(cua.subprocess, "run", fake_run)
    _press_install.launched = launched
    monkeypatch.setattr(api.platform, "system", lambda: "Windows")
    monkeypatch.setattr(api.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(cua, "PINNED_SHA256", {**cua.PINNED_SHA256, **_pin(data)})
    status = asyncio.run(api.install_cua_driver(api.InstallRequest()))
    return status, requested


def test_pressing_install_works_on_a_machine_that_never_allowed_github(fresh_gate, tmp_path, monkeypatch):
    gate, policy = fresh_gate
    assert not policy.has_rule("github.com")
    data = _zip({"cua-driver.exe": b"MZ not runnable"})
    status, requested = _press_install(monkeypatch, tmp_path, data)
    assert status.status == "complete", status.error
    assert requested == [cua.release_url("windows-x86_64.zip")]
    assert (tmp_path / "bin" / "cua-driver.exe").exists()
    # Rule 3: it left, and the log says so.
    entry = next(iter(gate.log.entries()))
    assert entry.host == "github.com" and entry.decision == "allowed"
    # ...and it is not a standing rule: nothing else may go to github.com afterwards.
    assert not policy.has_rule("github.com")


def test_installing_connects_it_as_a_tool_with_telemetry_off(fresh_gate, tmp_path, monkeypatch):
    """10 October 2026: a successful install left the program on disk and nothing else,
    so Settings still said "not installed" and the model never saw a tool. And the
    install's own `--version` launch let the driver record an installation for its
    telemetry before anyone had agreed to it."""
    from runtimes.mcp.config import ServerStore

    data = _zip({"cua-driver.exe": b"MZ not runnable"})
    status, _requested = _press_install(monkeypatch, tmp_path, data)
    assert status.status == "complete", status.error
    assert "connected" in status.message and "telemetry" in status.message

    servers = ServerStore(tmp_path / "mcp-servers.json").load()
    entry = servers[cua.SERVER_ID]
    assert entry.command == [str(tmp_path / "bin" / "cua-driver.exe"), "mcp"]
    assert entry.env.get("DO_NOT_TRACK") == "1"

    # Every launch the install made carried the switch, and one of them was the
    # persistent "telemetry disable".
    launched = _press_install.launched
    assert launched and all(env.get("DO_NOT_TRACK") == "1" for _argv, env in launched)
    assert any(argv[1:] == ["telemetry", "disable"] for argv, _env in launched)


def test_reinstalling_the_same_program_keeps_what_was_granted(fresh_gate, tmp_path, monkeypatch):
    from runtimes.mcp.config import ServerStore

    data = _zip({"cua-driver.exe": b"MZ"})
    _press_install(monkeypatch, tmp_path, data)
    store = ServerStore(tmp_path / "mcp-servers.json")
    store.grant(cua.SERVER_ID, "click")
    _press_install(monkeypatch, tmp_path, data)
    assert "click" in store.load()[cua.SERVER_ID].granted_tools


def test_every_launch_zaram_makes_carries_the_switch():
    """The driver sends telemetry unless told not to; `run_driver` is how Zaram starts it."""
    seen = {}

    def run(argv, **kwargs):
        seen.update(kwargs.get("env") or {})
        return None

    cua.run_driver(Path("cua-driver.exe"), "--version", run=run)
    assert seen.get("DO_NOT_TRACK") == "1" and seen.get("CUA_TELEMETRY_ENABLED") == "false"
    assert cua.server_entry(Path("x.exe"))["env"]["DO_NOT_TRACK"] == "1"


def test_the_install_route_never_launches_the_driver_without_the_switch():
    source = (Path(__file__).resolve().parents[1] / "runtimes" / "mcp" / "api.py").read_text(encoding="utf-8")
    start = source.index('@router.post("/cua-driver/install")')
    end = source.index('@router.get("/cua-driver/health")')
    assert "subprocess.run(" not in source[start:end]


def test_a_host_the_person_blocked_on_purpose_stays_blocked(fresh_gate, tmp_path, monkeypatch):
    from core.egress.policy import Mode

    _gate, policy = fresh_gate
    policy.set("github.com", Mode.DENY)
    data = _zip({"cua-driver.exe": b"MZ"})
    status, requested = _press_install(monkeypatch, tmp_path, data)
    assert status.status == "error" and "github.com" in status.error
    assert requested == [] and not (tmp_path / "bin").exists()


def test_the_kill_switch_stops_the_install_too(fresh_gate, tmp_path, monkeypatch):
    _gate, policy = fresh_gate
    policy.set_kill_switch(True)
    data = _zip({"cua-driver.exe": b"MZ"})
    status, requested = _press_install(monkeypatch, tmp_path, data)
    assert status.status == "error" and requested == []


def test_install_keeps_the_desktop_tools_in_front_of_the_model(fresh_gate, tmp_path, monkeypatch):
    """Nothing calls `set_ranker`, so tools reach the model in listing order: for
    cua-driver, `bring_to_front` and seven `browser_*` tools, and no click. Install
    pins a working set; it is visibility only and every call is still gated."""
    from runtimes.mcp.config import ServerStore

    data = _zip({"cua-driver.exe": b"MZ"})
    _press_install(monkeypatch, tmp_path, data)
    pinned = ServerStore(tmp_path / "mcp-servers.json").load()[cua.SERVER_ID].pinned_tools
    assert {"click", "type_text", "list_windows", "get_window_state", "get_desktop_state"} <= pinned
    assert pinned == set(cua.DEFAULT_PINS)


def test_every_default_pin_is_a_tool_the_driver_has():
    """Copied from cua-driver 0.34.1's `list-tools`, 10 October 2026."""
    published = {
        "bring_to_front", "click", "double_click", "drag", "get_accessibility_tree", "get_desktop_state",
        "get_window_state", "hotkey", "launch_app", "list_apps", "list_windows", "press_key",
        "right_click", "scroll", "set_value", "type_text", "zoom",
    }
    assert set(cua.DEFAULT_PINS) <= published


def test_a_pinned_tool_is_still_asked_about():
    from runtimes.mcp.policy import Verdict, WriteMode, decide

    for tool in ("click", "type_text", "press_key", "hotkey", "launch_app", "scroll"):
        assert decide(tool_name=tool, mode=WriteMode.HOST_UNDO, server_id="cua-driver").verdict is Verdict.CONFIRM


def test_installing_again_after_a_remove_downloads_nothing(fresh_gate, tmp_path, monkeypatch):
    """The only "off" used to be Remove, and undoing it re-downloaded 30 MB."""
    data = _zip({"cua-driver.exe": b"MZ"})
    _press_install(monkeypatch, tmp_path, data)
    from runtimes.mcp.config import ServerStore

    store = ServerStore(tmp_path / "mcp-servers.json")
    store.save({})  # what Remove leaves behind: the program, and no server entry
    status, requested = _press_install(monkeypatch, tmp_path, data)
    assert status.status == "complete" and requested == []
    assert "nothing was downloaded" in status.message
    assert store.load()[cua.SERVER_ID].enabled is True
