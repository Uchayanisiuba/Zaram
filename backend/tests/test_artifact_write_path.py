"""The write path can create files and nothing else.

CLAUDE.md: generated files go to a dedicated output directory, never overwrite
silently, and the write path has **no delete or overwrite capability at all**.

That last clause is why this file scans the source as well as exercising the
behaviour. A behavioural test proves the code did not delete anything this time;
a source scan proves it cannot. The capability existing is the violation — the
module it replaced had `delete()` and an `update()` that `setattr`'d any
attribute, and nothing called either, and it was still wrong.

Same enforcement shape as `test_egress_chokepoint.py`, for the same reason: it
must fail on the commit that introduces the capability rather than at runtime on
somebody's machine, by which point a file is already gone.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from artifacts.store import (
    MAX_COLLISION_ATTEMPTS,
    ArtifactStore,
    CollisionLimit,
    UnsafeFilename,
    sanitise_filename,
)

STORE_SOURCE = Path(__file__).resolve().parents[1] / "artifacts" / "store.py"

#: Anything that can unmake a file.
FORBIDDEN_CALLS = {
    ("os", "remove"),
    ("os", "unlink"),
    ("os", "rmdir"),
    ("os", "replace"),
    ("os", "rename"),
    ("shutil", "rmtree"),
    ("shutil", "move"),
    ("shutil", "copyfile"),
    ("Path", "unlink"),
    ("Path", "rmdir"),
    ("Path", "replace"),
    ("Path", "rename"),
    ("Path", "write_bytes"),
    ("Path", "write_text"),
}

#: Open modes that truncate or append to something already there.
DESTRUCTIVE_MODES = {"w", "wb", "w+", "wb+", "a", "ab", "a+", "ab+", "r+", "rb+"}


def _dotted(node: ast.AST) -> tuple[str, ...]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return tuple(reversed(parts))


@pytest.fixture(scope="module")
def store_tree() -> ast.AST:
    return ast.parse(STORE_SOURCE.read_text(encoding="utf-8"), filename=str(STORE_SOURCE))


class TestTheCapabilityDoesNotExist:
    def test_no_function_named_like_a_deletion(self, store_tree):
        """Not "we do not call delete" — there is no delete to call."""
        offenders = [
            node.name
            for node in ast.walk(store_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(
                word in node.name.lower()
                for word in ("delete", "remove", "unlink", "overwrite", "replace", "purge")
            )
        ]

        assert not offenders, (
            f"The write path defines {offenders}. CLAUDE.md requires it to have no "
            "delete or overwrite capability at all — a capability that exists is "
            "the violation, whether or not anything calls it."
        )

    def test_no_destructive_call_anywhere_in_the_module(self, store_tree):
        offenders: list[str] = []
        for node in ast.walk(store_tree):
            if not isinstance(node, ast.Call):
                continue
            dotted = _dotted(node.func)
            if len(dotted) >= 2 and dotted[-2:] in FORBIDDEN_CALLS:
                offenders.append(f"line {node.lineno}: {'.'.join(dotted)}")

        assert not offenders, (
            "These can unmake a file:\n  " + "\n  ".join(offenders)
        )

    def test_no_open_mode_can_truncate(self, store_tree):
        """`xb` is the guarantee. Any other write mode discards it.

        Check-then-write with `wb` would pass every behavioural test in this
        file and still lose a document to a race between two generations of the
        same name.
        """
        offenders: list[str] = []
        for node in ast.walk(store_tree):
            if not isinstance(node, ast.Call):
                continue
            dotted = _dotted(node.func)
            if not dotted or dotted[-1] != "open":
                continue

            mode = None
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value

            if mode in DESTRUCTIVE_MODES:
                offenders.append(f"line {node.lineno}: open(..., {mode!r})")

        assert not offenders, (
            "Destructive open modes in the write path:\n  "
            + "\n  ".join(offenders)
            + "\n\nUse 'xb' — create-or-fail, atomically."
        )


class TestCollisionsIncrement:
    def test_a_second_file_of_the_same_name_does_not_replace_the_first(self, tmp_path):
        store = ArtifactStore(tmp_path)

        first = store.write_new("proposal.docx", b"original")
        second = store.write_new("proposal.docx", b"different")

        assert first != second
        assert first.read_bytes() == b"original", "the first file was overwritten"
        assert second.name == "proposal-2.docx"

    def test_incrementing_continues_past_the_second(self, tmp_path):
        store = ArtifactStore(tmp_path)
        names = [store.write_new("report.pdf", b"x").name for _ in range(4)]

        assert names == ["report.pdf", "report-2.pdf", "report-3.pdf", "report-4.pdf"]

    def test_a_name_with_no_extension_still_increments(self, tmp_path):
        store = ArtifactStore(tmp_path)
        store.write_new("NOTES", b"a")

        assert store.write_new("NOTES", b"b").name == "NOTES-2"

    def test_it_asks_rather_than_inventing_forever(self, tmp_path):
        """The "or asks" half. An unbounded loop is a hang, not a policy."""
        store = ArtifactStore(tmp_path)
        for _ in range(MAX_COLLISION_ATTEMPTS):
            store.write_new("same.txt", b"x")

        with pytest.raises(CollisionLimit):
            store.write_new("same.txt", b"x")


class TestPathConfinement:
    """A security boundary, not tidiness.

    The *model* proposes filenames, so a traversal payload is an input that will
    arrive eventually rather than a hypothetical.
    """

    @pytest.mark.parametrize(
        "payload",
        [
            "../../.ssh/config",
            "../../../etc/passwd",
            "..\\..\\Windows\\System32\\drivers\\etc\\hosts",
            "/etc/shadow",
            "C:\\Windows\\win.ini",
            "C:notes.txt",
            "subdir/../../escape.txt",
            "....//....//escape.txt",
        ],
    )
    def test_traversal_payloads_cannot_escape(self, tmp_path, payload):
        store = ArtifactStore(tmp_path / "out")

        written = store.write_new(payload, b"payload")

        assert store.root in written.parents, f"{payload!r} escaped to {written}"
        assert written.parent == store.root, "wrote into a subdirectory"

    def test_nothing_outside_the_root_is_touched(self, tmp_path):
        outside = tmp_path / "secret.txt"
        outside.write_bytes(b"untouched")
        store = ArtifactStore(tmp_path / "out")

        store.write_new("../secret.txt", b"overwritten!")

        assert outside.read_bytes() == b"untouched"

    @pytest.mark.parametrize("payload", ["", "   ", "...", "/", "\\", "../.."])
    def test_names_with_nothing_usable_are_refused(self, tmp_path, payload):
        store = ArtifactStore(tmp_path)

        with pytest.raises(UnsafeFilename):
            store.write_new(payload, b"x")


class TestSanitising:
    def test_separators_are_removed_before_anything_else(self):
        """Order matters, and getting it wrong is safe only by accident.

        Stripping illegal characters first turns "../../etc/passwd" into
        "....etcpasswd" — contained, but by coincidence. Taking the basename
        first is contained by construction, and stays contained when the
        illegal-character set changes.
        """
        assert "/" not in sanitise_filename("a/b/c.txt")
        assert sanitise_filename("../../etc/passwd") == "passwd"

    def test_windows_reserved_names_are_escaped(self):
        for reserved in ("CON", "nul.txt", "COM1.docx"):
            assert sanitise_filename(reserved).startswith("_")

    def test_trailing_dots_and_spaces_go(self):
        """Windows silently strips them, which would change the name *after*
        the collision check and defeat the exclusive create."""
        assert sanitise_filename("report.docx. ") == "report.docx"

    def test_a_long_name_is_truncated_but_keeps_its_extension(self):
        result = sanitise_filename("x" * 400 + ".docx")

        assert len(result) <= 120
        assert result.endswith(".docx")
