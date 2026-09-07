"""The code tools exist in the running product, not only in their own test.

`test_the_code_tools_are_reachable.py` registers the server by hand and proves
the runtime can list and call it. That is necessary and it is not sufficient:
the same was true of the MCP runtime for a fortnight while nothing could name
`mcp.call`, and of fifteen other subsystems here. So this asserts the two links
that turn a module into a feature.

**The bootstrapper attaches it.** Against the real boot path, not a fixture
that repeats it.

**The sandbox comes from the open project.** A coding project's `root` is the
boundary; every other case — no project, another type, a project nobody has
pointed at a folder — resolves to nothing, and the tools refuse with a reason
rather than reading whatever was open last.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from packs.code import SERVER_ID, active_root, set_active_root
from projects.records import ProjectRecords, ProjectType


@pytest.fixture(autouse=True)
def _no_project_left_open():
    """A ContextVar set by one test is a sandbox inherited by the next."""
    set_active_root(None)
    yield
    set_active_root(None)


class TestTheActiveProjectIsTheBoundary:
    def test_a_folder_that_is_set_is_returned(self, tmp_path):
        set_active_root(str(tmp_path))

        assert active_root() == tmp_path

    def test_nothing_open_means_nothing_readable(self):
        assert active_root() is None

    def test_a_folder_that_has_gone_is_not_a_root(self, tmp_path):
        """Answering with a path that will fail on first use makes every tool
        report an OSError; answering None makes them report the real problem."""
        missing = tmp_path / "deleted"
        set_active_root(str(missing))

        assert active_root() is None

    def test_a_file_is_not_a_root(self, tmp_path):
        page = tmp_path / "notes.md"
        page.write_text("hello", encoding="utf-8")
        set_active_root(str(page))

        assert active_root() is None


class TestOnlyACodingProjectOpensAFolder:
    @pytest.fixture
    def records(self, tmp_path):
        return ProjectRecords(str(tmp_path / "projects.db"))

    def _open(self, monkeypatch, records, project_id):
        import main

        monkeypatch.setattr(main, "project_records", records)
        main._open_code_project(project_id)

    def test_a_coding_project_opens_its_repository(self, monkeypatch, records, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        project = records.create("Zaram", type=ProjectType.CODING, root=str(repo))

        self._open(monkeypatch, records, project.id)

        assert active_root() == repo

    def test_another_type_opens_nothing(self, monkeypatch, records, tmp_path):
        """A business project has documents, not a sandbox — and a folder is
        not a thing to hand a tool because a project happens to name one."""
        repo = tmp_path / "repo"
        repo.mkdir()
        project = records.create("Books", type=ProjectType.BUSINESS, root=str(repo))

        self._open(monkeypatch, records, project.id)

        assert active_root() is None

    def test_a_coding_project_with_no_folder_opens_nothing(self, monkeypatch, records):
        project = records.create("Later", type=ProjectType.CODING)

        self._open(monkeypatch, records, project.id)

        assert active_root() is None

    def test_no_project_clears_what_was_open(self, monkeypatch, records, tmp_path):
        """The failure this guards: a question asked with no project open
        reading the last repository somebody looked at."""
        repo = tmp_path / "repo"
        repo.mkdir()
        set_active_root(str(repo))

        self._open(monkeypatch, records, "")

        assert active_root() is None

    def test_an_unknown_project_is_not_an_error(self, monkeypatch, records):
        """A lookup that fails must not fail somebody's reply."""
        self._open(monkeypatch, records, "no-such-project")

        assert active_root() is None


class TestTheProjectRecordCarriesIt:
    def test_the_root_survives_a_round_trip(self, tmp_path):
        records = ProjectRecords(str(tmp_path / "projects.db"))
        stored = records.create("Zaram", type=ProjectType.CODING, root="C:/Zaram")

        assert records.get(stored.id).root == "C:/Zaram"

    def test_a_database_written_before_the_column_existed_still_opens(self, tmp_path):
        """`CREATE TABLE IF NOT EXISTS` is silent about a table that exists and
        differs, which is how a schema change becomes `no such column` on
        somebody's machine and nowhere else."""
        import sqlite3

        path = tmp_path / "old.db"
        old = sqlite3.connect(path)
        old.execute(
            "CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, "
            "type TEXT NOT NULL DEFAULT 'general', created_at REAL NOT NULL, "
            "note TEXT NOT NULL DEFAULT '')"
        )
        old.execute(
            "INSERT INTO projects VALUES ('old', 'Before', 'coding', 1.0, '')"
        )
        old.commit()
        old.close()

        records = ProjectRecords(str(path))

        assert records.get("old").root == ""
        assert records.create("After", root="/tmp/x").root == "/tmp/x"


