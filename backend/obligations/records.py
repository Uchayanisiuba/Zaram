"""Where obligations live once a document has been read.

`extract.py` reads commitments out of text and `contracts.py` says what one is.
Neither persists anything, and until this existed the whole package was
imported by nothing but its own tests — the eighteenth complete, tested,
unreachable subsystem in this repository.

Three design decisions, each of which is a rule rather than a preference.

**Nothing is ever updated in place, and nothing is deleted.** `Obligation` is
frozen because a correction should produce a new record rather than mutate an
old one, and this store honours that: correcting writes a new row and points
the old one at it, exactly as `MemoryRecord.superseded_by` does for facts. Rule
4 says the user can correct what Zaram believes and the affected answers must
change; it does not say the previous belief should vanish. A system that can
show you where it was wrong is one you can believe when it says it is right.

**A dismissal is a stored fact, not an absence.** "This was never an
obligation" is a correction worth remembering, because the alternative is that
the next ingest of the same document extracts it again and asks again — which
teaches the user that correcting Zaram does not stick.

**Unresolved clauses are stored beside resolved ones, not discarded.** A clause
that says payment is due thirty days after an issue date nobody supplied is a
real commitment the user is exposed to. Dropping it loses a deadline; guessing
at the date invents one. It is kept, with the question that would settle it.

The same-document rule: re-ingesting a document does not duplicate its
obligations. Identity is `(source_document_id, clause text, kind, due)`, which
is stable across re-parses of the same file and distinguishes two genuinely
different clauses that happen to fall due on the same day.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .contracts import (
    Clause,
    Direction,
    Obligation,
    ObligationKind,
    ObligationStatus,
    Unresolved,
    UnresolvedObligation,
)

__all__ = ["ObligationRecords", "default_db_path"]


def default_db_path() -> str:
    """The obligations database, inside the user's data directory.

    `core/paths` owns the one answer to where user data lives. Resolving to the
    backend source directory is correct in a checkout and unwritable in an
    install, which is the failure that put every other store here.
    """
    from core.paths import in_data_dir

    return in_data_dir("obligations.db", "ZARAM_OBLIGATIONS_DB")


class ObligationRecords:
    """Obligations and unresolved clauses on SQLite. Append and supersede only."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._create()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _create(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS obligations (
                    id              TEXT PRIMARY KEY,
                    kind            TEXT NOT NULL,
                    summary         TEXT NOT NULL,
                    due             TEXT NOT NULL,
                    clause_text     TEXT NOT NULL,
                    clause_start    INTEGER NOT NULL DEFAULT -1,
                    clause_end      INTEGER NOT NULL DEFAULT -1,
                    document_id     TEXT NOT NULL DEFAULT '',
                    direction       TEXT NOT NULL DEFAULT 'unknown',
                    status          TEXT NOT NULL DEFAULT 'open',
                    amount          TEXT,
                    currency        TEXT NOT NULL DEFAULT '',
                    scope           TEXT NOT NULL DEFAULT 'global',
                    confidence      REAL NOT NULL DEFAULT 0.0,
                    created_at      REAL NOT NULL,
                    superseded_by   TEXT,
                    superseded_at   REAL,
                    fingerprint     TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS obligations_due
                    ON obligations(status, due);
                CREATE INDEX IF NOT EXISTS obligations_document
                    ON obligations(document_id);
                CREATE UNIQUE INDEX IF NOT EXISTS obligations_fingerprint
                    ON obligations(fingerprint);

                CREATE TABLE IF NOT EXISTS unresolved (
                    id              TEXT PRIMARY KEY,
                    kind            TEXT NOT NULL,
                    clause_text     TEXT NOT NULL,
                    clause_start    INTEGER NOT NULL DEFAULT -1,
                    clause_end      INTEGER NOT NULL DEFAULT -1,
                    reason          TEXT NOT NULL,
                    question        TEXT NOT NULL,
                    document_id     TEXT NOT NULL DEFAULT '',
                    scope           TEXT NOT NULL DEFAULT 'global',
                    created_at      REAL NOT NULL,
                    answered_at     REAL,
                    became          TEXT,
                    fingerprint     TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS unresolved_fingerprint
                    ON unresolved(fingerprint);
                """
            )

    # -- writing -----------------------------------------------------------

    @staticmethod
    def _fingerprint(*parts: Any) -> str:
        """Stable identity for a clause, so re-ingesting a file is a no-op.

        Hashed, and length-prefixed before hashing, because the parts include
        free text: joining them with any separator lets two different clauses
        produce the same string when one of them contains the separator. For a
        deadline that would mean one commitment silently standing in for
        another.
        """
        payload = "".join(
            f"{len(s)}:{s}" for s in ("" if p is None else str(p) for p in parts)
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def record(
        self,
        obligations: List[Obligation] = (),
        unresolved: List[UnresolvedObligation] = (),
    ) -> Dict[str, List[str]]:
        """Store what an extraction found. Re-ingesting the same file is a no-op.

        Returns the ids actually written, so a caller can tell "found three,
        all of which we already had" from "found three new commitments" —
        a distinction that matters because the second is worth telling the user
        about and the first is not.
        """
        now = time.time()
        written: List[str] = []
        written_unresolved: List[str] = []

        with self._lock, self._connect() as connection:
            for item in obligations:
                fingerprint = self._fingerprint(
                    item.source_document_id,
                    item.source_clause.text.strip(),
                    item.kind.value,
                    item.due.isoformat(),
                )
                identifier = item.id or f"obl_{uuid.uuid4().hex[:12]}"
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO obligations (
                        id, kind, summary, due, clause_text, clause_start,
                        clause_end, document_id, direction, status, amount,
                        currency, scope, confidence, created_at, fingerprint
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        identifier,
                        item.kind.value,
                        item.summary,
                        item.due.isoformat(),
                        item.source_clause.text,
                        item.source_clause.start,
                        item.source_clause.end,
                        item.source_document_id,
                        item.direction.value,
                        item.status.value,
                        str(item.amount) if item.amount is not None else None,
                        item.currency,
                        item.scope,
                        item.confidence,
                        now,
                        fingerprint,
                    ),
                )
                if cursor.rowcount:
                    written.append(identifier)

            for item in unresolved:
                fingerprint = self._fingerprint(
                    item.source_document_id,
                    item.source_clause.text.strip(),
                    item.kind.value,
                    item.reason.value,
                )
                identifier = f"unr_{uuid.uuid4().hex[:12]}"
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO unresolved (
                        id, kind, clause_text, clause_start, clause_end,
                        reason, question, document_id, scope, created_at,
                        fingerprint
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        identifier,
                        item.kind.value,
                        item.source_clause.text,
                        item.source_clause.start,
                        item.source_clause.end,
                        item.reason.value,
                        item.question,
                        item.source_document_id,
                        item.scope,
                        now,
                        fingerprint,
                    ),
                )
                if cursor.rowcount:
                    written_unresolved.append(identifier)

        return {"obligations": written, "unresolved": written_unresolved}

    # -- reading -----------------------------------------------------------

    def open_obligations(
        self, *, scope: str = "", limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Live commitments, soonest first.

        Superseded rows are excluded, which is what makes a correction change
        the answer. Dismissed rows are excluded too and are still on disk —
        `all_obligations` returns them, because "show me what I dismissed" is a
        question the user is entitled to ask of a system that claims to be
        correctable.
        """
        query = (
            "SELECT * FROM obligations "
            "WHERE superseded_by IS NULL AND status = 'open'"
        )
        params: List[Any] = []
        if scope:
            query += " AND scope = ?"
            params.append(scope)
        query += " ORDER BY due ASC LIMIT ?"
        params.append(limit)

        with self._lock, self._connect() as connection:
            return [self._row(r) for r in connection.execute(query, params)]

    def all_obligations(self, *, limit: int = 500) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            return [
                self._row(r)
                for r in connection.execute(
                    "SELECT * FROM obligations ORDER BY due ASC LIMIT ?", (limit,)
                )
            ]

    def get(self, obligation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM obligations WHERE id = ?", (obligation_id,)
            ).fetchone()
        return self._row(row) if row else None

    def open_questions(self, *, limit: int = 200) -> List[Dict[str, Any]]:
        """Clauses Zaram can see and cannot date, with the question to ask."""
        with self._lock, self._connect() as connection:
            return [
                {
                    "id": r["id"],
                    "kind": r["kind"],
                    "clause": {
                        "text": r["clause_text"],
                        "start": r["clause_start"],
                        "end": r["clause_end"],
                    },
                    "reason": r["reason"],
                    "question": r["question"],
                    "document_id": r["document_id"],
                    "scope": r["scope"],
                    "created_at": r["created_at"],
                }
                for r in connection.execute(
                    "SELECT * FROM unresolved WHERE answered_at IS NULL "
                    "ORDER BY created_at ASC LIMIT ?",
                    (limit,),
                )
            ]

    @staticmethod
    def _row(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "kind": row["kind"],
            "summary": row["summary"],
            "due": row["due"],
            "source_clause": {
                "text": row["clause_text"],
                "start": row["clause_start"],
                "end": row["clause_end"],
            },
            "source_document_id": row["document_id"],
            "direction": row["direction"],
            "status": row["status"],
            "amount": row["amount"],
            "currency": row["currency"],
            "scope": row["scope"],
            "confidence": row["confidence"],
            "created_at": row["created_at"],
            "superseded_by": row["superseded_by"],
            "superseded_at": row["superseded_at"],
        }

    # -- correcting --------------------------------------------------------

    def dismiss(self, obligation_id: str) -> bool:
        """Mark it as never having been an obligation. Kept, not deleted.

        Deleting would mean the next ingest of the same document extracts the
        same clause and asks again, which teaches the user that correcting
        Zaram does not stick. The row stays and the fingerprint stays with it,
        so the re-extraction is absorbed silently.
        """
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE obligations SET status = ? "
                "WHERE id = ? AND superseded_by IS NULL",
                (ObligationStatus.DISMISSED.value, obligation_id),
            )
            return bool(cursor.rowcount)

    def mark_met(self, obligation_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE obligations SET status = ? "
                "WHERE id = ? AND superseded_by IS NULL",
                (ObligationStatus.MET.value, obligation_id),
            )
            return bool(cursor.rowcount)

    def correct(
        self,
        obligation_id: str,
        *,
        due: Optional[date] = None,
        summary: Optional[str] = None,
        amount: Optional[Decimal] = None,
        currency: Optional[str] = None,
        direction: Optional[Direction] = None,
    ) -> Optional[Dict[str, Any]]:
        """Replace an obligation with a corrected one, keeping the original.

        The new row carries the **same clause**. A correction says Zaram read
        the sentence wrongly, not that the sentence was different — and a
        correction that quietly rewrote the source clause would break the one
        guarantee this package exists to make.

        Returns the new record, or `None` if there was nothing to correct.
        """
        existing = self.get(obligation_id)
        if existing is None or existing["superseded_by"] is not None:
            return None

        new_id = f"obl_{uuid.uuid4().hex[:12]}"
        now = time.time()
        new_due = due.isoformat() if due is not None else existing["due"]

        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO obligations (
                    id, kind, summary, due, clause_text, clause_start,
                    clause_end, document_id, direction, status, amount,
                    currency, scope, confidence, created_at, fingerprint
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    new_id,
                    existing["kind"],
                    summary if summary is not None else existing["summary"],
                    new_due,
                    existing["source_clause"]["text"],
                    existing["source_clause"]["start"],
                    existing["source_clause"]["end"],
                    existing["source_document_id"],
                    direction.value if direction is not None else existing["direction"],
                    ObligationStatus.OPEN.value,
                    str(amount) if amount is not None else existing["amount"],
                    currency if currency is not None else existing["currency"],
                    existing["scope"],
                    # A corrected obligation is one the user has confirmed, so
                    # extractor confidence no longer describes it. 1.0 is the
                    # honest value: a person said so.
                    1.0,
                    now,
                    self._fingerprint(new_id, "corrected"),
                ),
            )
            connection.execute(
                "UPDATE obligations SET superseded_by = ?, superseded_at = ? "
                "WHERE id = ?",
                (new_id, now, obligation_id),
            )

        return self.get(new_id)

    def answer_question(
        self, unresolved_id: str, *, anchor: date
    ) -> Optional[Dict[str, Any]]:
        """Date an unresolved clause by supplying what was missing.

        Re-runs the extractor over the stored clause with the anchor the user
        gave, rather than computing the date here. The parsing rules live in
        one place, and a second implementation in this module would drift from
        it — which for a deadline means two different answers to what day
        something is due.
        """
        from .extract import extract_obligations

        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM unresolved WHERE id = ? AND answered_at IS NULL",
                (unresolved_id,),
            ).fetchone()
        if row is None:
            return None

        result = extract_obligations(
            row["clause_text"],
            document_id=row["document_id"],
            anchor_date=anchor,
            scope=row["scope"],
        )
        if not result.obligations:
            # The anchor did not settle it. The question stays open rather than
            # being marked answered, because the user's answer was accepted and
            # still did not produce a date — and silently closing it would lose
            # the clause.
            return None

        created = result.obligations[0]
        self.record(obligations=[created])
        stored = self.get(created.id) or None

        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE unresolved SET answered_at = ?, became = ? WHERE id = ?",
                (time.time(), created.id, unresolved_id),
            )
        return stored
