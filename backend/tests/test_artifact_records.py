"""Artifact records, the generation service, and the HTTP surface over both.

What is being defended:

**Work shows what exists, and nothing else.** The surface it replaced was
designed against twenty invented artifacts, which was safe only because it said
so on screen. Now that it reads real records, an empty Spine has to produce an
empty list rather than anything reassuring, and a record whose file has gone has
to say which of the two is missing.

**The record follows the file, never the reverse.** `ArtifactStore` increments
on collision and never replaces, so the name a caller asked for is not
necessarily the name on disk. A record storing the requested name would point at
a different document than the one that was written — and would keep pointing at
it, silently, because both files exist.

**Provenance survives the round trip.** Claims and sources go into SQLite as
JSON and come back as dataclasses. If that is lossy, every generated document
becomes unattributable the moment the process restarts, which is the whole
product failing quietly.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from artifacts.contracts import Artifact, ArtifactKind, ArtifactSource, Claim, Origin
from artifacts.records import ArtifactRecords, DuplicateArtifact
from artifacts.service import ArtifactService
from artifacts.store import ArtifactStore

RECORDS_SOURCE = Path(__file__).resolve().parents[1] / "artifacts" / "records.py"


def _executed_sql(path: Path) -> list[str]:
    """Every string literal in the module that is not a docstring.

    Docstrings are excluded because this codebase explains its constraints in
    prose next to the code enforcing them — "there is no `DELETE FROM` here" is
    a sentence a text scan reads as a `DELETE FROM`.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))

    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        )
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }

    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


CLAIM = Claim(
    id="c1",
    source_id="memory:55b6",
    excerpt="Northwind pay on 30-day terms.",
    source_excerpt="Clause 4.2: payment due within thirty (30) days.",
    source_revision="rev-3",
)
SOURCE = ArtifactSource(kind="document", title="Master agreement", url="file:///n.pdf")


@pytest.fixture
def records(tmp_path) -> ArtifactRecords:
    return ArtifactRecords(str(tmp_path / "artifacts.db"))


@pytest.fixture
def service(tmp_path, records) -> ArtifactService:
    return ArtifactService(records, ArtifactStore(tmp_path / "out"))


class TestRecordsRoundTrip:
    def test_provenance_survives_storage(self, records):
        """Lossy here means every document becomes unattributable on restart."""
        stored = records.put(
            Artifact(filename="p.docx", sources=[SOURCE], claims=[CLAIM], html="<p>x</p>")
        )

        back = records.get(stored.id)

        assert back is not None
        assert back.claims == [CLAIM]
        assert back.sources == [SOURCE]
        assert back.html == "<p>x</p>"

    def test_origin_and_kind_come_back_as_enums(self, records):
        stored = records.put(Artifact(filename="p.xlsx", kind=ArtifactKind.SPREADSHEET))

        back = records.get(stored.id)

        assert back.kind is ArtifactKind.SPREADSHEET
        assert back.origin is Origin.GENERATED

    def test_a_missing_id_is_none_not_an_error(self, records):
        assert records.get("art_nope") is None

    def test_an_id_is_written_once(self, records):
        """`INSERT`, not `INSERT OR REPLACE`. A silent replace turns a bug
        upstream into lost provenance, found later by someone reading a document
        whose citations point at the wrong conversation."""
        artifact = records.put(Artifact(filename="p.docx"))

        with pytest.raises(DuplicateArtifact):
            records.put(artifact)

    def test_an_unknown_kind_does_not_take_the_surface_down(self, records, tmp_path):
        """A build that adds a kind, then a rollback, must not make Work
        unopenable — one unreadable row would take the whole list with it."""
        import sqlite3

        stored = records.put(Artifact(filename="p.docx"))
        with sqlite3.connect(str(tmp_path / "artifacts.db")) as conn:
            conn.execute(
                "UPDATE artifacts SET kind = 'hologram' WHERE id = ?", (stored.id,)
            )

        back = records.get(stored.id)

        assert back.kind is ArtifactKind.DOCUMENT
        assert back.filename == "p.docx"


