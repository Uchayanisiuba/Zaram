"""The browser pane's new tab lists what is actually listening.

Asked for 3 October 2026, with a screenshot of Claude's new-tab page: *"when
the user opens a new tab, I want them to see all the running servers ...
Zaram's front end, back end etc. I want them to see Ride Share's own, or any
other project of theirs."*

The whole module is driven through an injected listener list. Reading the
real process table in a test would assert whatever happens to be running on
the machine it runs on, which is not a test — it is a description of a
laptop, and it passes or fails for reasons nobody can reproduce.

Two properties here are security rather than presentation, and they are the
reason this file is longer than the feature looks:

* **Only loopback is ever offered.** The pane reaches local things; handing
  it a routable address turns a stray click into an egress.
* **Nothing starts or stops.** This answers a question. A list that could
  also run things is a different risk tier and would need confirm and undo.
"""

from __future__ import annotations

import os

import pytest

from core.local_servers import MIN_PORT, KnownProject, _Listener, running_servers


def listener(port, address="127.0.0.1", pid=1, process="node.exe", cwd=""):
    return _Listener(port=port, address=address, pid=pid, process=process, cwd=cwd)


class TestWhatIsListed:
    def test_a_loopback_listener_is_offered(self):
        found = running_servers(listeners=[listener(5173)])
        assert [s.port for s in found] == [5173]
        assert found[0].url == "http://127.0.0.1:5173"

    def test_a_server_on_every_interface_is_offered_at_loopback(self):
        """`0.0.0.0` includes this machine, so the server belongs in the
        list — but it is reached at 127.0.0.1, never at the address it
        bound. The pane must not be able to navigate off-machine."""
        found = running_servers(listeners=[listener(3000, address="0.0.0.0")])
        assert found[0].url == "http://127.0.0.1:3000"

    def test_a_routable_listener_is_not_offered(self):
        found = running_servers(listeners=[listener(3000, address="192.168.1.40")])
        assert found == []

    def test_system_ports_are_left_out(self):
        """Noise on a panel that has to be scannable."""
        found = running_servers(listeners=[listener(443), listener(MIN_PORT)])
        assert [s.port for s in found] == [MIN_PORT]

    def test_one_row_per_port(self):
        """A server bound to both stacks is two rows in the process table
        and one server to a person."""
        found = running_servers(
            listeners=[listener(5173, address="127.0.0.1"), listener(5173, address="::1")]
        )
        assert len(found) == 1

    def test_nothing_running_is_an_empty_list_not_an_error(self):
        assert running_servers(listeners=[]) == []


