"""The uninstaller's data questions.

Guarded by a test for the same reason the installer payload is: nothing else
looks at this file until someone runs an uninstall, and by then the damage is
either done or the option silently never existed. Both failures are invisible
in a build log.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "build" / "installer.nsh"
CONFIG = ROOT / "electron-builder.yml"


@pytest.fixture(scope="module")
def script() -> str:
    assert SCRIPT.exists(), f"{SCRIPT} is missing; uninstall would keep data silently"
    return SCRIPT.read_text(encoding="utf-8")


def test_the_build_actually_includes_it():
    """Named in the config rather than found by convention — the same
    convention that shipped an installer wearing the default Electron icon."""
    assert "build/installer.nsh" in CONFIG.read_text(encoding="utf-8")


def test_an_update_never_asks_about_data(script: str):
    """electron-builder runs the uninstaller while installing a new version.
    A prompt there asks the user to decide about their data during what they
    believe is an update, and a wrong answer wipes the Spine mid-upgrade."""
    assert "${ifNot} ${isUpdated}" in script


def test_keeping_data_is_the_default(script: str):
    """The focused button and the silent-uninstall answer must both be "no".
    Someone pressing Enter through a dialog they did not read keeps their
    data, which is the only outcome still correctable afterwards."""
    delete_prompt = script.split("zaramAskExport", 1)[0]
    assert "MB_DEFBUTTON2" in delete_prompt
    assert "/SD IDNO" in delete_prompt


def test_it_offers_to_hand_the_data_back_before_deleting(script: str):
    """Rule 7: exportable in an open format, no lock-in. An uninstaller that
    can only keep or destroy makes leaving expensive."""
    assert "Compress-Archive" in script
    assert "zaramExport" in script


def test_a_failed_export_deletes_nothing(script: str):
    """Deleting after a backup that did not happen is the worst outcome
    available here."""
    export_block = script.split("zaramExport:", 1)[1].split("zaramConfirmDelete", 1)[0]
    failure_branch = export_block.split("${Else}", 1)[1]
    assert "zaramUninstallDone" in failure_branch
    assert "zaramRemoveData" not in failure_branch


def test_deleting_without_a_backup_asks_twice(script: str):
    """The one path that destroys data with no copy anywhere is the one path
    that confirms again."""
    assert "zaramConfirmDelete:" in script
    confirm = script.split("zaramConfirmDelete:", 1)[1].split("zaramRemoveData:", 1)[0]
    assert "MB_DEFBUTTON2" in confirm
    assert "/SD IDNO" in confirm


def test_removal_targets_only_zarams_own_directory(script: str):
    """A recursive delete in an uninstaller is the most dangerous line in the
    product. It must name one directory, and that directory must be ours."""
    removals = [line.strip() for line in script.splitlines() if "RMDir /r" in line]
    assert removals == ['RMDir /r "$APPDATA\\Zaram"']


def test_the_prompts_say_original_files_are_untouched(script: str):
    """The question a person actually has when a dialog offers to delete
    "everything Zaram remembers" is whether their documents are included."""
    assert "Your own files are never touched" in script
