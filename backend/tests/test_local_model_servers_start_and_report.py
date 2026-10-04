"""Zaram starts the local model servers it finds, and says what it can reach.

Asked for 4 October 2026, after the maintainer's TabbyAPI was not running and Zaram
therefore showed no Qwen: *"can we implement a permanent fix so Tabby always launches
when installed if the user has Tabby LLM, and confirm we have access to Ollama and
Tabby in the section of Settings where users download LLMs."*

What these assert that a green suite could otherwise hide:

* **That a launch really happens.** One test writes a fake TabbyAPI checkout whose
  `main.py` serves Tabby-shaped responses, and brings it up through the real
  detection, the real `Popen`, the real log file and the real probe. A fixture that
  never starts a process cannot say whether a detached child serves.
* **That LM Studio is not mistaken for Tabby.** Both default to port 1234, so "a
  server answered" proves nothing, and starting Tabby on top of LM Studio -- or
  reporting LM Studio's models as Tabby's -- is the failure.
* **That it never starts anything under test.** The backend suite boots the real
  application; a test run launching an 11 GB model server is not acceptable.
* **That no model name drives any decision.** Asserted on the module's code, not
  on its prose: `CLAUDE.md`'s *"build for the set of models, never for one"* is
  enforced by looking, not by remembering.
"""

from __future__ import annotations

import ast
import json
import os
import re
import socket
import sys
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import providers.model_servers as lr
from providers.model_servers import Install, Probe, ServerStartError


# --------------------------------------------------------------------- helpers


class _Handler(BaseHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):  # noqa: N802 - the name http.server looks for
        entry = self.routes.get(self.path)
        if entry is None:
            self.send_response(404)
            self.end_headers()
            return
        status, body = entry
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):  # silence the per-request line
        pass


@contextmanager
def _serving(routes):
    handler = type("H", (_Handler,), {"routes": routes})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def _closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _tabby_on(port: int) -> "lr._TabbyAPI":
    spec = lr._TabbyAPI()
    spec.port = port
    return spec


def _ollama_on(port: int) -> "lr._Ollama":
    spec = lr._Ollama()
    spec.port = port
    return spec


TABBY_MODELS = {"object": "list", "data": [{"id": "Big-27B", "owned_by": "tabbyAPI"}]}
HEALTHY = {"status": "healthy", "issues": []}


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    lr._launches.clear()
    monkeypatch.setattr(lr, "_log_path", lambda rid: str(tmp_path / f"{rid}.log"))
    yield
    for launch in list(lr._launches.values()):
        try:
            launch.process.kill()
        except Exception:  # noqa: BLE001 - a fake process has nothing to kill
            pass
    lr._launches.clear()


class _Proc:
    """A stand-in for a started process. `code` None means still running."""

    def __init__(self, code=None):
        self.code = code

    def poll(self):
        return self.code

    def kill(self):
        self.code = -9


class _Scripted(lr._Server):
    """A runtime whose answers are given, for testing the lifecycle."""

    id = "scripted"
    label = "Scripted"
    port = 9

    def __init__(self, probes, install):
        self._probes = list(probes)
        self._install = install
        self.probed = 0

    def probe(self, timeout):
        self.probed += 1
        return self._probes.pop(0) if len(self._probes) > 1 else self._probes[0]

    def find_install(self, config):
        return self._install


def _runnable(path="/x/serve"):
    return Install(path=path, source="found", argv=(path, "serve"), cwd=None)


@pytest.fixture()
def scripted(monkeypatch):
    def make(probes, install=None):
        spec = _Scripted(probes, install)
        monkeypatch.setitem(lr.SERVERS, "scripted", spec)
        return spec

    return make


# ---------------------------------------------------------------------- probing


class TestTellingServersApart:
    def test_tabbyapi_is_recognised_by_what_it_says_it_is(self):
        with _serving({"/v1/models": (200, TABBY_MODELS)}) as port:
            seen = _tabby_on(port).probe(2)
        assert seen.serving and seen.models == ("Big-27B",)

    def test_lm_studio_on_the_same_port_is_not_tabbyapi(self):
        """The reason this class exists. LM Studio and TabbyAPI both default to
        1234, and it lists models in the same OpenAI shape -- so reporting its
        models as Tabby's, or starting Tabby over it, is the failure."""
        lm_studio = {"object": "list", "data": [{"id": "some-model", "owned_by": "organization_owner"}]}
        with _serving({"/v1/models": (200, lm_studio)}) as port:
            seen = _tabby_on(port).probe(2)
        assert not seen.serving
        assert seen.other_server
        assert seen.models == ()

    def test_a_tabbyapi_with_no_model_in_its_folder_is_still_recognised(self):
        """It lists nothing, so `owned_by` cannot identify it. Its own health route
        is the second chance -- and an *empty* server must not read as absent."""
        with _serving({"/v1/models": (200, {"object": "list", "data": []}), "/health": (200, HEALTHY)}) as port:
            seen = _tabby_on(port).probe(2)
        assert seen.serving and seen.models == ()

    def test_a_tabbyapi_with_authentication_on_is_still_recognised(self):
        with _serving({"/v1/models": (401, {"detail": "no key"}), "/health": (200, HEALTHY)}) as port:
            seen = _tabby_on(port).probe(2)
        assert seen.serving

    def test_nothing_listening_is_not_serving_and_is_not_another_server(self):
        seen = _tabby_on(_closed_port()).probe(1.0)
        assert seen == Probe()

    def test_ollama_is_recognised_and_its_models_listed(self):
        body = {"models": [{"name": "a:1b"}, {"name": "b:2b"}]}
        with _serving({"/api/tags": (200, body)}) as port:
            seen = _ollama_on(port).probe(2)
        assert seen.serving and seen.models == ("a:1b", "b:2b")

    def test_something_else_on_ollamas_port_is_not_ollama(self):
        with _serving({"/api/tags": (200, {"unrelated": True})}) as port:
            seen = _ollama_on(port).probe(2)
        assert not seen.serving and seen.other_server

    def test_an_ollama_with_no_models_is_serving_with_none(self):
        with _serving({"/api/tags": (200, {"models": []})}) as port:
            seen = _ollama_on(port).probe(2)
        assert seen.serving and seen.models == ()


