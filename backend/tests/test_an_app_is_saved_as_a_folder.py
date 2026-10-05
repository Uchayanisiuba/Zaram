"""A multi-file app a reply wrote is kept as a new folder, and only ever new.

The maintainer asked, 5 October 2026, for single-file and multi-file apps with
no project behind them. Saving is generative tier: new files, never replaced.
The names come from a model's reply, so every one is treated as hostile.
"""

from __future__ import annotations

import pytest

from artifacts.app_folder import AppFolderRefused, save_app

FILES = [
    ("index.html", "<script src='game.js'></script>"),
    ("style.css", "body{margin:0}"),
    ("src/game.js", "console.log(1)"),
]


def test_writes_every_file_into_a_new_folder(tmp_path):
    folder = save_app(tmp_path, "Voxel World", FILES)
    assert folder.parent == (tmp_path / "apps").resolve()
    assert folder.name == "voxel-world"
    assert (folder / "index.html").read_text(encoding="utf-8") == FILES[0][1]
    assert (folder / "src" / "game.js").read_text(encoding="utf-8") == "console.log(1)"


def test_a_second_save_of_the_same_name_is_a_new_folder_not_a_replacement(tmp_path):
    first = save_app(tmp_path, "Voxel World", FILES)
    second = save_app(tmp_path, "Voxel World", [("index.html", "changed")])
    assert second != first
    assert second.name == "voxel-world-2"
    assert (first / "index.html").read_text(encoding="utf-8") == FILES[0][1]


@pytest.mark.parametrize(
    "bad",
    [
        "../escape.html",
        "a/../../escape.html",
        "/etc/passwd.html",
        "C:/x/index.html",
        "back\\slash.html",
        "a//b.html",
        ".hidden/index.html",
        "run.exe",
        "setup.bat",
        "noextension",
        "a/b/c/d/e/index.html",
    ],
)
def test_a_path_that_could_leave_the_folder_or_run_is_refused(tmp_path, bad):
    with pytest.raises(AppFolderRefused):
        save_app(tmp_path, "x", [("index.html", "ok"), (bad, "bad")])


def test_a_refused_save_leaves_nothing_behind(tmp_path):
    with pytest.raises(AppFolderRefused):
        save_app(tmp_path, "x", [("index.html", "ok"), ("../no.html", "bad")])
    assert not (tmp_path / "apps").exists() or not any((tmp_path / "apps").iterdir())


def test_the_same_path_twice_is_refused(tmp_path):
    with pytest.raises(AppFolderRefused):
        save_app(tmp_path, "x", [("a.html", "1"), ("A.html", "2")])


def test_size_and_count_are_bounded(tmp_path):
    with pytest.raises(AppFolderRefused):
        save_app(tmp_path, "x", [("big.js", "x" * (2 * 1024 * 1024 + 1))])
    with pytest.raises(AppFolderRefused):
        save_app(tmp_path, "x", [(f"f{i}.js", "1") for i in range(41)])
    with pytest.raises(AppFolderRefused):
        save_app(tmp_path, "x", [])
