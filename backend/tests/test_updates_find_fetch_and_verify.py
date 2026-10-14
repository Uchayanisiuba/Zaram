"""Updates: a newer build is found, fetched through the gate, checked, and left for
the installer -- and nothing happens that the person did not ask for.

Asked for 14 October 2026. What is pinned here is what could go wrong in a way a
person would not see: a version that sorts wrongly (alpha.10 below alpha.9), a
check that runs while the answer is no, a download accepted without its checksum,
an asset address the release API made up, a redirect hop the egress log never
heard about, an installer left on disk long after it was used.

A stand-in GitHub on this machine serves the release list, the checksums and the
installer, the last behind a redirect like the real storage host. The gate is the
real `EgressGate` with its `check` recorded, so what is asserted about hops is what
the real transport does with them.
"""

from __future__ import annotations

import hashlib
import json
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import updates
from core.egress import EgressDenied, EgressGate, EgressLog, EgressPolicy, Mode
from core.update_routes import build_router
from core.updates import (
    UpdateError,
    Updates,
    is_newer,
    parse_sums,
    parse_tag,
)

REPO = "Uchayanisiuba/Zaram"
INSTALLER = b"MZ" + b"installer-bytes-" * 5000


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _bytes(self, status, data, kind="application/octet-stream"):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        server = self.server
        server.seen.append(self.path)
        if server.fail:
            return self._bytes(500, b"{}")
        if self.path.startswith(f"/repos/{REPO}/releases"):
            return self._bytes(200, json.dumps(server.releases()).encode(), "application/json")
        if self.path.endswith("/SHA256SUMS.txt"):
            return self._bytes(200, server.sums().encode(), "text/plain")
        if self.path.startswith(f"/{REPO}/releases/download/") and self.path.endswith(".exe"):
            # Like GitHub: the asset address answers with a redirect to storage.
            self.send_response(302)
            self.send_header("Location", f"{server.url}/storage/blob?x=1")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path.startswith("/storage/blob"):
            return self._bytes(200, server.installer)
        self._bytes(404, b"{}")


class FakeGitHub(ThreadingHTTPServer):
    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.seen: list = []
        self.fail = False
        self.installer = INSTALLER
        self.published = [("v0.1.0-alpha.8", {})]
        self.sums_hash = None
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}"

    def sums(self):
        digest = self.sums_hash or hashlib.sha256(self.installer).hexdigest()
        return f"{digest}  Zaram-0.1.0-x64.exe\n{'0' * 64}  Zaram-Portable-0.1.0-x64.exe\n"

    def releases(self):
        out = []
        for tag, options in self.published:
            base = options.get("base", f"{self.url}/{REPO}/releases/download/{tag}/")
            assets = []
            if not options.get("no_installer"):
                assets.append({"name": options.get("installer_name", "Zaram-0.1.0-x64.exe"),
                               "browser_download_url": base + options.get("installer_name", "Zaram-0.1.0-x64.exe"),
                               "size": len(self.installer)})
            if not options.get("no_sums"):
                assets.append({"name": "SHA256SUMS.txt", "browser_download_url": base + "SHA256SUMS.txt", "size": 200})
            out.append({
                "tag_name": tag, "draft": bool(options.get("draft")), "prerelease": True,
                "html_url": options.get("page", f"{self.url}/{REPO}/releases/tag/{tag}"),
                "assets": assets,
            })
        return out


class RecordingGate(EgressGate):
    """The real transport, with each decision it is asked to make written down."""

    def __init__(self, log, policy, deny=None):
        super().__init__(log, policy)
        self.asked: list = []
        self.deny = deny

    def check(self, url, **kw):
        self.asked.append(url)
        if self.deny and self.deny in url:
            raise EgressDenied("that host is blocked", "storage")
        return super().check(url, **kw)


@pytest.fixture
def github():
    server = FakeGitHub()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def gate(tmp_path):
    return RecordingGate(EgressLog(str(tmp_path / "egress.db")), EgressPolicy(str(tmp_path / "policy.json")))