# ----------------------------------------------------------- finding an install


def _checkout(root: Path, *, config="config_sample.yml") -> Path:
    root.mkdir(parents=True)
    (root / "main.py").write_text("# serves\n")
    (root / "endpoints").mkdir()
    (root / config).write_text("x: 1\n")
    return root


def _venv(env: Path) -> Path:
    scripts = env / ("Scripts" if sys.platform == "win32" else "bin")
    scripts.mkdir(parents=True)
    exe = scripts / ("python.exe" if sys.platform == "win32" else "python")
    exe.write_text("")
    return exe


class TestOnlyLoopbackIsEverAsked:
    """The egress chokepoint exempts this module on the strength of speaking only to
    loopback. An exemption has to be a fact about the code, so this tries."""

    def test_a_probe_of_another_machine_is_refused_not_made(self, monkeypatch):
        called = []
        monkeypatch.setattr(lr, "urlopen", lambda *a, **k: called.append(a) or pytest.fail("connected"))
        assert lr._get_json("http://example.com/v1/models", 1.0) == (None, None)
        assert lr._get_json("http://192.168.1.20:1234/v1/models", 1.0) == (None, None)
        assert called == []

    def test_a_hostname_that_merely_contains_a_loopback_one_is_refused(self, monkeypatch):
        """`127.0.0.1.evil.example` starts like loopback and is not."""
        monkeypatch.setattr(lr, "urlopen", lambda *a, **k: pytest.fail("connected"))
        assert lr._get_json("http://127.0.0.1.evil.example/", 1.0) == (None, None)

    def test_loopback_itself_is_asked(self):
        with _serving({"/v1/models": (200, {"data": []})}) as port:
            status, _ = lr._get_json(f"http://127.0.0.1:{port}/v1/models", 2.0)
        assert status == 200


class TestFindingTabbyAPI:
    @pytest.fixture(autouse=True)
    def _home(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "home"))
        (tmp_path / "home").mkdir()
        self.home = tmp_path / "home"

    def test_a_checkout_in_the_home_folder_is_found_without_being_told(self):
        _checkout(self.home / "tabbyAPI")
        _venv(self.home / "tabbyAPI" / "venv")
        found = lr._TabbyAPI().find_install({})
        assert found is not None
        assert found.source == "found"
        assert found.path == str(self.home / "tabbyAPI")
        assert found.argv and found.argv[1] == "main.py"
        assert found.cwd == str(self.home / "tabbyAPI")

    def test_a_folder_that_only_has_the_name_is_not_a_checkout(self):
        """Found by what it contains, not by what it is called."""
        (self.home / "tabbyAPI").mkdir()
        assert lr._TabbyAPI().find_install({}) is None

    def test_a_checkout_missing_its_endpoints_is_not_one(self):
        root = _checkout(self.home / "tabbyAPI")
        (root / "endpoints").rmdir()
        assert lr._TabbyAPI().find_install({}) is None

    def test_the_environment_beside_the_checkout_is_found(self):
        """The maintainer's layout: the environment is a sibling, not inside."""
        _checkout(self.home / "tabbyAPI")
        env_python = _venv(self.home / "tabbyapi-env")
        found = lr._TabbyAPI().find_install({})
        assert Path(found.argv[0]).samefile(env_python)  # case-insensitive filesystems spell one path two ways

    def test_a_checkout_with_no_environment_says_so_rather_than_failing_later(self):
        _checkout(self.home / "tabbyAPI")
        found = lr._TabbyAPI().find_install({})
        assert found is not None and found.argv is None
        assert "Python environment" in found.problem

    def test_a_configured_path_is_used_and_marked_as_configured(self, tmp_path):
        root = _checkout(tmp_path / "elsewhere" / "tabby")
        _venv(root / ".venv")
        found = lr._TabbyAPI().find_install({"path": str(root)})
        assert found.source == "configured" and found.path == str(root)

    def test_a_configured_path_that_is_wrong_is_not_quietly_replaced_by_a_search(self, tmp_path):
        """The person said where. A copy that happens to sit in the home folder is
        not the answer to *"it is over there"*."""
        _checkout(self.home / "tabbyAPI")
        _venv(self.home / "tabbyAPI" / "venv")
        assert lr._TabbyAPI().find_install({"path": str(tmp_path / "nowhere")}) is None

    def test_an_explicit_interpreter_is_honoured(self, tmp_path):
        root = _checkout(self.home / "tabbyAPI")
        mine = tmp_path / "mypython"
        mine.write_text("")
        found = lr._TabbyAPI().find_install({"python": str(mine)})
        assert found.argv[0] == str(mine)
        assert found.cwd == str(root)

    def test_an_explicit_interpreter_that_does_not_exist_is_not_replaced(self, tmp_path):
        _checkout(self.home / "tabbyAPI")
        _venv(self.home / "tabbyAPI" / "venv")
        found = lr._TabbyAPI().find_install({"python": str(tmp_path / "gone")})
        assert found.argv is None

    def test_a_path_is_validated_when_it_is_given(self, tmp_path):
        assert "does not look like a TabbyAPI checkout" in lr._TabbyAPI().check_path(str(tmp_path))
        root = _checkout(tmp_path / "ok")
        assert lr._TabbyAPI().check_path(str(root)) == ""


