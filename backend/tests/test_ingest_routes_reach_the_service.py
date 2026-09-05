"""Drop, paste and upload are reachable over HTTP, not merely implemented.

**Why this file exists at all.** `ingest/service_api.py` has carried
`save_upload`, `save_text` and `stream_ingest_paths` — complete, commented, and
called by nothing. That is this repository's most expensive failure shape and
the reason the handover counts eleven of them: a feature whose unit tests pass
while the feature cannot happen, because no route serves it.

So these tests deliberately go in through the front door. Every one posts to a
URL and reads the response, and the assertions are about what a user would see:
the file is kept, its outcome is listed under Knowledge, the folder it landed in
is a source with a privacy policy. Nothing here calls the service directly —
that would test the half that already worked.

The service is rebound onto a temporary store, and `ZARAM_DATA_DIR` moves the
uploads directory with it, so a test run never writes into the maintainer's own
Spine.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client whose ingest service writes only inside `tmp_path`.

    `memory_runtime` is left unattached on purpose. These routes are about
    getting bytes to the parser and the outcome to Knowledge; whether a chunk
    reaches the Spine is `test_ingest.py`'s question, and pulling a real
    embedder into a route test would make it slow and flaky for no extra
    coverage.
    """
    from ingest.records import IngestRecords
    from ingest.service_api import IngestService

    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))

    main = importlib.import_module("main")
    monkeypatch.setattr(
        main, "ingest_service", IngestService(IngestRecords(str(tmp_path / "ingest.db")))
    )
    return TestClient(main.app)


def events(response) -> list[dict]:
    """The NDJSON stream, parsed. Same shape `/ingest` emits."""
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def uploads(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


class TestUpload:
    def test_dropped_files_are_kept_and_read(self, client, tmp_path):
        response = client.post(
            "/ingest/upload",
            files=[
                ("files", ("notes.txt", b"The Northwind rate is 450 a day.", "text/plain")),
                ("files", ("terms.txt", b"Payment is due thirty days after invoice.", "text/plain")),
            ],
        )
        assert response.status_code == 200

        stream = events(response)
        assert stream[0]["type"] == "start"
        assert stream[0]["total"] == 2
        assert stream[-1]["type"] == "done"

        read = {e["name"]: e for e in stream if e["type"] == "file"}
        assert set(read) == {"notes.txt", "terms.txt"}
        assert all(e["status"] == "indexed" for e in read.values())

        # The bytes are on disk, so the source row points at something real and
        # "delete this source" means something.
        assert (uploads(tmp_path) / "notes.txt").read_bytes() == b"The Northwind rate is 450 a day."

    def test_the_drop_is_listed_under_knowledge(self, client):
        """Reachability, asserted from the other end.

        A stream that reported success while recording nothing would look
        identical in the interface until the user opened Sources.
        """
        client.post("/ingest/upload", files=[("files", ("brief.txt", b"A brief about the work.", "text/plain"))])

        outcomes = client.get("/ingest/outcomes").json()["outcomes"]
        assert [o["name"] for o in outcomes] == ["brief.txt"]

        sources = client.get("/ingest/sources").json()["sources"]
        assert len(sources) == 1
        # Rule 5: a source is a place, and the place has a policy, default deny.
        assert sources[0]["policy"] == "local_only"
        assert sources[0]["root"].endswith("uploads")

    def test_two_drops_share_one_source(self, client):
        """One uploads directory, one source row, one privacy decision.

        A row per dropped file would scatter the user's answer to rule 5 across
        dozens of entries asking the same question.
        """
        for name in ("one.txt", "two.txt"):
            client.post("/ingest/upload", files=[("files", (name, b"Something worth keeping.", "text/plain"))])

        assert len(client.get("/ingest/sources").json()["sources"]) == 1
        assert len(client.get("/ingest/outcomes").json()["outcomes"]) == 2

    def test_the_same_name_twice_does_not_overwrite(self, client, tmp_path):
        """Two clients' `invoice.pdf` are not the same invoice."""
        for body in (b"The first invoice, for March.", b"The second invoice, for April."):
            client.post("/ingest/upload", files=[("files", ("invoice.txt", body, "text/plain"))])

        kept = sorted(p.name for p in uploads(tmp_path).iterdir())
        assert kept == ["invoice (2).txt", "invoice.txt"]
        assert (uploads(tmp_path) / "invoice.txt").read_bytes() == b"The first invoice, for March."

    def test_a_traversing_filename_cannot_escape(self, client, tmp_path):
        """A filename is third-party text, and it arrives over HTTP.

        `../../spine.db` would otherwise be written over the Spine itself. The
        upload is kept rather than refused — the bytes are what the user asked
        for and the name is not.
        """
        client.post(
            "/ingest/upload",
            files=[("files", ("../../spine.db", b"Not the database, whatever it claims.", "text/plain"))],
        )

        assert (uploads(tmp_path) / "spine.db").exists()
        assert not (tmp_path / "spine.db").exists()
        assert not (tmp_path.parent / "spine.db").exists()

    def test_a_file_that_gives_nothing_back_says_so(self, client):
        """An empty drop is graded, not rejected.

        Refusing it at the door would lose the one thing the user needs to know
        — that the document they dropped contains nothing Zaram can read.
        """
        response = client.post("/ingest/upload", files=[("files", ("blank.txt", b"", "text/plain"))])
        graded = [e for e in events(response) if e["type"] == "file"]
        assert graded[0]["status"] == "empty"
        assert graded[0]["reason"]

    def test_an_oversized_file_is_refused_rather_than_truncated(self, client, monkeypatch):
        """Half a document indexed as a whole one is rule 9 by the back door."""
        main = importlib.import_module("main")
        monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 1024)

        response = client.post(
            "/ingest/upload",
            files=[("files", ("huge.txt", b"x" * 4096, "text/plain"))],
        )
        assert response.status_code == 413
        assert "huge.txt" in response.json()["detail"]

    def test_a_refused_drop_leaves_nothing_behind(self, client, tmp_path, monkeypatch):
        """All or none.

        The oversized file is second, so the first has already been written by
        the time the refusal happens. Leaving it there would put bytes in the
        uploads directory that no source row mentions, no answer can cite and
        no "delete this source" can reach — and the next drop of the same
        document would land beside it as a duplicate.
        """
        main = importlib.import_module("main")
        monkeypatch.setattr(main, "MAX_UPLOAD_BYTES", 1024)

        response = client.post(
            "/ingest/upload",
            files=[
                ("files", ("small.txt", b"This one is a perfectly ordinary note.", "text/plain")),
                ("files", ("huge.txt", b"x" * 4096, "text/plain")),
            ],
        )

        assert response.status_code == 413
        assert not uploads(tmp_path).exists() or list(uploads(tmp_path).iterdir()) == []
        assert client.get("/ingest/outcomes").json()["outcomes"] == []

    def test_nothing_at_all_is_a_bad_request(self, client):
        assert client.post("/ingest/upload").status_code == 422


