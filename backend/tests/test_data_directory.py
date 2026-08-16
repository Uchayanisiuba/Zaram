"""Where an installed Zaram writes the user's data.

Every store used to resolve to the backend *source* directory. That is correct
in a checkout and wrong in an install, where it is a folder under Program Files
that a standard user cannot write to and that the next upgrade replaces. The
uninstaller had already been written against the fixed behaviour — it offers to
export or delete ``%APPDATA%\\Zaram`` — so the product disagreed with itself
about where the Spine lived, with only one side right.

These tests assert the three properties that make the move safe, because each
one has been the wrong way round somewhere in this codebase before:

* an install writes to the per-user location, not beside the executable;
* a checkout that already holds data keeps it, because silently relocating
  somebody's Spine is indistinguishable from losing it;
* every store agrees, since a per-store path is a per-store chance to diverge.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from core import paths


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch):
    """No inherited overrides. Each test states the environment it means."""
    for var in (
        paths.DATA_DIR_ENV,
        "ZARAM_PACKAGED",
        "ZARAM_ARTIFACTS_DB",
        "ZARAM_PROJECTS_DB",
        "ZARAM_INGEST_DB",
        "ZARAM_EGRESS_LOG",
        "ZARAM_EGRESS_POLICY",
        "ZARAM_SPINE_PATH",
        "ZARAM_OUTPUT_DIR",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


class TestWhereTheDataGoes:
    def test_an_install_writes_outside_the_program_directory(self, monkeypatch, tmp_path):
        """The whole point. A packaged build must not write beside itself."""
        monkeypatch.setenv("ZARAM_PACKAGED", "1")
        monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

        chosen = paths.data_dir()

        assert paths.source_dir() not in chosen.parents
        assert chosen != paths.source_dir()
        assert chosen.is_dir(), "the directory every caller is about to write to"

    def test_a_checkout_holding_data_keeps_it_exactly_where_it_is(
        self, monkeypatch, tmp_path
    ):
        """A `git pull` must never move somebody's Spine.

        This is the clause that makes the change safe to ship to the maintainer,
        whose databases are beside the backend today. Relocating them on an
        ordinary update looks precisely like losing them.
        """
        checkout = tmp_path / "Zaram" / "backend"
        checkout.mkdir(parents=True)
        (checkout / "spine.db").write_bytes(b"")
        monkeypatch.setattr(paths, "source_dir", lambda: checkout)
        monkeypatch.setenv("ZARAM_PACKAGED", "0")

        assert paths.data_dir() == checkout

    def test_a_fresh_checkout_with_no_data_still_uses_the_checkout(
        self, monkeypatch, tmp_path
    ):
        """Development stays development. Only installs relocate."""
        checkout = tmp_path / "Zaram" / "backend"
        checkout.mkdir(parents=True)
        monkeypatch.setattr(paths, "source_dir", lambda: checkout)
        monkeypatch.setenv("ZARAM_PACKAGED", "0")

        assert paths.data_dir() == checkout

    def test_one_variable_moves_everything(self, monkeypatch, tmp_path):
        """`ZARAM_DATA_DIR` is the portable-build and external-drive answer."""
        monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "elsewhere"))
        monkeypatch.setenv("ZARAM_PACKAGED", "1")

        assert paths.data_dir() == tmp_path / "elsewhere"

    def test_a_stores_own_variable_still_wins(self, monkeypatch, tmp_path):
        """Tests and the desktop host set these; the change is the default only."""
        monkeypatch.setenv(paths.DATA_DIR_ENV, str(tmp_path / "shared"))
        monkeypatch.setenv("ZARAM_SPINE_PATH", str(tmp_path / "named.db"))

        assert paths.in_data_dir("spine.db", "ZARAM_SPINE_PATH") == str(tmp_path / "named.db")
        assert paths.in_data_dir("egress.db", "ZARAM_EGRESS_LOG") == str(
            tmp_path / "shared" / "egress.db"
        )


class TestEveryStoreAgrees:
    """One location, six stores. A second spelling is a second answer."""

    def test_all_stores_land_in_the_one_directory(self, monkeypatch, tmp_path):
        from artifacts.records import default_db_path as artifacts_db
        from artifacts.store import default_output_root
        from core.egress.runtime import default_log_path, default_policy_path
        from ingest.service_api import default_db_path as ingest_db
        from projects.records import default_db_path as projects_db

        home = tmp_path / "data"
        monkeypatch.setenv(paths.DATA_DIR_ENV, str(home))

        located = {
            "artifacts": Path(artifacts_db()),
            "projects": Path(projects_db()),
            "ingest": Path(ingest_db()),
            "egress log": Path(default_log_path()),
            "egress policy": Path(default_policy_path()),
            "generated": Path(default_output_root()),
        }

        for name, where in located.items():
            assert where.parent == home, f"{name} landed in {where.parent}, not {home}"

    def test_settings_follow_the_policy_file(self, monkeypatch, tmp_path):
        """`user_settings` derives its path from the egress policy's directory.

        Asserted rather than assumed: it is the one store that does not call
        `in_data_dir` itself, so it is the one that could quietly stay behind.
        """
        from core.user_settings import default_settings_path

        home = tmp_path / "data"
        monkeypatch.setenv(paths.DATA_DIR_ENV, str(home))

        assert Path(default_settings_path()).parent == home


class TestPackagedDetection:
    def test_a_bundled_interpreter_reads_as_packaged(self, monkeypatch):
        """Inferred from where the interpreter is, not from a flag to forget."""
        monkeypatch.setattr(
            sys, "executable", os.path.join("C:", "App", "resources", "runtime", "python.exe")
        )
        assert paths.is_packaged()

    def test_a_venv_interpreter_does_not(self, monkeypatch):
        monkeypatch.setattr(
            sys, "executable", os.path.join("C:", "Zaram", "backend", "venv", "Scripts", "python.exe")
        )
        assert not paths.is_packaged()

    def test_the_host_can_say_so_outright(self, monkeypatch):
        """The desktop host knows for certain; this function only infers."""
        monkeypatch.setattr(sys, "executable", os.path.join("C:", "anywhere", "python.exe"))
        monkeypatch.setenv("ZARAM_PACKAGED", "1")
        assert paths.is_packaged()
