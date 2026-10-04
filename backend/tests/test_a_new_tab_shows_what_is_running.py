"""The browser pane's new tab lists what *Zaram* has running.

Asked for 3 October 2026 with a screenshot of Claude's new-tab page, and
narrowed the next day: *"make it such that it only shows the ones launched
or opened by Zaram."*

**The narrowing deleted the first implementation, and this file records
why.** The first version read the machine's process table and classified
what it found. It worked. Measured on the maintainer's machine, it found
46 listeners and 44 of them were Discord, OneDrive, Epic Games, svchost
and adb — so it was answering a broader question than anybody had asked,
and collapsing the noise behind a disclosure made it tidy rather than
right. A panel that enumerates somebody's installed software is also a
privacy smell nobody requested, and it lands in every screenshot.

What replaced it is narrower and holds more: Zaram's own registry of apps
it started. There is no heuristic left to be wrong about — no cwd
matching, no process-name guessing, no port cutoff — and `psutil` is off
this path entirely.

Driven through an injected registry. Reading the real one would assert
whatever happens to be running on the machine the suite runs on, which is
a description of a laptop rather than a test.
"""

from __future__ import annotations

import os
import time

import pytest

from core.local_servers import KnownProject, LocalServer, running_servers

BACKEND = "http://127.0.0.1:8420"


def app(
    root=r"C:\RideShare",
    url="http://127.0.0.1:5173",
    runner="npm run dev",
    pid=42,
    started_at=None,
):
    return {
        "root": root,
        "url": url,
        "runner": runner,
        "pid": pid,
        "started_at": started_at if started_at is not None else time.time(),
    }


def servers(entries, **kwargs):
    return running_servers(launched=lambda: list(entries), **kwargs)


class TestOnlyWhatZaramStarted:
    def test_an_app_zaram_launched_is_listed(self):
        found = servers([app()])
        assert [s.url for s in found] == ["http://127.0.0.1:5173"]
        assert found[0].origin == "project"

    def test_zarams_own_backend_is_listed(self):
        """The desktop host spawns it, so it is one of Zaram's."""
        found = servers([], backend_url=BACKEND)
        assert [s.name for s in found] == ["Zaram — backend"]
        assert found[0].origin == "zaram"

    def test_the_backend_comes_first(self):
        found = servers([app()], backend_url=BACKEND)
        assert [s.origin for s in found] == ["zaram", "project"]

    def test_nothing_else_on_the_machine_appears(self):
        """The whole point of the narrowing. Discord is running; it is not
        Zaram's business, and the panel is not a port scan."""
        found = servers([app()], backend_url=BACKEND)
        assert len(found) == 2

    def test_newest_first(self):
        now = time.time()
        found = servers(
            [
                app(url="http://127.0.0.1:3000", started_at=now - 600),
                app(url="http://127.0.0.1:5173", started_at=now),
            ]
        )
        assert [s.port for s in found] == [5173, 3000]

    def test_nothing_running_is_an_empty_list(self):
        assert servers([]) == []


class TestItStaysOnThisMachine:
    """Every entry is a loopback URL Zaram itself recorded. A routable
    address in this panel is one click from an egress."""

    def test_a_routable_dev_server_is_not_offered(self):
        assert servers([app(url="http://192.168.1.40:5173")]) == []

    def test_a_backend_somewhere_else_is_not_offered(self):
        assert servers([], backend_url="https://api.example.com") == []

    def test_a_localhost_subdomain_is_fine(self):
        """RFC 6761 reserves `*.localhost`, and dev servers use it for
        subdomain routing."""
        found = servers([app(url="http://app.localhost:5173")])
        assert len(found) == 1

    def test_nonsense_in_the_registry_is_skipped_not_raised(self):
        found = servers([{"root": "", "url": "", "pid": 0}, app()])
        assert len(found) == 1


