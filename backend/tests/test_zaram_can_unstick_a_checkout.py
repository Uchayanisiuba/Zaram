"""Zaram can install a project's dependencies, run its own scripts, and start it.

From a transcript on 29 September 2026. Zaram read the repository, started the
app, ran a command, found the true cause — `tsx` missing, and a
`moduleResolution: node` TypeScript 5.4 rejects — and then handed all three
fixes back to the person:

    1. npm install at the project root
    2. npm run db:migrate
    3. npm run dev

**It was not being timid; it had no runner for any of them.** The model is
given `Available runners: {listed}`, saw none of these in it, and did the
honest thing. Three holes:

* `npm install` is not a script. `detect` reads `package.json` → `scripts`,
  and `install` is a subcommand — no runner, no door, not even a locked one.
  Everything downstream was blocked by this one.
* `db:migrate` is a real script filtered out by `_OFFERED_SCRIPTS`, eight
  hardcoded names.
* `dev` is refused correctly, and the refusal never said that `start_app`
  runs exactly what `run_command` will not.

Each test below is one of those, plus the two things the fix must not break:
no shell, and installing is not covered by the project's `runs` tick.
"""
from __future__ import annotations

import json

import pytest

from packs.code.runners import (
    INSTALL_TIMEOUT_SECONDS,
    TIMEOUT_SECONDS,
    CodeRunner,
    detect,
    install_runners,
    is_long_running,
    long_running_scripts,
)
from runtimes.mcp.floors import INSTALL_RUNNER_PREFIX, runner_floor


def node_project(root, scripts: dict, *, lock: str = "") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text(json.dumps({"scripts": scripts}), encoding="utf-8")
    if lock:
        (root / lock).write_text("{}", encoding="utf-8")


@pytest.fixture()
def project(tmp_path):
    """The transcript's repository: a broken checkout with nothing installed."""
    node_project(
        tmp_path,
        {
            "dev": "tsx watch src/index.ts",
            "dev:frontend": "vite",
            "db:migrate": "prisma migrate deploy",
            "db:seed": "tsx scripts/seed.ts",
            "test": "vitest run",
            "deploy": "sst deploy --stage prod",
        },
    )
    return tmp_path


class TestStepOneInstall:
    """`npm install` — the one with no door at all."""

    def test_a_node_project_can_have_its_dependencies_installed(self, project):
        names = [r.name for r in install_runners(project)]
        assert f"{INSTALL_RUNNER_PREFIX}npm" in names

    def test_it_is_offered_to_the_model(self, project):
        # `install_runners` existing is not the claim. `detect` is what builds
        # the list the tool description shows, and a runner missing from there
        # is a runner the model will not name.
        assert f"{INSTALL_RUNNER_PREFIX}npm" in [r.name for r in detect(project)]

    def test_it_gets_longer_than_a_test_suite(self, project):
        """A timeout that kills an install leaves a half-populated
        `node_modules`, which is worse than the wait it avoided."""
        npm = next(r for r in detect(project) if r.name == f"{INSTALL_RUNNER_PREFIX}npm")
        assert npm.timeout == INSTALL_TIMEOUT_SECONDS
        assert npm.timeout > TIMEOUT_SECONDS

    def test_install_rather_than_ci(self, project):
        """`npm ci` refuses outright when the lockfile and package.json
        disagree — which is one of the states it would be called to repair."""
        npm = next(r for r in detect(project) if r.name == f"{INSTALL_RUNNER_PREFIX}npm")
        assert "install" in npm.argv
        assert "ci" not in npm.argv

    def test_nothing_is_offered_for_a_project_that_has_no_manifest(self, tmp_path):
        assert install_runners(tmp_path) == []

    def test_pip_is_offered_only_into_the_project_s_own_virtualenv(self, tmp_path):
        """Installing into a system interpreter because the project has no
        venv is a different and ruder act than the one being permitted."""
        (tmp_path / "requirements.txt").write_text("requests\n", encoding="utf-8")
        assert install_runners(tmp_path) == []

        venv = tmp_path / ".venv" / ("Scripts" if __import__("os").name == "nt" else "bin")
        venv.mkdir(parents=True)
        (venv / ("python.exe" if __import__("os").name == "nt" else "python")).write_text("", encoding="utf-8")
        assert any(r.name == f"{INSTALL_RUNNER_PREFIX}pip" for r in install_runners(tmp_path))


