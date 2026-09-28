"""The Spine, from a terminal — and the boundaries it must not cross.

Rule 7 claims the memory outlives the provider *and Zaram itself*. That claim
is much stronger when the memory can be piped, which is what this command is
for: `zaram recall "the Northwind rate" --json | jq`.

Two kinds of test here, and the second kind is the important one.

The first checks the commands work. The second checks what the CLI **refuses
to become**: it is a paired client, `main.PAIRED_CLIENT_ROUTES` is the
allow-list, and its comment is the rule — *"a paired client is a named client
of the memory, not a second owner."* A convenience command must not be the
thing that quietly widens that, so the absence of `ask` and `export` is
asserted rather than left to whoever reads the file next.
"""

from __future__ import annotations

import json

import pytest

typer_testing = pytest.importorskip("typer.testing", reason="the CLI needs typer")

import cli as zaram_cli  # noqa: E402

runner = typer_testing.CliRunner()


class _FakeSpine:
    """Stands in for the HTTP client, so these tests need no running Zaram."""

    def __init__(self, *, facts=None, fail: Exception | None = None) -> None:
        self._facts = facts if facts is not None else []
        self._fail = fail
        self.remembered: list[tuple] = []
        self.corrected: list[tuple] = []

    def _raise(self):
        if self._fail:
            raise self._fail

    def recall(self, query, project=None, limit=6):
        self._raise()
        return {"facts": self._facts}

    def remember(self, text, project=None):
        self._raise()
        self.remembered.append((text, project))
        return {"id": "fact-abcdef123456"}

    def correct(self, fact_id, text):
        self._raise()
        self.corrected.append((fact_id, text))
        return {"id": fact_id, "status": "corrected"}

    def projects(self):
        self._raise()
        return {"projects": [{"id": "keyline", "name": "Keyline", "type": "general"}]}


@pytest.fixture
def spine(monkeypatch):
    fake = _FakeSpine(
        facts=[
            {
                "id": "a59da6c9-e9bb-4309",
                "content": "Keyline pays on 45 days.",
                "origin": "user_document",
                "scope": "project:keyline",
            }
        ]
    )
    monkeypatch.setattr(zaram_cli, "_client", lambda: fake)
    return fake


# --------------------------------------------------------------------------- #
# It works
# --------------------------------------------------------------------------- #


def test_recall_prints_the_fact_and_where_it_came_from(spine):
    """**Provenance is printed, not optional.**

    Rule 2 says an answer that cites nothing is a bug, and a terminal is the
    easiest place in the product to quietly drop the citation because it costs
    a column.
    """
    result = runner.invoke(zaram_cli.app, ["recall", "when does Keyline pay"])
    assert result.exit_code == 0
    assert "Keyline pays on 45 days." in result.stdout
    assert "user_document" in result.stdout, "the origin is the citation"
    assert "keyline" in result.stdout, "the scope says which project it belongs to"