class TestWhatTheRowSays:
    def test_a_project_is_named_rather_than_its_folder(self):
        found = servers(
            [app(root=r"C:\RideShare")],
            projects=[KnownProject("ride-share", "Ride Share", r"C:\RideShare")],
        )
        assert found[0].name == "Ride Share"
        assert found[0].project_id == "ride-share"

    def test_an_unknown_folder_falls_back_to_its_name(self):
        """Honest rather than blank. An empty row reads as a bug."""
        found = servers([app(root=r"C:\Scratch\thing")])
        assert found[0].name == "thing"

    def test_a_subfolder_still_belongs_to_the_project(self, tmp_path):
        root = str(tmp_path / "ride-share")
        inner = os.path.join(root, "apps", "web")
        os.makedirs(inner)
        found = servers(
            [app(root=inner)],
            projects=[KnownProject("ride-share", "Ride Share", root)],
        )
        assert found[0].name == "Ride Share"

    def test_a_sibling_with_a_shared_prefix_is_a_different_project(self, tmp_path):
        """`startswith` calls `ride-share-old` a child of `ride-share`."""
        root = str(tmp_path / "ride-share")
        other = str(tmp_path / "ride-share-old")
        os.makedirs(root)
        os.makedirs(other)
        found = servers(
            [app(root=other)],
            projects=[KnownProject("ride-share", "Ride Share", root)],
        )
        assert found[0].project_id == ""

    def test_the_most_specific_project_claims_it(self, tmp_path):
        """Projects nest. First-match would depend on listing order."""
        outer = str(tmp_path / "mono")
        inner = os.path.join(outer, "services", "api")
        os.makedirs(inner)
        found = servers(
            [app(root=inner)],
            projects=[
                KnownProject("mono", "Monorepo", outer),
                KnownProject("api", "The API", inner),
            ],
        )
        assert found[0].name == "The API"

    def test_the_runner_travels_with_it(self):
        found = servers([app(runner="vite")])
        assert found[0].runner == "vite"

    def test_the_port_is_read_off_the_url_not_stored_twice(self):
        row = LocalServer(url="http://127.0.0.1:4321", name="x", origin="project")
        assert row.port == 4321

    def test_a_url_with_no_port_reports_zero_rather_than_guessing(self):
        assert LocalServer(url="http://localhost", name="x", origin="project").port == 0


class TestItSurvivesAnAbsentRegistry:
    def test_a_registry_that_raises_still_gives_the_backend(self):
        """A new tab that fails to open because the code pack is unhappy is
        worse than a new tab offering only the backend."""

        def angry():
            raise RuntimeError("no code pack")

        found = running_servers(backend_url=BACKEND, launched=angry)
        assert [s.origin for s in found] == ["zaram"]

    def test_the_real_registry_is_readable(self):
        """Reachability, not content. The route calls this with no
        `launched`, and an import error there would be a 500 on a panel
        nobody could then diagnose."""
        from packs.code.apps import launched

        assert isinstance(launched(), list)


class TestItIsReadOnly:
    """The route answers a question. Starting or stopping is the mutative
    tier and would need confirm, undo and a sandbox."""

    def test_the_module_cannot_start_or_stop_anything(self):
        import inspect

        import core.local_servers as module

        source = inspect.getsource(module)
        for forbidden in ("subprocess", "os.kill", "Popen", ".terminate()", ".kill()"):
            assert forbidden not in source, f"local_servers reaches {forbidden}"

    def test_it_no_longer_reads_the_process_table(self):
        """The narrowing, asserted. `psutil` coming back here would mean
        the panel had quietly widened into a port scan again.

        The *import* rather than the word: the module docstring explains at
        length why psutil was taken out, and an assertion that forbade
        naming it would train somebody to delete the explanation to get a
        green build — the trap `test_artifact_records` names.
        """
        import inspect

        import core.local_servers as module

        for line in inspect.getsource(module).splitlines():
            stripped = line.strip()
            assert not stripped.startswith(("import psutil", "from psutil")), stripped


class TestTheRoute:
    """Against the real application object.

    `tests/test_routes_are_mounted.py` exists because a complete router
    with a passing test file and no `include_router` answered 404 on the
    running product while its tests stayed green.
    """

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        import main

        return TestClient(main.app)

    def test_it_answers(self, client):
        response = client.get("/local-servers")
        assert response.status_code == 200, response.text
        assert isinstance(response.json()["servers"], list)

    def test_every_row_is_loopback(self, client):
        for server in client.get("/local-servers").json()["servers"]:
            host = server["url"].split("//", 1)[-1].split(":")[0].split("/")[0]
            assert (
                host in ("127.0.0.1", "localhost") or host.endswith(".localhost")
            ), server

    def test_it_sends_the_keys_the_renderer_reads(self, client):
        rows = client.get("/local-servers").json()["servers"]
        if not rows:
            pytest.skip("nothing launched in this process")
        for key in ("url", "name", "origin", "pid", "projectId", "runner", "port"):
            assert key in rows[0], f"{key} missing from the server row"