class TestWhoseServerItIs:
    def test_zarams_own_ports_are_named(self):
        found = running_servers(listeners=[listener(8420)], zaram_ports=[8420])
        assert found[0].origin == "zaram"
        assert "Zaram" in found[0].name

    def test_a_process_inside_the_open_project_is_the_projects(self, tmp_path):
        root = str(tmp_path / "ride-share")
        os.makedirs(root)
        found = running_servers(
            listeners=[listener(5173, cwd=root)],
            projects=[KnownProject("ride-share", "Ride Share", root)],
        )
        assert found[0].origin == "project"
        assert found[0].name == "Ride Share"

    def test_a_subfolder_of_the_project_still_counts(self, tmp_path):
        root = str(tmp_path / "ride-share")
        inner = os.path.join(root, "apps", "web")
        os.makedirs(inner)
        found = running_servers(
            listeners=[listener(5173, cwd=inner)],
            projects=[KnownProject("ride-share", "Ride Share", root)],
        )
        assert found[0].origin == "project"

    def test_a_sibling_folder_with_a_shared_prefix_is_not_the_project(self, tmp_path):
        """`startswith` calls `ride-share-old` a child of `ride-share`, which
        would label another project's server as this one's."""
        root = str(tmp_path / "ride-share")
        other = str(tmp_path / "ride-share-old")
        os.makedirs(root)
        os.makedirs(other)
        found = running_servers(
            listeners=[listener(5173, cwd=other)],
            projects=[KnownProject("ride-share", "Ride Share", root)],
        )
        assert found[0].origin == "other"

    def test_the_most_specific_project_claims_it(self, tmp_path):
        """Projects nest — a monorepo open as one project, a service inside
        it as another. The first match would hand the server to whichever
        was listed first, which is a label that changes on reorder."""
        outer = str(tmp_path / "mono")
        inner = os.path.join(outer, "services", "api")
        os.makedirs(inner)
        found = running_servers(
            listeners=[listener(5173, cwd=inner)],
            projects=[
                KnownProject("mono", "Monorepo", outer),
                KnownProject("api", "The API", inner),
            ],
        )
        assert found[0].name == "The API"

    def test_a_second_project_is_recognised_too(self, tmp_path):
        """The request was *"Ride Share's own, or any other project of
        theirs"* — not only the one that happens to be open."""
        ride = str(tmp_path / "ride-share")
        keyline = str(tmp_path / "keyline")
        os.makedirs(ride)
        os.makedirs(keyline)
        found = running_servers(
            listeners=[listener(5173, cwd=ride), listener(4321, cwd=keyline)],
            projects=[
                KnownProject("ride-share", "Ride Share", ride),
                KnownProject("keyline", "Keyline", keyline),
            ],
        )
        assert sorted(s.name for s in found) == ["Keyline", "Ride Share"]

    def test_a_project_with_no_folder_claims_nothing(self, tmp_path):
        """A general (non-coding) project has an empty root, and an empty
        root must not match every process on the machine."""
        found = running_servers(
            listeners=[listener(5173, cwd=str(tmp_path))],
            projects=[KnownProject("zaram", "Zaram", "")],
        )
        assert found[0].origin == "other"

    def test_an_unknown_process_is_named_without_its_extension(self):
        found = running_servers(listeners=[listener(7777, process="caddy.exe")])
        assert found[0].name == "caddy"

    def test_a_nameless_process_falls_back_to_its_port(self):
        """Honest rather than blank. An empty row reads as a bug."""
        found = running_servers(listeners=[listener(7777, process="")])
        assert found[0].name == "Port 7777"

    def test_the_project_falls_back_to_its_folder_name(self, tmp_path):
        root = str(tmp_path / "keyline")
        os.makedirs(root)
        found = running_servers(
            listeners=[listener(5173, cwd=root)],
            projects=[KnownProject("keyline", "", root)],
        )
        assert found[0].name == "keyline"


class TestZaramsOwn:
    """Identified by where it lives, not by a port number.

    The renderer's dev port moves when 5173 is taken, and a label that
    disagrees with the address bar is an invented value on the one panel
    whose job is to say what is up.
    """

    def test_the_backend_port_is_named(self):
        found = running_servers(listeners=[listener(8420)], zaram_ports=[8420])
        assert found[0].origin == "zaram"
        assert "backend" in found[0].name

    def test_a_process_inside_the_install_is_zarams(self, tmp_path):
        root = str(tmp_path / "Zaram")
        inner = os.path.join(root, "frontend")
        os.makedirs(inner)
        found = running_servers(listeners=[listener(5173, cwd=inner)], zaram_root=root)
        assert found[0].origin == "zaram"
        assert found[0].name == "Zaram — frontend"

    def test_it_is_named_for_the_first_folder_not_the_deepest(self, tmp_path):
        """A dev server started in `frontend/` and one started in
        `frontend/src` are the same thing to a person reading a list."""
        root = str(tmp_path / "Zaram")
        inner = os.path.join(root, "frontend", "src", "components")
        os.makedirs(inner)
        found = running_servers(listeners=[listener(5173, cwd=inner)], zaram_root=root)
        assert found[0].name == "Zaram — frontend"

    def test_the_users_own_project_wins_over_the_install(self, tmp_path):
        """Somebody who has opened Zaram's source as a coding project sees
        it as *their* project, because that is what it is to them."""
        root = str(tmp_path / "Zaram")
        os.makedirs(root)
        found = running_servers(
            listeners=[listener(5173, cwd=root)],
            projects=[KnownProject("zaram-src", "Zaram source", root)],
            zaram_root=root,
        )
        assert found[0].origin == "project"
        assert found[0].name == "Zaram source"