class TestFindingOllama:
    def test_it_is_found_on_the_path_and_started_with_serve(self, tmp_path, monkeypatch):
        exe = tmp_path / "ollama.exe"
        exe.write_text("")
        monkeypatch.setattr(lr.shutil, "which", lambda name: str(exe))
        found = lr._Ollama().find_install({})
        assert found.argv == (str(exe), "serve")

    def test_a_configured_folder_is_searched_for_the_program(self, tmp_path):
        (tmp_path / "ollama.exe").write_text("")
        found = lr._Ollama().find_install({"path": str(tmp_path)})
        assert found.source == "configured"

    def test_a_configured_path_with_nothing_there_is_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr(lr.shutil, "which", lambda name: "/somewhere/ollama")
        assert lr._Ollama().find_install({"path": str(tmp_path / "nothing")}) is None

    def test_nothing_installed_is_none_not_an_error(self, monkeypatch, tmp_path):
        monkeypatch.setattr(lr.shutil, "which", lambda name: None)
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        monkeypatch.setenv("ProgramFiles", str(tmp_path))
        if sys.platform == "win32":
            assert lr._Ollama().find_install({}) is None


# ------------------------------------------------------------------ describing


class TestWhatIsReported:
    def test_a_running_server_says_so_and_names_its_models(self, scripted):
        scripted([Probe(serving=True, models=("a", "b"))], _runnable())
        row = lr.describe("scripted", config={})
        assert row["state"] == "running" and row["model_count"] == 2
        assert row["models"] == ["a", "b"]
        assert row["can_start"] is False

    def test_an_installed_server_that_is_not_running_can_be_started(self, scripted):
        scripted([Probe()], _runnable())
        row = lr.describe("scripted", config={})
        assert row["state"] == "stopped" and row["can_start"] is True and row["installed"]

    def test_a_server_that_is_not_installed_says_so(self, scripted):
        scripted([Probe()], None)
        row = lr.describe("scripted", config={})
        assert row["state"] == "not_installed" and row["can_start"] is False

    def test_an_install_that_cannot_run_says_why(self, scripted):
        scripted([Probe()], Install(path="/p", source="found", argv=None, problem="no python"))
        row = lr.describe("scripted", config={})
        assert row["state"] == "cannot_start" and row["problem"] == "no python"

    def test_another_server_on_the_port_is_reported_not_started_over(self, scripted):
        scripted([Probe(other_server=True)], _runnable())
        row = lr.describe("scripted", config={})
        assert row["state"] == "port_taken" and row["can_start"] is False

    def test_the_model_list_is_capped_but_the_count_is_not(self, scripted):
        names = tuple(f"m{i}" for i in range(20))
        scripted([Probe(serving=True, models=names)], _runnable())
        row = lr.describe("scripted", config={})
        assert row["model_count"] == 20 and len(row["models"]) == lr.MAX_MODELS_SHOWN

    def test_auto_start_is_on_unless_somebody_turned_it_off(self, scripted):
        scripted([Probe()], _runnable())
        assert lr.describe("scripted", config={})["auto_start"] is True
        assert lr.describe("scripted", config={"auto_start": False})["auto_start"] is False

    def test_each_server_says_which_settings_apply_to_it(self):
        """The interface draws only these. A Python-interpreter field under Ollama,
        which is a single executable, would settle nothing."""
        assert lr._Ollama.fields == ("path",)
        assert lr._TabbyAPI.fields == ("path", "python")
        row = lr.describe("tabbyapi", config={}, probe=Probe())
        assert row["fields"] == ["path", "python"]

    def test_zaram_sees_is_not_asked_here(self, scripted):
        """`None` means *not asked*, which is not zero. The route, which can see
        the catalogue, fills it in."""
        scripted([Probe()], _runnable())
        assert lr.describe("scripted", config={})["zaram_sees"] is None

    def test_every_server_is_described_together(self, scripted):
        scripted([Probe()], None)
        ids = [row["id"] for row in lr.describe_all(config={})]
        assert set(ids) >= {"ollama", "tabbyapi", "scripted"}


# -------------------------------------------------------------------- starting


class TestStarting:
    def test_it_spawns_once_with_the_command_and_directory_found(self, scripted):
        scripted([Probe()], Install(path="/p", source="found", argv=("/p/py", "main.py"), cwd="/p"))
        calls = []
        row = lr.start("scripted", config={}, spawn=lambda a, c, log: calls.append((a, c, log)) or _Proc())
        assert calls and calls[0][0] == ("/p/py", "main.py") and calls[0][1] == "/p"
        assert row["state"] == "starting"

    def test_a_second_start_during_a_launch_does_not_start_a_second_server(self, scripted):
        """Two clicks, or a click racing the automatic start, spawn one server."""
        scripted([Probe()], _runnable())
        calls = []
        spawn = lambda a, c, log: calls.append(1) or _Proc()  # noqa: E731
        lr.start("scripted", config={}, spawn=spawn, now=100.0)
        lr.start("scripted", config={}, spawn=spawn, now=110.0)
        assert len(calls) == 1

    def test_it_starts_again_once_the_first_launch_has_died(self, scripted):
        scripted([Probe()], _runnable())
        calls = []
        procs = [_Proc(code=1), _Proc()]
        spawn = lambda a, c, log: calls.append(1) or procs.pop(0)  # noqa: E731
        lr.start("scripted", config={}, spawn=spawn, now=100.0)
        lr.start("scripted", config={}, spawn=spawn, now=101.0)
        assert len(calls) == 2

    def test_starting_a_server_that_is_already_up_starts_nothing(self, scripted):
        scripted([Probe(serving=True, models=("m",))], _runnable())
        calls = []
        row = lr.start("scripted", config={}, spawn=lambda *a: calls.append(1) or _Proc())
        assert calls == [] and row["state"] == "running"

    def test_it_refuses_to_start_over_another_server(self, scripted):
        scripted([Probe(other_server=True)], _runnable())
        with pytest.raises(ServerStartError, match="already using port"):
            lr.start("scripted", config={}, spawn=lambda *a: _Proc())

    def test_it_refuses_when_nothing_is_installed(self, scripted):
        scripted([Probe()], None)
        with pytest.raises(ServerStartError, match="not installed"):
            lr.start("scripted", config={}, spawn=lambda *a: _Proc())

    def test_it_refuses_with_the_reason_when_the_install_cannot_run(self, scripted):
        scripted([Probe()], Install(path="/p", source="found", argv=None, problem="no python found"))
        with pytest.raises(ServerStartError, match="no python found"):
            lr.start("scripted", config={}, spawn=lambda *a: _Proc())

    def test_a_program_that_will_not_launch_becomes_a_sentence_not_a_traceback(self, scripted):
        scripted([Probe()], _runnable())

        def refuse(*_a):
            raise PermissionError("blocked by policy")

        with pytest.raises(ServerStartError, match="would not start: blocked by policy"):
            lr.start("scripted", config={}, spawn=refuse)

    def test_an_unknown_server_is_refused_before_anything_runs(self):
        with pytest.raises(KeyError):
            lr.start("rm-rf", config={}, spawn=lambda *a: pytest.fail("spawned"))


