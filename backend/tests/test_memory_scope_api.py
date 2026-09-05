"""Moving a fact between global and a project, through the real route.

`test_memory_scope.py` grades the scoping *policy* and
`test_project_scope_reaches_the_spine.py` grades whether capture reaches it.
Neither covers the user changing their mind afterwards, which is the half rule
7i leaves to the person: promotion to global is evidence-driven and asked for,
but nothing let them answer, and nothing let them move a fact the system never
asked about.

The direction matters and is why the destination is validated. Project memory
is shareable and global memory never is, so moving a fact *into* a project
widens who could eventually see it. A typo that silently created a scope
nothing points at would put facts somewhere no project can be corrected or
deleted from — rule 4 broken by a spelling mistake.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from runtimes.memory.contracts import GLOBAL_SCOPE, project_scope


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """A backend with its own Spine and project store.

    `ZARAM_SPINE_PATH` matters most: these tests write facts, and without it
    they would land in the developer's real Spine and be recalled in their next
    conversation.
    """
    import importlib

    monkeypatch = pytest.MonkeyPatch()
    root = tmp_path_factory.mktemp("scope-api")
    monkeypatch.setenv("ZARAM_SPINE_PATH", str(root / "spine.db"))
    monkeypatch.setenv("ZARAM_PROJECTS_DB", str(root / "projects.db"))
    monkeypatch.setenv("ZARAM_ARTIFACTS_DB", str(root / "artifacts.db"))

    import main as main_module

    importlib.reload(main_module)
    with TestClient(main_module.app) as test_client:
        if main_module.kernel.memory_runtime is None:
            pytest.skip("No memory runtime: the scope route has nothing to move.")
        test_client.zaram_main = main_module  # type: ignore[attr-defined]
        yield test_client

    monkeypatch.undo()
    importlib.reload(main_module)


@pytest.fixture
def remember(client):
    """Store a fact and hand back its id.

    Awaited by the caller rather than driven with `run_until_complete`. The
    latter passed in isolation and failed under the full suite — by then
    another module has closed the thread's loop, and `get_event_loop()` raises
    instead of making one. A test that only passes when run alone is a test
    that will be blamed on the suite.
    """

    async def _remember(content: str, scope: str = GLOBAL_SCOPE) -> str:
        runtime = client.zaram_main.kernel.memory_runtime
        return await runtime.remember(content=content, scope=scope)

    return _remember


def scope_of(client, record_id: str) -> str:
    return client.get(f"/memory/{record_id}").json()["scope"]


class TestMoving:
    async def test_a_global_fact_moves_into_a_project(self, client, remember):
        client.post("/projects", json={"name": "Harbour Lane"})
        fact = await remember("The kickoff is on the 3rd.")

        response = client.post(f"/memory/{fact}/scope", json={"project_id": "harbour-lane"})

        assert response.status_code == 200
        assert response.json()["scope"] == "project:harbour-lane"
        assert scope_of(client, fact) == "project:harbour-lane"

    async def test_a_project_fact_is_promoted_to_global(self, client, remember):
        """Rule 7e's question, finally answerable.

        A fact recalled across three projects is probably about the person.
        Zaram asks at that point — and until this route existed there was
        nowhere for the answer to go.
        """
        client.post("/projects", json={"name": "Northwind"})
        fact = await remember("I write in British English.", scope=project_scope("northwind"))

        response = client.post(f"/memory/{fact}/scope", json={"project_id": ""})

        assert response.status_code == 200
        assert response.json()["scope"] == GLOBAL_SCOPE
        assert scope_of(client, fact) == GLOBAL_SCOPE

    async def test_the_project_fact_count_follows_it(self, client, remember):
        """The count the delete confirmation is built on has to move too.

        "This holds 0 facts" on a dialog that then destroys one is the failure
        the count exists to prevent, and a move that did not update it would
        produce exactly that.
        """
        client.post("/projects", json={"name": "Counted"})
        fact = await remember("Their day rate is 450.")

        before = _project(client, "counted")["facts"]
        client.post(f"/memory/{fact}/scope", json={"project_id": "counted"})
        after = _project(client, "counted")["facts"]

        assert before == 0
        assert after == 1


class TestRefusing:
    async def test_an_unknown_project_is_refused(self, client, remember):
        fact = await remember("Something true.")

        response = client.post(f"/memory/{fact}/scope", json={"project_id": "ghost"})

        assert response.status_code == 400
        assert scope_of(client, fact) == GLOBAL_SCOPE

    def test_an_unknown_fact_is_a_404(self, client):
        client.post("/projects", json={"name": "Real Enough"})

        response = client.post("/memory/mem_nothing/scope", json={"project_id": "real-enough"})

        assert response.status_code == 404


def _project(client, project_id: str) -> dict:
    projects = client.get("/projects").json()["projects"]
    return next(p for p in projects if p["id"] == project_id)
