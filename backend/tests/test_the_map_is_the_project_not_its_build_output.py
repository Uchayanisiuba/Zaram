"""The repository map shows the project, not what the project compiles to.

Reported 3 October 2026, with a screenshot. A coding project open on a real
Unreal plugin, the question *"do an audit on this project"*, and the reply:

    I cannot perform a full audit of the project because I don't have the
    specific project details or files in my current context.

**The model was right.** The map it had been given held 37 files and all 37
were under `Build/` — packaged output, triplicated across three staging
copies — with no source, no `Docs/`, no `README.md`. 1,410 files on disk and
**47 that are actually the project**; it had been shown none of them.

Two defects stacked, and the second is the familiar one:

* `SKIP_DIRS` holds `build`. Unreal writes `Build`. The comparison was a
  case-sensitive `in`, so on a filesystem that does not care about case the
  whole tree walked straight in. A one-character bug, invisible on the
  maintainer's own repositories, fatal on somebody else's.
* `_walk` stops at `MAX_FILES` in **alphabetical order**. `Build` sorts before
  `Docs`, `Keyline` and `README.md`, so the budget was spent long before the
  walk reached anything real. Which files the model is allowed to see was
  decided by which directory sorts first — membership settled by something
  that is not relevance, which is the error this codebase has now paid for
  four times.

**The fix asks git**, rather than lengthening a list of directory names.
`.gitignore` is the one authoritative statement of *"this is not source"*
that a repository already contains, and the author of this one had written
`Build/` in it. A hand-maintained skip list is a denylist: it fails open on
the next repository that names its output something new, which is exactly
what happened here. `test_no_store_is_one_add_from_being_published.py` made
the same move for the same reason — ask git, do not re-implement it.

The walk stays, for a directory that is not a repository.
"""

from __future__ import annotations

import subprocess

import pytest

from packs.code import repo_map


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture
def project(tmp_path):
    """A repository shaped like the one that failed: a little source, and a
    great deal of build output that its own `.gitignore` disclaims."""
    (tmp_path / ".gitignore").write_text("Build/\nTestBed/\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# The project", encoding="utf-8")

    source = tmp_path / "Keyline" / "Source"
    source.mkdir(parents=True)
    # The Unreal form, which is also the one that was read wrongly: the
    # dllexport macro sits exactly where the class name goes.
    (source / "KeylineIK.h").write_text(
        "class KEYLINE_API FKeylineIK\n{\n};\n", encoding="utf-8"
    )
    (source / "KeylinePose.h").write_text(
        "class FKeylinePose\n{\n};\n", encoding="utf-8"
    )

    # Enough staged copies to swallow the map, under a name that sorts first
    # and differs from `SKIP_DIRS` only by its capital.
    for copy in ("KeylineEd", "KeylineM2b", "KeylineM3a"):
        out = tmp_path / "Build" / copy / "Plugins" / "Keyline" / "Source"
        out.mkdir(parents=True)
        for n in range(200):
            (out / f"Generated{n:03d}.cpp").write_text("void Nothing() {}\n", encoding="utf-8")

    git("init", cwd=tmp_path)
    git("add", "-A", cwd=tmp_path)
    git("-c", "user.email=t@t", "-c", "user.name=T", "commit", "-m", "x", cwd=tmp_path)
    repo_map._cache.clear()
    return tmp_path


@pytest.fixture(autouse=True)
def no_cache():
    repo_map._cache.clear()
    yield
    repo_map._cache.clear()


def paths_in(text: str) -> list[str]:
    """The file paths in a rendered map — the unindented lines that are not
    prose. Definitions are indented two spaces."""
    return [
        line
        for line in text.splitlines()
        if line
        and not line.startswith(" ")
        and not line.startswith("#")
        and not line.startswith("Files in the repository")
        and not line.startswith("(")
    ]


