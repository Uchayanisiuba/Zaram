"""Projects as objects, not as labels that happen to exist.

Before this, a project was whatever `SELECT DISTINCT project_id FROM artifacts`
returned. That had a real argument behind it — a projects table is a second
place for the same truth, and the first thing it would do is disagree, offering
a filter for a project with nothing in it. The argument was sound for a
*filter*. It fails for everything the project has to become:

* **A project with no artifacts did not exist.** Facts scoped `project:<id>`
  were invisible, so a project you had only *talked* about was not there.
* **It could not be created**, only caused to appear by saving a file into it.
* **It could not be renamed or deleted**, so one made by a typo was permanent.
* **It had nowhere to keep a type**, and `CLAUDE.md` says the type is chosen at
  creation and activates a pack. Derived projects have no creation moment.

The disagreement the old comment feared is answered by making this store the
authority and Work's `projects()` a *view* over artifacts, rather than by having
no store at all.
"""

from .records import Project, ProjectRecords, ProjectType, UnknownProject

__all__ = ["Project", "ProjectRecords", "ProjectType", "UnknownProject"]
