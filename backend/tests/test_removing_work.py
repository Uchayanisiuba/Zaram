"""Removing a generated file, and the guarantees that survive it.

The maintainer asked for a Work surface where files can be selected and
deleted. `CLAUDE.md` said `ArtifactStore` has no delete capability by design
and put removing a file with the operating system, so this is a deliberate
revision rather than a gap being filled — and the revision is narrower than
"Zaram can delete files now".

**Two actors, two capabilities.** Generation still cannot destroy a document:
`store.py` has no unlink, no overwrite and no truncating open mode, and
`test_artifact_write_path.py` proves it by reading the source. That guard is
the first thing asserted here, because a delete added to the wrong module
would pass every behavioural test in this file.

**And nothing is destroyed.** The tier table requires undo for anything
mutative, so the file moves to a trash folder and the record is marked rather
than dropped. Emptying that folder stays the operating system's job, which is
the half of the original rule that did not change.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from artifacts.trash import ArtifactTrash, OutsideOutputRoot


# ------------------------------------------------------------------ the trash


@pytest.fixture()
def output(tmp_path: Path) -> Path:
    root = tmp_path / "generated"
    root.mkdir()
    return root


@pytest.fixture()
def trash(output: Path) -> ArtifactTrash:
    return ArtifactTrash(output)


def make(output: Path, name: str, body: bytes = b"x") -> Path:
    path = output / name
    path.write_bytes(body)
    return path


class TestNothingIsDestroyed:
    def test_the_file_moves_rather_than_vanishing(self, output, trash):
        source = make(output, "invoice-0007.pdf", b"the invoice")

        landed = trash.send(source)

        assert not source.exists()
        assert landed.is_file()
        assert landed.read_bytes() == b"the invoice"
        assert landed.parent == trash.root

    def test_it_can_be_put_back(self, output, trash):
        source = make(output, "brief.docx", b"the brief")
        landed = trash.send(source)

        restored = trash.restore(landed, source)

        assert restored == source
        assert source.read_bytes() == b"the brief"
        assert not landed.exists()

    def test_two_files_of_one_name_both_survive(self, output, trash):
        """Deleted, regenerated, deleted again.

        Without a distinguishing name the second would land on the first — a
        delete that silently destroys something *else*, which is the one
        outcome worse than the delete itself.
        """
        trash.send(make(output, "report.pdf", b"first"))
        trash.send(make(output, "report.pdf", b"second"))

        bodies = sorted(p.read_bytes() for p in trash.root.iterdir())
        assert bodies == [b"first", b"second"]

    def test_restoring_never_lands_on_top_of_a_newer_file(self, output, trash):
        """"Make me another one" between the delete and the undo.

        An undo that replaced it would destroy a file the user never asked to
        lose, while looking like the safe operation. It refuses, and says where
        the trashed copy still is.
        """
        source = make(output, "report.pdf", b"old")
        landed = trash.send(source)
        make(output, "report.pdf", b"new")

        with pytest.raises(FileExistsError) as raised:
            trash.restore(landed, source)

        assert "report.pdf" in str(raised.value)
        assert landed.is_file(), "the trashed copy must still be there"
        assert source.read_bytes() == b"new"

    def test_the_trash_folder_is_not_created_until_it_is_needed(self, trash):
        # An empty trash folder in every new install is a question the user did
        # not need asked.
        assert not trash.root.exists()


class TestTheSandbox:
    """Paths reach this module from records, and records were written from
    filenames a *model* proposed. `../../.ssh/config` is an input to assume,
    not a hypothesis."""

    def test_a_path_outside_the_output_root_is_refused(self, tmp_path, output, trash):
        outside = tmp_path / "not-ours.txt"
        outside.write_text("someone else's file", encoding="utf-8")

        with pytest.raises(OutsideOutputRoot):
            trash.send(outside)

        assert outside.exists()

    def test_traversal_out_of_the_root_is_refused(self, tmp_path, output, trash):
        outside = tmp_path / "secrets.txt"
        outside.write_text("no", encoding="utf-8")

        with pytest.raises(OutsideOutputRoot):
            trash.send(output / ".." / "secrets.txt")

        assert outside.exists()

    def test_restoring_to_somewhere_outside_the_root_is_refused(
        self, tmp_path, output, trash
    ):
        landed = trash.send(make(output, "doc.pdf"))

        with pytest.raises(OutsideOutputRoot):
            trash.restore(landed, tmp_path / "elsewhere" / "doc.pdf")

    def test_a_missing_file_is_named_rather_than_ignored(self, output, trash):
        with pytest.raises(FileNotFoundError):
            trash.send(output / "never-existed.pdf")


class TestTheWritePathStillCannotDelete:
    """The guarantee this whole design exists to preserve.

    Asserted here as well as in `test_artifact_write_path.py`, because that
    file's scan is easy to read as being about tidiness and this one states
    what it is for: a delete added to `store.py` would pass every behavioural
    test above and break the property that matters.
    """

    def test_the_store_exposes_no_removal(self):
        from artifacts.store import ArtifactStore

        surface = {name for name in dir(ArtifactStore) if not name.startswith("_")}
        assert not surface & {"delete", "remove", "unlink", "trash", "overwrite"}

    def test_the_store_source_names_no_destructive_call(self):
        source = (
            Path(__file__).resolve().parents[1] / "artifacts" / "store.py"
        ).read_text(encoding="utf-8")
        for forbidden in ("os.remove", "os.replace", "shutil.move", ".unlink("):
            assert forbidden not in source, f"{forbidden} reached the write path"


# ---------------------------------------------------------------- the records


@pytest.fixture()
def records(tmp_path):
    from artifacts.records import ArtifactRecords

    return ArtifactRecords(str(tmp_path / "artifacts.db"))


def record(records, artifact_id: str, **over):
    from artifacts.contracts import Artifact, ArtifactKind, Origin

    records.put(
        Artifact(
            id=artifact_id,
            filename=over.pop("filename", f"{artifact_id}.pdf"),
            kind=over.pop("kind", ArtifactKind.DOCUMENT),
            origin=Origin.GENERATED,
            created_at=time.time(),
            **over,
        )
    )


class TestTheRecordIsMarkedNotDropped:
    def test_a_removed_record_leaves_the_listing(self, records):
        record(records, "a")
        record(records, "b")

        assert records.soft_delete("a") is True

        assert [r.id for r in records.list()] == ["b"]
        assert records.count() == 1
        assert records.get("a") is None

    def test_it_is_still_there_when_asked_for(self, records):
        """Undo needs something to restore *to*.

        Without the record there is no provenance, no conversation and no
        claims, and "undo" would mean rebuilding a record from a filename.
        """
        record(records, "a", conversation_title="Northwind rate change")
        records.soft_delete("a")

        kept = records.get("a", include_deleted=True)
        assert kept is not None
        assert kept.conversation_title == "Northwind rate change"

    def test_restoring_puts_it_back_in_the_listing(self, records):
        record(records, "a")
        records.soft_delete("a")

        assert records.restore("a") is True
        assert [r.id for r in records.list()] == ["a"]

    def test_removing_twice_reports_the_second_as_a_no_op(self, records):
        record(records, "a")
        assert records.soft_delete("a") is True
        assert records.soft_delete("a") is False

    def test_a_removed_file_leaves_the_project_counts(self, records):
        # Otherwise Work offers a project filter that leads to an empty list —
        # which is the thing `projects()` exists to make impossible.
        record(records, "a", project_id="northwind")
        record(records, "b", project_id="northwind")
        records.soft_delete("a")

        assert records.projects() == [{"id": "northwind", "count": 1}]
        assert records.count_for_project("northwind") == 1

    def test_an_older_database_gains_the_column_rather_than_failing(self, tmp_path):
        """`CREATE TABLE IF NOT EXISTS` does nothing to a table that exists.

        So without the migration every query naming `deleted_at` would fail on
        exactly the machines that have work in them — and only on those.
        """
        import sqlite3

        from artifacts.records import ArtifactRecords

        path = str(tmp_path / "old.db")
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE artifacts ("
                "id TEXT PRIMARY KEY, filename TEXT NOT NULL, kind TEXT NOT NULL,"
                "project_id TEXT NOT NULL DEFAULT '', origin TEXT NOT NULL,"
                "created_at REAL NOT NULL, size_bytes INTEGER NOT NULL DEFAULT 0,"
                "path TEXT, html TEXT NOT NULL DEFAULT '',"
                "conversation_id TEXT NOT NULL DEFAULT '',"
                "conversation_title TEXT NOT NULL DEFAULT '',"
                "sources TEXT NOT NULL DEFAULT '[]', claims TEXT NOT NULL DEFAULT '[]',"
                "indexed INTEGER NOT NULL DEFAULT 0, remember_override INTEGER)"
            )
            conn.execute(
                "INSERT INTO artifacts (id, filename, kind, origin, created_at) "
                "VALUES ('old', 'old.pdf', 'document', 'generated', 1)"
            )

        opened = ArtifactRecords(path)

        # The pre-existing row survives, is listed, and can be removed.
        assert [r.id for r in opened.list()] == ["old"]
        assert opened.soft_delete("old") is True
        assert opened.list() == []