def test_json_goes_to_stdout_and_parses(spine):
    """The piping claim, asserted.

    Everything a person reads goes to stderr precisely so this stream stays
    clean — `zaram recall x --json | jq` must not have a table in it.
    """
    result = runner.invoke(zaram_cli.app, ["recall", "keyline", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed["facts"][0]["id"] == "a59da6c9-e9bb-4309"


def test_remember_stores_the_fact_globally_when_no_project_is_named(spine):
    """Rule 7i read honestly: a fact stated outside any project is not about one.

    Inventing a project for it would be a value nobody entered.
    """
    result = runner.invoke(zaram_cli.app, ["remember", "Keyline pays on 45 days."])
    assert result.exit_code == 0
    assert spine.remembered == [("Keyline pays on 45 days.", None)]


def test_remember_carries_the_project_when_one_is_named(spine):
    runner.invoke(zaram_cli.app, ["remember", "Rate is 620.", "--project", "keyline"])
    assert spine.remembered == [("Rate is 620.", "keyline")]


def test_correct_is_rule_four_from_a_terminal(spine):
    result = runner.invoke(zaram_cli.app, ["correct", "fact-1", "Keyline pays on 60 days."])
    assert result.exit_code == 0
    assert spine.corrected == [("fact-1", "Keyline pays on 60 days.")]


def test_nothing_recalled_says_so_rather_than_printing_an_empty_table(monkeypatch):
    """Rule 9 in the smallest possible place.

    An empty table reads as a broken command; "nothing recalled" reads as an
    answer, and it is the true one.
    """
    monkeypatch.setattr(zaram_cli, "_client", lambda: _FakeSpine(facts=[]))
    result = runner.invoke(zaram_cli.app, ["recall", "something nobody said"])
    assert result.exit_code == 0
    assert "Nothing recalled" in result.stderr


# --------------------------------------------------------------------------- #
# It fails like a command, not like a library
# --------------------------------------------------------------------------- #


def test_an_unreachable_zaram_is_a_sentence_and_a_non_zero_exit(monkeypatch):
    """A stack trace is not a message, and a script needs the exit code."""
    monkeypatch.setattr(
        zaram_cli,
        "_client",
        lambda: _FakeSpine(fail=RuntimeError("Zaram is not reachable at http://127.0.0.1:8420. Is it running?")),
    )
    result = runner.invoke(zaram_cli.app, ["recall", "anything"])
    assert result.exit_code == 1
    assert "Is it running?" in result.stderr
    assert "Traceback" not in result.stderr


def test_an_unpaired_cli_says_how_to_pair_rather_than_how_it_failed(monkeypatch, tmp_path):
    """The first thing a new user hits, so it is the one that must not be a 401."""
    monkeypatch.delenv("ZARAM_CLI_TOKEN", raising=False)
    monkeypatch.setattr(zaram_cli, "_token_path", lambda: tmp_path / "nothing.json")
    result = runner.invoke(zaram_cli.app, ["projects"])
    assert result.exit_code == 2
    assert "zaram pair" in result.stderr


# --------------------------------------------------------------------------- #
# What it must never become
# --------------------------------------------------------------------------- #


def test_the_cli_is_a_client_of_the_memory_and_not_a_second_owner():
    """`ask` and `export` are absent **on purpose**, and this says so.

    Both would need routes outside `main.PAIRED_CLIENT_ROUTES` — `/chat` for
    one, the whole Spine for the other. Adding either means widening that
    allow-list, which is a security decision for the maintainer and not one a
    convenience command gets to make on its way past.

    Asserted rather than trusted to a comment, because the pressure to add
    `zaram ask` is exactly the pressure this boundary exists to survive.
    """
    # Typer leaves `name` unset when the command is named after its function,
    # which is every command here — so the callback's name is the real one.
    commands = {
        command.name or command.callback.__name__
        for command in zaram_cli.app.registered_commands
    }
    assert commands == {"pair", "recall", "remember", "correct", "show", "projects"}
    assert "ask" not in commands
    assert "export" not in commands


def test_every_command_the_cli_offers_is_one_a_paired_client_may_reach():
    """The allow-list is the contract, so the contract is read from it.

    A hand-written list here would drift from `main.py` silently, which is how
    a boundary becomes decorative.
    """
    from main import _paired_client_may

    assert _paired_client_may("POST", "/memory/recall")
    assert _paired_client_may("POST", "/memory")
    assert _paired_client_may("POST", "/memory/abc/correct")
    assert _paired_client_may("GET", "/memory/abc")
    assert _paired_client_may("GET", "/projects")

    # The two the CLI deliberately does not offer.
    assert not _paired_client_may("POST", "/chat")
    assert not _paired_client_may("GET", "/egress")


def test_it_talks_only_to_the_zaram_on_this_machine():
    """`require_loopback` is reused rather than re-implemented.

    `http://127.0.0.1.evil.test` begins like loopback and is not, and a second
    copy of that check is a second place for it to be subtly wrong.
    """
    from zaram_mcp import require_loopback

    assert require_loopback("http://127.0.0.1:8420") == "http://127.0.0.1:8420"
    # `SystemExit`, not a plain exception — it inherits `BaseException`, so
    # `pytest.raises(Exception)` sails straight past it and the test passes
    # while asserting nothing. Naming the real type is the whole value here.
    with pytest.raises(SystemExit):
        require_loopback("http://127.0.0.1.evil.test")
