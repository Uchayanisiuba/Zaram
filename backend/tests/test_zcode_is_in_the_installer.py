"""ZCode ships, can start, and its dependencies are declared.

ZCode worked in a checkout and was in no installer ever built. Three separate
things were wrong, none of them visible from inside the repository:

1. **`zcode.cmd` was not in the payload at all.** `files:` lists `electron`,
   `desktop/dist`, `frontend/dist`, `package.json` and the backend globs; a
   script at the repository root matched none of them.
2. **It pointed at `backend\\venv`**, which exists only in a checkout. A
   packaged install has the bundled interpreter at `resources/runtime` and the
   backend unpacked out of the asar.
3. **`typer` and `rich` were never declared.** `cli.py` imports both, neither
   was in `requirements.txt`, and the runtime builder installs from
   `requirements.txt` — so the packaged interpreter had no typer. Running it
   is what found it:

       ModuleNotFoundError: No module named 'typer'

The third is the one worth a test rather than a fix, and `check:runtime` shows
why. It verifies every pin in `requirements.txt` is met, and it passed
throughout — correctly, because an undeclared import is not a pin. The guard
was not broken; it was never given the fact. `TestEveryImportIsDeclared`
supplies it, and it generalises: any future import added to `cli.py` has to be
pinned or this fails, whatever the module is.

`CLAUDE.md`'s working agreement is the frame for all three — *assume
unreachable until the caller is seen*, and *a number without its condition is
not a measurement*. "It works" measured in a checkout said nothing about the
thing users install.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from tests.test_installer_payload import is_excluded, load_patterns  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
CONFIG = REPO_ROOT / "electron-builder.yml"
LAUNCHER = REPO_ROOT / "zcode.cmd"
REQUIREMENTS = BACKEND / "requirements.txt"
NSH = REPO_ROOT / "build" / "installer.nsh"


def pinned_names() -> set[str]:
    """Every distribution named in `requirements.txt`, normalised.

    PyPI treats `-`, `_` and `.` as equivalent and is case-insensitive, so
    `markdown-it-py`, `typing_extensions` and `Pygments` all have to compare
    equal to the import names they provide.
    """
    names: set[str] = set()
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("==")[0].split(">=")[0].split("[")[0].strip()
        if name:
            names.add(name.lower().replace("_", "-").replace(".", "-"))
    return names


def third_party_imports(module: Path) -> set[str]:
    """Top-level modules `module` imports that are neither stdlib nor ours.

    Read with `ast` rather than by importing: importing `cli` pulls in typer,
    which is the thing under test, and a test that cannot run until the bug is
    fixed cannot report the bug.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])

    def is_ours(name: str) -> bool:
        return (BACKEND / name).is_dir() or (BACKEND / f"{name}.py").is_file()

    return {
        name
        for name in roots
        if name not in sys.stdlib_module_names and not is_ours(name)
    }


#: The import name each distribution provides, where the two differ. Only the
#: ones ZCode actually reaches; a general mapping would be a package index.
IMPORT_TO_DISTRIBUTION = {
    "rich": "rich",
    "typer": "typer",
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
    "PIL": "pillow",
}


class TestEveryImportIsDeclared:
    """The guard that was missing. `typer` was the cost of not having it."""

    def test_cli_imports_something_third_party(self):
        """A sanity check on the instrument before its result is read.

        If the parser silently returned nothing, the test below would pass on
        an empty set and report a guarantee it never checked — which is the
        assertion-free test `CLAUDE.md` calls worse than no test.
        """
        assert third_party_imports(BACKEND / "cli.py"), (
            "parsed no third-party imports from cli.py — the parser is broken, "
            "not the dependency list"
        )

    def test_every_third_party_import_is_pinned(self):
        pins = pinned_names()
        missing = sorted(
            name
            for name in third_party_imports(BACKEND / "cli.py")
            if IMPORT_TO_DISTRIBUTION.get(name, name).lower().replace("_", "-")
            not in pins
        )
        assert not missing, (
            f"cli.py imports {missing}, which requirements.txt does not pin. "
            "The bundled runtime installs from requirements.txt, so ZCode "
            "would work here and fail on every install."
        )

    @pytest.mark.parametrize("distribution", ["typer", "rich"])
    def test_the_two_that_were_missing_stay_pinned(self, distribution):
        assert distribution in pinned_names()


class TestTheLauncherShips:
    def test_it_is_carried_as_an_extra_file(self):
        """`extraFiles`, so it lands at the install root and not under
        `resources` — the root is the directory put on PATH."""
        config = CONFIG.read_text(encoding="utf-8")
        extra = config.split("extraFiles:", 1)
        assert len(extra) == 2, "electron-builder.yml has no extraFiles section"
        assert "zcode.cmd" in extra[1].split("extraMetadata:", 1)[0]

    def test_it_is_not_swept_up_by_the_backend_allow_list(self):
        """The launcher is not backend content and must not rely on being.

        `files:` is the allow-list that keeps the Spine out of the installer.
        A root script arriving through it would mean that list had grown a
        hole wide enough for a root script.
        """
        includes, _ = load_patterns()
        assert not any("zcode" in pattern for pattern in includes)


