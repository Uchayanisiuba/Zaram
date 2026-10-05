"""The terminal Zaram drives is one its owner can watch and type in.

`packs/code/terminal.py` promised it in its first paragraphs -- *the person sees
every command and can type their own* -- and for a day it was untrue: three
tools, a session per project, and no route, so a shell Zaram could use was a
shell its owner could not see. These are the three routes and the properties the
promise needs.

* **The panel shows the sessions Zaram uses**, not a second shell.
* **Both authors are kept and labelled** -- a terminal that does not say who
  typed what cannot be audited.
* **The grant still governs.** Off for the project means off for the panel too.
* **Shells are closed at shutdown**, or they outlive the backend.
"""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

from packs.code.terminal import TerminalTools


@pytest.fixture
def app_with_project(tmp_path, monkeypatch):
    import main
    from projects import ProjectRecords, ProjectType

    records = ProjectRecords(str(tmp_path / "projects.db"))
    monkeypatch.setattr(main, "project_records", records)

    tools = TerminalTools(push_check=lambda command, root: None)
    monkeypatch.setattr(main.kernel, "terminal_tools", tools, raising=False)

    folder = tmp_path / "work"
    folder.mkdir()
    project = records.create("Keyline", type=ProjectType.CODING)
    records.set_root(project.id, str(folder))
    yield TestClient(main.app), records, project, tools, folder
    tools.close_all()


def test_a_project_without_the_grant_has_no_terminal(app_with_project):
    http, _records, project, _tools, _folder = app_with_project
    response = http.get(f"/projects/{project.id}/terminal")
    assert response.status_code == 403
    assert "off for this project" in response.json()["detail"]


def test_a_project_without_a_folder_says_so(tmp_path, monkeypatch):
    import main
    from projects import ProjectRecords, ProjectType

    records = ProjectRecords(str(tmp_path / "p.db"))
    monkeypatch.setattr(main, "project_records", records)
    monkeypatch.setattr(main.kernel, "terminal_tools", TerminalTools(), raising=False)
    project = records.create("Empty", type=ProjectType.CODING)
    response = TestClient(main.app).get(f"/projects/{project.id}/terminal")
    assert response.status_code == 409
    assert "no folder" in response.json()["detail"]


def test_an_unknown_project_is_a_404(app_with_project):
    http, *_ = app_with_project
    assert http.get("/projects/nope/terminal").status_code == 404


def test_nothing_is_shown_before_anything_is_run(app_with_project):
    http, records, project, _tools, _folder = app_with_project
    records.set_shell(project.id, True)
    body = http.get(f"/projects/{project.id}/terminal").json()
    assert body["lines"] == []
    assert body["alive"] is False


@pytest.mark.skipif(sys.platform != "win32" and not os.environ.get("SHELL"), reason="needs a shell")
def test_the_persons_command_runs_and_is_labelled_theirs(app_with_project):
    http, records, project, _tools, _folder = app_with_project
    records.set_shell(project.id, True)

    response = http.post(f"/projects/{project.id}/terminal", json={"command": "echo hello-from-the-panel"})

    assert response.status_code == 200
    lines = response.json()["lines"]
    typed = [line for line in lines if line["kind"] == "command"]
    assert typed and typed[0]["who"] == "user"
    assert any("hello-from-the-panel" in line["text"] for line in lines if line["kind"] == "output")


@pytest.mark.skipif(sys.platform != "win32" and not os.environ.get("SHELL"), reason="needs a shell")
def test_the_panel_shows_what_zaram_ran_in_the_same_shell(app_with_project):
    """One session, two authors. If these were two instances the panel would
    show neither's output."""
    http, records, project, tools, folder = app_with_project
    records.set_shell(project.id, True)

    tools.call("run_in_terminal", {"command": "echo ran-by-zaram"}, folder)
    http.post(f"/projects/{project.id}/terminal", json={"command": "echo typed-by-me"})

    lines = http.get(f"/projects/{project.id}/terminal").json()["lines"]
    who = {line["text"]: line["who"] for line in lines if line["kind"] == "command"}
    assert who["echo ran-by-zaram"] == "zaram"
    assert who["echo typed-by-me"] == "user"


def test_an_empty_command_is_refused(app_with_project):
    http, records, project, *_ = app_with_project
    records.set_shell(project.id, True)
    assert http.post(f"/projects/{project.id}/terminal", json={"command": "   "}).status_code == 400


def test_a_pasted_novel_is_refused(app_with_project):
    http, records, project, *_ = app_with_project
    records.set_shell(project.id, True)
    response = http.post(f"/projects/{project.id}/terminal", json={"command": "x" * 9000})
    assert response.status_code == 413


def test_stopping_closes_the_shell(app_with_project):
    http, records, project, tools, folder = app_with_project
    records.set_shell(project.id, True)
    http.post(f"/projects/{project.id}/terminal", json={"command": "echo hi"})
    assert tools._sessions

    assert http.delete(f"/projects/{project.id}/terminal").json() == {"stopped": True}
    assert tools._sessions == {}
    assert http.delete(f"/projects/{project.id}/terminal").json() == {"stopped": False}


def test_the_grant_withdrawn_closes_the_door_again(app_with_project):
    http, records, project, *_ = app_with_project
    records.set_shell(project.id, True)
    assert http.get(f"/projects/{project.id}/terminal").status_code == 200
    records.set_shell(project.id, False)
    assert http.get(f"/projects/{project.id}/terminal").status_code == 403


def test_the_kernel_holds_the_terminal_and_shutdown_closes_it():
    """Reachability: the instance the routes read is the one the tool set uses,
    and it is closed with the backend."""
    import inspect

    import main
    from core import bootstrapper

    boot = inspect.getsource(bootstrapper)
    assert "self.terminal_tools = TerminalTools()" in boot
    assert "shell=self.terminal_tools" in boot
    assert "terminal.close_all()" in inspect.getsource(main.shutdown_event)
