"""A project is an object you can make, rename and remove.

Before this it was `SELECT DISTINCT project_id FROM artifacts` — so a project
existed only if a file had been saved into it, could not be created, could not
be renamed, could not be deleted, and had nowhere to keep the **type** that
`CLAUDE.md` says is chosen at creation and activates a pack.

The measurement that made it urgent: on the live machine, `artifacts.db` held
projects `harbour` and `northwind`, and `spine.db` held **zero** facts scoped to
either. Project scope reaches the Spine by design and had never been exercised,
because nothing could put a user inside a project before they saved a file.
"""

from __future__ import annotations

import pytest

from projects.records import (
    Project,
    ProjectRecords,
    ProjectType,
    UnknownProject,
    slugify,
)


@pytest.fixture
def records(tmp_path) -> ProjectRecords:
    return ProjectRecords(str(tmp_path / "projects.db"))


class TestCreating:
    def test_a_project_exists_before_it_has_any_files(self, records):
        """The gap that motivated the whole store."""
        project = records.create("Harbour Lane")
        assert records.get(project.id) == project
        assert [p.id for p in records.list()] == [project.id]

    def test_the_id_is_readable(self, records):
        """It appears in `project:<id>` on every fact and in the egress log.

        `project:a3f9c2` tells a user reading their own logs nothing, which is
        why this is a slug and not a uuid.
        """
        assert records.create("Harbour Lane").id == "harbour-lane"

    def test_the_type_is_recorded_at_creation(self, records):
        project = records.create("Books", type=ProjectType.BUSINESS)
        assert records.get(project.id).type is ProjectType.BUSINESS

    def test_the_type_defaults_rather_than_demanding_a_choice(self, records):
        """A required choice at creation is a wall in front of the first project.

        Rule 7e: never ask a question the system can answer from behaviour. It
        cannot answer this one, so it is asked — but it must be answerable by
        someone who does not yet know, or nobody makes a first project.
        """
        assert records.create("Something").type is ProjectType.GENERAL

    def test_two_projects_may_share_a_name(self, records):
        """A rebuild, a second season. Refusing it makes people invent names."""
        first = records.create("Harbour Lane")
        second = records.create("Harbour Lane")

        assert first.id != second.id
        assert second.id == "harbour-lane-2"
        assert {p.name for p in records.list()} == {"Harbour Lane"}

    def test_a_nameless_project_is_refused(self, records):
        with pytest.raises(ValueError):
            records.create("   ")

    def test_a_name_of_only_punctuation_still_gets_a_usable_id(self, records):
        """The slug cannot be empty — it is a primary key and a scope string."""
        project = records.create("!!!")
        assert project.id
        assert records.get(project.id).name == "!!!"


class TestRenaming:
    def test_the_name_changes_and_the_id_does_not(self, records):
        """**The important one.**

        Facts carry `project:<id>` and artifacts carry `project_id`. Re-slugging
        on rename would orphan every one of them — a migration wearing the
        costume of an edit. So a rename is exactly and only a rename.
        """
        project = records.create("Harbour Lane")
        renamed = records.rename(project.id, "Harbour Lane — Season 2")

        assert renamed.id == project.id == "harbour-lane"
        assert renamed.name == "Harbour Lane — Season 2"

    def test_renaming_something_that_is_not_there_says_so(self, records):
        with pytest.raises(UnknownProject):
            records.rename("nope", "New")

    def test_an_empty_rename_is_refused(self, records):
        project = records.create("Harbour Lane")
        with pytest.raises(ValueError):
            records.rename(project.id, "  ")