def make(github, gate, tmp_path, current="v0.1.0-alpha.7", **options):
    defaults = dict(portable=False, packaged=True, platform="win32")
    defaults.update(options)
    return Updates(
        gate=gate, directory=tmp_path / "data", current=current,
        api_base=github.url, web_base=github.url, repo=REPO, **defaults,
    )


# --------------------------------------------------------------------- versions


class TestVersionsOrderAsPeopleExpect:
    def test_the_ninth_alpha_is_below_the_tenth(self):
        assert is_newer("v0.1.0-alpha.10", "v0.1.0-alpha.9")
        assert not is_newer("v0.1.0-alpha.9", "v0.1.0-alpha.10")

    def test_a_stage_orders_alpha_beta_rc_release(self):
        order = ["v0.1.0-alpha.9", "v0.1.0-beta.1", "v0.1.0-rc.1", "v0.1.0", "v0.1.1-alpha.1", "v0.2.0-alpha.1"]
        keys = [parse_tag(tag) for tag in order]
        assert keys == sorted(keys)

    def test_the_same_version_is_not_newer(self):
        assert not is_newer("v0.1.0-alpha.7", "v0.1.0-alpha.7")

    @pytest.mark.parametrize("tag", ["", None, "latest", "v1", "v0.1.0-nightly.3", "0.1.0-alpha", "v0.1.0-alpha.x"])
    def test_what_is_not_a_version_is_neither_newer_nor_older(self, tag):
        assert parse_tag(tag) is None
        assert not is_newer(tag, "v0.1.0-alpha.1") and not is_newer("v0.1.0-alpha.1", tag)

    def test_the_running_release_comes_from_the_environment_and_only_when_valid(self, monkeypatch):
        monkeypatch.delenv(updates.RELEASE_ENV, raising=False)
        assert updates.current_tag() is None
        monkeypatch.setenv(updates.RELEASE_ENV, "v0.1.0-alpha.7")
        assert updates.current_tag() == "v0.1.0-alpha.7"
        monkeypatch.setenv(updates.RELEASE_ENV, "dev")
        assert updates.current_tag() is None

    def test_checksums_are_read_by_name(self):
        text = f"{'A' * 64}  one.exe\n{'b' * 64} *two.exe\nnot a line\n"
        assert parse_sums(text) == {"one.exe": "a" * 64, "two.exe": "b" * 64}


# ---------------------------------------------------------------------- finding