class TestWhenALaunchGoesWrong:
    def test_an_early_exit_reports_the_end_of_its_log(self, scripted, tmp_path):
        scripted([Probe()], _runnable())
        log = tmp_path / "scripted.log"
        log.write_text("loading\nTraceback (most recent call last):\nModuleNotFoundError: No module named 'exllamav3'\n")
        lr.start("scripted", config={}, spawn=lambda *a: _Proc(code=1), now=0.0)
        row = lr.describe("scripted", config={}, now=1.0)
        assert row["state"] == "stopped"
        assert "No module named 'exllamav3'" in row["failure"]
        assert row["log_path"].endswith("scripted.log")

    def test_an_early_exit_with_no_output_still_says_it_stopped(self, scripted):
        scripted([Probe()], _runnable())
        lr.start("scripted", config={}, spawn=lambda *a: _Proc(code=1), now=0.0)
        assert lr.describe("scripted", config={}, now=1.0)["failure"]

    def test_a_launch_still_running_is_starting_then_not_responding(self, scripted):
        """Not *starting* forever. A server silent for two minutes is reported as
        not answering, with its log, rather than as perpetually on its way."""
        scripted([Probe()], _runnable())
        lr.start("scripted", config={}, spawn=lambda *a: _Proc(), now=1000.0)
        assert lr.describe("scripted", config={}, now=1010.0)["state"] == "starting"
        late = 1000.0 + lr.STALLED_AFTER_SECONDS + 1
        assert lr.describe("scripted", config={}, now=late)["state"] == "stalled"

    def test_a_server_that_comes_up_leaves_its_failures_behind(self, scripted):
        scripted([Probe(), Probe(serving=True, models=("m",))], _runnable())
        lr.start("scripted", config={}, spawn=lambda *a: _Proc(code=1), now=0.0)
        row = lr.describe("scripted", config={}, now=1.0, probe=Probe(serving=True))
        assert row["state"] == "running" and row["failure"] == ""


# ------------------------------------------------------- the automatic start


class TestTheAutomaticStart:
    def test_it_starts_a_server_that_is_installed_wanted_and_down(self, scripted):
        scripted([Probe()], _runnable())
        calls = []
        lr.ensure_started("scripted", config={}, allowed=True, spawn=lambda *a: calls.append(1) or _Proc())
        assert calls == [1]

    def test_it_waits_for_the_server_to_answer_when_asked_to(self, scripted):
        """What lets Ollama be up *before* the backend's own discovery looks."""
        scripted([Probe(), Probe(), Probe(serving=True, models=("m",))], _runnable())
        row = lr.ensure_started(
            "scripted", wait_seconds=30, config={}, allowed=True, spawn=lambda *a: _Proc(), sleep=lambda s: None
        )
        assert row["state"] == "running"

    def test_it_stops_waiting_the_moment_the_launch_has_failed(self, scripted, tmp_path):
        scripted([Probe()], _runnable())
        (tmp_path / "scripted.log").write_text("boom\n")
        row = lr.ensure_started(
            "scripted", wait_seconds=30, config={}, allowed=True, spawn=lambda *a: _Proc(code=1), sleep=lambda s: None
        )
        assert row["failure"] == "boom"

    def test_it_does_not_return_until_the_deadline_when_it_never_comes_up(self, scripted):
        scripted([Probe()], _runnable())
        started = time.monotonic()
        row = lr.ensure_started(
            "scripted", wait_seconds=0.2, config={}, allowed=True, spawn=lambda *a: _Proc(), sleep=lambda s: time.sleep(0.05)
        )
        assert row["state"] == "starting"
        assert time.monotonic() - started < 5

    def test_it_does_nothing_when_the_server_is_already_up(self, scripted):
        scripted([Probe(serving=True)], _runnable())
        lr.ensure_started("scripted", config={}, allowed=True, spawn=lambda *a: pytest.fail("spawned"))

    def test_it_does_nothing_when_the_person_turned_it_off(self, scripted):
        spec = scripted([Probe()], _runnable())
        lr.ensure_started("scripted", config={"auto_start": False}, allowed=True, spawn=lambda *a: pytest.fail("spawned"))
        assert spec.probed == 0  # decided before any probe

    def test_it_does_nothing_when_not_installed(self, scripted):
        scripted([Probe()], None)
        lr.ensure_started("scripted", config={}, allowed=True, spawn=lambda *a: pytest.fail("spawned"))

    def test_it_does_nothing_over_another_server(self, scripted):
        scripted([Probe(other_server=True)], _runnable())
        lr.ensure_started("scripted", config={}, allowed=True, spawn=lambda *a: pytest.fail("spawned"))

    def test_it_never_raises_because_it_runs_on_the_way_to_the_first_screen(self, scripted):
        scripted([Probe()], _runnable())

        def explode(*_a):
            raise RuntimeError("anything at all")

        row = lr.ensure_started("scripted", config={}, allowed=True, spawn=explode)
        assert row["serving"] is False

    def test_it_does_not_start_under_test_and_does_not_even_probe(self, scripted):
        """**A test run must never launch an 11 GB model server on a developer's
        machine.** The backend suite boots the real application, so the guard is
        in the code and not in anyone's care. Decided before any probe as well:
        a closed port costs seconds on Windows and this is on the path to boot."""
        spec = scripted([Probe()], _runnable())
        assert lr.autostart_allowed() is False
        lr.ensure_started("scripted", config={}, spawn=lambda *a: pytest.fail("spawned"))
        assert spec.probed == 0

    def test_it_can_be_switched_off_for_everyone_by_the_environment(self, monkeypatch):
        monkeypatch.setenv("ZARAM_AUTOSTART", "0")
        assert lr.autostart_allowed() is False

    def test_the_start_button_still_works_when_the_automatic_start_is_off(self, scripted, monkeypatch):
        """Only *unprompted* starting is gated. Somebody pressing Start is asking."""
        monkeypatch.setenv("ZARAM_AUTOSTART", "0")
        scripted([Probe()], _runnable())
        calls = []
        lr.start("scripted", config={}, spawn=lambda *a: calls.append(1) or _Proc())
        assert calls == [1]