class TestWhatTheModelIsShown:
    def test_the_source_is_in_the_map(self, project):
        shown = paths_in(repo_map.repo_map(project, "do an audit", budget_tokens=2000))
        assert "Keyline/Source/KeylineIK.h" in shown
        assert "Keyline/Source/KeylinePose.h" in shown

    def test_the_build_output_is_not(self, project):
        """The whole report, in one assertion."""
        shown = paths_in(repo_map.repo_map(project, "do an audit", budget_tokens=2000))
        assert not [p for p in shown if p.startswith("Build/")], (
            "the map is showing what the project compiles to instead of the "
            "project; its own .gitignore says Build/ is not source"
        )

    def test_a_tight_budget_still_spends_it_on_source(self, project):
        """The failure was a budget spent before the walk reached anything
        real, so a small budget is the case that has to hold."""
        shown = paths_in(repo_map.repo_map(project, "do an audit", budget_tokens=60))
        assert shown
        assert all(not p.startswith("Build/") for p in shown)

    def test_definitions_still_come_through(self, project):
        """Lifting the file-reading out of `_walk` must not lose them."""
        text = repo_map.repo_map(project, "ik solver", budget_tokens=2000)
        assert "FKeylineIK" in text

    def test_the_class_name_is_the_class_not_the_export_macro(self, project):
        """The second defect the same repository showed.

        `class KEYLINE_API FKeylineIK` captured `KEYLINE_API`, so the map
        listed the macro once per header instead of the class names — a
        symbol list that says the same word thirty times tells a model
        nothing.
        """
        text = repo_map.repo_map(project, "ik solver", budget_tokens=2000)
        assert "KEYLINE_API" not in text


class TestItAsksGitRatherThanGuessing:
    def test_a_file_the_author_ignores_is_absent_whatever_it_is_called(self, project):
        """The reason this is not another entry in a list of directory names.

        A skip list is a denylist and fails open on the next repository that
        names its output something nobody predicted. `.gitignore` is the
        statement the author already wrote.
        """
        (project / ".gitignore").write_text("Build/\nTestBed/\nWhatever/\n", encoding="utf-8")
        odd = project / "Whatever"
        odd.mkdir()
        (odd / "Nobody.cpp").write_text("void X() {}\n", encoding="utf-8")
        repo_map._cache.clear()
        shown = paths_in(repo_map.repo_map(project, "x", budget_tokens=2000))
        assert "Whatever/Nobody.cpp" not in shown

    def test_a_new_file_nobody_has_committed_is_present(self, project):
        """`--others --exclude-standard`, not `--cached`.

        On a coding project the file written five minutes ago is the one most
        likely to be the question, and listing only tracked files would hide
        it.
        """
        (project / "Keyline" / "Source" / "Fresh.cpp").write_text(
            "void JustWritten() {}\n", encoding="utf-8"
        )
        repo_map._cache.clear()
        shown = paths_in(repo_map.repo_map(project, "fresh", budget_tokens=2000))
        assert "Keyline/Source/Fresh.cpp" in shown


class TestADirectoryThatIsNotARepository:
    """The walk is still there, and still has to work.

    Somebody opens a folder of scripts that was never `git init`-ed, and the
    map must not be empty — a fallback that silently returns nothing is worse
    than the bug it replaced.
    """

    @pytest.fixture
    def loose(self, tmp_path):
        (tmp_path / "tool.py").write_text("def run():\n    pass\n", encoding="utf-8")
        (tmp_path / "helper.py").write_text("def helpful():\n    pass\n", encoding="utf-8")
        return tmp_path

    def test_it_still_maps(self, loose):
        shown = paths_in(repo_map.repo_map(loose, "run", budget_tokens=2000))
        assert "tool.py" in shown
        assert "helper.py" in shown

    def test_git_not_being_installed_is_not_a_blank_map(self, loose, monkeypatch):
        """`_git_listed` answers `None` and the walk takes over."""
        def no_git(*args, **kwargs):
            raise OSError("git is not on this machine")

        monkeypatch.setattr(repo_map.subprocess, "run", no_git)
        repo_map._cache.clear()
        assert "tool.py" in paths_in(repo_map.repo_map(loose, "run", budget_tokens=2000))

    def test_the_skip_list_is_matched_without_case(self, tmp_path):
        """The one-character half of the defect, on the fallback path.

        `SKIP_DIRS` holds `build`; Unreal writes `Build`; `in` is case
        sensitive and Windows is not.
        """
        (tmp_path / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")
        for name in ("Build", "DIST", "Node_Modules"):
            d = tmp_path / name
            d.mkdir()
            (d / "artefact.py").write_text("def nope():\n    pass\n", encoding="utf-8")
        repo_map._cache.clear()
        shown = paths_in(repo_map.repo_map(tmp_path, "main", budget_tokens=2000))
        assert "main.py" in shown
        assert not [p for p in shown if "/" in p], shown