class TestListing:
    def test_newest_first(self, records):
        for index in range(3):
            records.put(Artifact(filename=f"{index}.docx", created_at=1000.0 + index))

        assert [a.filename for a in records.list()] == ["2.docx", "1.docx", "0.docx"]

    def test_filters_by_project_and_kind(self, records):
        records.put(Artifact(filename="a.docx", project_id="north"))
        records.put(Artifact(filename="b.xlsx", project_id="north",
                             kind=ArtifactKind.SPREADSHEET))
        records.put(Artifact(filename="c.docx", project_id="south"))

        assert len(records.list(project_id="north")) == 2
        assert len(records.list(project_id="north", kind="spreadsheet")) == 1
        assert records.count(project_id="south") == 1

    def test_projects_are_derived_from_the_artifacts(self, records):
        """Not a second table. A projects table's first act would be to disagree
        — Work offering a filter that leads to an empty list."""
        records.put(Artifact(filename="a.docx", project_id="north"))
        records.put(Artifact(filename="b.docx", project_id="north"))
        records.put(Artifact(filename="c.docx"))  # no project

        assert records.projects() == [{"id": "north", "count": 2}]

    def test_an_empty_store_lists_nothing(self, records):
        """The state Work now has to render truthfully."""
        assert records.list() == []
        assert records.projects() == []


class TestRememberOverrideIsThreeValued:
    def test_none_and_false_are_different_answers(self, records):
        """None is "not decided" and may be changed by a default later. False is
        a refusal and may not."""
        stored = records.put(Artifact(filename="p.docx"))
        assert records.get(stored.id).remember_override is None

        records.set_remember_override(stored.id, False)
        assert records.get(stored.id).remember_override is False

        records.set_remember_override(stored.id, None)
        assert records.get(stored.id).remember_override is None

    def test_setting_it_on_a_missing_artifact_reports_that(self, records):
        assert records.set_remember_override("art_nope", True) is False


class TestTheRecordStoreHasNoGeneralMutation:
    """The module this replaced kept artifacts in a dict and exposed an
    `update()` that `setattr`'d any attribute passed to it. Nothing called it,
    and it was still wrong: nothing in that signature said which fields were
    safe to move. Mutation here is one named method, and adding a second has to
    be a deliberate act rather than a keyword argument nobody reviews.
    """

    def test_no_function_named_for_deletion_or_general_update(self):
        tree = ast.parse(RECORDS_SOURCE.read_text(encoding="utf-8"))

        offenders = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(
                word in node.name.lower()
                for word in ("delete", "remove", "drop", "purge", "update", "setattr")
            )
        ]

        assert not offenders, (
            f"records.py defines {offenders}. Mutation is one named method for "
            "the one field the user controls."
        )

    #: The columns a user may change after an artifact is written. Everything
    #: else — filename, path, size, origin, sources, claims — is provenance,
    #: and a provenance record that can be edited is not one.
    #:
    #: Adding to this list is the deliberate act the class docstring asks for.
    #: It is a list rather than a count because a count says *how many* named
    #: mutations exist and not *which*, so swapping a safe one for a dangerous
    #: one leaves it green — the number was never the property worth guarding.
    MUTABLE_COLUMNS = {"REMEMBER_OVERRIDE", "PROJECT_ID"}

    def test_no_sql_deletes_or_blanket_updates(self):
        """Every UPDATE names one allowed column, and nothing else mutates.

        Scans the SQL the module actually executes, not its text. A raw-text
        scan matches the docstrings explaining *why* these statements are
        absent, so it fails on a module that is correct and documented — which
        would train someone to delete the explanation to get a green build.
        """
        statements = [s.upper() for s in _executed_sql(RECORDS_SOURCE)]
        sql = " ".join(statements)

        assert "DELETE FROM" not in sql
        assert "DROP TABLE" not in sql
        assert "INSERT OR REPLACE" not in sql

        updates = [s for s in statements if "UPDATE ARTIFACTS" in s]
        assert updates, "records.py updates nothing — has the mutation path moved?"

        for statement in updates:
            column = statement.split("SET", 1)[1].split("=", 1)[0].strip()
            assert column in self.MUTABLE_COLUMNS, (
                f"records.py updates {column!r}, which is not one of "
                f"{sorted(self.MUTABLE_COLUMNS)}. Mutation is one named method "
                "per field the user controls; add the column here deliberately."
            )
            # One column per statement. A comma would mean a statement that
            # moves several fields at once, which is the blanket update this
            # store exists without.
            assert "," not in statement.split("SET", 1)[1].split("WHERE")[0]


