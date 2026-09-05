"""Importing files from a project puts them *in* that project.

Reported by the maintainer, 3 September 2026: Project had no way to bring
documents in, so the only way to give Zaram a project's own material was to
index it in Knowledge, where it lands global and is recalled everywhere.

**The thing that made it worth a test rather than a form field**: rule 7i's
scope has been on the store since M8, and `IngestService._store_fact` has read
`metadata.get("scope")` since then too, with a comment saying *"a folder is
indexed into a project when one is active"*. Nothing ever put a scope in that
metadata. So the field existed, the reader existed, the migration existed, and
every ingested fact was global — the same shape as this repository's fifteen
unreachable subsystems, at the size of one dictionary key.

These go in through the front door for the same reason
`test_ingest_routes_reach_the_service.py` does: the half that was missing was
never the service.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient


class _Spine:
    """A memory runtime that records what it was asked to remember."""

    def __init__(self) -> None:
        self.written: list[dict[str, Any]] = []

    async def remember(self, **kwargs: Any) -> str:
        self.written.append(kwargs)
        return f"fact-{len(self.written)}"

    def scopes(self) -> set[str | None]:
        return {entry.get("scope") for entry in self.written}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A client whose ingest, projects and Spine all live in `tmp_path`."""
    from ingest.records import IngestRecords
    from ingest.service_api import IngestService
    from projects.records import ProjectRecords

    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))

    main = importlib.import_module("main")
    monkeypatch.setattr(
        main, "ingest_service", IngestService(IngestRecords(str(tmp_path / "ingest.db")))
    )
    monkeypatch.setattr(
        main, "project_records", ProjectRecords(str(tmp_path / "projects.db"))
    )

    spine = _Spine()
    # The routes re-attach the kernel's runtime on every request, so the fake
    # has to be reachable from there rather than set on the service.
    monkeypatch.setattr(main.kernel, "memory_runtime", spine, raising=False)

    test_client = TestClient(main.app)
    test_client.spine = spine  # type: ignore[attr-defined]
    test_client.projects = main.project_records  # type: ignore[attr-defined]
    return test_client


def events(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def _upload(client, *, project_id: str | None = None):
    data = {"project_id": project_id} if project_id is not None else None
    return client.post(
        "/ingest/upload",
        files=[("files", ("brief.txt", b"The Northwind rate is 450 a day.", "text/plain"))],
        data=data,
    )


class TestAnImportBelongsToItsProject:
    def test_every_fact_carries_the_project_scope(self, client):
        project = client.projects.create("Northwind")

        response = _upload(client, project_id=project.id)

        assert response.status_code == 200
        assert [e["status"] for e in events(response) if e["type"] == "file"] == ["indexed"]
        assert client.spine.written, "nothing reached the Spine at all"
        assert client.spine.scopes() == {f"project:{project.id}"}

    def test_the_same_files_without_a_project_stay_global(self, client):
        """The unscoped path is unchanged, byte for byte.

        `None` and not the string "global": the store's own default decides
        what an unscoped fact is called, and spelling it here would be a second
        place that has to agree with it.
        """
        response = _upload(client)

        assert response.status_code == 200
        assert client.spine.written
        assert client.spine.scopes() == {None}


class TestAnUnknownProjectIsRefused:
    """Quietly indexing globally is the one outcome that cannot be undone.

    The scope is written onto each fact and nothing records which run wrote it,
    so a stale or mistyped id would put a project's documents in the general
    pool with no way to find them again. Rule 5's posture, applied to scope.
    """

    def test_it_is_a_404_rather_than_a_silent_global_ingest(self, client):
        response = _upload(client, project_id="no-such-project")

        assert response.status_code == 404
        assert "no project" in response.json()["detail"].lower()
        assert client.spine.written == []

    def test_and_nothing_is_left_on_disk(self, client, tmp_path: Path):
        _upload(client, project_id="no-such-project")

        kept = list((tmp_path / "uploads").glob("*")) if (tmp_path / "uploads").exists() else []
        assert kept == [], f"files were written for a request that was refused: {kept}"

    def test_pasted_text_is_refused_the_same_way(self, client):
        response = client.post(
            "/ingest/text",
            json={"text": "Payment is due thirty days after invoice.",
                  "project_id": "no-such-project"},
        )

        assert response.status_code == 404
        assert client.spine.written == []
