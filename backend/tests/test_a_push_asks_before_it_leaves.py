"""A repository leaves only when the destination has been asked about, by class.

The terminal can run `git push`, and a push made by a command line is invisible
to `EgressGate`, which sees only what the backend sends. Without this a model
with the terminal grant could publish a repository with nothing asked and nothing
logged -- rule 3, broken by a subprocess. `docs/MILESTONES.md` decided pushes go
through the terminal and the OS credential helper so Zaram never holds a
credential; this is the consent that decision left open.

What is asserted is also what is *not* claimed: it reads the command line, and a
test says plainly what that cannot see.
"""

from __future__ import annotations

import subprocess

import pytest

from core.egress import DataClass, EgressDenied, EgressPolicy, Mode
from packs.code.publishing import check_push, find_pushes, host_of
from packs.code.terminal import RUN_IN_TERMINAL, TerminalTools


class TestFindingAPush:
    @pytest.mark.parametrize(
        "command, remote",
        [
            ("git push", None),
            ("git push origin main", "origin"),
            ("git push -u origin feature/x", "origin"),
            ("git push --force-with-lease origin main", "origin"),
            ("git -C sub push origin", "origin"),
            ("git -c core.sshCommand=ssh push upstream main", "upstream"),
            ("git push https://github.com/me/repo.git main", "https://github.com/me/repo.git"),
            ("git push git@github.com:me/repo.git", "git@github.com:me/repo.git"),
            ("npm test && git push origin main", "origin"),
            ("git add . ; git commit -m x; git push", None),
            ("git push -o ci.skip origin", "origin"),
        ],
    )
    def test_it_is_found_wherever_it_is_chained(self, command, remote):
        found = find_pushes(command)
        assert len(found) == 1
        assert found[0].remote == remote

    @pytest.mark.parametrize(
        "command",
        ["git status", "git pull", "git pushd", "mygit push", "git log --oneline", ""],
    )
    def test_things_that_are_not_pushes(self, command):
        assert find_pushes(command) == []

    def test_printing_the_words_errs_toward_asking(self):
        """`echo git push` is the honest false positive of reading a command
        line. It costs a prompt and never a leak, which is the right way round."""
        assert len(find_pushes("echo git push")) == 1

    def test_a_dry_run_is_marked_because_it_sends_nothing(self):
        assert find_pushes("git push --dry-run origin")[0].dry_run is True
        assert find_pushes("git push -n")[0].dry_run is True

    def test_two_pushes_are_two_questions(self):
        assert len(find_pushes("git push origin a && git push backup b")) == 2


class TestWhereItGoes:
    @pytest.mark.parametrize(
        "url, host",
        [
            ("https://github.com/me/repo.git", "github.com"),
            ("https://user:token@GitHub.com/me/repo.git", "github.com"),
            ("ssh://git@gitlab.com/me/repo.git", "gitlab.com"),
            ("git@github.com:me/repo.git", "github.com"),
            ("bitbucket.org:me/repo.git", "bitbucket.org"),
        ],
    )
    def test_a_network_remote_has_a_host(self, url, host):
        assert host_of(url) == host

    @pytest.mark.parametrize(
        "url",
        ["file:///srv/repo.git", "/srv/repo.git", "../sibling", "C:\\work\\repo.git", "C:/work/repo.git", ""],
    )
    def test_a_local_remote_has_none_because_nothing_leaves(self, url):
        assert host_of(url) is None


class _Gate:
    def __init__(self, deny=False):
        self.deny = deny
        self.asked = []

    def check(self, url, **kwargs):
        self.asked.append((url, kwargs))
        if self.deny:
            raise EgressDenied("Zaram blocked a request to github.com.", host="github.com")


@pytest.fixture
def repo(tmp_path):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "T")
    (tmp_path / "f.txt").write_text("x")
    git("add", ".")
    git("commit", "-qm", "a private commit message")
    git("remote", "add", "origin", "https://github.com/me/repo.git")
    git("remote", "add", "local", str(tmp_path / "elsewhere.git"))
    return tmp_path