# -------------------------------------------------------- a real launch, for real


class TestTheLogsAreBounded:
    """*No new store ships without an answer to how long it keeps things.* Measured the
    day this was written: `ollama.log` reached 2.3 MB in about an hour and a half of use
    with nothing bounding it. These hold the answer."""

    def test_an_oversized_log_is_moved_aside_at_launch(self, tmp_path):
        log = tmp_path / "x.log"
        log.write_bytes(b"old line\n" * 100_000)  # ~900 KB
        proc = lr._spawn((sys.executable, "-c", "print('fresh start')"), None, str(log))
        proc.wait(timeout=20)
        assert (tmp_path / "x.log.1").read_bytes().startswith(b"old line")
        assert b"fresh start" in log.read_bytes()
        assert log.stat().st_size < 1_000

    def test_a_small_log_is_appended_to_not_rotated(self, tmp_path):
        log = tmp_path / "x.log"
        log.write_text("earlier start\n")
        lr._spawn((sys.executable, "-c", "print('later start')"), None, str(log)).wait(timeout=20)
        text = log.read_text()
        assert "earlier start" in text and "later start" in text
        assert not (tmp_path / "x.log.1").exists()

    def test_only_one_previous_log_is_kept(self, tmp_path):
        """A bounded folder, not an archive: each rotation replaces the last."""
        log = tmp_path / "x.log"
        for generation in (b"first", b"second", b"third"):
            log.write_bytes(generation + b"\n" * (lr.MAX_LOG_BYTES + 10))
            lr._rotate(str(log))
        assert (tmp_path / "x.log.1").read_bytes().startswith(b"third")
        assert sorted(p.name for p in tmp_path.iterdir()) == ["x.log.1"]

    def test_rotating_a_log_that_is_not_there_is_not_an_error(self, tmp_path):
        lr._rotate(str(tmp_path / "never-written.log"))  # must simply return

    def test_the_bound_is_stated_where_the_next_person_will_read_it(self):
        assert "512 KB" in lr.__doc__ and "weeks" in lr.__doc__


class TestARealLaunch:
    def test_the_spawn_goes_to_a_log_and_never_through_a_shell(self, tmp_path):
        """`&` in an argument is an argument. A shell would have run it."""
        log = tmp_path / "out.log"
        proc = lr._spawn((sys.executable, "-c", "print('a & b | c')"), str(tmp_path), str(log))
        proc.wait(timeout=20)
        text = log.read_text()
        assert "a & b | c" in text
        assert "Zaram started this at" in text

    def test_a_directory_with_a_space_in_it_is_just_a_directory(self, tmp_path):
        spaced = tmp_path / "my models folder"
        spaced.mkdir()
        log = tmp_path / "out.log"
        proc = lr._spawn((sys.executable, "-c", "import os; print(os.getcwd())"), str(spaced), str(log))
        proc.wait(timeout=20)
        assert "my models folder" in log.read_text()

    def test_a_fake_tabbyapi_is_found_started_and_recognised(self, tmp_path, monkeypatch):
        """**The whole path, once, for real**: detection of a checkout by its
        contents, a real process started in it, its output in a log, and the probe
        recognising what it serves as TabbyAPI -- the sequence a stopped Tabby goes
        through when Zaram opens, which no fixture can prove."""
        root = _checkout(tmp_path / "tabbyAPI")
        (root / "main.py").write_text(
            "import json, os\n"
            "from http.server import BaseHTTPRequestHandler, HTTPServer\n"
            "class H(BaseHTTPRequestHandler):\n"
            "    def do_GET(self):\n"
            "        body = json.dumps({'object':'list','data':[{'id':'Fake-7B','owned_by':'tabbyAPI'}]}).encode()\n"
            "        self.send_response(200)\n"
            "        self.send_header('Content-Length', str(len(body)))\n"
            "        self.end_headers()\n"
            "        self.wfile.write(body)\n"
            "    def log_message(self, *a): pass\n"
            "HTTPServer(('127.0.0.1', int(os.environ['FAKE_TABBY_PORT'])), H).serve_forever()\n"
        )
        port = _closed_port()
        monkeypatch.setenv("FAKE_TABBY_PORT", str(port))
        spec = _tabby_on(port)
        monkeypatch.setitem(lr.SERVERS, "tabbyapi", spec)
        config = {"path": str(root), "python": sys.executable}

        before = lr.describe("tabbyapi", config=config, timeout=1.0)
        assert before["state"] == "stopped" and before["can_start"]

        row = lr.ensure_started("tabbyapi", wait_seconds=30, config=config, allowed=True)

        assert row["state"] == "running", row
        assert row["models"] == ["Fake-7B"]
        assert (tmp_path / "tabbyapi.log").exists()


# ----------------------------------------------------------- rescan once it is up


