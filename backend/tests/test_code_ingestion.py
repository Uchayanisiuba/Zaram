"""A repository can enter the Spine, and a retrieved slice can be opened.

The first test is the one that matters, and it is a regression test for a
feature that was never built: **a repository pointed at Knowledge indexed its
README and skipped every file the project is made of.** `PlainTextParser`
claims `.md`, `.json` and `.yaml`; nothing claimed `.py`, `.ts` or `.go`. So
"ask Zaram about this codebase" retrieved documentation, answered thinly, and
looked like weak recall when it was an empty index.

The rest are about what a *slice* has to be, because a coding agent is only as
good as the passage it is handed. Whole lines, a whole definition where one
fits, and a line range that can be opened in an editor — without the last one,
provenance for code is `readiness.py, somewhere`, which cannot be checked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ingest.parsers import parsers_for, supported_suffixes
from ingest.parsers.code import CodeParser, looks_generated
from ingest.service import CHUNK_CHARS, chunk_code, discover, parse_file

PYTHON = '''"""A module docstring, which belongs to no function."""

import os


def first(value):
    """Does a thing."""
    return value + 1


def second(value):
    return value * 2


class Holder:
    def method(self):
        return None
'''


class TestARepositoryIsReadableAtAll:
    def test_source_suffixes_are_supported(self):
        """The gap this whole file exists for."""
        for suffix in (".py", ".ts", ".tsx", ".go", ".rs", ".java", ".sql"):
            assert suffix in supported_suffixes(), suffix

    def test_prose_suffixes_did_not_change_hands(self):
        """`.md` and `.json` stay with plaintext. Two parsers claiming one
        suffix is an ambiguity resolved by list order, which is not a thing to
        rely on."""
        assert [p.name for p in parsers_for(".md")] == ["plaintext"]
        assert [p.name for p in parsers_for(".json")] == ["plaintext"]
        assert [p.name for p in parsers_for(".py")] == ["code"]

    def test_a_python_file_in_a_folder_is_discovered(self, tmp_path):
        """`discover` is what the folder scan walks with. A parser nothing
        discovers is the unreachable-subsystem failure in miniature."""
        (tmp_path / "app.py").write_text(PYTHON, encoding="utf-8")
        (tmp_path / "notes.md").write_text("# Notes", encoding="utf-8")

        found = {p.name for p in discover(tmp_path)}

        assert found == {"app.py", "notes.md"}

    def test_the_walk_still_skips_machine_written_directories(self, tmp_path):
        """A repository holds a `venv` and a `node_modules`, and indexing them
        would bury the user's own code under its dependencies."""
        (tmp_path / "app.py").write_text(PYTHON, encoding="utf-8")
        for junk in ("venv", "node_modules", "__pycache__"):
            (tmp_path / junk).mkdir()
            (tmp_path / junk / "buried.py").write_text(PYTHON, encoding="utf-8")

        assert [p.name for p in discover(tmp_path)] == ["app.py"]

    def test_a_source_file_parses_to_its_own_text(self, tmp_path):
        path = tmp_path / "app.py"
        path.write_text(PYTHON, encoding="utf-8")

        result, reason, _ = parse_file(path)

        assert reason == ""
        assert result is not None
        assert result.parser == CodeParser.name
        assert result.text == PYTHON
        assert result.detail["language"] == "py"


class TestWhatASliceLooksLike:
    def test_it_never_splits_inside_a_line(self):
        """A chunk ending halfway through a condition is not shorter, it is
        wrong — and a model reading it completes the thought itself."""
        chunks = chunk_code(PYTHON)
        source = PYTHON.splitlines()

        for piece in chunks:
            for line in piece.text.splitlines():
                assert line in source

    def test_the_line_range_maps_back_to_the_file(self):
        """The property that makes `readiness.py:156-181` checkable."""
        lines = PYTHON.splitlines()

        for piece in chunk_code(PYTHON):
            quoted = "\n".join(lines[piece.start_line - 1 : piece.end_line])
            assert piece.text == quoted, piece.citation

    def test_line_numbers_are_one_based_and_ordered(self):
        chunks = chunk_code(PYTHON)

        assert chunks[0].start_line == 1
        for piece in chunks:
            assert piece.start_line <= piece.end_line
        for earlier, later in zip(chunks, chunks[1:]):
            assert later.start_line > earlier.end_line, "chunks overlap"

    def test_a_short_function_arrives_whole_with_its_signature(self):
        """A body retrieved without its `def` line is anonymous, and the model
        has to guess what it was reading."""
        joined = "\n\n".join(piece.text for piece in chunk_code(PYTHON))

        assert "def first(value):" in joined
        assert "return value + 1" in joined
        # And in the same piece, not split across two.
        holding = [p for p in chunk_code(PYTHON) if "return value + 1" in p.text]
        assert "def first(value):" in holding[0].text

    def test_nothing_is_duplicated_across_chunks(self):
        """Prose chunks overlap so a straddling sentence stays findable. Code
        must not: the same function in two facts is the duplicate-citation
        failure rule 7d exists to prevent, arriving through the chunker."""
        pieces = chunk_code(PYTHON)
        seen = [line for piece in pieces for line in piece.text.splitlines()]

        assert len(seen) == len(set(seen)) or all(
            seen.count(line) == 1 for line in seen if line.strip()
        )

    def test_the_header_above_the_first_definition_is_kept(self):
        """Imports and the module docstring belong to no function and are often
        the most useful passage in the file."""
        first = chunk_code(PYTHON)[0]

        assert "import os" in first.text

    def test_a_passage_names_every_definition_it_contains(self):
        """Not just the one it opens on. Small definitions are merged, and a
        chunk holding `first`, `second` and `Holder` captioned only `first` is
        wrong about its own contents — which is worse than being unlabelled."""
        named = {name for piece in chunk_code(PYTHON) for name in piece.symbols}

        assert {"first", "second", "Holder"} <= named


