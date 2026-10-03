"""Every store git could stage, wherever the backend writes it.

Found 3 October 2026 by `git status` after a development run, not by reading
`.gitignore`. Two directories had appeared and neither was ignored:

    backend/backups/   copies of the Spine, the egress log, the
                       conversations, and five more — written before a
                       migration, so by definition the whole thing
    backend/screens/   a screenshot of a page, from `look_at_app`

One `git add -A` would have published the maintainer's own data to a public
repository.

**The cause is a shape this codebase has already paid for once.**
`electron-builder.yml` records it: *"A denylist fails open: the next database
somebody adds is included by default and nobody finds out"*, which is why the
installer's payload became an allow-list. `.gitignore` had the same defect by
a different route — it names databases **by path**, so `backend/spine.db*`
covers one location and says nothing about the identical file one directory
along.

git cannot be made an allow-list, so this is the other half: a test that asks
git itself, about every store the code actually opens, in the places the code
actually writes them. Reading the ignore file would only re-read the thing
that was wrong.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

#: Every store the backend opens. Read off `core/paths.py`'s own list plus
#: the ones added since — a name here that no longer exists is harmless, and
#: one missing is the whole failure, so this errs long.
STORES = [
    "spine.db",
    "egress.db",
    "artifacts.db",
    "projects.db",
    "ingest.db",
    "conversations.db",
    "domains.db",
    "obligations.db",
    "plans.db",
    "triggers.db",
    "paired-clients.db",
]

#: Where a store has actually been found. `backups/` is the one that was
#: missed; `screens/` is not a database but is the user's pages.
WHERE = ["", "backups/", "data/", "store/"]

#: SQLite writes these beside the database and they hold the most recent
#: rows — a rule matching only `.db` leaks exactly what was written last.
SIDECARS = ["", "-wal", "-shm", "-journal"]


def ignored(relative: str) -> bool:
    """Does git itself ignore this path?

    Asked of git rather than parsed out of `.gitignore`, because the bug was
    in reading that file correctly. `check-ignore` answers 0 for ignored and
    1 for not.
    """
    result = subprocess.run(
        ["git", "check-ignore", "-q", relative],
        cwd=REPO,
        capture_output=True,
    )
    return result.returncode == 0


@pytest.mark.parametrize("store", STORES)
@pytest.mark.parametrize("where", WHERE)
def test_a_store_is_ignored_wherever_it_is_written(store, where):
    assert ignored(f"backend/{where}{store}"), (
        f"backend/{where}{store} would be staged by `git add -A`. "
        "Ignore it by kind, not by path — a rule naming one location says "
        "nothing about a copy one directory along."
    )


@pytest.mark.parametrize("sidecar", SIDECARS)
def test_the_sidecars_go_too(sidecar):
    """The rows written last are in the WAL, not the database file."""
    assert ignored(f"backend/spine.db{sidecar}")
    assert ignored(f"backend/backups/spine.db{sidecar}")


def test_the_two_directories_that_were_missed():
    assert ignored("backend/backups/anything-at-all.db")
    # Not a database. Screenshots of the person's own pages, which in a
    # checkout land under `backend/` because `data_dir()` is `backend/`.
    assert ignored("backend/screens/some-project/20261001-082714.png")


def test_a_database_nobody_has_invented_yet_is_covered():
    """The point of ignoring by kind.

    The next store added will not be in `STORES` above until somebody
    remembers, and this is what covers it in the meantime.
    """
    assert ignored("backend/whatever_comes_next.db")
    assert ignored("backend/some/deep/place/whatever_comes_next.sqlite3")


def test_the_repository_has_no_store_committed_already():
    """A rule added after the fact does not remove what is already tracked.

    `git check-ignore` answers about untracked files; a database committed
    before the rule existed stays in history and in the working tree, and
    the ignore would hide it from `git status` rather than from anybody
    reading the repository.
    """
    listed = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    tracked = [
        path
        for path in listed
        if path.endswith((".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3"))
        # The manual's own fixtures are checked in on purpose where they
        # exist; a store is what this is about.
        and "test" not in path.lower()
    ]
    assert not tracked, f"these are committed: {tracked}"