class TestTheLauncherKnowsBothLayouts:
    """Read off the file, because the packaged paths cannot be guessed.

    Verified against a real build on 29 September 2026:
    `resources/runtime/python.exe` and
    `resources/app.asar.unpacked/backend/cli.py` both exist in
    `dist-electron/win-unpacked`.
    """

    @pytest.mark.parametrize(
        "fragment",
        [
            r"resources\runtime\python.exe",     # packaged interpreter
            r"resources\app.asar.unpacked\backend",  # packaged backend
            r"backend\venv\Scripts\python.exe",  # a checkout
            "ZARAM_PYTHON",                      # named outright, and first
        ],
    )
    def test_the_launcher_names_it(self, fragment):
        assert fragment in LAUNCHER.read_text(encoding="utf-8")

    def test_path_is_not_a_fallback(self):
        """Falling back to any Python on PATH is worse than failing.

        It will not carry Zaram's dependencies, so the failure arrives later
        and reads as a broken product. `backendLauncher.js` refuses for the
        same reason and the two must not drift.
        """
        text = LAUNCHER.read_text(encoding="utf-8")
        run_lines = [
            line for line in text.splitlines()
            if line.strip().startswith('"%ZCODE_PYTHON%"')
        ]
        assert run_lines, "the launcher never runs an interpreter"
        assert 'python -m cli' not in text, "a bare `python` is a PATH fallback"


class TestTheThreeFilesThatShouldNeverHaveShipped:
    """Audited against a built tree on 29 September 2026, not against config.

    `character.json` and `characters.json` carry the eight named personas —
    *"You are Baba, a wise Nigerian elder..."*. `CLAUDE.md` records them as
    removed on 13 August 2026 because each makes a rival identity claim, and
    they were removed from the code and left on disk, where
    `backend/**/*.json` published them in every installer since. Dead as well
    as forbidden: `set_personality_source` has no caller outside tests.

    `conftest.py` is pytest scaffolding that imports `starlette.testclient`.
    """

    @pytest.mark.parametrize(
        "path",
        ["backend/character.json", "backend/characters.json", "backend/conftest.py"],
    )
    def test_it_is_excluded(self, path):
        _, excludes = load_patterns()
        assert is_excluded(path, excludes), f"{path} would ship"

    def test_no_named_persona_survives_anywhere_reachable(self):
        """The files may still sit in the checkout; nothing may read them.

        This is the assertion that matters if somebody restores the files: the
        rule is about what the model is told, not about which paths exist.
        """
        callers = [
            p
            for p in BACKEND.rglob("*.py")
            # The cheap tests first, and the virtualenv excluded: this read every Python
            # file under `backend/`, `venv/` included, which is tens of thousands of
            # files and about three minutes of every full run -- and a file inside
            # site-packages is not Zaram's code, so it could neither satisfy nor
            # violate a rule about what Zaram wires.
            if "venv" not in p.parts
            and "site-packages" not in p.parts
            and "tests" not in p.parts
            and p.name != "registry.py"
            and "set_personality_source(" in p.read_text(encoding="utf-8", errors="ignore")
        ]
        assert not callers, (
            f"{[str(p) for p in callers]} wires a personality source; the named "
            "personas would reach the model again"
        )


class TestUninstallDoesNotBreakAnUpgrade:
    def test_removing_from_path_is_guarded_by_is_updated(self):
        """electron-builder runs the old uninstaller during an upgrade.

        An unguarded removal would strip the PATH entry on every update, and
        restore it only if the new install's `customInstall` happened to win
        the race. The data question is guarded for the same reason and this
        sits inside the same block.
        """
        text = NSH.read_text(encoding="utf-8")
        body = text.split("!macro customUnInstall", 1)[1]
        guard = body.index("${ifNot} ${isUpdated}")
        removal = body.index("customRemoveFromPath")
        assert guard < removal, "PATH removal runs outside the isUpdated guard"


class TestTheInstallerScriptCompiles:
    """The collision class that cost a build, caught in milliseconds instead.

    `installer.nsh` defined `HWND_BROADCAST` behind an `!ifndef`, which reads
    as the careful choice and is exactly backwards. electron-builder includes
    this file *before* `WinMessages.nsh`, so the guard succeeded, the name got
    defined, and then `WinMessages.nsh` line 82 did an unguarded `!define` of
    the same name and makensis aborted:

        !include: error in script: "...\Include\WinMessages.nsh" on line 82

    The guard protected this file from a collision it could not have and
    caused one it could. Prefixed names cannot collide in either order, and
    the rule generalises to every constant added here later.
    """

    #: Names NSIS's own headers define. Not exhaustive and does not need to
    #: be — the prefix rule below is the real guard, and this is the specific
    #: one that has already bitten.
    NSIS_OWNS = {"HWND_BROADCAST", "WM_WININICHANGE", "WM_SETTINGCHANGE"}

    def _defines(self) -> list[str]:
        import re

        return re.findall(
            r"^\s*!define\s+(\w+)", NSH.read_text(encoding="utf-8"), re.MULTILINE
        )

    def test_it_defines_something(self):
        assert self._defines(), "no !define found — the parser or the file moved"

    def test_nothing_shadows_a_name_nsis_owns(self):
        clashes = sorted(set(self._defines()) & self.NSIS_OWNS)
        assert not clashes, (
            f"{clashes} is defined by an NSIS header too. This file is included "
            "first, so makensis aborts when the header redefines it — an "
            "!ifndef guard here makes it worse, not better."
        )

    def test_every_define_is_namespaced(self):
        loose = sorted(
            name
            for name in self._defines()
            if not name.startswith(("ZCODE_", "ZARAM_"))
        )
        assert not loose, (
            f"{loose} is not prefixed. Anything this file defines shares a "
            "namespace with every NSIS header electron-builder includes after "
            "it, and a redefinition there is a build error."
        )