class TestFindingANewerBuild:
    def test_a_build_with_no_release_number_does_not_guess(self, github, gate, tmp_path):
        service = make(github, gate, tmp_path, current=None)
        status = service.check(force=True)
        assert status["known"] is False and status["can_install"] is False
        assert github.seen == []

    def test_up_to_date_says_so_and_offers_nothing(self, github, gate, tmp_path):
        service = make(github, gate, tmp_path, current="v0.1.0-alpha.8")
        status = service.check(force=True)
        assert status["phase"] == "up_to_date" and status["latest"] is None

    def test_a_newer_release_is_offered_with_its_page_and_size(self, github, gate, tmp_path):
        status = make(github, gate, tmp_path).check(force=True)
        assert status["phase"] == "available"
        assert status["latest"]["tag"] == "v0.1.0-alpha.8"
        assert status["latest"]["page"].endswith("/releases/tag/v0.1.0-alpha.8")
        assert status["latest"]["installer"]["size"] == len(INSTALLER)

    def test_the_highest_version_wins_not_the_first_listed_or_the_last(self, github, gate, tmp_path):
        github.published = [("v0.1.0-alpha.9", {}), ("v0.1.0-alpha.10", {}), ("v0.1.0-alpha.8", {})]
        assert make(github, gate, tmp_path).check(force=True)["latest"]["tag"] == "v0.1.0-alpha.10"

    def test_a_draft_a_release_without_its_files_and_a_stray_tag_are_ignored(self, github, gate, tmp_path):
        github.published = [
            ("v0.1.0-alpha.12", {"draft": True}),
            ("v0.1.0-alpha.11", {"no_sums": True}),
            ("v0.1.0-alpha.10", {"no_installer": True}),
            ("nightly", {}),
            ("v0.1.0-alpha.8", {}),
        ]
        assert make(github, gate, tmp_path).check(force=True)["latest"]["tag"] == "v0.1.0-alpha.8"

    def test_an_asset_address_outside_the_repositorys_release_path_is_not_taken(self, github, gate, tmp_path):
        github.published = [("v0.1.0-alpha.9", {"base": "https://evil.example/Zaram/"}), ("v0.1.0-alpha.8", {})]
        assert make(github, gate, tmp_path).check(force=True)["latest"]["tag"] == "v0.1.0-alpha.8"

    def test_only_the_installer_the_build_names_is_taken_never_the_portable_one(self, github, gate, tmp_path):
        github.published = [("v0.1.0-alpha.9", {"installer_name": "Zaram-Portable-0.1.0-x64.exe"})]
        assert make(github, gate, tmp_path).check(force=True)["latest"] is None

    def test_a_page_that_is_not_the_repositorys_is_replaced_by_the_tag_page(self, github, gate, tmp_path):
        github.published = [("v0.1.0-alpha.8", {"page": "https://evil.example/phish"})]
        page = make(github, gate, tmp_path).check(force=True)["latest"]["page"]
        assert page.startswith(f"{github.url}/{REPO}/releases/")

    def test_the_last_answer_is_trusted_for_an_hour_unless_asked_again(self, github, gate, tmp_path):
        clock = [1000.0]
        service = make(github, gate, tmp_path, now=lambda: clock[0])
        service.check()
        calls = len(github.seen)
        service.check()
        assert len(github.seen) == calls
        clock[0] += updates.CHECK_EVERY_SECONDS + 1
        service.check()
        assert len(github.seen) > calls
        calls = len(github.seen)
        service.check(force=True)
        assert len(github.seen) > calls

    def test_a_failed_check_is_a_sentence_not_an_exception(self, github, gate, tmp_path):
        github.fail = True
        status = make(github, gate, tmp_path).check(force=True)
        assert status["error"] and status["phase"] == "idle" and status["latest"] is None

    def test_a_blocked_host_is_reported_and_nothing_is_fetched(self, github, gate, tmp_path):
        gate.deny = "/repos/"
        status = make(github, gate, tmp_path).check(force=True)
        assert "Nothing was fetched" in status["error"]


# ------------------------------------------------------------------ downloading


def downloaded(github, gate, tmp_path, **options):
    service = make(github, gate, tmp_path, **options)
    service.check(force=True)
    service.download()
    service.wait()
    return service