class TestRescanningOnceItIsUp:
    @pytest.mark.asyncio
    async def test_it_rescans_when_the_server_answers(self):
        rescanned = []

        async def refresh():
            rescanned.append(1)

        ok = await lr.refresh_when_up(
            "x", refresh, interval=0.01, describe_fn=lambda rid: {"serving": True, "failure": "", "state": "running"}
        )
        assert ok and rescanned == [1]

    @pytest.mark.asyncio
    async def test_it_waits_through_starting(self):
        states = iter([{"serving": False, "failure": "", "state": "starting"}] * 3 + [{"serving": True, "failure": "", "state": "running"}])
        rescanned = []

        async def refresh():
            rescanned.append(1)

        ok = await lr.refresh_when_up("x", refresh, interval=0.01, describe_fn=lambda rid: next(states))
        assert ok and rescanned == [1]

    @pytest.mark.asyncio
    async def test_it_gives_up_at_once_when_the_launch_failed(self):
        """A server that failed to start does not become more started, so waiting
        out the timeout would only delay saying so."""
        started = time.monotonic()
        ok = await lr.refresh_when_up(
            "x", lambda: pytest.fail("rescanned"), timeout=60, interval=5,
            describe_fn=lambda rid: {"serving": False, "failure": "died", "state": "stopped"},
        )
        assert ok is False and time.monotonic() - started < 2

    @pytest.mark.asyncio
    async def test_it_gives_up_when_nothing_is_launching(self):
        ok = await lr.refresh_when_up(
            "x", lambda: pytest.fail("rescanned"), timeout=60, interval=5,
            describe_fn=lambda rid: {"serving": False, "failure": "", "state": "not_installed"},
        )
        assert ok is False

    @pytest.mark.asyncio
    async def test_it_gives_up_at_the_timeout(self):
        ok = await lr.refresh_when_up(
            "x", lambda: pytest.fail("rescanned"), timeout=0.1, interval=0.02,
            describe_fn=lambda rid: {"serving": False, "failure": "", "state": "starting"},
        )
        assert ok is False


# ------------------------------------------------------------ the settings store


class TestTheSettings:
    @pytest.fixture()
    def store(self, tmp_path, monkeypatch):
        import core.user_settings as module

        monkeypatch.setattr(module, "_SETTINGS", None, raising=False)
        return module.UserSettings(str(tmp_path / "settings.json"))

    def test_a_server_nobody_configured_has_no_settings(self, store):
        assert store.model_server("tabbyapi") == {}

    def test_a_choice_is_kept_and_survives_a_restart(self, tmp_path, monkeypatch):
        import core.user_settings as module

        monkeypatch.setattr(module, "_SETTINGS", None, raising=False)
        path = str(tmp_path / "s.json")
        module.UserSettings(path).set_model_server("tabbyapi", auto_start=False, path="/opt/tabby")
        again = module.UserSettings(path).model_server("tabbyapi")
        assert again == {"auto_start": False, "path": "/opt/tabby"}

    def test_an_empty_string_clears_a_field(self, store):
        store.set_model_server("tabbyapi", path="/p", python="/py")
        store.set_model_server("tabbyapi", path="")
        assert store.model_server("tabbyapi") == {"python": "/py"}

    def test_none_leaves_a_field_alone(self, store):
        store.set_model_server("tabbyapi", path="/p")
        store.set_model_server("tabbyapi", auto_start=True)
        assert store.model_server("tabbyapi") == {"path": "/p", "auto_start": True}

    def test_clearing_everything_removes_the_entry(self, store):
        store.set_model_server("tabbyapi", path="/p")
        store.set_model_server("tabbyapi", path="")
        assert "tabbyapi" not in store.to_dict()["model_servers"]

    def test_a_hostile_file_cannot_smuggle_in_a_field(self, tmp_path, monkeypatch):
        """These values are later *executed*, so the set of things that can reach
        that path is closed: a field outside it, a path that is not a string, a
        flag that is not a boolean -- all dropped, none coerced."""
        import core.user_settings as module

        path = tmp_path / "s.json"
        path.write_text(json.dumps({"model_servers": {
            "tabbyapi": {"auto_start": "yes", "path": 7, "python": "/py", "argv": ["calc.exe"], "env": {"A": "b"}},
            "": {"path": "/x"},
            "x" * 80: {"path": "/x"},
            "ollama": "not a dict",
        }}), encoding="utf-8")
        monkeypatch.setattr(module, "_SETTINGS", None, raising=False)
        kept = module.UserSettings(str(path)).to_dict()["model_servers"]
        assert kept == {"tabbyapi": {"python": "/py"}}

    def test_a_path_is_bounded(self, store):
        store.set_model_server("tabbyapi", path="p" * 5000)
        assert len(store.model_server("tabbyapi")["path"]) == 500

    def test_the_number_of_servers_is_bounded(self, store):
        for i in range(40):
            store.set_model_server(f"s{i}", auto_start=False)
        assert len(store.to_dict()["model_servers"]) == 16


# ------------------------------------------------------------------- the routes


