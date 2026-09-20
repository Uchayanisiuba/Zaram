"""Work that runs on its own — and never approves itself.

Coworker step 4, `docs/MILESTONES.md`; `docs/PLAN.md` F4 and G6. The
maintainer's direction: *a Monday-morning month's picture that ran while the
window was closed, with its transcript*, and *"when an obligation is seven
days out, draft the reply and hold it."*

What a trigger is
-----------------
A question, and when to ask it. Nothing else: no separate engine, no
separate memory, no separate permission model. A run is the same request a
person would have sent — `POST /chat`, in process, with a session of its own
and a fresh conversation — so it gets recall, the planner, the tools, the
gate, the egress log and the transcript exactly as a typed question does. The
transcript *is* the conversation it made, kept under Activity's retention
like any other. Nothing here invents a second store for what was said.

Three kinds, and the third expands:

* ``daily`` at ``HH:MM``;
* ``weekly`` on a weekday at ``HH:MM`` — the Monday picture;
* ``obligations``: once a day, every open obligation due within
  ``days_ahead`` that this trigger has not yet drafted for becomes one run —
  *"Draft a reply about <what>, due <when>"* — deduplicated by obligation id,
  so a commitment is drafted for once, not every morning.

Unattended runs never self-approve
----------------------------------
Rule 6: autonomy is granted by the user, never a default. An unattended run
has no person at the pause, so it gets **no** plan-level Go, **no**
"run without stopping", **no** conversation-scoped grants — its session id
is minted here and nothing ever adds to it. The first tool the gate holds
stops the run exactly as it would stop a typed one; the unfinished task
lands in `PlanRecords` and Activity's *waiting on you* lists it, which is
the inbox. What was granted *always*, by name, in Settings, still applies:
that is the person's standing decision and it is why standing rules exist.

The circuit breaker
-------------------
A trigger whose last ``BREAKER_AFTER`` runs in a row each stopped at a
permission is **paused**, with the reason, until the person re-enables it.
A run that keeps being held is a run somebody has to look at, and
re-asking every morning is the nag `CLAUDE.md` forbids. Three, because two
is one bad day.

Retention
---------
A trigger lives until deleted. A *run record* — when, which conversation,
how it ended — is kept for ``RUN_TTL_DAYS`` and pruned on open and on every
write; the conversation it points at has Activity's own retention. Both are
the person's to delete.

**Nothing here is a menu item.** Triggers are configured under Settings with
Tools; their runs and held asks appear in Activity. Rule against engagement
mechanics: a trigger runs because the person made it, and Zaram never
suggests one.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from core.paths import data_dir

logger = logging.getLogger(__name__)

DB_NAME = "triggers.db"
RUN_TTL_DAYS = 30
#: Consecutive runs stopped at a permission before the trigger is paused.
BREAKER_AFTER = 3
#: How often the runner looks for due triggers.
TICK_SECONDS = 60

KINDS = ("daily", "weekly", "obligations")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

#: How a run ended. `held` is the interesting one: the gate stopped it and a
#: person is needed. `failed` is an error, not a refusal.
OUTCOMES = ("done", "held", "failed")


@dataclass
class Trigger:
    id: str
    question: str
    kind: str
    at: str  # "HH:MM"
    weekday: str = "mon"
    days_ahead: int = 7
    project_id: str = ""
    enabled: bool = True
    created_at: float = 0.0
    last_run_at: float = 0.0
    held_in_a_row: int = 0
    paused_reason: str = ""

    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "kind": self.kind,
            "at": self.at,
            "weekday": self.weekday,
            "days_ahead": self.days_ahead,
            "project_id": self.project_id,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_run_at": self.last_run_at,
            "held_in_a_row": self.held_in_a_row,
            "paused_reason": self.paused_reason,
            "next_run_at": self.next_run_at(),
        }

    def _time(self) -> tuple[int, int]:
        hh, _, mm = self.at.partition(":")
        return int(hh), int(mm)

    def next_run_at(self, now: Optional[datetime] = None) -> Optional[float]:
        """When this would next run, as a timestamp, or ``None`` when it will
        not (disabled or paused). Local time — a person's nine o'clock."""
        if not self.enabled or self.paused_reason:
            return None
        now = now or datetime.now()
        hh, mm = self._time()
        candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if self.kind == "weekly":
            wanted = WEEKDAYS.index(self.weekday)
            ahead = (wanted - candidate.weekday()) % 7
            candidate = candidate + timedelta(days=ahead)
            if candidate <= now:
                candidate = candidate + timedelta(days=7)
        else:
            if candidate <= now:
                candidate = candidate + timedelta(days=1)
        return candidate.timestamp()

    def is_due(self, now: Optional[datetime] = None) -> bool:
        """Due when the scheduled moment has passed since the last run. A
        machine that was asleep at nine runs it at ten rather than skipping
        the day — the person asked for the picture, not for punctuality."""
        if not self.enabled or self.paused_reason:
            return False
        now = now or datetime.now()
        hh, mm = self._time()
        today_at = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if self.kind == "weekly":
            wanted = WEEKDAYS.index(self.weekday)
            behind = (today_at.weekday() - wanted) % 7
            scheduled = today_at - timedelta(days=behind)
        else:
            scheduled = today_at
        if scheduled > now:
            scheduled -= timedelta(days=7 if self.kind == "weekly" else 1)
        return self.last_run_at < scheduled.timestamp()


@dataclass(frozen=True)
class Run:
    id: str
    trigger_id: str
    started_at: float
    finished_at: float
    outcome: str
    conversation_id: str
    question: str
    #: For an obligations run, which one; otherwise "".
    obligation_id: str = ""
    note: str = ""

    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "trigger_id": self.trigger_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "outcome": self.outcome,
            "conversation_id": self.conversation_id,
            "question": self.question,
            "obligation_id": self.obligation_id,
            "note": self.note,
        }


def _valid_time(at: str) -> bool:
    hh, sep, mm = at.partition(":")
    return sep == ":" and hh.isdigit() and mm.isdigit() and 0 <= int(hh) < 24 and 0 <= int(mm) < 60


class TriggerStore:
    """Triggers and their runs, in SQLite under `data_dir()`."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or str(Path(data_dir()) / DB_NAME)
        self._lock = threading.Lock()
        self._init()
        self.prune()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS triggers (
                    id TEXT PRIMARY KEY, question TEXT NOT NULL, kind TEXT NOT NULL,
                    at TEXT NOT NULL, weekday TEXT NOT NULL, days_ahead INTEGER NOT NULL,
                    project_id TEXT NOT NULL, enabled INTEGER NOT NULL, created_at REAL NOT NULL,
                    last_run_at REAL NOT NULL, held_in_a_row INTEGER NOT NULL, paused_reason TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, trigger_id TEXT NOT NULL, started_at REAL NOT NULL,
                    finished_at REAL NOT NULL, outcome TEXT NOT NULL, conversation_id TEXT NOT NULL,
                    question TEXT NOT NULL, obligation_id TEXT NOT NULL, note TEXT NOT NULL
                )"""
            )

    @staticmethod
    def _row(r: sqlite3.Row) -> Trigger:
        return Trigger(
            id=r["id"], question=r["question"], kind=r["kind"], at=r["at"], weekday=r["weekday"],
            days_ahead=int(r["days_ahead"]), project_id=r["project_id"], enabled=bool(r["enabled"]),
            created_at=float(r["created_at"]), last_run_at=float(r["last_run_at"]),
            held_in_a_row=int(r["held_in_a_row"]), paused_reason=r["paused_reason"],
        )

    # ------------------------------------------------------------- triggers

    def create(
        self,
        question: str,
        kind: str,
        at: str,
        *,
        weekday: str = "mon",
        days_ahead: int = 7,
        project_id: str = "",
        created_at: Optional[float] = None,
    ) -> Trigger:
        """`created_at` is also the first `last_run_at`: a trigger is not owed
        the runs from before it existed, so one made on Monday at 08:59 for
        Mondays at 09:00 waits a minute, not a week in arrears."""
        question = question.strip()
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {', '.join(KINDS)}")
        if kind != "obligations" and not question:
            raise ValueError("a trigger needs a question")
        if not _valid_time(at):
            raise ValueError("at must be HH:MM")
        if weekday not in WEEKDAYS:
            raise ValueError(f"weekday must be one of {', '.join(WEEKDAYS)}")
        if not 1 <= int(days_ahead) <= 60:
            raise ValueError("days_ahead must be between 1 and 60")
        born = created_at if created_at is not None else time.time()
        trigger = Trigger(
            id=uuid.uuid4().hex[:12], question=question, kind=kind, at=at, weekday=weekday,
            days_ahead=int(days_ahead), project_id=project_id, created_at=born, last_run_at=born,
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO triggers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (trigger.id, trigger.question, trigger.kind, trigger.at, trigger.weekday, trigger.days_ahead,
                 trigger.project_id, 1, trigger.created_at, trigger.last_run_at, 0, ""),
            )
        return trigger

    def all(self) -> List[Trigger]:
        with self._connect() as conn:
            return [self._row(r) for r in conn.execute("SELECT * FROM triggers ORDER BY created_at")]

    def get(self, trigger_id: str) -> Optional[Trigger]:
        with self._connect() as conn:
            r = conn.execute("SELECT * FROM triggers WHERE id = ?", (trigger_id,)).fetchone()
        return self._row(r) if r else None

    def set_enabled(self, trigger_id: str, enabled: bool) -> Optional[Trigger]:
        """Re-enabling clears a pause: the person looked, and that is what
        the pause was for."""
        with self._lock, self._connect() as conn:
            if enabled:
                conn.execute(
                    "UPDATE triggers SET enabled = 1, paused_reason = '', held_in_a_row = 0 WHERE id = ?",
                    (trigger_id,),
                )
            else:
                conn.execute("UPDATE triggers SET enabled = 0 WHERE id = ?", (trigger_id,))
        return self.get(trigger_id)

    def delete(self, trigger_id: str) -> bool:
        with self._lock, self._connect() as conn:
            gone = conn.execute("DELETE FROM triggers WHERE id = ?", (trigger_id,)).rowcount
            conn.execute("DELETE FROM runs WHERE trigger_id = ?", (trigger_id,))
        return gone > 0

    def due(self, now: Optional[datetime] = None) -> List[Trigger]:
        return [t for t in self.all() if t.is_due(now)]

    # ----------------------------------------------------------------- runs

    def record_run(
        self,
        trigger: Trigger,
        *,
        started_at: float,
        outcome: str,
        conversation_id: str,
        question: str,
        obligation_id: str = "",
        note: str = "",
    ) -> Run:
        """Write the run, advance the trigger, and trip the breaker if it is
        the ``BREAKER_AFTER``-th hold in a row."""
        if outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {', '.join(OUTCOMES)}")
        run = Run(
            id=uuid.uuid4().hex[:12], trigger_id=trigger.id, started_at=started_at, finished_at=time.time(),
            outcome=outcome, conversation_id=conversation_id, question=question,
            obligation_id=obligation_id, note=note,
        )
        held = trigger.held_in_a_row + 1 if outcome == "held" else 0
        paused = ""
        if held >= BREAKER_AFTER:
            paused = (
                f"Paused: the last {held} runs each stopped at something that needed you. "
                "Look at what it asked for under Activity, then turn it back on."
            )
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?)",
                (run.id, run.trigger_id, run.started_at, run.finished_at, run.outcome, run.conversation_id,
                 run.question, run.obligation_id, run.note),
            )
            # The run belongs to the moment it started: a run that began at
            # 09:05 satisfies the 09:00 slot, whenever it finished.
            conn.execute(
                "UPDATE triggers SET last_run_at = ?, held_in_a_row = ?, paused_reason = ? WHERE id = ?",
                (max(trigger.last_run_at, run.started_at), held, paused, trigger.id),
            )
        self.prune()
        return run

    def runs(self, *, trigger_id: str = "", limit: int = 50) -> List[Run]:
        with self._connect() as conn:
            if trigger_id:
                rows = conn.execute(
                    "SELECT * FROM runs WHERE trigger_id = ? ORDER BY started_at DESC LIMIT ?", (trigger_id, limit)
                )
            else:
                rows = conn.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,))
            return [
                Run(
                    id=r["id"], trigger_id=r["trigger_id"], started_at=float(r["started_at"]),
                    finished_at=float(r["finished_at"]), outcome=r["outcome"], conversation_id=r["conversation_id"],
                    question=r["question"], obligation_id=r["obligation_id"], note=r["note"],
                )
                for r in rows
            ]

    def drafted_obligations(self, trigger_id: str) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT obligation_id FROM runs WHERE trigger_id = ? AND obligation_id != ''", (trigger_id,)
            )
            return {r["obligation_id"] for r in rows}

    def prune(self) -> int:
        cutoff = time.time() - RUN_TTL_DAYS * 24 * 60 * 60
        with self._lock, self._connect() as conn:
            return conn.execute("DELETE FROM runs WHERE finished_at < ?", (cutoff,)).rowcount


# ------------------------------------------------------------------ the runner

#: Asks the product one question, unattended, and reports how it ended:
#: ``(outcome, conversation_id, note)``. Injected so the runner can be tested
#: without a model — and so it never imports `main`.
Ask = Callable[[str, str, str], Awaitable[tuple[str, str, str]]]
#: Open obligations due within N days: ``[(id, what, due_iso)]``.
Obligations = Callable[[int], List[tuple[str, str, str]]]


def obligation_question(what: str, due_iso: str) -> str:
    return (
        f"An obligation is coming up: {what}, due {due_iso}. Draft the reply or the "
        "message that should go out about it, ready for me to read. Do not send anything."
    )


class TriggerRunner:
    """Ticks, finds what is due, and runs it one at a time."""

    def __init__(self, store: TriggerStore, ask: Ask, obligations: Optional[Obligations] = None) -> None:
        self._store = store
        self._ask = ask
        self._obligations = obligations
        self._task: Optional[asyncio.Task] = None
        self._running = asyncio.Lock()

    async def run_trigger(
        self, trigger: Trigger, *, force: bool = False, now: Optional[datetime] = None
    ) -> List[Run]:
        """Run one trigger now. `force` runs a disabled or paused one — the
        person pressed *Run now*, which is a person at the pause."""
        if not force and (not trigger.enabled or trigger.paused_reason):
            return []
        async with self._running:
            if trigger.kind == "obligations":
                return await self._run_obligations(trigger, now=now)
            started = (now or datetime.now()).timestamp()
            session = f"trigger:{trigger.id}:{int(started)}"
            outcome, conversation_id, note = await self._ask(trigger.question, session, trigger.project_id)
            return [
                self._store.record_run(
                    trigger, started_at=started, outcome=outcome, conversation_id=conversation_id,
                    question=trigger.question, note=note,
                )
            ]

    async def _run_obligations(self, trigger: Trigger, *, now: Optional[datetime] = None) -> List[Run]:
        if self._obligations is None:
            return []
        already = self._store.drafted_obligations(trigger.id)
        runs: List[Run] = []
        started = (now or datetime.now()).timestamp()
        for obligation_id, what, due_iso in self._obligations(trigger.days_ahead):
            if obligation_id in already:
                continue
            question = obligation_question(what, due_iso)
            session = f"trigger:{trigger.id}:{obligation_id}"
            outcome, conversation_id, note = await self._ask(question, session, trigger.project_id)
            runs.append(
                self._store.record_run(
                    trigger, started_at=started, outcome=outcome, conversation_id=conversation_id,
                    question=question, obligation_id=obligation_id, note=note,
                )
            )
        if not runs:
            # Nothing to draft is a run that happened, so the trigger does not
            # stay "due" all day.
            runs.append(
                self._store.record_run(
                    trigger, started_at=started, outcome="done", conversation_id="",
                    question="", note="nothing due within the window",
                )
            )
        return runs

    async def tick(self, now: Optional[datetime] = None) -> List[Run]:
        runs: List[Run] = []
        for trigger in self._store.due(now):
            try:
                runs.extend(await self.run_trigger(trigger, now=now))
            except Exception:  # noqa: BLE001 - one trigger's failure must not stop the others
                logger.exception("trigger %s failed", trigger.id)
                self._store.record_run(
                    trigger, started_at=(now or datetime.now()).timestamp(), outcome="failed",
                    conversation_id="", question=trigger.question, note="the run raised; see the log",
                )
        return runs

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.get_running_loop().create_task(self._loop())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:  # noqa: BLE001
                logger.exception("trigger tick failed")
            await asyncio.sleep(TICK_SECONDS)


def outcome_of(events: List[Dict[str, Any]]) -> tuple[str, str]:
    """How a run ended, read off the stream's events, in words the run
    record keeps: ``held`` when the gate stopped a tool, ``failed`` on an
    error event, else ``done``. The note names the tool, so Activity can
    say *"held at write_file"* without opening the conversation."""
    for event in events:
        if event.get("type") == "error":
            return "failed", str(event.get("data", {}).get("message") or "error")
    for event in events:
        if event.get("type") == "tool_call" and event.get("data", {}).get("verdict") in ("confirm", "refuse"):
            data = event["data"]
            return "held", f"held at {data.get('server')}/{data.get('tool')}: {data.get('reason', '')}"[:300]
    return "done", ""