class TestFetchingAndVerifying:
    def test_the_installer_is_saved_checked_and_ready_to_run(self, github, gate, tmp_path):
        service = downloaded(github, gate, tmp_path)
        status = service.status()
        assert status["phase"] == "ready" and status["ready"] is True and status["error"] == ""
        found = service.pending()
        assert found["name"] == "Zaram-0.1.0-x64.exe" and found["tag"] == "v0.1.0-alpha.8"
        assert found["sha256"] == hashlib.sha256(INSTALLER).hexdigest()
        with open(found["path"], "rb") as handle:
            assert handle.read() == INSTALLER

    def test_each_hop_of_the_redirect_is_a_decision_of_its_own(self, github, gate, tmp_path):
        downloaded(github, gate, tmp_path)
        assert any("/releases/download/v0.1.0-alpha.8/Zaram-0.1.0-x64.exe" in url for url in gate.asked)
        assert any("/storage/blob" in url for url in gate.asked), "the storage host was never put to the gate"

    def test_a_hop_the_person_blocked_is_refused_and_leaves_nothing_behind(self, github, gate, tmp_path):
        gate.deny = "/storage/"
        service = downloaded(github, gate, tmp_path)
        assert "Nothing was fetched" in service.status()["error"]
        assert service.pending() is None
        assert [p.name for p in (tmp_path / "data" / updates.FOLDER).iterdir()] == []

    def test_a_download_that_does_not_match_its_checksum_is_thrown_away(self, github, gate, tmp_path):
        github.sums_hash = "f" * 64
        service = downloaded(github, gate, tmp_path)
        assert "checksum" in service.status()["error"]
        assert service.pending() is None
        assert [p.name for p in (tmp_path / "data" / updates.FOLDER).iterdir()] == []

    def test_a_release_with_no_checksum_for_its_installer_is_not_used(self, github, gate, tmp_path):
        github.sums = lambda: f"{'a' * 64}  Zaram-Portable-0.1.0-x64.exe\n"
        service = downloaded(github, gate, tmp_path)
        assert "no checksum" in service.status()["error"] and service.pending() is None

    def test_a_file_changed_after_it_was_checked_is_not_handed_over(self, github, gate, tmp_path):
        service = downloaded(github, gate, tmp_path)
        path = service.pending()["path"]
        with open(path, "ab") as handle:
            handle.write(b"tampered")
        assert service.pending() is None

    def test_progress_is_reported_while_it_arrives(self, github, gate, tmp_path):
        seen = []
        service = make(github, gate, tmp_path)
        service.check(force=True)
        real = gate.download_to_file

        def watching(url, destination, **kw):
            inner = kw["progress"]
            kw["progress"] = lambda done, total: (seen.append((done, total)), inner(done, total))
            return real(url, destination, **kw)

        gate.download_to_file = watching
        service.download()
        service.wait()
        assert seen and seen[-1][0] == len(INSTALLER)

    def test_nothing_to_download_is_an_error_not_a_crash(self, github, gate, tmp_path):
        service = make(github, gate, tmp_path, current="v0.1.0-alpha.8")
        service.check(force=True)
        with pytest.raises(UpdateError):
            service.download()
        with pytest.raises(UpdateError):
            make(github, gate, tmp_path, current=None).download()

    def test_an_installer_is_deleted_once_the_running_build_has_caught_up(self, github, gate, tmp_path):
        downloaded(github, gate, tmp_path)
        caught_up = make(github, gate, tmp_path, current="v0.1.0-alpha.8")
        assert caught_up.status()["phase"] == "up_to_date"
        assert caught_up.pending() is None
        assert [p.name for p in (tmp_path / "data" / updates.FOLDER).iterdir()] == []

    def test_the_file_the_flag_and_the_timestamp_are_all_that_is_kept(self, github, gate, tmp_path):
        service = downloaded(github, gate, tmp_path)
        service.set_checks(True)
        data = json.loads((tmp_path / "data" / updates.FILENAME).read_text())
        assert set(data) <= {"checks", "last_checked", "latest", "downloaded"}


class TestWhatCannotBeInstalledInPlace:
    @pytest.mark.parametrize("options", [{"portable": True}, {"platform": "linux"}, {"packaged": False}])
    def test_it_says_why_and_hands_nothing_to_the_shell(self, github, gate, tmp_path, options):
        service = downloaded(github, gate, tmp_path, **options)
        status = service.status()
        assert status["can_install"] is False and status["manual_reason"]
        assert service.pending() is None

    def test_a_portable_build_still_learns_a_newer_one_exists(self, github, gate, tmp_path):
        service = make(github, gate, tmp_path, portable=True)
        assert service.check(force=True)["latest"]["tag"] == "v0.1.0-alpha.8"


# ------------------------------------------------------------------ the consent


class TestTheAnswerIsTheDecision:
    def test_nobody_has_been_asked_until_they_answer(self, github, gate, tmp_path):
        service = make(github, gate, tmp_path)
        assert service.checks() is None and service.status()["checks"] is None
        service.set_checks(False)
        assert service.checks() is False
        service.set_checks(True)
        assert service.checks() is True

    def test_the_answer_survives_a_restart(self, github, gate, tmp_path):
        make(github, gate, tmp_path).set_checks(True)
        assert make(github, gate, tmp_path).checks() is True