class TestTheRoutes:
    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        import main

        return TestClient(main.app)

    def test_the_status_lists_every_server_with_what_settings_draws(self, client):
        rows = client.get("/providers/model-servers").json()
        assert {r["id"] for r in rows} >= {"ollama", "tabbyapi"}
        for row in rows:
            assert {"state", "installed", "serving", "model_count", "models", "can_start",
                    "auto_start", "zaram_sees", "failure", "problem", "port"} <= set(row)

    def test_looking_starts_nothing(self, client, monkeypatch):
        """Opening Settings must not launch a stranger's process -- or anyone's."""
        monkeypatch.setattr(lr, "_spawn", lambda *a: pytest.fail("a status check started a server"))
        assert client.get("/providers/model-servers").status_code == 200

    def test_an_unknown_server_is_a_404_not_a_command(self, client):
        assert client.post("/providers/model-servers/calc/start").status_code == 404
        assert client.put("/providers/model-servers/calc", json={"auto_start": False}).status_code == 404

    def test_a_server_that_cannot_be_started_is_a_409_with_the_reason(self, client, monkeypatch):
        def refuse(rid, **kw):
            raise ServerStartError("TabbyAPI is not installed where Zaram looks.")

        monkeypatch.setattr(lr, "start", refuse)
        reply = client.post("/providers/model-servers/tabbyapi/start")
        assert reply.status_code == 409
        assert "not installed" in reply.json()["detail"]

    def test_a_wrong_location_is_refused_where_it_is_given(self, client, tmp_path):
        reply = client.put("/providers/model-servers/tabbyapi", json={"path": str(tmp_path)})
        assert reply.status_code == 400
        assert "TabbyAPI checkout" in reply.json()["detail"]

    def test_auto_start_can_be_turned_off_and_back_on(self, client):
        try:
            off = client.put("/providers/model-servers/tabbyapi", json={"auto_start": False}).json()
            assert off["auto_start"] is False
            on = client.put("/providers/model-servers/tabbyapi", json={"auto_start": True}).json()
            assert on["auto_start"] is True
        finally:
            client.put("/providers/model-servers/tabbyapi", json={"auto_start": True})

    def test_starting_rescans_once_the_server_is_up(self, client, monkeypatch):
        """Without this a started server runs and **does not appear**, which is
        exactly how a started Tabby showed no Qwen."""
        import providers.api as api

        row = {"id": "tabbyapi", "port": 1234, "serving": False, "state": "starting"}
        monkeypatch.setattr(lr, "start", lambda rid, **kw: dict(row))
        seen = []

        async def fake_refresh_when_up(rid, refresh, **kw):
            seen.append(rid)

        monkeypatch.setattr(lr, "refresh_when_up", fake_refresh_when_up)

        class Manager:
            async def refresh(self):  # pragma: no cover - handed over, not called here
                pass

            def list_models(self):
                return []

        monkeypatch.setattr(api, "_PROVIDERS_RUNTIME", type("R", (), {"manager": Manager()})())
        reply = client.post("/providers/model-servers/tabbyapi/start")
        assert reply.status_code == 200
        assert seen == ["tabbyapi"]

    def test_a_server_already_up_is_not_rescanned_for(self, client, monkeypatch):
        import providers.api as api

        monkeypatch.setattr(lr, "start", lambda rid, **kw: {"id": rid, "port": 1234, "serving": True, "state": "running"})
        monkeypatch.setattr(lr, "refresh_when_up", lambda *a, **k: pytest.fail("rescanned a running server"))
        monkeypatch.setattr(api, "_PROVIDERS_RUNTIME", type("R", (), {"manager": object()})())
        assert client.post("/providers/model-servers/tabbyapi/start").status_code == 200


class TestWhatZaramItselfHolds:
    def _runtime(self, monkeypatch, models):
        import providers.api as api

        class Manager:
            def list_models(self):
                return models

        monkeypatch.setattr(api, "_PROVIDERS_RUNTIME", type("R", (), {"manager": Manager()})())
        return api

    def _model(self, endpoint, available=True):
        return type("M", (), {"endpoint": endpoint, "available": available})()

    def test_models_are_counted_by_the_port_they_came_from(self, monkeypatch):
        api = self._runtime(monkeypatch, [
            self._model("http://127.0.0.1:1234"),
            self._model("http://127.0.0.1:1234/v1"),
            self._model("http://127.0.0.1:11434"),
        ])
        assert api._models_zaram_sees(1234) == 2
        assert api._models_zaram_sees(11434) == 1

    def test_a_model_that_is_not_available_is_not_counted(self, monkeypatch):
        api = self._runtime(monkeypatch, [self._model("http://127.0.0.1:1234", available=False)])
        assert api._models_zaram_sees(1234) == 0

    def test_a_server_up_and_unseen_reads_as_zero_not_as_unknown(self, monkeypatch):
        """The gap this field exists to show: the server lists a model, Zaram holds
        none from it. Zero is that finding; `None` would hide it."""
        api = self._runtime(monkeypatch, [])
        assert api._models_zaram_sees(1234) == 0

    def test_no_catalogue_is_unknown_not_zero(self, monkeypatch):
        import providers.api as api

        monkeypatch.setattr(api, "_PROVIDERS_RUNTIME", None)
        assert api._models_zaram_sees(1234) is None

    def test_a_catalogue_that_raises_is_unknown_not_a_failed_status(self, monkeypatch):
        import providers.api as api

        class Broken:
            def list_models(self):
                raise RuntimeError("scan in progress")

        monkeypatch.setattr(api, "_PROVIDERS_RUNTIME", type("R", (), {"manager": Broken()})())
        assert api._models_zaram_sees(1234) is None


# ------------------------------------------------------------------------ boot


def _code_of(function) -> str:
    """A function's code as the interpreter sees it: no docstring, no comments.

    `ast.unparse` drops comments by construction, and the docstring is removed
    explicitly -- so a docstring that explains *why* it names no server can say
    the name, and a branch that actually keys on it cannot hide.
    """
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    node = tree.body[0]
    if node.body and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant):
        node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


class _Manager:
    """Enough of the provider manager for the boot helper to hold `refresh`."""

    async def refresh(self):  # pragma: no cover - handed over, never awaited here
        pass