class TestTheServiceWritesTheFileThenRecordsIt:
    def test_a_document_produces_a_file_and_a_record(self, service):
        artifact = service.create_document(
            title="Proposal — Northwind",
            blocks=["Here is the scope.", CLAIM],
            project_id="north",
            conversation_id="conv-1",
            conversation_title="Q3 scoping",
            sources=[SOURCE],
            claims=[CLAIM],
        )

        assert artifact.path and os.path.isfile(artifact.path)
        assert artifact.size_bytes == os.path.getsize(artifact.path)
        assert service.records.get(artifact.id) is not None

    def test_the_record_follows_the_file_when_a_name_collides(self, service):
        """The store increments rather than replacing, so a record holding the
        *requested* name would point at a different document than the one
        written — and both would exist, so nothing would ever notice."""
        first = service.create_document(title="Proposal", blocks=["a"])
        second = service.create_document(title="Proposal", blocks=["b"])

        assert first.filename != second.filename
        assert second.filename == "proposal-2.docx"
        assert os.path.basename(second.path) == second.filename
        assert service.records.get(second.id).filename == second.filename

    def test_the_kind_picks_the_format(self, service):
        spreadsheet = service.create_spreadsheet(
            title="Invoices", header=["Invoice"], rows=[["INV-1"]]
        )

        assert spreadsheet.filename.endswith(".xlsx")

    def test_claims_reach_the_stored_html(self, service):
        artifact = service.create_document(
            title="P", blocks=[CLAIM], claims=[CLAIM], sources=[SOURCE]
        )

        stored = service.records.get(artifact.id)
        assert "data-zaram-claim" in stored.html
        assert CLAIM.excerpt in stored.html

    def test_a_model_proposed_traversal_cannot_escape(self, service):
        artifact = service.create_document(
            title="P", blocks=["x"], filename="../../escape"
        )

        assert Path(artifact.path).parent == service.store.root

    def test_generated_documents_are_indexed(self, service):
        """Rule 7b's default-on, switched on in the M8 commit.

        This asserted the opposite while the gap was open: `indexed` defaulted
        to False because recall could not yet rank by origin, so a generated
        fact would have entered the Spine with no penalty and Zaram would have
        cited its own restatements. Facts now carry `Origin` and
        `MemoryRankerImpl.GENERATED_PENALTY` demotes them in the ordering, so
        the protection the rule describes — tagging, not exclusion — actually
        exists.
        """
        artifact = service.create_document(title="P", blocks=["x"])

        assert service.records.get(artifact.id).indexed is True

    def test_the_user_can_still_refuse(self, service):
        """`remember_override` is a veto over the default, not a gate."""
        artifact = service.create_document(title="P", blocks=["x"])

        service.records.set_remember_override(artifact.id, False)

        assert service.records.get(artifact.id).remember_override is False


class TestReExport:
    def test_it_re_renders_from_the_stored_html(self, service):
        """Not from the file, and not by re-asking a model. A user wanting the
        PDF of something generated last month must get that document, not a
        fresh one written by a model that has since changed its mind."""
        original = service.create_document(
            title="P", blocks=[CLAIM], claims=[CLAIM], sources=[SOURCE]
        )

        copy = service.re_export(original.id, "md")

        assert copy.id != original.id
        assert copy.html == original.html
        assert copy.filename.endswith(".md")
        assert CLAIM.excerpt in Path(copy.path).read_text(encoding="utf-8")

    def test_it_is_a_new_record_not_a_second_path_on_the_old_one(self, service):
        """Pretending one record describes two files is how a download serves
        the wrong one."""
        original = service.create_document(title="P", blocks=["x"])

        copy = service.re_export(original.id, "md")

        assert service.records.get(original.id).path != copy.path
        assert service.records.get(original.id).path.endswith(".docx")

    def test_re_exporting_something_that_does_not_exist_says_so(self, service):
        with pytest.raises(KeyError):
            service.re_export("art_nope", "md")


