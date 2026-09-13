"""An unfinished task, kept so it can be picked up after a restart.

`projects/records.py` predicted this file: *"everything a project appears to
contain (artifacts, facts, later a plan) lives in its own store and points back
here by id"*. This is the plan, and `CLAUDE.md` assigns it to **Project** —
*"the steps, decisions taken and decisions rejected"*.

What it is, and what it is not
------------------------------
**It holds what the tools returned, never what was said.** Rule 7d keeps session
state and long-term memory apart, and the patterns section rejects persisting
raw dialogue by name — their pipeline keeps L0 for verification, ours keeps
provenance instead. So a step here is a call that ran and its result. The
model's prose between calls does not survive, and nothing here is ever recalled
into another conversation: this is machinery, not memory, and putting machinery
in the Spine is how Zaram would start citing its own working notes.

**It does not carry a system prompt, deliberately.** The obvious design stores
the context the task was running under so a resume is identical. That would
freeze a copy of whatever recall found at the time — and rule 4 says a fact the
user corrects or deletes must change the answers. A frozen copy would quietly
resurrect a deleted fact days later, inside a task the user had forgotten
about. So a resumed task **re-recalls** from the question, and its context is
rebuilt rather than replayed. It is not byte-identical, and that is the point.

Retention, because a store without an answer to this is an unshipped feature
--------------------------------------------------------------------------
**A row exists only while a task is unfinished.** Finishing deletes it: the
answer lives in the conversation, and the steps that produced it are working
state that has done its job. That keeps this store small by construction rather
than by a sweep.

**An unfinished task expires after seven days**, untouched, pruned on open and
on every write. Seven because the thing this exists for is *"stop on Tuesday,
carry on Thursday"*; a task nobody returned to in a week is not being resumed,
and tool results include file contents, which is a liability to hold rather than
an asset — `CLAUDE.md`'s own note that retention is a liability before it is a
feature. The user can delete one at any time, which is rule 4's shape applied to
a store that is not the Spine.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_NAME = "plans.db"

#: How long an unfinished task waits to be picked up. See the module docstring.
UNFINISHED_TTL_SECONDS = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class PlanStep:
    """One completed tool call, and what it returned.

    The result is stored as JSON text and handed back parsed. A result that
    cannot be re-read is not an error worth failing a resume over — it comes
    back as the raw string, which the model can still read, rather than taking
    the whole task down with it.
    """

    server: str
    tool: str
    arguments: dict
    result: Any


#: The statuses a checklist item may carry. `skipped` needs a reason — a
#: decision rejected is only useful if the resumed task can read why.
ITEM_STATUSES = ("todo", "doing", "done", "skipped")


@dataclass(frozen=True)
class PlanItem:
    """One line of the checklist the model wrote for itself.

    `docs/AGENT-UX.md`: the plan is a checklist, written by the model through
    the `plan` tool, rendered by Zaram from this record rather than typed as
    prose — so an item is `done` because the record says so, and a resumed
    task reads `skipped` with its reason rather than re-taking a decision the
    person already refused.
    """

    text: str
    status: str = "todo"
    reason: str = ""

    def to_json(self) -> dict:
        out = {"text": self.text, "status": self.status}
        if self.reason:
            out["reason"] = self.reason
        return out

    @classmethod
    def from_json(cls, raw: Any) -> Optional["PlanItem"]:
        if not isinstance(raw, dict):
            return None
        text = str(raw.get("text") or "").strip()
        if not text:
            return None
        status = str(raw.get("status") or "todo").strip().lower()
        if status not in ITEM_STATUSES:
            status = "todo"
        return cls(text=text[:300], status=status, reason=str(raw.get("reason") or "").strip()[:300])


@dataclass(frozen=True)
class Plan:
    """A task that stopped with work left — or, since 13 September, one that
    finished and keeps its checklist for the record.

    `project_id` is empty when no project was open, which is a real answer and
    not a missing one — the same distinction rule 7i draws for a fact's scope.
    """

    id: str
    question: str
    steps: List[PlanStep]
    project_id: str = ""
    session_id: str = ""
    model: str = ""
    #: What the user was told about why it stopped. Kept so a resume reads as
    #: the same task rather than as something new that appeared on its own.
    stopped_because: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    #: The checklist. Empty for a task the model never planned.
    items: List[PlanItem] = field(default_factory=list)
    #: Whether the person pressed Go on this plan. A long plan with writes in
    #: it pauses before its first mutative call until this is true.
    approved: bool = False
    #: A finished task keeps its checklist and drops its steps — the steps
    #: hold file contents, which are the liability; the ticked list is the
    #: record of what was done, which is the asset.
    finished: bool = False

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.items if i.status == "done")


class PlanRecords:
    """Unfinished tasks on SQLite. Save, find, resume, forget."""

    def __init__(self, path: str, *, ttl_seconds: int = UNFINISHED_TTL_SECONDS) -> None:
        self._path = path
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()
        # On open as well as on write, so a machine that has been off for a
        # fortnight is clean before anything reads from it rather than after
        # the next save.
        self.prune()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id              TEXT PRIMARY KEY,
                    question        TEXT NOT NULL,
                    project_id      TEXT NOT NULL DEFAULT '',
                    session_id      TEXT NOT NULL DEFAULT '',
                    model           TEXT NOT NULL DEFAULT '',
                    stopped_because TEXT NOT NULL DEFAULT '',
                    created_at      REAL NOT NULL,
                    updated_at      REAL NOT NULL,
                    items           TEXT NOT NULL DEFAULT '[]',
                    approved        INTEGER NOT NULL DEFAULT 0,
                    finished        INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            # Added after the table shipped; `CREATE TABLE IF NOT EXISTS` is
            # silent about a table that exists and differs.
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(plans)").fetchall()}
            for name, ddl in (
                ("items", "TEXT NOT NULL DEFAULT '[]'"),
                ("approved", "INTEGER NOT NULL DEFAULT 0"),
                ("finished", "INTEGER NOT NULL DEFAULT 0"),
            ):
                if name not in columns:
                    conn.execute(f"ALTER TABLE plans ADD COLUMN {name} {ddl}")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plan_steps (
                    plan_id   TEXT NOT NULL,
                    ordinal   INTEGER NOT NULL,
                    server    TEXT NOT NULL,
                    tool      TEXT NOT NULL,
                    arguments TEXT NOT NULL DEFAULT '{}',
                    result    TEXT NOT NULL DEFAULT 'null',
                    PRIMARY KEY (plan_id, ordinal),
                    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
                )
                """
            )

    # ------------------------------------------------------------------ read

    def get(self, plan_id: str) -> Optional[Plan]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if row is None:
                return None
            return self._hydrate(conn, row)

    def unfinished(
        self, *, project_id: Optional[str] = None, limit: int = 20
    ) -> List[Plan]:
        """Tasks waiting to be picked up, most recently touched first.

        ``project_id=None`` means every project *and* the tasks that belong to
        none. An empty string means specifically the ones with no project, which
        is a different question and has to stay askable — the same care
        `only_ids` needs between "unrestricted" and "a domain holding nothing".
        """
        query = "SELECT * FROM plans WHERE finished = 0"
        params: list = []
        if project_id is not None:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, limit))

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._hydrate(conn, row) for row in rows]

    def latest_for(
        self, *, session_id: str = "", project_id: str = ""
    ) -> Optional[Plan]:
        """The task a bare *Continue* means, or ``None``.

        This session's own stopped task first, because that is what somebody
        pressing Continue under a reply is looking at. Only then the project's,
        which is the Thursday case: a new session, a task left on Tuesday, and
        no session id in common with it.
        """
        with self._connect() as conn:
            if session_id:
                row = conn.execute(
                    "SELECT * FROM plans WHERE finished = 0 AND session_id = ? "
                    "ORDER BY updated_at DESC LIMIT 1",
                    (session_id,),
                ).fetchone()
                if row is not None:
                    return self._hydrate(conn, row)
            if project_id:
                row = conn.execute(
                    "SELECT * FROM plans WHERE finished = 0 AND project_id = ? "
                    "ORDER BY updated_at DESC LIMIT 1",
                    (project_id,),
                ).fetchone()
                if row is not None:
                    return self._hydrate(conn, row)
        return None

    # ----------------------------------------------------------------- write

    def save(self, plan: Plan) -> Plan:
        """Store a task, replacing any earlier version of it.

        Replacing rather than appending: a task that stops twice is one task
        that got further, and two rows would offer the user the same job twice
        with different amounts of it done.
        """
        stored = Plan(
            id=plan.id or uuid.uuid4().hex[:12],
            question=plan.question,
            steps=list(plan.steps),
            project_id=plan.project_id,
            session_id=plan.session_id,
            model=plan.model,
            stopped_because=plan.stopped_because,
            created_at=plan.created_at,
            updated_at=time.time(),
            items=list(plan.items),
            approved=plan.approved,
            finished=plan.finished,
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO plans (id, question, project_id, session_id, model, "
                "stopped_because, created_at, updated_at, items, approved, finished) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET question=excluded.question, "
                "project_id=excluded.project_id, session_id=excluded.session_id, "
                "model=excluded.model, stopped_because=excluded.stopped_because, "
                "updated_at=excluded.updated_at, items=excluded.items, "
                "approved=excluded.approved, finished=excluded.finished",
                (
                    stored.id, stored.question, stored.project_id, stored.session_id,
                    stored.model, stored.stopped_because, stored.created_at,
                    stored.updated_at, _dumps([i.to_json() for i in stored.items]),
                    1 if stored.approved else 0, 1 if stored.finished else 0,
                ),
            )
            conn.execute("DELETE FROM plan_steps WHERE plan_id = ?", (stored.id,))
            conn.executemany(
                "INSERT INTO plan_steps (plan_id, ordinal, server, tool, arguments, "
                "result) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        stored.id,
                        ordinal,
                        step.server,
                        step.tool,
                        _dumps(step.arguments),
                        _dumps(step.result),
                    )
                    for ordinal, step in enumerate(stored.steps)
                ],
            )
        self.prune()
        return stored

    def finish(self, plan_id: str) -> bool:
        """Mark a task done: keep the checklist, drop the steps.

        The steps hold tool results — file contents — and `CLAUDE.md` is
        explicit that those are a liability to keep. The checklist is what a
        person opens Project to see on Thursday: what was done on Tuesday.
        A task that was never planned has nothing to keep and is deleted.
        """
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT items FROM plans WHERE id = ?", (plan_id,)).fetchone()
            if row is None:
                return False
            if not (_loads(row["items"]) or []):
                conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
                return True
            conn.execute("DELETE FROM plan_steps WHERE plan_id = ?", (plan_id,))
            conn.execute(
                "UPDATE plans SET finished = 1, stopped_because = '', updated_at = ? WHERE id = ?",
                (time.time(), plan_id),
            )
        return True

    def approve(self, plan_id: str) -> bool:
        """The person pressed Go."""
        with self._lock, self._connect() as conn:
            changed = conn.execute(
                "UPDATE plans SET approved = 1, updated_at = ? WHERE id = ?", (time.time(), plan_id)
            ).rowcount
        return bool(changed)

    def finished_for(self, project_id: str = "", *, limit: int = 20) -> List[Plan]:
        """Finished tasks, most recent first — the ticked lists Project shows."""
        with self._lock, self._connect() as conn:
            if project_id:
                rows = conn.execute(
                    "SELECT * FROM plans WHERE finished = 1 AND project_id = ? ORDER BY updated_at DESC LIMIT ?",
                    (project_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM plans WHERE finished = 1 ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
            return [self._hydrate(conn, row) for row in rows]

    def delete(self, plan_id: str) -> bool:
        """Forget a task. True when there was one.

        The one operation the user reaches for directly, and the one the loop
        calls when a task finishes — the same call for both, because a finished
        task and a discarded one leave the same amount behind: nothing.
        """
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM plan_steps WHERE plan_id = ?", (plan_id,))
            return bool(
                conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,)).rowcount
            )

    def prune(self, *, now: Optional[float] = None) -> int:
        """Drop tasks nobody came back to. Returns how many went."""
        cutoff = (now if now is not None else time.time()) - self._ttl
        with self._lock, self._connect() as conn:
            stale = [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM plans WHERE updated_at < ?", (cutoff,)
                ).fetchall()
            ]
            if not stale:
                return 0
            marks = ",".join("?" for _ in stale)
            conn.execute(f"DELETE FROM plan_steps WHERE plan_id IN ({marks})", stale)
            conn.execute(f"DELETE FROM plans WHERE id IN ({marks})", stale)
        logger.info("Pruned %d unfinished task(s) older than the retention window", len(stale))
        return len(stale)

    # ---------------------------------------------------------------- shared

    def _hydrate(self, conn: sqlite3.Connection, row: sqlite3.Row) -> Plan:
        steps = [
            PlanStep(
                server=step["server"],
                tool=step["tool"],
                arguments=_loads(step["arguments"]) or {},
                result=_loads(step["result"]),
            )
            for step in conn.execute(
                "SELECT * FROM plan_steps WHERE plan_id = ? ORDER BY ordinal",
                (row["id"],),
            ).fetchall()
        ]
        return Plan(
            id=row["id"],
            question=row["question"],
            steps=steps,
            project_id=row["project_id"],
            session_id=row["session_id"],
            model=row["model"],
            stopped_because=row["stopped_because"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            items=[i for i in (PlanItem.from_json(r) for r in (_loads(row["items"]) or [])) if i],
            approved=bool(row["approved"]),
            finished=bool(row["finished"]),
        )


def _dumps(value: Any) -> str:
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return json.dumps(str(value))


def _loads(text: str) -> Any:
    """Parsed, or the raw text when it will not parse.

    A step that cannot be re-read must not take the resume down with it: the
    string is still something the model can read, and refusing to continue a
    week's work over one malformed row would be the worse failure.
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


def default_db_path() -> str:
    from core.paths import in_data_dir

    return in_data_dir(DEFAULT_DB_NAME, "ZARAM_PLANS_DB")