class TestPaste:
    def test_pasted_text_is_read_by_the_same_parser(self, client, tmp_path):
        response = client.post(
            "/ingest/text",
            json={"text": "Northwind agreed to 450 a day, net thirty.", "name": "call notes"},
        )
        assert response.status_code == 200

        stream = events(response)
        assert stream[-1]["type"] == "done"
        indexed = [e for e in stream if e["type"] == "file"]
        assert indexed[0]["status"] == "indexed"
        assert indexed[0]["name"] == "call notes.txt"

        kept = uploads(tmp_path) / "call notes.txt"
        assert kept.read_text(encoding="utf-8").startswith("Northwind agreed")

    def test_an_unnamed_paste_still_gets_a_file(self, client, tmp_path):
        client.post("/ingest/text", json={"text": "Something said in passing that mattered."})
        kept = list(uploads(tmp_path).iterdir())
        assert len(kept) == 1
        assert kept[0].suffix == ".txt"

    def test_a_paste_appears_under_knowledge(self, client):
        client.post("/ingest/text", json={"text": "A note long enough to be indexed properly."})
        outcomes = client.get("/ingest/outcomes").json()["outcomes"]
        assert len(outcomes) == 1
        assert outcomes[0]["status"] == "indexed"

    @pytest.mark.parametrize("text", ["", "   ", "\n\t "])
    def test_an_empty_paste_is_refused(self, client, text, tmp_path):
        response = client.post("/ingest/text", json={"text": text})
        assert response.status_code == 400
        # And nothing was written on the way to refusing.
        assert not uploads(tmp_path).exists() or not list(uploads(tmp_path).iterdir())


