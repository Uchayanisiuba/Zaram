"""The egress log — the append-only record of what left this machine.

Rule 3 of the project contract: *every byte that leaves is logged*, in an
append-only, tamper-evident log, built into the core rather than added later.
This module is that log.

Two design points are worth stating, because both are easy to get wrong in ways
that look fine until someone actually needs the log.

**It records the literal outbound text.** Not "a request was made to
wikipedia.org" but the exact URL, query string and body that left. What left
matters more than that something left, and a log that only records the fact of a
request cannot answer the one question a privacy-conscious user actually has.

**Retention and tamper-evidence genuinely conflict, and the conflict is
resolved in favour of honesty.** A permanent record of every question a user has
asked is itself a privacy problem, so retention has to prune. But pruning breaks
a hash chain. Rather than pretend otherwise, pruning writes a *retention marker*
recording how many entries were removed and the hash they ended on. Verification
treats a marker as a legitimate chain restart. The deletion is therefore itself
an audited event: the log can no longer show you what was pruned, but it can
always prove that pruning is what happened, and that nothing else was altered.

The chain
---------
Each entry stores ``prev_hash`` and ``entry_hash``, where::

    entry_hash = sha256(prev_hash || canonical_json(payload))

``canonical_json`` sorts keys and uses no whitespace, so the hash depends on the
values rather than on how sqlite happened to return them. Altering, reordering
or removing any entry breaks every hash after it, which :meth:`verify` reports
with the row where the break begins.

What the chain does and does not prove
--------------------------------------
State this accurately rather than generously, in the UI as well as here.

It **does** detect editing, reordering, deletion and partial corruption of the
database by anything that did not go through :meth:`append` — a hand-run
``UPDATE``, a truncated file, a sync conflict, a bug in our own code.

It **does not** stop someone who can already write to the file and run this
code from rebuilding the whole chain around a removed entry. Nothing local-only
can: detecting that requires anchoring the head hash somewhere the attacker
cannot reach, which Zaram deliberately does not have because it would mean
sending something off the machine. The guarantee is *evidence of tampering*,
not *prevention* of it. The log must never be described in the interface as
making the record impossible to alter.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable

#: Written as the previous hash of the very first entry. Any value would do; a
#: fixed sentinel makes a fresh log's first hash reproducible in tests.
GENESIS_HASH = "0" * 64

#: Marks a row that records a retention prune rather than an outbound request.
KIND_REQUEST = "request"
KIND_RETENTION = "retention"


def _canonical(payload: dict[str, Any]) -> str:
    """Serialise deterministically, so the hash depends on values alone."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash(prev_hash: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical(payload)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EgressEntry:
    """One record of something that left, or was stopped from leaving."""

    id: str
    at: float
    kind: str
    #: Hostname the request was addressed to, e.g. "en.wikipedia.org".
    host: str
    method: str
    #: The literal URL including query string. This is the outbound text.
    url: str
    #: The literal request body, if any. Also outbound text.
    body: str | None
    #: How many bytes of URL + body left the machine.
    byte_count: int
    #: "allowed", "denied", or "cancelled" — the last meaning the user was asked
    #: and said no. A denied or cancelled entry means nothing left; it is logged
    #: because an attempt is as worth seeing as a success.
    decision: str
    #: Why. The policy rule that applied, or the reason for refusal.
    reason: str
    #: What asked for this — the module or provider making the request.
    source: str
    prev_hash: str = GENESIS_HASH
    entry_hash: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        """The fields the hash covers. Everything except the hashes themselves."""
        return {
            "id": self.id,
            "at": self.at,
            "kind": self.kind,
            "host": self.host,
            "method": self.method,
            "url": self.url,
            "body": self.body,
            "byte_count": self.byte_count,
            "decision": self.decision,
            "reason": self.reason,
            "source": self.source,
            "meta": self.meta,
        }


class TamperDetected(Exception):
    """Raised when the chain does not verify. Carries the offending row."""

    def __init__(self, message: str, at_row: int, entry_id: str | None = None):
        super().__init__(message)
        self.at_row = at_row
        self.entry_id = entry_id


