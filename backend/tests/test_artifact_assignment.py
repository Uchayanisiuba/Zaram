"""Putting a file into a project, taking it out, and moving it between two.

Project shipped as a node you could create, name, type and delete — and could
not put anything into. The store had carried `project_id` since M8 and the
surface had no way to set it, so a project could only be filled by being
selected in the composer *before* a file existed. That is rule 7h backwards: it
asks the user to decide in advance of the work instead of at the moment the
answer is obvious.

The decision this file is really guarding is **validation on the destination**.
An unchecked write would let a typo create a project that exists only as a
string on one artifact — absent from `/projects`, so unnameable, undeletable,
and able to accumulate facts under a scope nothing points at. Splitting
`/projects` from `/artifacts/projects` fixed exactly that class of ghost; an
unvalidated assignment would reintroduce it from the other end.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """A backend with its own projects *and* artifacts databases.

    Both, not just projects: these tests write artifacts, and pointing only the
    project store at a temporary file would leave the developer's real
    `artifacts.db` accumulating test rows that then show up in Work.

    Module-scoped for the reason `test_project_api.py` gives — reloading `main`
    boots the whole kernel, and doing that per test costs minutes.
    """
    import importlib

    monkeypatch = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("assignment")
    monkeypatch.setenv("ZARAM_PROJECTS_DB", str(root / "projects.db"))
    monkeypatch.setenv("ZARAM_ARTIFACTS_DB", str(root / "artifacts.db"))

    import main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.app) as test_client:
        test_client.zaram_main = main_module  # type: ignore[attr-defined]
        yield test_client

    monkeypatch.undo()
    # Leave the module as the rest of the suite expects to find it.
    importlib.reload(main_module)


def make_artifact(client, filename: str, project_id: str = "") -> str:
    """A stored artifact, without going through generation.

    Generation is a different subject with its own suite. What assignment needs
    is a row with an id, and building one directly keeps the failure messages
    about assignment rather than about rendering.
    """
    from artifacts.contracts import Artifact

    artifact = client.zaram_main.artifact_service.records.put(
        Artifact(filename=filename, project_id=project_id)
    )
    return artifact.id


class TestAssigning:
    def test_a_file_moves_into_a_project(self, client):
        client.post("/projects", json={"name": "Harbour Lane"})
        artifact = make_artifact(client, "harbour-brief.docx")

        response = client.patch(f"/artifacts/{artifact}", json={"project_id": "harbour-lane"})

        assert response.status_code == 200
        assert response.json()["project_id"] == "harbour-lane"
        assert client.get(f"/artifacts/{artifact}").json()["project_id"] == "harbour-lane"

    def test_the_project_counts_it(self, client):
        """The count on the delete confirmation is the one that matters.

        It is derived from the artifacts table rather than stored on the
        project, so assignment has to be enough to move it. A count that needed
        a second write to stay true would be wrong for as long as that write
        was missing.
        """
        client.post("/projects", json={"name": "Northwind"})
        artifact = make_artifact(client, "northwind-quote.docx")

        before = _project(client, "northwind")["artifacts"]
        client.patch(f"/artifacts/{artifact}", json={"project_id": "northwind"})
        after = _project(client, "northwind")["artifacts"]

        assert (before, after) == (0, 1)

    def test_a_file_moves_between_projects(self, client):
        client.post("/projects", json={"name": "First"})
        client.post("/projects", json={"name": "Second"})
        artifact = make_artifact(client, "moved.docx", project_id="first")

        client.patch(f"/artifacts/{artifact}", json={"project_id": "second"})

        assert _project(client, "first")["artifacts"] == 0
        assert _project(client, "second")["artifacts"] == 1

    def test_a_file_leaves_its_project_without_being_deleted(self, client):
        """Unassigning is `""`, and it restores the state a file is born in.

        Not a third state, and not a delete. Work's "No project" filter has to
        find it afterwards, which it cannot do if leaving a project invents a
        new value for "nowhere".
        """
        client.post("/projects", json={"name": "Temporary"})
        artifact = make_artifact(client, "loose.docx", project_id="temporary")

        response = client.patch(f"/artifacts/{artifact}", json={"project_id": ""})

        assert response.status_code == 200
        assert client.get(f"/artifacts/{artifact}").json()["project_id"] == ""
        assert _project(client, "temporary")["artifacts"] == 0


class TestRefusing:
    def test_an_unknown_project_is_refused_rather_than_created(self, client):
        """The ghost-project bug, approached from the artifact side.

        Storing the string would produce a project that `/projects` has never
        heard of: it cannot be renamed, cannot be deleted, and its scope would
        collect facts nothing points at.
        """
        artifact = make_artifact(client, "orphan.docx")

        response = client.patch(f"/artifacts/{artifact}", json={"project_id": "no-such-project"})

        assert response.status_code == 400
        assert "no-such-project" in response.json()["detail"]
        assert client.get(f"/artifacts/{artifact}").json()["project_id"] == ""

    def test_an_unknown_artifact_is_a_404(self, client):
        client.post("/projects", json={"name": "Real"})

        response = client.patch("/artifacts/art_nothing", json={"project_id": "real"})

        assert response.status_code == 404

    def test_an_omitted_project_id_is_not_read_as_unassign(self, client):
        """`null` and `""` are different instructions.

        A caller that sent no field said nothing; a caller that sent `""` asked
        for the file to leave its project. Treating the first as the second
        makes any future partial update silently destructive.
        """
        client.post("/projects", json={"name": "Kept"})
        artifact = make_artifact(client, "kept.docx", project_id="kept")

        response = client.patch(f"/artifacts/{artifact}", json={})

        assert response.status_code == 400
        assert client.get(f"/artifacts/{artifact}").json()["project_id"] == "kept"


def _project(client, project_id: str) -> dict:
    projects = client.get("/projects").json()["projects"]
    return next(p for p in projects if p["id"] == project_id)
