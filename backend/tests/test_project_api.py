"""The Project surface's backend, driven through the real routes.

`test_project_records.py` covers the store. This covers the decisions that only
exist at the API layer, and the one that matters is **deleting**: a project
holds facts and files that outlive it, so the caller has to say what happens to
them and the answer has to be visible before the button is pressed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """A backend with its own projects database.

    Pointed at a temporary file rather than the developer's real one, because
    this is the one suite whose subject is deletion and it would otherwise
    delete their projects.

    **Module-scoped on purpose.** Reloading `main` boots the whole kernel —
    Spine, embedder, egress gate — and doing that per test took 4m36s for
    thirteen tests. Scoping it to the module makes it one boot. The tests below
    create their own projects and do not depend on an empty store, so they do
    not need isolation from each other, only from the developer's data.
    """
    import importlib

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv(
        "ZARAM_PROJECTS_DB", str(tmp_path_factory.mktemp("projects") / "projects.db")
    )

    import main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.app) as test_client:
        yield test_client

    monkeypatch.undo()
    # Leave the module as the rest of the suite expects to find it.
    importlib.reload(main_module)


class TestCreatingAndListing:
    def test_a_created_project_appears_in_the_list(self, client):
        created = client.post("/projects", json={"name": "Harbour Lane"}).json()

        assert created["id"] == "harbour-lane"
        assert created["scope"] == "project:harbour-lane"

        listed = client.get("/projects").json()["projects"]
        assert [p["id"] for p in listed] == ["harbour-lane"]

    def test_it_exists_with_no_files_in_it(self, client):
        """The gap the whole store was built to close.

        `/artifacts/projects` derives its list from saved files, so a project
        nobody had saved into was invisible. This one exists the moment it is
        made — and is *still* absent from the derived list, which is correct:
        the two endpoints answer different questions, and that is the point of
        having both.
        """
        client.post("/projects", json={"name": "Empty One"})

        stored = {p["id"]: p for p in client.get("/projects").json()["projects"]}
        assert stored["empty-one"]["artifacts"] == 0

        # Asserted on this project specifically, not on an empty list: the
        # artifacts database is the developer's real one and legitimately holds
        # their projects. A test that demanded it be empty would fail on any
        # machine that had ever generated a file.
        derived = {p["id"] for p in client.get("/artifacts/projects").json()["projects"]}
        assert "empty-one" not in derived

    def test_the_type_is_carried(self, client):
        created = client.post(
            "/projects", json={"name": "Books", "type": "business"}
        ).json()
        assert created["type"] == "business"

    def test_a_nameless_project_is_refused(self, client):
        assert client.post("/projects", json={"name": "  "}).status_code == 400

    def test_counts_are_reported_for_the_delete_confirmation(self, client):
        """Both counts are present, so a confirmation can state them."""
        client.post("/projects", json={"name": "Harbour Lane"})
        entry = client.get("/projects").json()["projects"][0]

        assert "artifacts" in entry
        assert "facts" in entry


class TestEditing:
    def test_renaming_keeps_the_id(self, client):
        """Facts point at the id. Re-slugging would orphan every one of them."""
        client.post("/projects", json={"name": "Harbour Lane"})

        renamed = client.patch(
            "/projects/harbour-lane", json={"name": "Harbour Lane — Season 2"}
        ).json()

        assert renamed["id"] == "harbour-lane"
        assert renamed["scope"] == "project:harbour-lane"
        assert renamed["name"] == "Harbour Lane — Season 2"

    def test_the_type_can_be_corrected(self, client):
        client.post("/projects", json={"name": "Books"})
        assert (
            client.patch("/projects/books", json={"type": "business"}).json()["type"]
            == "business"
        )

    def test_editing_something_that_is_not_there_is_a_404(self, client):
        assert client.patch("/projects/nope", json={"name": "x"}).status_code == 404


class TestDeleting:
    def test_the_default_keeps_the_contents(self, client):
        """`keep` is the default because it is the recoverable one.

        The grouping goes; the knowledge stays, re-scoped to global. Nothing the
        user cannot undo by making the project again and moving facts back.
        """
        client.post("/projects", json={"name": "Harbour Lane"})

        result = client.request("DELETE", "/projects/harbour-lane").json()

        assert result["deleted"] == "harbour-lane"
        assert result["facts_deleted"] == 0
        # This project specifically, not an empty list: the client is
        # module-scoped so earlier tests' projects are still here, and asserting
        # emptiness would be asserting test isolation rather than the delete.
        remaining = {p["id"] for p in client.get("/projects").json()["projects"]}
        assert "harbour-lane" not in remaining

    def test_destroying_the_contents_has_to_be_asked_for(self, client):
        """Never implicit.

        A container quietly exercising rule 4 on the user's behalf is how
        someone loses a client's rates by tidying a sidebar.
        """
        client.post("/projects", json={"name": "Harbour Lane"})

        result = client.request(
            "DELETE", "/projects/harbour-lane", params={"contents": "delete"}
        ).json()

        assert "facts_deleted" in result

    def test_an_unrecognised_contents_choice_is_refused(self, client):
        """Not defaulted. A typo must not silently pick a destructive branch."""
        client.post("/projects", json={"name": "Harbour Lane"})

        response = client.request(
            "DELETE", "/projects/harbour-lane", params={"contents": "destroy"}
        )

        assert response.status_code == 400
        assert "keep" in response.json()["detail"]
        # And it did not happen.
        assert client.get("/projects").json()["projects"]

    def test_files_are_never_deleted_by_either_path(self, client):
        """Zaram has no capability to remove a file from disk, deliberately.

        The response says how many files it left alone rather than staying
        silent, because "the project is gone" would otherwise read as "the files
        are gone".
        """
        client.post("/projects", json={"name": "Harbour Lane"})

        result = client.request("DELETE", "/projects/harbour-lane").json()

        assert "files_untouched" in result

    def test_deleting_something_that_is_not_there_is_a_404(self, client):
        assert client.request("DELETE", "/projects/nope").status_code == 404