class TestTheGateIsAsked:
    def test_a_push_asks_with_the_repo_class_and_the_right_host(self, repo):
        gate = _Gate()
        assert check_push("git push origin main", repo, gate=gate) is None
        ((url, kwargs),) = gate.asked
        assert url == "https://github.com/"
        assert kwargs["data_class"] is DataClass.REPO
        assert kwargs["source"] == "code.git_push"

    def test_what_is_logged_is_a_summary_not_the_content(self, repo):
        gate = _Gate()
        check_push("git push origin main", repo, gate=gate)
        body = gate.asked[0][1]["body"]
        assert "to origin" in body
        assert "private commit message" not in body

    def test_a_refusal_comes_back_as_a_sentence_with_the_remedy(self, repo):
        refusal = check_push("git push origin main", repo, gate=_Gate(deny=True))
        assert refusal.startswith("Not run.")
        assert "github.com" in refusal
        assert "Nothing was sent" in refusal

    def test_a_local_remote_asks_nothing(self, repo):
        gate = _Gate()
        assert check_push("git push local main", repo, gate=gate) is None
        assert gate.asked == []

    def test_a_remote_the_repository_does_not_have_is_left_for_git_to_report(self, repo):
        gate = _Gate()
        assert check_push("git push nowhere main", repo, gate=gate) is None
        assert gate.asked == []

    def test_a_dry_run_asks_nothing(self, repo):
        gate = _Gate()
        assert check_push("git push --dry-run origin", repo, gate=gate) is None
        assert gate.asked == []

    def test_no_remote_named_uses_origin_as_git_would(self, repo):
        gate = _Gate()
        check_push("git push", repo, gate=gate)
        assert gate.asked[0][0] == "https://github.com/"

    def test_a_command_that_is_not_a_push_never_touches_the_gate(self, repo):
        gate = _Gate()
        assert check_push("git status", repo, gate=gate) is None
        assert gate.asked == []

    def test_a_url_on_the_command_line_is_asked_about_as_written(self, repo):
        gate = _Gate()
        check_push("git push git@gitlab.com:me/other.git main", repo, gate=gate)
        assert gate.asked[0][0] == "https://gitlab.com/"

    def test_the_first_refused_push_stops_the_second(self, repo):
        gate = _Gate(deny=True)
        check_push("git push origin a && git push origin b", repo, gate=gate)
        assert len(gate.asked) == 1


class TestAgainstTheRealPolicy:
    """No fake gate: the real policy, so the claim in the module docstring is
    checked end to end -- a connected host does not carry repositories."""

    def _gate(self, tmp_path):
        from core.egress import EgressGate
        from core.egress.log import EgressLog

        policy = EgressPolicy(str(tmp_path / "policy.json"))
        return EgressGate(EgressLog(str(tmp_path / "egress.db")), policy), policy

    def test_default_deny_refuses(self, repo, tmp_path):
        gate, _ = self._gate(tmp_path)
        assert check_push("git push origin main", repo, gate=gate).startswith("Not run.")

    def test_allowing_github_for_chat_does_not_allow_a_push(self, repo, tmp_path):
        gate, policy = self._gate(tmp_path)
        policy.set("github.com", Mode.ALLOW)
        # ASK, and the default confirm refuses, so the push is not run.
        assert check_push("git push origin main", repo, gate=gate).startswith("Not run.")

    def test_a_repo_grant_lets_it_through(self, repo, tmp_path):
        gate, policy = self._gate(tmp_path)
        policy.set("github.com", Mode.ALLOW, DataClass.REPO)
        assert check_push("git push origin main", repo, gate=gate) is None


class TestTheTerminalHonoursIt:
    def test_a_refused_push_never_starts_a_shell(self, tmp_path):
        tools = TerminalTools(push_check=lambda command, root: "Not run. Nothing was sent.")
        result = tools.call(RUN_IN_TERMINAL, {"command": "git push"}, tmp_path)
        assert result["error"].startswith("Not run.")
        assert tools._sessions == {}

    def test_an_ordinary_command_is_not_stopped(self, tmp_path):
        seen = []
        tools = TerminalTools(push_check=lambda command, root: seen.append(command) or None)
        tools.session_for = lambda root, create=True: None  # no real shell in a unit test
        result = tools.call(RUN_IN_TERMINAL, {"command": "npm test"}, tmp_path)
        assert seen == ["npm test"]
        assert "could not be started" in result["error"]  # got past the push check

    def test_the_default_check_is_the_real_one(self):
        from packs.code.publishing import check_push as real

        assert TerminalTools()._push_check is real


def test_what_it_cannot_see_is_said_as_a_test():
    """A limit that lives only in a docstring is the kind this codebase has
    learned to distrust. A terminal grant runs arbitrary commands; this makes
    the ordinary route ask and does not claim more."""
    assert find_pushes('sh -c "git push origin main"')  # the words are visible
    assert find_pushes("$p = 'push'; git $p origin") == []  # a built command line is not