class TestBoot:
    def test_ollama_is_brought_up_before_the_kernel_boots(self):
        """Where the wait is: with Ollama stopped, `kernel.boot()` probes a closed
        port again and again, and boot was measured taking minutes. The order is
        the fix, so the order is what is asserted."""
        import inspect

        import main

        source = inspect.getsource(main.startup_event)
        started = source.index('model_servers.ensure_started, "ollama"')
        booted = source.index("await kernel.boot()")
        assert started < booted

    def test_every_server_is_brought_up_not_one_by_name(self):
        """`CLAUDE.md`: *build for the set, never for one.* Adding a server to the
        table is the whole change, so the loop must be over the table."""
        import main

        code = _code_of(main._bring_up_model_servers)
        assert "model_servers.SERVERS" in code
        assert "tabby" not in code.lower()

    @pytest.mark.asyncio
    async def test_a_server_that_was_started_is_rescanned_for_and_one_already_up_is_not(self, monkeypatch):
        import asyncio

        import main

        rescanned = []

        async def fake_wait(rid, refresh, **kw):
            rescanned.append(rid)

        statuses = {"coming": {"state": "starting"}, "already": {"state": "running"}, "off": {"state": "off"}}
        monkeypatch.setattr(lr, "SERVERS", {k: None for k in statuses})
        monkeypatch.setattr(lr, "ensure_started", lambda rid, **kw: statuses[rid])
        monkeypatch.setattr(lr, "refresh_when_up", fake_wait)

        main._bring_up_model_servers(type("R", (), {"manager": _Manager()})())
        await asyncio.gather(*list(main._model_server_tasks))
        assert rescanned == ["coming"]

    @pytest.mark.asyncio
    async def test_a_failure_while_bringing_one_up_does_not_stop_the_rest(self, monkeypatch):
        import asyncio

        import main

        rescanned = []

        def ensure(rid, **kw):
            if rid == "broken":
                raise RuntimeError("boom")
            return {"state": "starting"}

        async def fake_wait(rid, refresh, **kw):
            rescanned.append(rid)

        monkeypatch.setattr(lr, "SERVERS", {"broken": None, "fine": None})
        monkeypatch.setattr(lr, "ensure_started", ensure)
        monkeypatch.setattr(lr, "refresh_when_up", fake_wait)

        main._bring_up_model_servers(type("R", (), {"manager": _Manager()})())
        await asyncio.gather(*list(main._model_server_tasks))
        assert rescanned == ["fine"]


# ---------------------------------------------------------- model neutrality


class TestNoModelIsNamedInAnyDecision:
    #: Model families and weight formats -- never the *servers* ("Ollama" contains
    #: "llama", and a scan that flagged it would be flagging the product's own
    #: subject). A word boundary, so `ollama` is not a hit and `llama3` is.
    NAMES = re.compile(r"qwen|gemma|mistral|deepseek|nemotron|phi-?\d|\bllama\b|llama-?\d|exl[23]|gguf")

    def test_no_string_in_the_code_names_a_model(self):
        """`CLAUDE.md`: *build for the set of models, never for one.* Asserted on the
        code's string constants rather than on its prose, so a docstring explaining
        why is free to give the example and a branch keyed to a name is not."""
        source = Path(lr.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                body = getattr(node, "body", [])
                if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
                    docstrings.add(id(body[0].value))
        offending = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and self.NAMES.search(node.value.lower())
        ]
        assert offending == []

    def test_a_third_server_is_one_table_entry(self, monkeypatch):
        """The extension point, exercised: a new runtime needs a class and a row,
        and the status, the start and the boot loop all pick it up unchanged."""

        class Third(lr._Server):
            id = "third"
            label = "Third"
            port = 5

            def probe(self, timeout):
                return Probe(serving=True, models=("z",))

            def find_install(self, config):
                return None

        monkeypatch.setitem(lr.SERVERS, "third", Third())
        assert "third" in {row["id"] for row in lr.describe_all(config={})}


# ------------------------------------------------- reached by address, not by name


class TestReachedByAddressNotByName:
    """**Found 4 October 2026 while testing the launcher, and it was costing every
    Windows user two seconds per embedding.** The memory embedder reached Ollama as
    `localhost`. On Windows that resolves to IPv6 first; Ollama listens on IPv4
    only; the refused IPv6 attempt takes about two seconds before the fallback to
    127.0.0.1 succeeds. Measured against the live server: **2,105 ms per embedding
    through `localhost`, 73 ms through `127.0.0.1`** -- 139 seconds against 4.8 for
    the 66 exemplars the router embeds at boot, which was the multi-minute boot
    stall, and two extra seconds on every chat turn that recalls from memory.

    Nothing about the server was wrong, which is why it hid: each request took
    ~60 ms *on the server*. The cost was entirely the client connecting, and no
    log on either side said so."""

    def test_the_embedder_is_pointed_at_the_address(self):
        from runtimes.memory.embeddings import DEFAULT_OLLAMA_URL

        assert "127.0.0.1" in DEFAULT_OLLAMA_URL
        assert "localhost" not in DEFAULT_OLLAMA_URL

    def test_the_other_local_defaults_are_too(self):
        import inspect

        from implementations.ollama_llm import OllamaLLM
        from knowledge.backends.model_registry import ModelRegistry

        for cls in (OllamaLLM, ModelRegistry):
            default = inspect.signature(cls.__init__).parameters["base_url"].default
            assert "127.0.0.1" in default and "localhost" not in default, cls

    def test_the_default_connects_at_once_to_a_server_listening_on_ipv4_only(self):
        """The behaviour, not the spelling. A server on 127.0.0.1 alone -- which is
        what Ollama binds -- must be reachable through the default without waiting
        out an IPv6 attempt. Fast on every platform with the address; on Windows
        with the *name* this took two seconds a call, so this is the guard that
        would have failed."""
        from urllib.request import urlopen

        from runtimes.memory.embeddings import DEFAULT_OLLAMA_URL

        with _serving({"/api/tags": (200, {"models": []})}) as port:
            host = DEFAULT_OLLAMA_URL.rsplit(":", 1)[0]
            url = f"{host}:{port}/api/tags"
            urlopen(url, timeout=5).read()  # warm: first connection, any lazy setup
            started = time.perf_counter()
            for _ in range(3):
                urlopen(url, timeout=5).read()
            per_call = (time.perf_counter() - started) / 3
        assert per_call < 0.5, f"{per_call * 1000:.0f} ms per call to a local server"