class EgressLog:
    """Append-only, hash-chained store of outbound requests.

    Deliberately its own SQLite file rather than a table inside the Spine. The
    Spine is exportable by Rule 7, and a record of every question the user has
    asked is not something that should ride along with an export of their notes.
    Keeping it separate also means retention deletion can never touch Spine data.

    There is no ``update`` and no ``delete``. The only way to remove anything is
    :meth:`apply_retention`, which writes a marker recording that it did.
    """

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    # ---------------------------------------------------------------- schema

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=10)
        conn.row_factory = sqlite3.Row
        # WAL keeps a reader (the Activity view) from blocking a writer (a
        # request trying to leave). A log that stalls outbound traffic would
        # get switched off, and a log that is off is worse than a slow one.
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS egress (
                    row        INTEGER PRIMARY KEY AUTOINCREMENT,
                    id         TEXT    NOT NULL UNIQUE,
                    at         REAL    NOT NULL,
                    kind       TEXT    NOT NULL,
                    host       TEXT    NOT NULL,
                    method     TEXT    NOT NULL,
                    url        TEXT    NOT NULL,
                    body       TEXT,
                    byte_count INTEGER NOT NULL,
                    decision   TEXT    NOT NULL,
                    reason     TEXT    NOT NULL,
                    source     TEXT    NOT NULL,
                    meta       TEXT    NOT NULL,
                    prev_hash  TEXT    NOT NULL,
                    entry_hash TEXT    NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_egress_at ON egress(at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_egress_host ON egress(host)")

    # ---------------------------------------------------------------- append

    def append(
        self,
        *,
        host: str,
        method: str,
        url: str,
        body: str | None,
        decision: str,
        reason: str,
        source: str,
        meta: dict[str, Any] | None = None,
        kind: str = KIND_REQUEST,
    ) -> EgressEntry:
        """Record one outbound request. The only way to write to this log.

        Returns the stored entry, including its position in the hash chain.
        """
        byte_count = len(url.encode("utf-8")) + (len(body.encode("utf-8")) if body else 0)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT entry_hash FROM egress ORDER BY row DESC LIMIT 1"
            ).fetchone()
            prev_hash = row["entry_hash"] if row else GENESIS_HASH

            entry = EgressEntry(
                id=str(uuid.uuid4()),
                at=time.time(),
                kind=kind,
                host=host,
                method=method,
                url=url,
                body=body,
                byte_count=byte_count,
                decision=decision,
                reason=reason,
                source=source,
                prev_hash=prev_hash,
                meta=meta or {},
            )
            entry_hash = _hash(prev_hash, entry.payload())
            conn.execute(
                """
                INSERT INTO egress
                    (id, at, kind, host, method, url, body, byte_count,
                     decision, reason, source, meta, prev_hash, entry_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id, entry.at, entry.kind, entry.host, entry.method,
                    entry.url, entry.body, entry.byte_count, entry.decision,
                    entry.reason, entry.source, _canonical(entry.meta),
                    entry.prev_hash, entry_hash,
                ),
            )
        return EgressEntry(**{**entry.__dict__, "entry_hash": entry_hash})

    # ----------------------------------------------------------------- reads

    def entries(self, limit: int = 100, offset: int = 0) -> list[EgressEntry]:
        """Most recent first — the order the Activity view wants."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM egress ORDER BY row DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._to_entry(r) for r in rows]

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) AS n FROM egress").fetchone()["n"]

    def bytes_since(self, since: float) -> int:
        """Total bytes that actually left since ``since``.

        Only counts allowed entries — a denied request sent nothing, and
        including it would overstate what left.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(byte_count), 0) AS n FROM egress "
                "WHERE at >= ? AND decision = 'allowed' AND kind = ?",
                (since, KIND_REQUEST),
            ).fetchone()
        return int(row["n"])

    @staticmethod
    def _to_entry(r: sqlite3.Row) -> EgressEntry:
        return EgressEntry(
            id=r["id"], at=r["at"], kind=r["kind"], host=r["host"],
            method=r["method"], url=r["url"], body=r["body"],
            byte_count=r["byte_count"], decision=r["decision"],
            reason=r["reason"], source=r["source"],
            prev_hash=r["prev_hash"], entry_hash=r["entry_hash"],
            meta=json.loads(r["meta"]) if r["meta"] else {},
        )

    # ------------------------------------------------------------- integrity

    def verify(self) -> bool:
        """Walk the chain. Raises :class:`TamperDetected` at the first break.

        A retention marker legitimately restarts the chain, so the walk resets
        its expectation when it meets one rather than reporting a false break.
        """
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM egress ORDER BY row ASC").fetchall()

        expected_prev = GENESIS_HASH
        for i, r in enumerate(rows):
            entry = self._to_entry(r)
            if entry.kind == KIND_RETENTION:
                # A prune. The chain restarts from this marker's own hash.
                if _hash(entry.prev_hash, entry.payload()) != entry.entry_hash:
                    raise TamperDetected(
                        "retention marker has been altered", at_row=i, entry_id=entry.id
                    )
                expected_prev = entry.entry_hash
                continue

            if entry.prev_hash != expected_prev:
                raise TamperDetected(
                    f"chain broken: entry {i} expected prev_hash {expected_prev[:12]}… "
                    f"but records {entry.prev_hash[:12]}… — an entry was removed or reordered",
                    at_row=i,
                    entry_id=entry.id,
                )
            recomputed = _hash(entry.prev_hash, entry.payload())
            if recomputed != entry.entry_hash:
                raise TamperDetected(
                    f"entry {i} has been altered: its contents no longer match its hash",
                    at_row=i,
                    entry_id=entry.id,
                )
            expected_prev = entry.entry_hash
        return True

    # ------------------------------------------------------------- retention

    def apply_retention(self, max_age_days: int | None) -> int:
        """Delete entries older than ``max_age_days`` and record that it happened.

        ``None`` means keep everything, which is a legitimate choice but not the
        default — see the Settings privacy pane.

        Pruning cannot leave the chain intact, because the surviving entries
        still point at hashes that no longer exist. So the prune is performed as
        one audited operation: a marker is written recording how many entries
        went and what the last of them hashed to, and the survivors are then
        re-linked to run from that marker. Their *contents* are untouched — only
        the chain pointers are recomputed — and :meth:`verify` treats a marker
        as a legitimate restart.

        Returns the number of entries removed.
        """
        if max_age_days is None:
            return 0
        cutoff = time.time() - (max_age_days * 86400)

        with self._lock, self._connect() as conn:
            doomed = conn.execute(
                "SELECT row, entry_hash FROM egress WHERE at < ? AND kind = ? ORDER BY row DESC",
                (cutoff, KIND_REQUEST),
            ).fetchall()
            if not doomed:
                return 0
            removed = len(doomed)
            last_hash = doomed[0]["entry_hash"]
            conn.execute(
                "DELETE FROM egress WHERE at < ? AND kind = ?", (cutoff, KIND_REQUEST)
            )

            # The marker goes in as an ordinary appended row, and everything
            # that survived is re-linked to follow it.
            marker = EgressEntry(
                id=str(uuid.uuid4()),
                at=time.time(),
                kind=KIND_RETENTION,
                host="-",
                method="-",
                url="-",
                body=None,
                byte_count=0,
                decision="allowed",
                reason=(
                    f"retention: removed {removed} entr{'y' if removed == 1 else 'ies'} "
                    f"older than {max_age_days} day{'s' if max_age_days != 1 else ''}"
                ),
                source="egress.retention",
                prev_hash=GENESIS_HASH,
                meta={
                    "removed": removed,
                    "last_removed_hash": last_hash,
                    "max_age_days": max_age_days,
                },
            )
            survivors = conn.execute(
                "SELECT * FROM egress ORDER BY row ASC"
            ).fetchall()

            # The marker takes the place of everything it replaced, so it sits
            # at the front and the survivors follow it in their original order.
            conn.execute("DELETE FROM egress")
            prev = GENESIS_HASH
            marker_hash = _hash(prev, marker.payload())
            self._insert(conn, marker, prev, marker_hash)
            prev = marker_hash

            for r in survivors:
                entry = self._to_entry(r)
                relinked = EgressEntry(**{**entry.__dict__, "prev_hash": prev})
                entry_hash = _hash(prev, relinked.payload())
                self._insert(conn, relinked, prev, entry_hash)
                prev = entry_hash

        return removed

    @staticmethod
    def _insert(conn: sqlite3.Connection, entry: EgressEntry,
                prev_hash: str, entry_hash: str) -> None:
        conn.execute(
            """
            INSERT INTO egress
                (id, at, kind, host, method, url, body, byte_count,
                 decision, reason, source, meta, prev_hash, entry_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id, entry.at, entry.kind, entry.host, entry.method,
                entry.url, entry.body, entry.byte_count, entry.decision,
                entry.reason, entry.source, _canonical(entry.meta),
                prev_hash, entry_hash,
            ),
        )

    def hosts(self) -> Iterable[str]:
        """Distinct hosts contacted. Feeds the per-source policy screen."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT host FROM egress WHERE kind = ? ORDER BY host",
                (KIND_REQUEST,),
            ).fetchall()
        return [r["host"] for r in rows]
