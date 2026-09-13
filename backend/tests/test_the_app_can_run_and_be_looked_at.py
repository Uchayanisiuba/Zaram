"""Running the app and looking at it — slice 8 of the code pack.

**A dev server is a managed process**, not a `run_command` with a timeout:
started, its URL read off its output, its log kept, stopped by the model or by
the person, and ended with Zaram. One per project.

**Looking at it is local twice over.** The screenshot is taken with the
browser the person already has, of a loopback URL only, and read by a local
vision model when one exists — never a cloud one, and never silently skipped
when none does.
"""

from __future__ import annotations

import http.server
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from packs.code import AppTools, CodeTools
from packs.code.apps import (
    APP_STATUS,
    LOOK_AT_APP,
    READ_APP_LOG,
    START_APP,
    STOP_APP,
    app_runners,
    find_browser,
    screens_dir_for,
)


@pytest.fixture
def node_app(tmp_path):
    """A `package.json` whose `dev` script is a tiny Python server that prints
    a localhost URL and serves a page — no npm needed, since `start_app`
    resolves npm and the test resolves the script itself."""
    (tmp_path / "package.json").write_text(
        '{"scripts": {"dev": "python -m http.server", "test": "pytest"}}', encoding="utf-8"
    )
    (tmp_path / "index.html").write_text(
        "<html><body style='background:#123456'><h1 style='color:white'>Hello from the app</h1></body></html>",
        encoding="utf-8",
    )
    return tmp_path


def _fake_dev_server_argv(port: int) -> tuple:
    """A process that behaves like a dev server: prints its URL, serves, stays up."""
    script = (
        "import http.server, socketserver, sys, os\n"
        f"port = {port}\n"
        "print(f'  Local:   http://localhost:{port}/', flush=True)\n"
        "os.chdir(sys.argv[1])\n"
        "with socketserver.TCPServer(('127.0.0.1', port), http.server.SimpleHTTPRequestHandler) as s:\n"
        "    s.serve_forever()\n"
    )
    return (sys.executable, "-c", script)


class TestDetection:
    def test_long_running_scripts_are_app_runners_not_command_runners(self, node_app, monkeypatch):
        from packs.code import apps as module

        monkeypatch.setattr(module, "_npm", lambda: "npm")
        names = {r.name for r in app_runners(node_app)}
        assert names == {"npm:dev"}

        from packs.code.runners import detect

        assert "npm:dev" not in {r.name for r in detect(node_app)}


class TestTheManagedProcess:
    @pytest.fixture
    def tools(self, node_app, monkeypatch, tmp_path_factory):
        from packs.code import apps as module

        port = 8765 + (hash(str(node_app)) % 1000)
        monkeypatch.setattr(module, "_npm", lambda: "npm")
        monkeypatch.setattr(
            module, "app_runners",
            lambda root: [module.Runner(name="npm:dev", argv=(*_fake_dev_server_argv(port), str(root)), description="dev")],
        )
        app = AppTools(screens_dir=tmp_path_factory.mktemp("screens"))
        yield CodeTools(lambda: node_app, app=app, runs_granted=lambda: True), app, port
        app.stop_all()

    def test_start_reports_the_url_and_stop_ends_it(self, tools):
        code, app, port = tools

        started = code.call_tool(START_APP, {"runner": "npm:dev"})
        assert started.get("running") is True, started
        assert started["url"] == f"http://localhost:{port}/"

        status = code.call_tool(APP_STATUS, {})
        assert status["running"] is True and status["url"].endswith(f":{port}/")

        log = code.call_tool(READ_APP_LOG, {"lines": 5})
        assert any("Local:" in line for line in log["lines"])

        again = code.call_tool(START_APP, {"runner": "npm:dev"})
        assert "already running" in again["error"]

        stopped = code.call_tool(STOP_APP, {})
        assert stopped["stopped"] is True
        time.sleep(0.5)
        assert code.call_tool(APP_STATUS, {})["running"] is False

    def test_an_app_that_exits_at_once_says_so_with_its_output(self, node_app, tmp_path_factory, monkeypatch):
        from packs.code import apps as module

        monkeypatch.setattr(
            module, "app_runners",
            lambda root: [module.Runner(name="npm:dev", argv=(sys.executable, "-c", "print('boom: port in use'); raise SystemExit(1)"), description="dev")],
        )
        app = AppTools(screens_dir=tmp_path_factory.mktemp("screens"))
        code = CodeTools(lambda: node_app, app=app, runs_granted=lambda: True)
        started = code.call_tool(START_APP, {"runner": "npm:dev"})
        assert "exited straight away" in started["error"]
        assert "boom" in started["log"]

    def test_an_unknown_runner_names_the_available_ones(self, tools):
        code, _, _ = tools
        assert "npm:dev" in code.call_tool(START_APP, {"runner": "nope"})["error"]

    def test_stop_with_nothing_running_is_not_an_error(self, tools):
        code, _, _ = tools
        assert code.call_tool(STOP_APP, {})["stopped"] is False