class TestSomethingTooLongToHandOverWhole:
    def _long_function(self) -> str:
        body = "\n".join(f"    step_{n} = compute({n})" for n in range(400))
        return f"def enormous():\n{body}\n    return None\n"

    def test_it_is_split_rather_than_truncated(self):
        source = self._long_function()

        chunks = chunk_code(source)

        assert len(chunks) > 1
        assert all(len(piece.text) <= CHUNK_CHARS + 200 for piece in chunks)

    def test_every_line_survives_the_split(self):
        """Truncation is the failure that would be invisible: the chunks look
        fine and the middle of the function is simply gone."""
        source = self._long_function()
        expected = [line for line in source.splitlines() if line.strip()]

        kept = [
            line
            for piece in chunk_code(source)
            for line in piece.text.splitlines()
            if line.strip()
        ]

        assert kept == expected

    def test_each_piece_still_says_which_function_it_is(self):
        for piece in chunk_code(self._long_function()):
            assert piece.symbols == ("enormous",)

    def test_a_file_with_no_recognisable_definition_still_chunks(self):
        """A language none of the patterns match must degrade to whole lines,
        not to nothing. This is why the pattern list is allowed to be short."""
        source = "\n".join(f"SET @row_{n} = {n};" for n in range(300))

        chunks = chunk_code(source)

        assert chunks
        assert all(piece.start_line >= 1 for piece in chunks)


class TestGeneratedFilesAreRefusedOutLoud:
    def test_a_minified_bundle_is_refused_with_a_reason(self, tmp_path):
        """Chunking it produces a thousand facts of noise that then compete
        with real code for every retrieval slot."""
        path = tmp_path / "bundle.min.js"
        path.write_text("var a=1;" * 20_000, encoding="utf-8")

        result, reason, _ = parse_file(path)

        assert result is None
        assert "generated or minified" in reason.lower()

    def test_ordinary_source_is_not_refused_for_being_large(self, tmp_path):
        """The check is conservative on purpose: a false positive loses a real
        file, which is worse than indexing one bundle."""
        source = "\n".join(f"def function_{n}():\n    return {n}" for n in range(3000))
        assert len(source) > 50_000

        generated, _ = looks_generated(source)

        assert generated is False

    def test_a_small_file_of_long_lines_is_not_judged(self):
        """Below the size floor the mean says nothing."""
        assert looks_generated("x" * 5_000)[0] is False


def test_the_chunker_is_reached_by_the_thing_that_stores_facts(tmp_path):
    """A named caller is part of done. `_store_chunks` chooses the chunker from
    the parser that read the file, so this asserts the branch is taken and the
    line range reaches the metadata a recalled fact carries."""
    from ingest.service import _ingest_one

    path = tmp_path / "app.py"
    path.write_text(PYTHON, encoding="utf-8")

    stored: list[dict] = []

    def store_fact(text: str, metadata: dict) -> str:
        stored.append(metadata)
        return f"fact_{len(stored)}"

    outcome = _ingest_one(path, store_fact)

    assert outcome.fact_ids
    assert stored, "nothing was stored"
    for metadata in stored:
        assert metadata["start_line"] >= 1
        assert metadata["end_line"] >= metadata["start_line"]
        assert metadata["symbols"] == list(metadata["symbols"])


def test_prose_carries_no_invented_line_numbers(tmp_path):
    """The other half of the branch. A paragraph chunker has no line range to
    report, and reporting one would be a value nobody measured."""
    from ingest.service import _ingest_one

    path = tmp_path / "notes.md"
    path.write_text("# Notes\n\nA paragraph about something.\n", encoding="utf-8")

    stored: list[dict] = []
    _ingest_one(path, lambda text, metadata: (stored.append(metadata), "fact")[1])

    assert stored
    assert all("start_line" not in metadata for metadata in stored)
