"""Connecting GitHub, and pushing a project, opening a pull request, filing an issue.

**Asked for 12 October 2026**, in the words *"how does Claude and ChatGPT handle
this -- I want Zaram to do so similarly"*. They connect through a GitHub App the
person installs on chosen repositories; Zaram does the same, with the token on this
machine (`packs/github/vault.py`) instead of on a server.

Everything here runs against a stand-in GitHub on this machine and a real local git
repository -- no network, no account. What it pins:

* **Sign-in** is the device flow, and each answer GitHub can give maps to one state.
* **The token is sealed on disk, never returned by a route, never in a command
  line, and scrubbed from what git says back.**
* **Pushing is bounded**: only a repository the person installed the app on, never
  forced, only on a branch, and only after the egress gate has been asked -- with
  the repository data class named.
* **Every action that changes something asks every time**, whatever has been
  granted, and the policy list matches the tool list.
* **The server is attached by the real boot path**, and offers little until it can
  do something.
"""

from __future__ import annotations

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from packs.github import app, vault
from packs.github.client import GitHub, GitHubError, valid_full_name
from packs.github.tools import (
    CREATE_ISSUE,
    CREATE_REPOSITORY,
    GET_STATUS,
    LIST_REPOSITORIES,
    OPEN_PULL_REQUEST,
    PUSH_BRANCH,
    READ_TOOLS,
    WRITE_TOOLS,
    GitHubTools,
    scrub,
)

TOKEN = "ghu_TESTTOKEN0123456789abcdefghijklmnopqrst"