class TestWithdrawing:
    """*"Forget this folder and everything Zaram learned from it"* has to be true.

    It was not. The facts went, the rows went, and every dropped document stayed
    on disk — unreachable by any other route, because the row naming it had just
    been deleted. Four files had to be removed by hand after one session's
    verification.

    The distinction these tests exist to protect is **whose file it is**. A
    staged copy is Zaram's; a scanned folder holds the user's originals, and
    deleting those would be unrecoverable.
    """

    def test_withdrawing_uploads_deletes_the_copies_zaram_made(self, client, tmp_path):
        client.post(
            "/ingest/upload",
            files=[
                ("files", ("one.txt", b"A document worth keeping for now.", "text/plain")),
                ("files", ("two.txt", b"Another document, also worth keeping.", "text/plain")),
            ],
        )
        assert len(list(uploads(tmp_path).iterdir())) == 2

        source_id = client.get("/ingest/sources").json()["sources"][0]["id"]
        body = client.delete(f"/ingest/sources/{source_id}").json()

        assert body["files_deleted"] == 2
        assert list(uploads(tmp_path).iterdir()) == []
        assert client.get("/ingest/sources").json()["sources"] == []
        assert client.get("/ingest/outcomes").json()["outcomes"] == []

    def test_withdrawing_a_scanned_folder_never_touches_the_users_files(
        self, client, tmp_path
    ):
        """The half that must not regress.

        These are the user's originals, in their own folder. Withdrawing a
        *source* is a statement about Zaram's memory, never about their disk.
        """
        folder = tmp_path / "Contracts"
        folder.mkdir()
        (folder / "northwind.txt").write_text("The agreed day rate is 450.", encoding="utf-8")
        (folder / "osun.txt").write_text("Delivery moves to September.", encoding="utf-8")

        client.post("/ingest", json={"path": str(folder)})
        source_id = client.get("/ingest/sources").json()["sources"][0]["id"]

        body = client.delete(f"/ingest/sources/{source_id}").json()

        assert body["files_deleted"] == 0
        assert sorted(p.name for p in folder.iterdir()) == ["northwind.txt", "osun.txt"]
        assert client.get("/ingest/sources").json()["sources"] == []

    def test_a_stored_path_pointing_elsewhere_is_refused(self, client, tmp_path):
        """An outcome's `path` is stored data, not a promise.

        Following it to a delete without checking where it lands is how "Zaram
        deleted my file" happens. The row is rewritten here to point outside the
        uploads directory — the shape a traversal or a tampered database would
        take — and the file it names must survive.
        """
        client.post(
            "/ingest/upload",
            files=[("files", ("staged.txt", b"A perfectly ordinary staged note.", "text/plain"))],
        )

        precious = tmp_path / "the-users-real-contract.txt"
        precious.write_text("Not Zaram's to delete.", encoding="utf-8")

        main = importlib.import_module("main")
        records = main.ingest_service.records
        outcome_id = client.get("/ingest/outcomes").json()["outcomes"][0]["id"]
        with records._connect() as connection:  # noqa: SLF001 — rewriting a row on purpose
            connection.execute(
                "UPDATE outcomes SET path = ? WHERE id = ?", (str(precious), outcome_id)
            )

        source_id = client.get("/ingest/sources").json()["sources"][0]["id"]
        body = client.delete(f"/ingest/sources/{source_id}").json()

        assert body["files_deleted"] == 0
        assert precious.exists(), "a stored path outside the uploads directory was followed"

    def test_a_file_already_gone_does_not_fail_the_withdrawal(self, client, tmp_path):
        client.post(
            "/ingest/upload",
            files=[("files", ("vanishing.txt", b"Here now, gone in a moment.", "text/plain"))],
        )
        (uploads(tmp_path) / "vanishing.txt").unlink()

        source_id = client.get("/ingest/sources").json()["sources"][0]["id"]
        response = client.delete(f"/ingest/sources/{source_id}")

        assert response.status_code == 200
        assert response.json()["files_deleted"] == 0
        assert client.get("/ingest/sources").json()["sources"] == []

    def test_withdrawing_something_unknown_is_a_404(self, client):
        assert client.delete("/ingest/sources/src-nothing").status_code == 404

    def test_sources_say_which_ones_hold_zarams_own_copies(self, client, tmp_path):
        """`staged` is what makes the interface warn before deleting documents.

        If it were wrong in either direction the failure would be silent: the
        warning never appears on a source that deletes files, or it appears on a
        scanned folder and teaches the user to click through it.
        """
        folder = tmp_path / "Contracts"
        folder.mkdir()
        (folder / "a.txt").write_text("A document of the user's own.", encoding="utf-8")

        client.post("/ingest", json={"path": str(folder)})
        client.post(
            "/ingest/upload",
            files=[("files", ("dropped.txt", b"A document Zaram copied.", "text/plain"))],
        )

        staged = {s["name"]: s["staged"] for s in client.get("/ingest/sources").json()["sources"]}
        assert staged == {"Contracts": False, "uploads": True}

    def test_a_users_folder_merely_named_uploads_is_not_staged(self, client, tmp_path):
        """Not inferred from the name. Someone's own `uploads` folder is theirs."""
        decoy = tmp_path / "Pictures" / "uploads"
        decoy.mkdir(parents=True)
        (decoy / "photo-notes.txt").write_text("Notes beside some photos.", encoding="utf-8")

        client.post("/ingest", json={"path": str(decoy)})
        source = client.get("/ingest/sources").json()["sources"][0]

        assert source["name"] == "uploads"
        assert source["staged"] is False, "a folder of the user's own was marked as Zaram's"

        client.delete(f"/ingest/sources/{source['id']}")
        assert (decoy / "photo-notes.txt").exists()


def test_the_stream_shape_matches_the_folder_scan(client, tmp_path):
    """One NDJSON vocabulary for every way in.

    The interface parses this stream once. A second event shape for drops would
    be a second set of split-chunk bugs, and the folder scan's parser is the one
    that has already been through them.
    """
    folder = tmp_path / "papers"
    folder.mkdir()
    (folder / "one.txt").write_text("A document in a folder somewhere.", encoding="utf-8")

    scanned = events(client.post("/ingest", json={"path": str(folder)}))
    dropped = events(
        client.post("/ingest/upload", files=[("files", ("one.txt", b"A document that was dropped.", "text/plain"))])
    )

    assert [e["type"] for e in scanned] == [e["type"] for e in dropped]
    for a, b in zip(scanned, dropped):
        assert set(a) == set(b), f"{a['type']} events disagree about their fields"