class TestStepTwoTheProjectsOwnScripts:
    """`npm run db:migrate` — a real script that eight hardcoded names hid."""

    def test_a_script_outside_the_known_eight_is_offered(self, project):
        names = [r.name for r in detect(project)]
        assert "npm:db:migrate" in names
        assert "npm:db:seed" in names

    def test_the_well_known_ones_still_come_first(self, project):
        names = [r.name for r in detect(project) if r.name.startswith("npm:")]
        assert names[0] == "npm:test"

    def test_the_order_is_stable(self, project):
        assert [r.name for r in detect(project)] == [r.name for r in detect(project)]


class TestStepThreeTheDevServer:
    """`npm run dev` — refused correctly, and now pointed somewhere."""

    def test_a_namespaced_dev_script_is_still_long_running(self):
        # The regression this change nearly shipped. `_LONG_RUNNING` was an
        # exact match, so `dev:frontend` would have been handed to
        # `run_command` to start Vite, wait three minutes, be killed, and
        # report a failure that was really a stopwatch.
        assert is_long_running("dev:frontend") is True
        assert is_long_running("watch:css") is True
        assert is_long_running("build:desktop") is False
        assert is_long_running("check:release") is False

    def test_they_are_not_offered_to_run_command(self, project):
        names = [r.name for r in detect(project)]
        assert "npm:dev" not in names
        assert "npm:dev:frontend" not in names

    def test_they_are_handed_to_start_app_instead(self, project):
        offered = long_running_scripts(project)
        assert "dev" in offered
        assert "dev:frontend" in offered

    def test_the_refusal_names_the_tool_that_can_run_it(self, project):
        answer = CodeRunner().call({"runner": "npm:dev"}, project)
        assert "start_app" in answer["error"]

    def test_the_tool_description_says_so_too(self, project):
        # Where the model actually reads it, before it has failed once.
        said = CodeRunner().descriptor("code", project).description
        assert "start_app" in said


class TestWhatMustNotHaveChanged:
    def test_installing_always_asks_whatever_is_granted(self):
        """The one runner whose payload comes from a registry rather than
        from the repository the person already trusted, and the one the tier
        table's undo cannot reach."""
        floor = runner_floor("run_command", {"runner": f"{INSTALL_RUNNER_PREFIX}npm"})
        assert floor is not None
        assert floor.verdict == "confirm"
        assert floor.grantable is False

    def test_something_that_leaves_this_machine_always_asks(self):
        for name in ("npm:deploy", "npm:publish", "make:release"):
            floor = runner_floor("run_command", {"runner": name})
            assert floor is not None, name
            assert floor.grantable is False, name

    def test_an_ordinary_script_is_covered_by_the_project_grant(self):
        # Otherwise the widening above becomes forty dialogs a day, which is
        # the product nobody opens on the second day.
        for name in ("npm:test", "npm:db:migrate", "pytest", "tsc"):
            assert runner_floor("run_command", {"runner": name}) is None, name

    def test_a_floor_never_applies_to_a_tool_it_was_not_asked_about(self):
        assert runner_floor("read_lines", {"runner": "install:npm"}) is None

    def test_there_is_still_no_shell(self, project):
        """Every runner is a whole command chosen from a detected list. The
        floors module's own line: shell safety here was solved by not having
        a shell, and widening the list of nouns is not accepting a verb."""
        for runner in detect(project):
            assert isinstance(runner.argv, tuple)
            joined = " ".join(runner.argv)
            for shellish in (";", "&&", "||", "|", ">", "`", "$("):
                assert shellish not in joined, f"{runner.name}: {joined}"

    def test_an_unknown_runner_is_still_refused(self, project):
        answer = CodeRunner().call({"runner": "npm:whatever"}, project)
        assert "no runner called" in answer["error"]