class TestTheHttpSurface:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        monkeypatch.setenv("ZARAM_ARTIFACTS_DB", str(tmp_path / "a.db"))
        monkeypatch.setenv("ZARAM_OUTPUT_DIR", str(tmp_path / "out"))

        import main

        # The app is built at import time, so point its service at this test's
        # directories rather than the developer's real ones.
        main.artifact_service = ArtifactService(
            ArtifactRecords(str(tmp_path / "a.db")),
            ArtifactStore(tmp_path / "out"),
        )
        return TestClient(main.app)

    @staticmethod
    def _generate(client, **overrides):
        body = {
            "title": "Proposal — Northwind",
            "blocks": ["Here is the scope.", {"claim_id": "c1"}],
            "project_id": "north",
            "conversation_id": "conv-1",
            "conversation_title": "Q3 scoping",
            "sources": [{"kind": "document", "title": "Master agreement"}],
            "claims": [
                {
                    "id": "c1",
                    "source_id": "memory:55b6",
                    "excerpt": CLAIM.excerpt,
                    "source_excerpt": CLAIM.source_excerpt,
                }
            ],
        }
        body.update(overrides)
        return client.post("/artifacts/generate", json=body)

    def test_an_empty_store_returns_an_empty_list(self, client):
        """Work now renders this, so it has to be the truth and not a 404."""
        body = client.get("/artifacts").json()

        assert body["artifacts"] == []
        assert body["total"] == 0

    def test_generate_then_find_it_in_the_listing(self, client):
        created = self._generate(client).json()

        listed = client.get("/artifacts").json()["artifacts"]

        assert [a["id"] for a in listed] == [created["id"]]
        assert listed[0]["conversation_title"] == "Q3 scoping"
        assert listed[0]["exists"] is True

    def test_the_listing_does_not_carry_the_html(self, client):
        """It is the re-export source and can be large. Twenty documents to
        draw twenty rows is waste."""
        self._generate(client)

        assert "html" not in client.get("/artifacts").json()["artifacts"][0]

    def test_the_detail_view_can_ask_for_it(self, client):
        created = self._generate(client).json()

        detail = client.get(f"/artifacts/{created['id']}?include_html=true").json()

        assert "data-zaram-claim" in detail["html"]

    def test_download_serves_the_file_with_its_real_type(self, client):
        created = self._generate(client).json()

        response = client.get(f"/artifacts/{created['id']}/download")

        assert response.status_code == 200
        assert "wordprocessingml" in response.headers["content-type"]
        assert len(response.content) == created["size_bytes"]

    def test_a_record_whose_file_has_gone_says_which_is_missing(self, client):
        """410, not 404. The user may have moved it, and that is a different
        problem from Zaram having lost the document."""
        created = self._generate(client).json()
        os.remove(created["path"])

        assert client.get(f"/artifacts/{created['id']}/download").status_code == 410
        assert client.get("/artifacts").json()["artifacts"][0]["exists"] is False

    def test_filters_reach_the_query(self, client):
        self._generate(client)

        assert client.get("/artifacts?project_id=north").json()["total"] == 1
        assert client.get("/artifacts?project_id=south").json()["total"] == 0

    def test_projects_are_listed_with_counts(self, client):
        self._generate(client)

        assert client.get("/artifacts/projects").json()["projects"] == [
            {"id": "north", "count": 1}
        ]

    def test_the_static_route_is_not_swallowed_by_the_id_route(self, client):
        """FastAPI matches in declaration order, so `/artifacts/projects`
        registered after `/artifacts/{id}` would 404 as an artifact id."""
        assert client.get("/artifacts/projects").status_code == 200
        assert client.get("/artifacts/formats").status_code == 200

    def test_formats_report_the_unavailable_ones_too(self, client):
        """Disabled capabilities are visible, not silent."""
        formats = client.get("/artifacts/formats").json()["formats"]

        assert {f["extension"] for f in formats} >= {"docx", "md", "xlsx", "png", "pdf"}
        for entry in formats:
            if not entry["available"]:
                assert entry["reason"] and entry["remedy"]

    def test_an_unavailable_format_is_503_with_a_reason(self, client, monkeypatch):
        from artifacts import export
        from artifacts.export.base import Availability

        monkeypatch.setattr(
            export.get("md"),
            "availability",
            lambda: Availability(ok=False, reason="needs a thing", remedy="install it"),
        )

        response = self._generate(client, fmt="md")

        assert response.status_code == 503
        assert response.json()["detail"]["reason"] == "needs a thing"

    def test_a_block_citing_a_claim_that_was_not_supplied_is_refused(self, client):
        """An unanchored sentence that was meant to be cited is the failure the
        whole provenance chain exists to prevent."""
        response = self._generate(
            client, blocks=[{"claim_id": "c-missing"}], claims=[]
        )

        assert response.status_code == 400

    def test_an_unknown_kind_is_refused(self, client):
        assert self._generate(client, kind="hologram").status_code == 400

    def test_missing_artifacts_are_404(self, client):
        assert client.get("/artifacts/art_nope").status_code == 404
        assert client.get("/artifacts/art_nope/download").status_code == 404
        assert (
            client.post("/artifacts/art_nope/remember", json={"remember": True}).status_code
            == 404
        )

    def test_the_remember_override_round_trips_through_http(self, client):
        created = self._generate(client).json()

        client.post(f"/artifacts/{created['id']}/remember", json={"remember": False})
        assert client.get(f"/artifacts/{created['id']}").json()["remember_override"] is False

        client.post(f"/artifacts/{created['id']}/remember", json={"remember": None})
        assert client.get(f"/artifacts/{created['id']}").json()["remember_override"] is None