class TestTheType:
    def test_it_can_be_corrected(self, records):
        """CLAUDE.md says the type is chosen "once at creation".

        The alternative to allowing a change is deleting and remaking the
        project, which takes its facts and files with it — much worse than
        letting someone fix a ten-second choice made before they knew what the
        project was.
        """
        project = records.create("Books")
        assert records.set_type(project.id, ProjectType.BUSINESS).type is ProjectType.BUSINESS

    def test_a_type_from_a_newer_build_degrades_instead_of_raising(self, records):
        """A project made by a newer version must still open.

        Raising here would take the whole list down with it, so one unreadable
        row cannot cost the user every project they have.
        """
        project = records.create("Books")
        with records._connect() as conn:
            conn.execute(
                "UPDATE projects SET type = ? WHERE id = ?", ("quantum", project.id)
            )

        assert records.get(project.id).type is ProjectType.GENERAL
        assert len(records.list()) == 1


class TestDeleting:
    def test_it_removes_the_record(self, records):
        project = records.create("Harbour Lane")
        records.delete(project.id)

        assert records.list() == []
        with pytest.raises(UnknownProject):
            records.get(project.id)

    def test_deleting_something_that_is_not_there_says_so(self, records):
        with pytest.raises(UnknownProject):
            records.delete("nope")

    def test_it_does_not_reach_into_anything_else(self, records):
        """Asserted on the method's own surface, deliberately.

        `delete` takes no store but its own and touches nothing but its own
        table. A project holds facts and files that outlive it; rule 4 gives the
        *user* power over their facts, and a container exercising that power on
        their behalf is how someone loses a client's rates by tidying a sidebar.
        Deciding the contents' fate belongs one layer up, where the counts are
        known and can be shown.
        """
        import inspect

        source = inspect.getsource(ProjectRecords.delete)
        assert "DELETE FROM projects" in source
        for other in ("artifacts", "memories", "spine"):
            assert other not in source.lower().split('"""')[-1], (
                f"delete reaches into {other}; contents are not its decision"
            )


class TestScope:
    def test_a_project_knows_its_scope_string(self, records):
        """One obvious way from a project to the scope its facts carry.

        Delegated to `runtimes.memory.contracts.project_scope` rather than
        spelled here — rule 7i says that spelling lives in one place, and two
        copies is precisely how they diverge.
        """
        assert records.create("Harbour Lane").scope == "project:harbour-lane"


class TestSlug:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Harbour Lane", "harbour-lane"),
            ("  Spaced  Out  ", "spaced-out"),
            ("Ampersand & Co.", "ampersand-co"),
            # Accents fold to their base letter rather than vanishing. The first
            # version stripped them and turned this into "n-cod-studio", which
            # is what a French, German or Yorùbá business name would have got.
            ("Ünïcodé Studio", "unicode-studio"),
            ("Café Ròsé", "cafe-rose"),
            ("2026 Season", "2026-season"),
        ],
    )
    def test_readable_and_stable(self, name, expected):
        assert slugify(name) == expected

    def test_a_name_in_a_non_latin_script_still_gets_an_id(self):
        """It folds to nothing, which is a real case and not an error.

        A generated id is worse to read than a slug and infinitely better than a
        refusal to create the project.
        """
        slug = slugify("日本語プロジェクト")
        assert slug.startswith("project-")

    def test_a_very_long_name_is_truncated(self):
        """It ends up in every log line for that project."""
        assert len(slugify("word " * 60)) <= 48

    def test_it_is_deterministic(self):
        assert slugify("Harbour Lane") == slugify("Harbour Lane")


class TestPersistence:
    def test_projects_survive_a_restart(self, tmp_path):
        path = str(tmp_path / "p.db")
        created = ProjectRecords(path).create("Harbour Lane", type=ProjectType.THREE_D)

        reopened = ProjectRecords(path)
        assert reopened.get(created.id).type is ProjectType.THREE_D
        assert reopened.get(created.id).name == "Harbour Lane"

    def test_the_list_is_in_creation_order(self, records):
        """The order they built them in, not the alphabet.

        Closer to how someone thinks about their own projects, and it keeps a
        newly created one at the end where it was just added rather than
        jumping into the middle of the list.
        """
        names = ["Zulu", "Alpha", "Mike"]
        for name in names:
            records.create(name)
        assert [p.name for p in records.list()] == names
