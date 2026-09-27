"""The job-hunt pack's tool: a posting the model found becomes a record.

This is what makes `posting.py` reachable. The scheduler can already ask
*"find remote 3D roles posted this week"* every Monday, unattended; the model
searches, reads what comes back, and until now had nowhere to put it but prose
in a transcript nobody will query in March.

`record_job_posting` is that place. One call turns a wall of text into three
durable things, and each of them is a thing the rest of the hunt stands on:

* **facts on the Spine**, one sentence per claim, scoped to the project — so
  recall can answer "what did Northwind pay?" six months later, and rule 4
  lets the person correct the salary without deleting the deadline;
* **the closing date as an obligation**, which is what surfaces it before it
  lapses rather than after;
* **a follow-up**, seven days out, because an application nobody chases is
  most of an application wasted.

Why a tool and not an endpoint
------------------------------
An endpoint would need a person to press something, which is exactly what an
unattended Monday-morning run does not have. A tool is offered to the model
inside the same loop, gate and log as every other tool, so the run that found
the posting is the run that files it — and the egress log records it like any
other step.

Generative tier, deliberately
-----------------------------
It writes new facts and new obligations and can destroy neither a file nor an
existing record. Nothing here sends anything anywhere: the posting has already
been fetched by the search step, under the gate, before this ever sees it. The
one thing it must never grow is a `submit` verb — that is mutative and
egressive with no undo, and `CLAUDE.md` puts it outside the hunt on purpose.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from runtimes.mcp.client import ToolDescriptor

from .posting import Posting, parse_posting

logger = logging.getLogger(__name__)

__all__ = ["JobTools", "RECORD_POSTING", "SERVER_ID"]

SERVER_ID = "jobs"
RECORD_POSTING = "record_job_posting"

#: Days after applying that a follow-up is worth sending. Seven, because a
#: week is long enough not to read as pestering and short enough that the
#: reader still remembers the name.
FOLLOW_UP_DAYS = 7

#: Below this many characters there is no posting here — somebody has passed a
#: link's title or a snippet. Refusing is better than filing a fact that says
#: a company is hiring a "Senior" and nothing else.
_MINIMUM_POSTING = 120


class JobTools:
    """Zaram's built-in job-hunt server: one tool, `record_job_posting`."""

    def __init__(
        self,
        *,
        remember: Callable[[str, str], None],
        record_obligations: Callable[[List[Any]], Dict[str, List[str]]] = None,
        today: Callable[[], date] = date.today,
    ) -> None:
        # Both injected rather than imported, for the reason `DrawTools` gives
        # about the images runtime: this module should hold no opinion about
        # how the Spine or the obligation store is reached, and a test must be
        # able to exercise the tool's own rules — the refusals, the wording,
        # what it files — without a database or an embedder.
        self._remember = remember
        self._record_obligations = record_obligations
        self._today = today

    # -- the built-in server surface ------------------------------------------ #

    def connect(self) -> None:
        """Nothing to start. Present because the runtime calls it."""

    def close(self) -> None:
        """Nothing to stop."""

    def granted_tools(self) -> set:
        """Always offered. Generative tier: it creates records and destroys
        nothing, so there is nothing a confirmation would protect."""
        return {RECORD_POSTING}

    def list_tools(self) -> List[ToolDescriptor]:
        return [
            ToolDescriptor(
                server_id=SERVER_ID,
                name=RECORD_POSTING,
                description=(
                    "File a job posting you have found or been shown: its role, company, "
                    "pay, closing date and the skills it asks for become facts you can "
                    "recall later, and the closing date becomes a reminder. Pass the "
                    "posting's text as it was written — do not summarise it first, and do "
                    "not fill in details it does not state. Use it once per posting. It "
                    "does not apply for anything and never sends a message."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The posting, as written. The whole advertisement, not a summary.",
                        },
                        "url": {
                            "type": "string",
                            "description": "Where it was found, if known.",
                        },
                        "project_id": {
                            "type": "string",
                            "description": "The hunt this belongs to. Leave empty outside a project.",
                        },
                    },
                    "required": ["text"],
                },
            )
        ]

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        arguments = arguments or {}
        if name != RECORD_POSTING:
            return {"error": f"the jobs server has no tool called {name!r}"}
        return self.record(
            str(arguments.get("text") or ""),
            url=str(arguments.get("url") or ""),
            project_id=str(arguments.get("project_id") or ""),
        )

    # -- the tool ------------------------------------------------------------- #

    def record(self, text: str, *, url: str = "", project_id: str = "") -> Dict[str, Any]:
        """Parse a posting, store what it says, and date what it needs.

        The refusals are the interesting part. A snippet is refused rather than
        filed, and a posting with no company **and** no title is refused too —
        a record that cannot be identified later is worse than none, because
        recall will surface it and nobody will know what it refers to.
        """
        if len(text.strip()) < _MINIMUM_POSTING:
            return {
                "error": (
                    "that is too short to be a posting — pass the advertisement's text "
                    "rather than a link or a snippet"
                )
            }

        posting = parse_posting(text, source_url=url, today=self._today())

        if not posting.title and not posting.company:
            return {
                "error": (
                    "no role and no company could be read from that, so there would be "
                    "nothing to recognise the record by later"
                )
            }

        scope = f"project:{project_id}" if project_id.strip() else "global"
        facts = posting.facts()
        for fact in facts:
            self._remember(fact, scope)

        dated = self._dates(posting, project_id=project_id)

        return {
            "success": True,
            "role": posting.title,
            "company": posting.company,
            "workplace": posting.workplace or "not stated",
            "pay": posting.salary.raw if posting.salary else "not stated",
            "closes": posting.closes.isoformat() if posting.closes else "not stated",
            "skills": list(posting.skills),
            "facts_stored": len(facts),
            "reminders": dated,
        }

    def _dates(self, posting: Posting, *, project_id: str) -> List[str]:
        """The closing date, and a follow-up a week after applying.

        Both are **expiries**, which is the honest kind: a job posting lapses
        if nothing is done, and so does the moment when following up is still
        natural. Direction stays `UNKNOWN` — nobody owes anybody anything yet,
        and the `Direction` docstring is explicit that guessing here is the
        expensive kind of wrong.

        Confidence orders what a person reviews first and gates nothing, which
        is the rule about scores that a caller might otherwise be tempted to
        treat as permission.
        """
        if self._record_obligations is None or posting.closes is None:
            return []

        from obligations.contracts import Clause, Obligation, ObligationKind

        who = posting.company or "the company"
        role = posting.title or "the role"
        scope = f"project:{project_id}" if project_id.strip() else "global"
        source = posting.apply_url or posting.source_url or ""

        entries = [
            Obligation(
                id="",
                kind=ObligationKind.EXPIRY,
                summary=f"Applications for {role} at {who} close",
                due=posting.closes,
                source_clause=Clause(text=posting.excerpt[:300]),
                source_document_id=source,
                scope=scope,
                confidence=0.9,
            )
        ]

        follow_up = self._today() + timedelta(days=FOLLOW_UP_DAYS)
        # Only when it would still be before the deadline. A follow-up dated
        # after the posting has closed is a reminder to chase something that
        # is over, which is the kind of noise that makes a person stop reading
        # the list.
        if follow_up < posting.closes:
            entries.append(
                Obligation(
                    id="",
                    kind=ObligationKind.EXPIRY,
                    summary=f"Follow up with {who} about {role}",
                    due=follow_up,
                    source_clause=Clause(text=f"Recorded {self._today().isoformat()}."),
                    source_document_id=source,
                    scope=scope,
                    confidence=0.5,
                )
            )

        written = self._record_obligations(entries)
        ids = written.get("obligations", []) if isinstance(written, dict) else []
        return [e.summary for e in entries[: len(ids)]] if ids else [e.summary for e in entries]