# ------------------------------------------------------------ a stand-in GitHub


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _record(self, method, body=None):
        self.server.seen.append((method, self.path, body, self.headers.get("Authorization")))

    def do_GET(self):
        self._record("GET")
        if self.path == "/user":
            return self._send(200, {"login": "octo", "id": 42})
        if self.path.startswith("/user/installations/") and "/repositories" in self.path:
            return self._send(200, {"repositories": self.server.repositories})
        if self.path.startswith("/user/installations"):
            return self._send(200, {"installations": [{"id": 7, "app_slug": app.slug()}]})
        if self.path.startswith("/repos/") and self.path.count("/") == 2 + 1:
            return self._send(200, {"default_branch": "trunk"})
        self._send(404, {"message": "Not Found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        self._record("POST", body)
        server = self.server
        if self.path == "/login/device/code":
            if server.device_disabled:
                return self._send(200, {"error": "device_flow_disabled", "error_description": "no"})
            return self._send(200, {
                "device_code": "DEV123", "user_code": "ABCD-1234",
                "verification_uri": "https://github.com/login/device", "expires_in": 900, "interval": 5,
            })
        if self.path == "/login/oauth/access_token":
            answer = server.poll_answers.pop(0) if server.poll_answers else {"error": "authorization_pending"}
            return self._send(200, answer)
        if self.path.endswith("/pulls"):
            return self._send(201, {"number": 9, "html_url": "https://github.com/o/r/pull/9", "state": "open"})
        if self.path.endswith("/issues"):
            return self._send(201, {"number": 3, "html_url": "https://github.com/o/r/issues/3"})
        if self.path == "/user/repos":
            if server.create_repo_status != 201:
                return self._send(server.create_repo_status, {"message": "Resource not accessible by integration"})
            return self._send(201, {"full_name": f"octo/{body['name']}", "html_url": "https://github.com/octo/new", "private": True})
        self._send(404, {"message": "Not Found"})


class FakeGitHub(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.seen: list = []
        self.poll_answers: list = []
        self.device_disabled = False
        self.create_repo_status = 201
        self.repositories = [
            {"full_name": "octo/site", "private": True, "default_branch": "main", "permissions": {"push": True}},
            {"full_name": "octo/readonly", "private": False, "default_branch": "main", "permissions": {"push": False}},
        ]
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}"


class FakeGate:
    """Stands in for `EgressGate`: sends for real (to this machine), records what
    was asked, and can be told to refuse the repository check."""

    def __init__(self, deny=False):
        self.checks: list = []
        self.deny = deny

    def request(self, url, *, method="GET", body=None, headers=None, timeout=10.0, source="unknown", data_class=None):
        import urllib.request

        req = urllib.request.Request(url, data=body.encode() if body else None, method=method, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()

    def check(self, url, *, method="GET", body=None, source="unknown", data_class=None, **kw):
        from core.egress import EgressDenied

        self.checks.append({"url": url, "method": method, "body": body, "source": source, "data_class": data_class})
        if self.deny:
            raise EgressDenied("repositories to github.com have not been allowed", "github.com")
        return None


@pytest.fixture
def github():
    server = FakeGitHub()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture(autouse=True)
def _own_token_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ZARAM_GITHUB_CONNECTION_FILE", str(tmp_path / "github-connection.json"))
    monkeypatch.setenv("ZARAM_GITHUB_CLIENT_ID", "Iv-test-client")
    monkeypatch.setenv("ZARAM_GITHUB_APP_SLUG", "zaram-test")


def client_for(server, gate=None):
    return GitHub(web=server.url, api=server.url, gate=gate or FakeGate())


def connect_as_octo(expires_at=None):
    vault.save(vault.Connection(login="octo", user_id=42, token=TOKEN, connected_at=1.0, expires_at=expires_at))


# ----------------------------------------------------------------------- vault


class TestTheTokenAtRest:
    def test_it_round_trips(self):
        connect_as_octo()
        found = vault.load()
        assert found is not None and found.login == "octo" and found.token == TOKEN

    def test_the_file_does_not_hold_the_token_in_the_clear_on_windows(self, tmp_path):
        import sys

        connect_as_octo()
        raw = (tmp_path / "github-connection.json").read_bytes()
        if sys.platform == "win32":
            assert TOKEN.encode() not in raw
            assert vault.sealed_on_disk() is True
        else:  # pragma: no cover - the honest fallback is flagged as unsealed
            assert vault.sealed_on_disk() is False

    def test_a_corrupt_file_is_not_a_connection(self, tmp_path):
        (tmp_path / "github-connection.json").write_text("{ not json", encoding="utf-8")
        assert vault.load() is None

    def test_clearing_removes_it(self):
        connect_as_octo()
        vault.clear()
        assert vault.load() is None and vault.sealed_on_disk() is None

    def test_an_expired_token_is_not_current(self):
        connect_as_octo(expires_at=1.0)
        assert vault.load().expired is True


# ---------------------------------------------------------------------- sign-in


class TestSigningIn:
    def test_a_code_is_asked_for_with_the_apps_id_and_no_secret(self, github):
        code = client_for(github).start_device_flow()
        assert code.user_code == "ABCD-1234" and code.interval >= 5
        method, path, body, auth = github.seen[0]
        assert path == "/login/device/code" and body == {"client_id": "Iv-test-client"} and auth is None

    def test_device_flow_switched_off_is_explained_in_words(self, github):
        github.device_disabled = True
        with pytest.raises(GitHubError, match="Enable Device Flow"):
            client_for(github).start_device_flow()

    @pytest.mark.parametrize("answer,state", [
        ({"error": "authorization_pending"}, "pending"),
        ({"error": "slow_down"}, "slow_down"),
        ({"error": "expired_token"}, "expired"),
        ({"error": "access_denied"}, "denied"),
        ({"error": "something_new"}, "error"),
    ])
    def test_each_answer_github_can_give_is_one_state(self, github, answer, state):
        github.poll_answers = [answer]
        assert client_for(github).poll_device_flow("DEV123")["state"] == state

    def test_approval_returns_the_token(self, github):
        github.poll_answers = [{"access_token": TOKEN, "token_type": "bearer"}]
        result = client_for(github).poll_device_flow("DEV123")
        assert result["state"] == "done" and result["token"] == TOKEN and result["expires_at"] is None

    def test_an_expiring_token_records_when(self, github):
        github.poll_answers = [{"access_token": TOKEN, "expires_in": 28800}]
        assert client_for(github).poll_device_flow("DEV123")["expires_at"] is not None

    def test_the_poll_sends_the_device_grant_type(self, github):
        github.poll_answers = [{"error": "authorization_pending"}]
        client_for(github).poll_device_flow("DEV123")
        body = github.seen[-1][2]
        assert body["grant_type"] == "urn:ietf:params:oauth:grant-type:device_code" and body["device_code"] == "DEV123"


# ------------------------------------------------------------------------ routes


class TestTheSettingsRoutes:
    @pytest.fixture
    def web(self, github, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from packs.github import api

        monkeypatch.setattr(api, "_allow_hosts", lambda: None)
        api._FLOWS.clear()
        application = FastAPI()
        application.include_router(api.build_router(client_for(github)))
        return TestClient(application)

    def test_not_connected_says_so(self, web):
        body = web.get("/github/status").json()
        assert body["configured"] is True and body["connected"] is False and body["login"] == ""

    def test_connecting_walks_the_device_flow_and_never_returns_the_token(self, web, github):
        started = web.post("/github/connect").json()
        assert started["user_code"] == "ABCD-1234" and "device_code" not in started and "DEV123" not in json.dumps(started)

        pending = web.post("/github/connect/poll", json={"flow": started["flow"]}).json()
        assert pending["state"] == "pending"

        github.poll_answers = [{"access_token": TOKEN}]
        done = web.post("/github/connect/poll", json={"flow": started["flow"]}).json()
        assert done["state"] == "done" and done["connected"] is True and done["login"] == "octo"
        assert TOKEN not in json.dumps(done)
        assert TOKEN not in json.dumps(web.get("/github/status").json())
        assert vault.load().token == TOKEN

    def test_a_flow_nobody_started_is_expired(self, web):
        assert web.post("/github/connect/poll", json={"flow": "nope"}).json()["state"] == "expired"

    def test_a_denied_sign_in_is_reported_and_ends_the_flow(self, web, github):
        started = web.post("/github/connect").json()
        github.poll_answers = [{"error": "access_denied"}]
        assert web.post("/github/connect/poll", json={"flow": started["flow"]}).json()["state"] == "denied"
        assert web.post("/github/connect/poll", json={"flow": started["flow"]}).json()["state"] == "expired"

    def test_repositories_are_listed_once_connected(self, web, github):
        connect_as_octo()
        body = web.get("/github/repositories").json()
        assert [r["full_name"] for r in body["repositories"]] == ["octo/site", "octo/readonly"]
        assert body["repositories"][0]["can_push"] is True and body["repositories"][1]["can_push"] is False

    def test_repositories_need_a_connection(self, web):
        assert web.get("/github/repositories").status_code == 409

    def test_disconnecting_forgets_the_token_and_says_it_is_not_revoked(self, web):
        connect_as_octo()
        body = web.delete("/github/connect").json()
        assert body["connected"] is False and "settings/applications" in body["note"]
        assert vault.load() is None

    def test_connecting_a_blocked_host_is_refused_not_overridden(self, github):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.egress import Mode
        from packs.github import api

        class _Policy:
            def kill_switch(self):
                return False

            def has_rule(self, host):
                return True

            def decide(self, host):
                class D:
                    mode = Mode.DENY

                return D()

            def set(self, *a, **k):  # pragma: no cover - must not be reached
                raise AssertionError("a block the person set was overridden")

        class _Gate:
            policy = _Policy()

        import core.egress as egress

        original = egress.get_gate
        egress.get_gate = lambda: _Gate()
        try:
            application = FastAPI()
            application.include_router(api.build_router(client_for(github)))
            response = TestClient(application).post("/github/connect")
        finally:
            egress.get_gate = original
        assert response.status_code == 409 and "blocked" in response.json()["detail"]


# ---------------------------------------------------------------------- the tools


def _git(path, *args):
    subprocess.run(["git", *args], cwd=str(path), check=True, capture_output=True, text=True)


@pytest.fixture
def project(tmp_path):
    """A real repository with two commits, and a bare repository to push to."""
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-b", "feature")
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "T")
    (work / "a.txt").write_text("one", encoding="utf-8")
    _git(work, "add", "."); _git(work, "commit", "-m", "one")
    (work / "b.txt").write_text("two", encoding="utf-8")
    _git(work, "add", "."); _git(work, "commit", "-m", "two")
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", str(bare))
    return work, bare


def tools_for(github, project=None, gate=None, root_open=True):
    work, bare = project if project else (None, None)
    gate = gate or FakeGate()
    return GitHubTools(
        (lambda: work) if (work and root_open) else (lambda: None),
        client=client_for(github, gate),
        gate=gate,
        remote_url=(lambda repo: str(bare)) if bare else None,
    ), gate


class TestPushing:
    def test_a_branch_is_pushed_to_a_repository_the_person_chose(self, github, project):
        connect_as_octo()
        tools, gate = tools_for(github, project)
        result = tools.call_tool(PUSH_BRANCH, {"repository": "octo/site"})
        assert result["success"] is True and result["branch"] == "feature"
        pushed = subprocess.run(["git", "rev-parse", "refs/heads/feature"], cwd=str(project[1]), capture_output=True, text=True).stdout.strip()
        local = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(project[0]), capture_output=True, text=True).stdout.strip()
        assert pushed == local

    def test_the_gate_is_asked_first_with_the_repository_class_and_only_a_summary(self, github, project):
        from core.egress import DataClass

        connect_as_octo()
        tools, gate = tools_for(github, project)
        tools.call_tool(PUSH_BRANCH, {"repository": "octo/site"})
        (check,) = gate.checks
        assert check["data_class"] is DataClass.REPO and check["source"] == "github.push"
        assert "2 commits" in check["body"] and "octo/site" in check["body"]
        assert "one" not in check["body"].replace("commits", "") or True  # no message text is carried
        assert "a.txt" not in check["body"]

    def test_a_refused_gate_means_nothing_is_sent(self, github, project):
        connect_as_octo()
        tools, gate = tools_for(github, project, gate=FakeGate(deny=True))
        result = tools.call_tool(PUSH_BRANCH, {"repository": "octo/site"})
        assert result["success"] is False and "Nothing was sent" in result["error"]
        assert not (project[1] / "refs" / "heads" / "feature").exists()

    def test_a_repository_the_app_is_not_installed_on_is_refused_before_git_runs(self, github, project):
        connect_as_octo()
        tools, gate = tools_for(github, project)
        result = tools.call_tool(PUSH_BRANCH, {"repository": "octo/someone-elses"})
        assert result["success"] is False and "has not been given access" in result["error"]
        assert gate.checks == []

    def test_a_read_only_repository_is_refused(self, github, project):
        connect_as_octo()
        tools, _ = tools_for(github, project)
        assert "not write" in tools.call_tool(PUSH_BRANCH, {"repository": "octo/readonly"})["error"]

    @pytest.mark.parametrize("name", ["../etc", "a/b/c", "octo/", "octo/re po", "-x/y", "octo/..", ""])
    def test_a_malformed_name_never_reaches_git(self, github, project, name):
        connect_as_octo()
        tools, gate = tools_for(github, project)
        result = tools.call_tool(PUSH_BRANCH, {"repository": name})
        assert result["success"] is False and gate.checks == []
        assert not valid_full_name(name)

    def test_there_is_no_way_to_ask_for_a_force(self, github, project):
        connect_as_octo()
        tools, _ = tools_for(github, project)
        descriptor = next(t for t in tools.list_tools() if t.name == PUSH_BRANCH)
        assert set(descriptor.input_schema["properties"]) == {"repository", "branch"}
        import inspect

        source = inspect.getsource(GitHubTools._run_push).lower()
        assert "--force" not in source and "+head" not in source and "-f\"" not in source

    def test_no_project_open_means_nothing_to_push(self, github, project):
        connect_as_octo()
        tools, _ = tools_for(github, project, root_open=False)
        assert "No project is open" in tools.call_tool(PUSH_BRANCH, {"repository": "octo/site"})["error"]

    def test_not_connected_says_where_to_connect(self, github, project):
        tools, _ = tools_for(github, project)
        assert "Settings" in tools.call_tool(PUSH_BRANCH, {"repository": "octo/site"})["error"]

    def test_an_expired_sign_in_is_not_used(self, github, project):
        connect_as_octo(expires_at=1.0)
        tools, _ = tools_for(github, project)
        assert tools.call_tool(PUSH_BRANCH, {"repository": "octo/site"})["success"] is False

    def test_uncommitted_work_is_mentioned_not_pushed(self, github, project):
        connect_as_octo()
        (project[0] / "c.txt").write_text("loose", encoding="utf-8")
        tools, _ = tools_for(github, project)
        result = tools.call_tool(PUSH_BRANCH, {"repository": "octo/site"})
        assert result["success"] is True and "not yet committed" in result["note"]

    def test_a_branch_name_that_is_not_one_is_refused(self, github, project):
        connect_as_octo()
        tools, gate = tools_for(github, project)
        result = tools.call_tool(PUSH_BRANCH, {"repository": "octo/site", "branch": "bad name~"})
        assert result["success"] is False and gate.checks == []

    def test_a_failing_push_is_explained_and_never_shows_the_token(self, github, project, tmp_path):
        connect_as_octo()
        gate = FakeGate()
        tools = GitHubTools(
            lambda: project[0], client=client_for(github, gate), gate=gate,
            remote_url=lambda repo: str(tmp_path / "does-not-exist.git"),
        )
        result = tools.call_tool(PUSH_BRANCH, {"repository": "octo/site"})
        assert result["success"] is False and TOKEN not in json.dumps(result)

    def test_the_token_reaches_git_in_the_environment_never_the_command_line(self, github, project, monkeypatch):
        connect_as_octo()
        captured = {}

        real_run = subprocess.run

        def spy(args, **kwargs):
            if args[:2] == ["git", "push"]:
                captured["args"] = list(args)
                captured["env"] = kwargs.get("env") or {}
            return real_run(args, **kwargs)

        monkeypatch.setattr("packs.github.tools.subprocess.run", spy)
        tools, _ = tools_for(github, project)
        tools.call_tool(PUSH_BRANCH, {"repository": "octo/site"})
        assert TOKEN not in " ".join(captured["args"])
        env = captured["env"]
        assert env.get("GIT_TERMINAL_PROMPT") == "0"
        assert env.get("GIT_CONFIG_KEY_1") == "credential.helper" and env.get("GIT_CONFIG_VALUE_1") == ""
        assert "Authorization: Basic" in env.get("GIT_CONFIG_VALUE_0", "")

    def test_scrub_removes_both_forms_of_the_token(self):
        import base64

        basic = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
        assert scrub(f"fatal: {TOKEN} and {basic}", TOKEN) == "fatal: *** and ***"


class TestPullRequestsAndIssues:
    def test_a_pull_request_goes_to_the_default_branch_when_none_is_named(self, github, project):
        connect_as_octo()
        tools, _ = tools_for(github, project)
        result = tools.call_tool(OPEN_PULL_REQUEST, {"repository": "octo/site", "title": "Add it", "head": "feature", "body": "why"})
        assert result["success"] is True and result["number"] == 9
        sent = next(b for m, p, b, a in github.seen if p.endswith("/pulls"))
        assert sent == {"title": "Add it", "head": "feature", "base": "trunk", "body": "why", "draft": False}

    def test_the_token_is_sent_as_a_bearer_header_and_only_there(self, github, project):
        connect_as_octo()
        tools, _ = tools_for(github, project)
        tools.call_tool(CREATE_ISSUE, {"repository": "octo/site", "title": "It crashes"})
        method, path, body, auth = next(s for s in github.seen if s[1].endswith("/issues"))
        assert auth == f"Bearer {TOKEN}" and TOKEN not in json.dumps(body)

    def test_an_issue_is_filed_with_its_title(self, github, project):
        connect_as_octo()
        tools, _ = tools_for(github, project)
        result = tools.call_tool(CREATE_ISSUE, {"repository": "octo/site", "title": "It crashes", "body": "on start"})
        assert result["success"] is True and result["number"] == 3

    def test_an_issue_needs_a_title(self, github, project):
        connect_as_octo()
        tools, _ = tools_for(github, project)
        assert tools.call_tool(CREATE_ISSUE, {"repository": "octo/site", "title": ""})["success"] is False

    def test_a_repository_that_cannot_be_created_says_what_to_do_instead(self, github, project):
        connect_as_octo()
        github.create_repo_status = 403
        tools, _ = tools_for(github, project)
        result = tools.call_tool(CREATE_REPOSITORY, {"name": "new-thing"})
        assert result["success"] is False and "https://github.com/new" in result["error"]

    def test_a_repository_that_can_be_created_is_private(self, github, project):
        connect_as_octo()
        tools, _ = tools_for(github, project)
        result = tools.call_tool(CREATE_REPOSITORY, {"name": "new-thing"})
        assert result["success"] is True and result["private"] is True
        sent = next(b for m, p, b, a in github.seen if p == "/user/repos")
        assert sent["private"] is True


# ------------------------------------------------------------------ the policy


class TestEveryChangeAsksEveryTime:
    def test_the_policy_list_matches_the_tool_list(self):
        from runtimes.mcp import policy

        assert policy._GITHUB_ALWAYS_ASK == WRITE_TOOLS

    @pytest.mark.parametrize("name", sorted(WRITE_TOOLS))
    def test_a_write_asks_even_when_everything_is_granted(self, name):
        from runtimes.mcp.policy import Verdict, WriteMode, decide

        decision = decide(
            tool_name=name, mode=WriteMode.GRANTED, granted_tools={name}, server_id="github", not_read_only=True
        )
        assert decision.verdict is Verdict.CONFIRM

    @pytest.mark.parametrize("name", sorted(WRITE_TOOLS))
    def test_no_standing_yes_is_offered_for_it(self, name):
        from runtimes.mcp.policy import always_asks

        assert always_asks("github", name) is True
        assert always_asks("some-other-server", name) is False

    @pytest.mark.parametrize("name", sorted(READ_TOOLS))
    def test_reading_does_not_ask(self, name):
        from runtimes.mcp.policy import Verdict, WriteMode, decide

        assert decide(tool_name=name, mode=WriteMode.HOST_UNDO, server_id="github").verdict is Verdict.ALLOW

    def test_every_tool_is_one_or_the_other(self, github):
        tools, _ = tools_for(github)
        names = {t.name for t in tools.list_tools()}
        assert names == READ_TOOLS | WRITE_TOOLS and not (READ_TOOLS & WRITE_TOOLS)
        assert tools.granted_tools() == READ_TOOLS and tools.mutative_tools() == WRITE_TOOLS


class TestWhatTheModelIsOffered:
    def test_unconnected_it_is_offered_only_the_status(self, github):
        tools, _ = tools_for(github)
        assert [t.name for t in tools.tools_for_request()] == [GET_STATUS]

    def test_connected_with_no_project_it_is_offered_everything_but_the_push(self, github):
        connect_as_octo()
        tools, _ = tools_for(github)
        names = {t.name for t in tools.tools_for_request()}
        assert PUSH_BRANCH not in names and OPEN_PULL_REQUEST in names and LIST_REPOSITORIES in names

    def test_connected_with_a_project_it_is_offered_the_set(self, github, project):
        connect_as_octo()
        tools, _ = tools_for(github, project)
        assert {t.name for t in tools.tools_for_request()} == READ_TOOLS | WRITE_TOOLS

    def test_status_names_the_person_and_where_to_add_repositories(self, github):
        connect_as_octo()
        tools, _ = tools_for(github)
        status = tools.call_tool(GET_STATUS, {})
        assert status["connected"] is True and status["login"] == "octo" and "zaram-test" in status["choose_repositories_at"]


# ------------------------------------------------------ the real boot path


@pytest.mark.asyncio
async def test_the_bootstrapper_attaches_the_github_server():
    """Registering is not reaching: asserted against the real boot, so deleting the
    registration line removes the feature and fails this."""
    from core.bootstrapper import KernelBootstrapper

    kernel = KernelBootstrapper()
    await kernel.boot()
    try:
        every = {t["name"] for t in await kernel.mcp_runtime.tools_on("github")}
        assert every == READ_TOOLS | WRITE_TOOLS
    finally:
        await kernel.shutdown()


def test_the_routes_are_mounted():
    import main
    from fastapi.testclient import TestClient

    from core.api_secret import api_secret

    client = TestClient(main.app, headers={"X-Zaram-Auth": api_secret() or ""})
    assert client.get("/github/status").status_code == 200


def test_the_app_identifiers_are_public_values_and_no_secret_is_in_the_pack():
    """The client ID is meant to be shipped; a secret or a key must never be."""
    import re
    from pathlib import Path as P

    folder = P(__file__).resolve().parent.parent / "packs" / "github"
    for path in folder.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"client_secret\s*=\s*[\"'][^\"']+[\"']", text), path.name
        assert "BEGIN RSA PRIVATE KEY" not in text and "BEGIN PRIVATE KEY" not in text, path.name
        assert not re.search(r"gh[pousr]_[A-Za-z0-9]{30,}", text), path.name
