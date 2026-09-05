"""Claiming the groups that exist only on their contents.

Project shipped able to create, name, type and delete a project — and both
creation paths for *contents* wrote `project_id` and `project:<id>` without
checking that the project existed. So a stale selection or a typo produced a
group Work grouped files under and Project could not show, rename or delete.

Assignment then started validating its destination, which was right and which
turned untidiness into a **one-way door**: a file could leave such a group and
could not return, because the destination was not a project. On the machine this
was written on that was not hypothetical — nine artifacts carried `harbour` and
`northwind`, and `projects.db` held nothing at all.

Two halves, and both are needed. Adoption is the way back in; validating
generation is what stops the next one arriving. A fix that only did the first
would keep refilling the list it just emptied.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """One backend for the file, as every other route test here does.

    Function scope was the obvious choice — these tests create and adopt
    projects, which is state the next test would inherit — and it cost **255
    seconds for sixteen tests**, because reloading `main` reboots the kernel
    every time. Against a suite that runs in ~197s total, that is not a
    trade-off, it is the wrong fixture.

    Isolation comes from `group()` instead: every test works on an id nothing
    else touches, and assertions are about membership rather than the whole
    list. That is also the more honest shape — a real machine has other groups
    on it, and a test that only passes against an empty database is asserting
    something the product does not promise.
    """
    import importlib

    monkeypatch = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("adoption")
    monkeypatch.setenv("ZARAM_ARTIFACTS_DB", str(root / "artifacts.db"))
    monkeypatch.setenv("ZARAM_PROJECTS_DB", str(root / "projects.db"))
    monkeypatch.setenv("ZARAM_OUTPUT_DIR", str(root / "generated"))

    import main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.app) as test_client:
        test_client.zaram_main = main_module  # type: ignore[attr-defined]
        yield test_client

    monkeypatch.undo()
    importlib.reload(main_module)


#: One id per test, so a shared backend cannot make two tests depend on each
#: other's leftovers. Named after what the test is about rather than numbered —
#: a failure names the id, and "harbour-one-way" locates it immediately.
def group(name: str) -> str:
    return f"ghost-{name}"


def unclaimed_ids(client) -> list[str]:
    return [u["id"] for u in client.get("/projects/unclaimed").json()["unclaimed"]]


def entry_for(client, project_id: str) -> dict:
    body = client.get("/projects/unclaimed").json()["unclaimed"]
    found = [u for u in body if u["id"] == project_id]
    assert found, f"{project_id!r} is not in the unclaimed list: {body}"
    return found[0]


def strand(client, project_id: str, title: str = "Stranded") -> str:
    """Write an artifact carrying a project id no project record exists for.

    Through the records layer rather than the route, and that is the point: the
    route now refuses this, so the only way to produce the condition under test
    is to write it the way the old build did. A fixture that could still be
    made through the front door would mean the door was not closed.
    """
    main_module = client.zaram_main
    artifact = main_module.artifact_service.create_document(
        title=title, blocks=["A paragraph."], fmt="md"
    )
    assert main_module.artifact_service.records.set_project(artifact.id, project_id)
    return artifact.id


class TestSeeingWhatIsUnclaimed:
    def test_a_group_with_files_and_no_project_is_listed(self, client):
        ghost = group("listed")
        strand(client, ghost)

        assert ghost in unclaimed_ids(client)
        assert entry_for(client, ghost)["artifacts"] == 1

    def test_a_real_project_is_not_listed(self, client):
        """The list is what is *missing*, not what exists.

        A project with files in it is the normal case and must never appear
        here — offering to adopt something already adopted is how a user learns
        to distrust the screen.
        """
        created = client.post("/projects", json={"name": "Northwind Real"}).json()
        strand(client, created["id"])

        assert created["id"] not in unclaimed_ids(client)

    def test_counts_say_what_adoption_would_claim(self, client):
        ghost = group("counted")
        strand(client, ghost, title="One")
        strand(client, ghost, title="Two")

        assert entry_for(client, ghost)["artifacts"] == 2

    def test_an_unknown_fact_count_stays_distinguishable_from_zero(self, client):
        """`-1`, never folded into `0`.

        The same rule the delete confirmation follows, for the same reason: "no
        facts" and "the Spine could not say" are different, and adoption is
        about to act on the difference. A test run with no memory runtime is
        exactly the condition that produces it.
        """
        ghost = group("facts")
        strand(client, ghost)

        body = client.get("/projects/unclaimed").json()
        entry = entry_for(client, ghost)

        if body["facts_counted"]:
            assert entry["facts"] >= 0
        else:
            assert entry["facts"] == -1


class TestAdopting:
    def test_the_id_is_kept_exactly(self, client):
        """The whole operation.

        Every artifact row and every `project:<id>` scope points at this
        string. A project created under any other id adopts nothing while
        looking like it succeeded, which is worse than refusing.
        """
        ghost = group("kept-id")
        strand(client, ghost)

        adopted = client.post(f"/projects/{ghost}/adopt", json={"name": "Harbour Lane"}).json()

        assert adopted["id"] == ghost
        assert adopted["name"] == "Harbour Lane"

    def test_the_files_are_in_it_afterwards(self, client):
        """The reason to do any of this — nothing moves, the record arrives."""
        ghost = group("contents")
        artifact_id = strand(client, ghost)

        client.post(f"/projects/{ghost}/adopt", json={"name": "Harbour Lane"})

        listed = {p["id"]: p for p in client.get("/projects").json()["projects"]}
        assert listed[ghost]["artifacts"] == 1
        assert client.get(f"/artifacts/{artifact_id}").json()["project_id"] == ghost

    def test_it_leaves_the_unclaimed_list(self, client):
        ghost = group("leaves-list")
        strand(client, ghost)
        assert ghost in unclaimed_ids(client)

        client.post(f"/projects/{ghost}/adopt", json={"name": "Harbour Lane"})

        assert ghost not in unclaimed_ids(client)

    def test_the_one_way_door_is_open_again(self, client):
        """The defect, stated as the user meets it.

        A file could leave a ghost group and not return, because assignment
        validates its destination and the destination was not a project. This
        is the whole point of adoption, so it is asserted end to end rather
        than inferred from the record existing.
        """
        ghost = group("one-way")
        artifact_id = strand(client, ghost)

        # Before adoption: out is allowed, back in is not.
        assert client.patch(f"/artifacts/{artifact_id}", json={"project_id": ""}).status_code == 200
        assert (
            client.patch(f"/artifacts/{artifact_id}", json={"project_id": ghost}).status_code == 400
        )

        # Adopt via another stranded file, since the first one just left and the
        # group would otherwise be empty — which adoption correctly refuses.
        strand(client, ghost, title="Still here")
        client.post(f"/projects/{ghost}/adopt", json={"name": "Harbour Lane"})

        assert (
            client.patch(f"/artifacts/{artifact_id}", json={"project_id": ghost}).status_code == 200
        )

    def test_the_name_defaults_to_the_id(self, client):
        """The only string the user ever actually wrote for this group.

        Inventing a prettier one would be Zaram deciding what their work is
        called, on evidence that amounts to a slug.
        """
        ghost = group("default-name")
        strand(client, ghost)

        adopted = client.post(f"/projects/{ghost}/adopt", json={}).json()

        assert adopted["name"] == ghost

    def test_the_type_is_asked_for_and_kept(self, client):
        """Adoption is the creation moment, so it is where the type is chosen.

        Rule 7e's one genuine exception: the type activates a pack and cannot
        be inferred from behaviour, so it is asked once rather than guessed
        from whatever files happen to be in the group.
        """
        ghost = group("typed")
        strand(client, ghost)

        adopted = client.post(
            f"/projects/{ghost}/adopt", json={"name": "Harbour Lane", "type": "business"}
        ).json()

        assert adopted["type"] == "business"


class TestRefusing:
    def test_adopting_an_existing_project_is_a_409(self, client):
        created = client.post("/projects", json={"name": "Already A Project"}).json()

        response = client.post(f"/projects/{created['id']}/adopt", json={"name": "Again"})

        assert response.status_code == 409
        assert "already a project" in response.json()["detail"]

    def test_adopting_an_empty_group_is_a_404(self, client):
        """Otherwise this is a create route that picks its own id.

        The ids it would mint are exactly the ones `slugify` exists to keep
        readable in `project:<id>` and in the egress log.
        """
        response = client.post("/projects/nothing-here/adopt", json={"name": "Nothing"})

        assert response.status_code == 404
        assert "nothing to adopt" in response.json()["detail"]

    def test_a_collision_never_silently_renames(self, client):
        """`create` appends `-2` on a colliding slug, which is right for a user
        naming two projects the same and catastrophic here.

        A `<id>-2` would be a cheerful 200 for a project that adopted nothing,
        with the files still stranded — the exact failure this route exists to
        end. The 409 above is what prevents it; this asserts the *outcome*
        rather than the mechanism, so a future change that resolves collisions
        some other way still has to keep the promise.
        """
        created = client.post("/projects", json={"name": "Collision Test"}).json()
        strand(client, created["id"])

        client.post(f"/projects/{created['id']}/adopt", json={"name": "Collision Test"})

        ids = [p["id"] for p in client.get("/projects").json()["projects"]]
        assert ids.count(created["id"]) == 1
        assert f"{created['id']}-2" not in ids


class TestNoNewGhosts:
    def test_generating_into_an_unknown_project_is_refused(self, client):
        """The other half. Adoption without this refills the list it empties.

        Generation wrote `project_id` unchecked while assignment refused it,
        so a file could be born into a project it was forbidden from moving
        into. That asymmetry is how the ghosts arrived.
        """
        response = client.post(
            "/artifacts/generate",
            json={
                "title": "A doc",
                "blocks": ["Text."],
                "fmt": "md",
                "project_id": group("never-existed"),
            },
        )

        assert response.status_code == 400
        assert "No project called" in response.json()["detail"]

    def test_generating_into_a_real_project_still_works(self, client):
        created = client.post("/projects", json={"name": "Generate Target"}).json()

        response = client.post(
            "/artifacts/generate",
            json={
                "title": "A doc",
                "blocks": ["Text."],
                "fmt": "md",
                "project_id": created["id"],
            },
        )

        assert response.status_code == 200, response.text
        assert response.json()["project_id"] == created["id"]

    def test_generating_without_a_project_still_works(self, client):
        """Empty is a real answer, not a missing one.

        Work done outside any project genuinely is not in one, and a check that
        treated "" as an unknown project would make every unfiled document a
        400.
        """
        response = client.post(
            "/artifacts/generate", json={"title": "A doc", "blocks": ["Text."], "fmt": "md"}
        )

        assert response.status_code == 200, response.text
        assert response.json()["project_id"] == ""