class TestTheOrder:
    def test_zaram_then_the_project_then_everything_else(self, tmp_path):
        root = str(tmp_path / "ride-share")
        os.makedirs(root)
        found = running_servers(
            listeners=[
                listener(9999, process="postgres.exe"),
                listener(5173, cwd=root),
                listener(8420),
            ],
            projects=[KnownProject("ride-share", "Ride Share", root)],
            zaram_ports=[8420],
        )
        assert [s.origin for s in found] == ["zaram", "project", "other"]

    def test_something_that_serves_pages_comes_before_something_that_does_not(self):
        found = running_servers(
            listeners=[listener(6000, process="postgres.exe"), listener(7000, process="node.exe")]
        )
        assert [s.port for s in found] == [7000, 6000]

    def test_a_server_in_an_unrecognised_language_is_still_listed(self):
        """Ordering only. A server written in Go is still a server, and a
        list that quietly omitted it would be worse than one with an extra
        row."""
        found = running_servers(listeners=[listener(8080, process="myserver.exe")])
        assert [s.port for s in found] == [8080]
        assert found[0].webbish is False


class TestItIsReadOnly:
    """The route answers a question. Starting or stopping a process is the
    mutative tier and would need confirm, undo and a sandbox — none of which
    a list has."""

    def test_the_module_exposes_no_way_to_start_or_stop_anything(self):
        import core.local_servers as module

        verbs = [n for n in dir(module) if any(
            v in n.lower() for v in ("start", "stop", "kill", "terminate", "spawn", "restart")
        )]
        assert verbs == [], f"local_servers exposes {verbs}"

    def test_the_source_calls_nothing_that_could(self):
        """Asserted against the source, because the guarantee is that this
        module cannot reach those calls rather than that it happens not to."""
        import inspect

        import core.local_servers as module

        source = inspect.getsource(module)
        for forbidden in ("subprocess", "os.kill", "Popen", ".terminate()", ".kill()"):
            assert forbidden not in source, f"local_servers reaches {forbidden}"


class TestItSurvivesAnUnhelpfulMachine:
    def test_a_refused_process_table_is_an_empty_list(self, monkeypatch):
        """Enumerating sockets needs privileges this process may not have.
        A new tab that fails to open because the process table was shy is
        worse than a new tab with an empty list."""
        import psutil

        def refuse(**_kwargs):
            raise psutil.AccessDenied(1)

        monkeypatch.setattr(psutil, "net_connections", refuse)
        assert running_servers() == []

    def test_a_process_that_will_not_say_its_folder_is_still_listed(self):
        """Common: a process owned by another user answers its name and
        refuses its cwd. It is not the project's, and it is still running."""
        found = running_servers(
            listeners=[listener(5173, cwd="")],
            projects=[KnownProject("x", "X", "C:/whatever")],
        )
        assert found[0].origin == "other"
        assert found[0].port == 5173


class TestTheRoute:
    """Against the real application object.

    `tests/test_routes_are_mounted.py` exists because a complete router with
    a passing test file and no `include_router` answered 404 on the running
    product while its tests stayed green.
    """

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        import main

        return TestClient(main.app)

    def test_it_answers(self, client):
        response = client.get("/local-servers")
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body["servers"], list)
        assert isinstance(body["hidden"], int)

    def test_every_row_is_loopback(self, client):
        """The property that matters most, asserted against whatever is
        actually running on the machine the suite runs on. A routable
        address reaching this list is a stray click away from an egress."""
        for server in client.get("/local-servers").json()["servers"]:
            assert server["url"].startswith("http://127.0.0.1:"), server

    def test_it_counts_what_it_collapses(self, client):
        body = client.get("/local-servers").json()
        others = [s for s in body["servers"] if s["origin"] == "other"]
        assert body["hidden"] == len(others)

    def test_it_sends_the_keys_the_renderer_reads(self, client):
        servers = client.get("/local-servers").json()["servers"]
        if not servers:
            pytest.skip("nothing listening on this machine above the system ports")
        for key in ("port", "url", "name", "pid", "process", "origin", "projectId", "webbish"):
            assert key in servers[0], f"{key} missing from the server row"

    def test_this_backend_is_in_its_own_list(self, client):
        """The suite is talking to it, so it is listening -- unless the
        process table refused, which is its own documented outcome."""
        from core.local_servers import running_servers

        if not running_servers():
            pytest.skip("the process table is not readable here")
        body = client.get("/local-servers").json()
        assert any(s["origin"] == "zaram" for s in body["servers"]), (
            "Zaram did not recognise its own backend in the list"
        )