@pytest.mark.asyncio
async def test_the_bootstrapper_attaches_the_code_server():
    """Registering is not reaching, and this repository has the scars. Asserted
    against the real boot path — if the registration line is deleted, the tools
    stop existing for the product while every other test here still passes."""
    from core.bootstrapper import KernelBootstrapper

    kernel = KernelBootstrapper()
    await kernel.boot()
    try:
        listed = await kernel.mcp_runtime.execute("mcp.list_tools", {"query": "read a file"})

        assert listed["success"] is True
        offered = {tool["name"] for tool in listed["tools"] if tool["server"] == SERVER_ID}
        assert {"list_files", "read_lines", "search_code"} <= offered
    finally:
        await kernel.shutdown()


class TestAUserCanPointItAtARepository:
    """The gap that made every test above true and the feature unusable.

    `Project.root` shipped on 6 September with its migration, its `ContextVar`
    and a sandbox check on every path — and **no route could set it**.
    `ProjectCreateRequest` had no such field and neither did the update, so a
    coding project could only be given a folder by calling `ProjectRecords`
    from Python. The tools were reachable; the feature was not, which is this
    repository's own failure shape arriving through the API layer rather than
    through a missing caller.

    A handoff written the day before said it was "reachable through the API
    only". That was wrong, and reading the request model rather than the note is
    what found it.
    """

    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        import main
        from fastapi.testclient import TestClient

        monkeypatch.setattr(
            main, "project_records", ProjectRecords(str(tmp_path / "projects.db"))
        )
        return TestClient(main.app)

    def test_a_project_can_be_created_with_a_repository(self, client, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()

        made = client.post(
            "/projects", json={"name": "Zaram", "type": "coding", "root": str(repo)}
        )

        assert made.status_code == 200, made.text
        assert made.json()["root"] == str(repo.resolve())

    def test_a_repository_can_be_added_afterwards(self, client, tmp_path):
        """Every project made before today has no folder, so this is the path
        that matters most — a create-only field would strand all of them."""
        repo = tmp_path / "repo"
        repo.mkdir()
        made = client.post("/projects", json={"name": "Zaram", "type": "coding"}).json()

        changed = client.patch(f"/projects/{made['id']}", json={"root": str(repo)})

        assert changed.status_code == 200, changed.text
        assert changed.json()["root"] == str(repo.resolve())

    def test_a_folder_that_does_not_exist_is_refused_with_the_reason(self, client, tmp_path):
        """Rule 9's shape: a root naming nothing makes every later tool call
        refuse with "outside the project folder", which is a true sentence about
        the wrong problem and sends the user looking at permissions."""
        answer = client.post(
            "/projects",
            json={"name": "Zaram", "type": "coding", "root": str(tmp_path / "nope")},
        )

        assert answer.status_code == 400
        assert "not a folder" in answer.json()["detail"]

    def test_a_file_is_not_a_repository(self, client, tmp_path):
        loose = tmp_path / "notes.md"
        loose.write_text("hello", encoding="utf-8")

        answer = client.post(
            "/projects", json={"name": "Zaram", "type": "coding", "root": str(loose)}
        )

        assert answer.status_code == 400

    def test_the_folder_can_be_withdrawn_without_deleting_the_project(self, client, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        made = client.post(
            "/projects", json={"name": "Zaram", "type": "coding", "root": str(repo)}
        ).json()

        cleared = client.patch(f"/projects/{made['id']}", json={"root": ""})

        assert cleared.status_code == 200
        assert cleared.json()["root"] == ""

    def test_the_listing_says_which_folder_each_project_reads(self, client, tmp_path):
        """Without this the interface cannot show an unfinished setup — a coding
        project with no folder looks identical to one with a folder."""
        repo = tmp_path / "repo"
        repo.mkdir()
        client.post("/projects", json={"name": "Zaram", "type": "coding", "root": str(repo)})

        listed = client.get("/projects").json()

        assert listed["projects"][0]["root"] == str(repo.resolve())