class TestTheLook:
    def test_only_loopback_urls(self, node_app, tmp_path_factory):
        app = AppTools(screens_dir=tmp_path_factory.mktemp("screens"), browser="C:/nope/chrome.exe")
        code = CodeTools(lambda: node_app, app=app, runs_granted=lambda: True)
        result = code.call_tool(LOOK_AT_APP, {"url": "https://example.com"})
        assert "not on this machine" in result["error"]

    def test_no_url_and_nothing_running_says_so(self, node_app, tmp_path_factory):
        app = AppTools(screens_dir=tmp_path_factory.mktemp("screens"), browser="C:/nope/chrome.exe")
        code = CodeTools(lambda: node_app, app=app, runs_granted=lambda: True)
        assert "start the app first" in code.call_tool(LOOK_AT_APP, {})["error"]

    def test_a_screenshot_is_taken_and_read_by_the_injected_reader(self, node_app, tmp_path_factory):
        seen = {}

        def browser_run(argv, **kwargs):
            out = next(a for a in argv if a.startswith("--screenshot=")).split("=", 1)[1]
            Path(out).write_bytes(b"\x89PNG fake")
            seen["url"] = argv[-1]
            return subprocess.CompletedProcess(argv, 0, "", "")

        def reader(path, question):
            seen["read"] = (Path(path).name, question)
            return "A blue page with a white heading that says Hello from the app."

        screens = tmp_path_factory.mktemp("screens")
        app = AppTools(screens_dir=screens, browser="C:/fake/chrome.exe", run=browser_run, describe_image=reader)
        code = CodeTools(lambda: node_app, app=app, runs_granted=lambda: True)

        result = code.call_tool(LOOK_AT_APP, {"url": "http://localhost:5173/", "question": "is the heading visible?"})

        assert seen["url"] == "http://localhost:5173/"
        assert result["description"].startswith("A blue page")
        assert seen["read"][1] == "is the heading visible?"
        assert Path(result["image"]).is_file()
        assert Path(result["image"]).parent == screens_dir_for(node_app, screens)

    def test_without_a_local_vision_model_the_picture_is_kept_and_the_fix_is_named(self, node_app, tmp_path_factory):
        def browser_run(argv, **kwargs):
            out = next(a for a in argv if a.startswith("--screenshot=")).split("=", 1)[1]
            Path(out).write_bytes(b"\x89PNG fake")
            return subprocess.CompletedProcess(argv, 0, "", "")

        app = AppTools(screens_dir=tmp_path_factory.mktemp("screens"), browser="C:/fake/chrome.exe", run=browser_run)
        code = CodeTools(lambda: node_app, app=app, runs_granted=lambda: True)
        result = code.call_tool(LOOK_AT_APP, {"url": "http://127.0.0.1:3000"})
        assert result["description"] is None
        # The fix, with its size, and both local routes — never a model
        # filename, which `test_no_second_entrance_to_inference.py` forbids in
        # a sentence shown to a person. This used to demand `ollama pull
        # <model>` and contradicted that rule; the two were reconciled on 13
        # September when the Tabby route turned out to be the one that worked.
        note = result["note"]
        assert "Ollama" in note and "TabbyAPI" in note and "GB" in note
        assert "never leaves the machine" in note
        assert Path(result["image"]).is_file()

    def test_the_grant_covers_it_and_status_needs_none(self, node_app, tmp_path_factory):
        from runtimes.mcp.policy import looks_read_only

        app = AppTools(screens_dir=tmp_path_factory.mktemp("screens"))
        granted = CodeTools(lambda: node_app, app=app, runs_granted=lambda: True).granted_tools()
        assert {START_APP, STOP_APP, LOOK_AT_APP} <= granted
        assert {START_APP, STOP_APP, LOOK_AT_APP} & CodeTools(lambda: node_app, app=app).granted_tools() == set()
        assert looks_read_only(APP_STATUS) and looks_read_only(READ_APP_LOG)

    def test_a_real_screenshot_with_the_browser_on_this_machine(self, node_app, tmp_path_factory):
        """No spy. A real page on a real port, the real Chrome or Edge."""
        browser = find_browser()
        if browser is None:
            pytest.skip("no Chrome or Edge on this machine")

        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):  # noqa: D401
                pass

            def __init__(self, *a, **k):
                super().__init__(*a, directory=str(node_app), **k)

        with socketserver.TCPServer(("127.0.0.1", 0), Quiet) as server:
            port = server.server_address[1]
            threading.Thread(target=server.serve_forever, daemon=True).start()
            app = AppTools(screens_dir=tmp_path_factory.mktemp("screens"))
            code = CodeTools(lambda: node_app, app=app, runs_granted=lambda: True)
            try:
                result = code.call_tool(LOOK_AT_APP, {"url": f"http://127.0.0.1:{port}/"})
            finally:
                server.shutdown()

        assert "error" not in result, result
        image = Path(result["image"])
        assert image.is_file() and image.stat().st_size > 1000
        assert image.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