@pytest.fixture
def web(github, gate, tmp_path, monkeypatch):
    service = make(github, gate, tmp_path)
    monkeypatch.setattr(updates, "allow_hosts", lambda gate=None: None)
    app = FastAPI()
    app.include_router(build_router(service))
    return TestClient(app), service, github


class TestTheRoutes:
    def test_a_launch_check_does_nothing_until_the_person_has_said_yes(self, web):
        client, service, github = web
        for answer in (None, False):
            if answer is not None:
                service.set_checks(answer)
            assert client.post("/updates/check", json={"force": False}).status_code == 200
            assert github.seen == []

    def test_pressing_check_is_an_act_and_goes_ahead_whatever_the_setting(self, web):
        client, service, github = web
        service.set_checks(False)
        body = client.post("/updates/check", json={"force": True}).json()
        assert body["phase"] == "available" and github.seen

    def test_a_launch_check_runs_once_the_person_said_yes(self, web):
        client, service, github = web
        assert client.put("/updates/settings", json={"checks": True}).json()["checks"] is True
        assert client.post("/updates/check", json={"force": False}).json()["phase"] == "available"

    def test_a_blocked_host_stops_the_check_with_the_reason(self, web, monkeypatch):
        client, service, github = web
        monkeypatch.setattr(updates, "allow_hosts", lambda gate=None: "api.github.com is blocked in Activity.")
        response = client.post("/updates/check", json={"force": True})
        assert response.status_code == 409 and "blocked" in response.json()["detail"]
        assert github.seen == []

    def test_download_then_the_shell_can_ask_for_the_installer(self, web):
        client, service, github = web
        assert client.get("/updates/installer").status_code == 404
        client.post("/updates/check", json={"force": True})
        client.post("/updates/download")
        service.wait()
        found = client.get("/updates/installer")
        assert found.status_code == 200 and found.json()["tag"] == "v0.1.0-alpha.8"
        assert client.get("/updates/status").json()["ready"] is True

    def test_downloading_with_nothing_newer_is_refused_in_words(self, web):
        client, service, github = web
        response = client.post("/updates/download")
        assert response.status_code == 409 and "no newer" in response.json()["detail"].lower()


class TestAllowingTheHosts:
    class _Gate:
        def __init__(self, policy):
            self.policy = policy

    @pytest.fixture
    def policy(self, tmp_path):
        return EgressPolicy(str(tmp_path / "policy.json"))

    def test_saying_yes_gives_each_host_a_rule(self, policy):
        assert updates.allow_hosts(self._Gate(policy)) is None
        for host in updates.HOSTS:
            assert policy.has_rule(host) and policy.decide(host).mode is Mode.ALLOW

    def test_a_block_the_person_set_is_respected_not_overridden(self, policy):
        policy.set("github.com", Mode.DENY)
        said = updates.allow_hosts(self._Gate(policy))
        assert "github.com" in said and "blocked" in said
        assert policy.decide("github.com").mode is Mode.DENY
        assert not policy.has_rule("api.github.com"), "nothing was allowed while a block stood"

    def test_the_kill_switch_stops_it(self, policy):
        policy.set_kill_switch(True)
        assert "kill switch" in updates.allow_hosts(self._Gate(policy))

    def test_the_hosts_are_only_the_ones_a_release_is_served_from(self):
        assert set(updates.HOSTS) == {
            "api.github.com", "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com",
        }


def test_the_routes_are_mounted(tmp_path, monkeypatch):
    import main

    from core.api_secret import api_secret

    # Its own data folder: status reads and tidies the update folder, and a test
    # must not create one beside somebody's real Spine.
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    updates.reset_shared()
    client = TestClient(main.app, headers={"X-Zaram-Auth": api_secret() or ""})
    assert client.get("/updates/status").status_code == 200
    updates.reset_shared()
