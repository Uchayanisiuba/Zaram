"""A message that names a folder on this machine gets an offer to open it.

`docs/PLAN.md` F1, rule 7h. The offer is a notice with the folder and a
prefilled name; the interface's one press creates and selects the coding
project. Decided by looking at the file system, never by asking the model,
and only when no coding project is already open.
"""

from __future__ import annotations

import os
from pathlib import Path

from core.named_folder import named_folder


class TestFindingTheFolder:
    def test_a_quoted_path_with_spaces(self, tmp_path: Path):
        folder = tmp_path / "my app"
        folder.mkdir()
        found = named_folder(f'add dark mode to the app in "{folder}"')
        assert found is not None
        assert Path(found.path) == folder.resolve()
        assert found.name == "my app"

    def test_a_bare_path(self, tmp_path: Path):
        folder = tmp_path / "proj"
        folder.mkdir()
        found = named_folder(f"look at {folder} please")
        assert found is not None and Path(found.path) == folder.resolve()

    def test_a_trailing_full_stop_is_not_part_of_the_path(self, tmp_path: Path):
        folder = tmp_path / "proj"
        folder.mkdir()
        found = named_folder(f"open {folder}.")
        assert found is not None and found.name == "proj"

    def test_a_path_that_does_not_exist_is_nothing(self, tmp_path: Path):
        assert named_folder(f"look at {tmp_path / 'nowhere'}") is None

    def test_a_file_is_not_a_folder(self, tmp_path: Path):
        f = tmp_path / "notes.txt"
        f.write_text("x")
        assert named_folder(f"read {f}") is None

    def test_a_word_is_not_a_path(self):
        assert named_folder("the frontend folder needs dark mode") is None
        assert named_folder("") is None

    def test_a_url_is_not_a_path(self):
        assert named_folder("see https://example.com/path/to/thing") is None

    def test_home_expands(self):
        home = Path.home()
        child = next((c for c in home.iterdir() if c.is_dir() and " " not in c.name), None)
        if child is None:
            return
        found = named_folder(f"open ~{os.sep}{child.name} and tell me what is there")
        assert found is not None and Path(found.path) == child.resolve()
