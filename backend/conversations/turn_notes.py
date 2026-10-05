"""What a reply *did*, read off the stream it already sent.

Asked for 3 October 2026: *"when a Zaram session is closed the plans, tools
used, files download etc attached to the session seems to disappear ... users
should be able to go back to previous conversations and access them."*

Measured before building. Of 50 artifacts in the maintainer's own store,
**none** was filed under a conversation that exists — 27 under `''` and 23
under a `session-…` id. The `conversation_id` column, its index, the
`?conversation_id=` query parameter and the Work surface that reads it were
all present and correct. Nothing had ever written a value that matched,
because the chat path passes the *session* id — ephemeral, minted per
launch — where the durable conversation id belongs. The seventeenth complete,
tested, unreachable subsystem, and the first one found by querying the
database rather than by reading the code.

**Why the backend assembles this and not the renderer.** `chatStore` already
builds exactly this shape for the live reply, so having it post the result
back would be one writer and no duplication — and it was the first design.
It loses to rule 7d: deciding what enters the store is the system's job, and
a transcript assembled by the client is a transcript the client can be wrong
about. So the shape is built here, from the same frames the renderer sees,
and `test_a_reply_remembers_what_it_did.py` pins the field names against the
TypeScript interfaces so the two cannot drift silently.

**What is deliberately not kept here: citations.** `resumeConversation`
refuses to restore sources, and that refusal is right — a citation is a live
claim that *this* answer used *that* fact, and the fact may since have been
corrected or deleted under rule 4, so yesterday's citation against today's
Spine shows provenance that no longer holds. None of that applies to a tool
call, a checklist or a file: a tool ran or it did not, and a file is on disk.
They are records of what happened rather than claims about what is true now.

**Citations arrive here as references, 4 October 2026, and not as claims.**
Restoring them as history was the better answer and is what this now does, but
the argument above still governs how: what is kept is *which fact or page an
answer leaned on* -- an id, a kind, a number -- and never the fact's text. The
text is the user's data, and a copy of it in the transcript would survive
rule 4: delete the fact and its wording would still sit here. On reopen the
references are resolved against the Spine as it is **now**, and a fact that was
corrected or deleted says so (`conversations/citations.py`). A web page is the
exception that proves it: what was read from the web is a record of something
that happened and left the machine, so its title and address are kept.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

#: How much of one tool's output is kept in the transcript.
#:
#: The stream already bounds this (`output_excerpt`), so the cap here is a
#: second fence rather than the first — a `diff` for a large file is the one
#: that actually grows, and a transcript row is not where somebody reads a
#: whole file back.
MAX_FIELD_CHARS = 4_000

#: How many calls one reply may record. A loop that ran away is still worth
#: showing, but it must not be able to put megabytes into a row that is read
#: whole every time the conversation is opened.
MAX_CALLS = 200

#: How many citations one reply may keep. A reply that recalled hundreds is a
#: different problem, and a row read whole on every open must stay small.
MAX_SOURCES = 60


def _clip(value: Any) -> str:
    text = value if isinstance(value, str) else ""
    if len(text) <= MAX_FIELD_CHARS:
        return text
    # Marked rather than silently cut: a diff that simply stops looks like a
    # diff that was that length.
    return text[:MAX_FIELD_CHARS] + "\n…"


class TurnNotes:
    """Collects the plan, the tool calls and the files out of one reply.

    Fed every frame the chat endpoint yields, including the ones it does not
    care about. It never raises: a frame it cannot read is skipped, because
    bookkeeping must not be able to interrupt a reply.
    """

    def __init__(self) -> None:
        self._text_len = 0
        self._calls: List[Dict[str, Any]] = []
        self._plan: Optional[Dict[str, Any]] = None
        self._artifact_ids: List[str] = []
        self._sources: List[Dict[str, Any]] = []

    # ---------------------------------------------------------------- input

    def see(self, chunk: str, *, answer_len: Optional[int] = None) -> None:
        """Read one IPC frame. Anything unparseable is ignored."""
        try:
            frame = json.loads(chunk)
        except Exception:
            return
        if not isinstance(frame, dict):
            return
        data = frame.get("data")
        if not isinstance(data, dict):
            # Dropped rather than coerced to `{}`. Coercing it recorded a tool
            # row with every field empty — a blank line in the transcript that
            # reads as a call Zaram made and cannot describe, which is the
            # invented value the UI principles rule out. Caught by
            # `test_an_unreadable_frame_is_skipped_not_raised`.
            return
        kind = frame.get("type")

        if answer_len is not None:
            self._text_len = answer_len

        try:
            if kind == "plan":
                self._see_plan(data)
            elif kind == "tool_call":
                self._see_tool_call(data)
            elif kind == "step_start":
                self._see_step_start(data)
            elif kind == "step_complete":
                self._see_step_complete(data)
            elif kind == "artifact":
                self._see_artifact(data)
            elif kind == "source":
                self._see_source(data)
        except Exception:
            # Same reasoning as the parse guard above.
            return

    # --------------------------------------------------------------- frames

    def _see_plan(self, data: Dict[str, Any]) -> None:
        """The checklist, whole — the last one sent wins.

        **The engine's own step list is not kept.** `source == "planner"` is
        the list built from the plan's steps, which the interface shows only
        while the reply is in flight; storing it would put a second,
        differently-worded checklist under every planned reply after the fact.
        The renderer makes the same exclusion on the live path.
        """
        if data.get("source") == "planner":
            return
        items = data.get("items")
        if not isinstance(items, list):
            return
        self._plan = {
            "items": [i for i in items if isinstance(i, dict)],
            "awaitingGo": bool(data.get("awaiting_go")),
        }

    def _see_tool_call(self, data: Dict[str, Any]) -> None:
        # A call with no name is not a call anybody can read. Same reasoning
        # as the non-dict payload above: a row saying nothing is worse in a
        # transcript than no row.
        if not data.get("tool") or len(self._calls) >= MAX_CALLS:
            return
        call: Dict[str, Any] = {
            "server": data.get("server") or "",
            "tool": data.get("tool") or "",
            "verdict": data.get("verdict") or "",
            "reason": data.get("reason") or "",
            "target": data.get("target") or "",
            "output": _clip(data.get("output")),
            # Where the row sits between the paragraphs. The tokens counted
            # here are the ones the user sees — citation markers are already
            # stripped upstream — so this is the same number the renderer
            # computes from the text on screen.
            "at": self._text_len,
        }
        # Absent rather than empty, matching the renderer: a field that is
        # present-but-meaningless on the common case is one the next reader
        # has to test twice.
        for wire, key in (
            ("diff", "diff"),
            ("commit", "commit"),
            ("image", "image"),
            ("app_url", "appUrl"),
            ("step_id", "stepId"),
        ):
            if data.get(wire):
                call[key] = _clip(data.get(wire)) if wire == "diff" else data[wire]
        if data.get("grantable"):
            call["grantable"] = True
        if data.get("grant_scope"):
            call["grantScope"] = data["grant_scope"]
        # `is not None` rather than truthy: step 0 is the first step of every
        # plan and is the one most calls belong to.
        if data.get("plan_step") is not None:
            call["planStep"] = data["plan_step"]
        self._calls.append(call)

    def _see_step_start(self, data: Dict[str, Any]) -> None:
        """A planner step, shown as a row while it runs."""
        if not data.get("doing") or len(self._calls) >= MAX_CALLS:
            return
        self._calls.append(
            {
                "server": "zaram",
                "tool": data.get("capability") or "",
                "verdict": "running",
                "reason": "",
                "target": data.get("target") or "",
                "output": "",
                "label": data.get("done") or "",
                "doing": data.get("doing") or "",
                "stepId": data.get("step_id") or "",
                "at": self._text_len,
            }
        )

    def _see_step_complete(self, data: Dict[str, Any]) -> None:
        """Settle the running row in place rather than adding a second one."""
        if not data.get("done"):
            return
        step_id = data.get("step_id") or ""
        settled = {
            "server": "zaram",
            "tool": data.get("capability") or "",
            "verdict": "allow" if data.get("success") else "refuse",
            "reason": data.get("detail") or "",
            "target": data.get("target") or "",
            "output": "",
            "label": data.get("done") or "",
            "stepId": step_id,
            "seconds": data.get("seconds"),
        }
        at = -1
        if step_id:
            for i, call in enumerate(self._calls):
                if call.get("stepId") == step_id:
                    at = i
                    break
        if at >= 0:
            self._calls[at] = {**self._calls[at], **settled}
        elif len(self._calls) < MAX_CALLS:
            self._calls.append({**settled, "at": self._text_len})

    def _see_artifact(self, data: Dict[str, Any]) -> None:
        """A file this reply produced. Ids only — see `Message.artifact_ids`."""
        artifact_id = data.get("id")
        if isinstance(artifact_id, str) and artifact_id and artifact_id not in self._artifact_ids:
            self._artifact_ids.append(artifact_id)

    def _see_source(self, data: Dict[str, Any]) -> None:
        """A citation, kept as a reference. See the module docstring.

        Nothing is stored that is the user's own text: not the excerpt, and for
        a fact or a document not the title either (a memory's title *is* the
        fact). What identifies the thing is enough to find it again.
        """
        if len(self._sources) >= MAX_SOURCES:
            return
        kind = str(data.get("kind") or "")
        url = data.get("url")
        record_id = data.get("record_id")
        if not kind or not (url or record_id):
            return
        key = str(record_id or url)
        if any((s.get("recordId") or s.get("url")) == key for s in self._sources):
            return
        ref: Dict[str, Any] = {
            "kind": kind,
            "url": url if isinstance(url, str) else None,
            "number": data.get("number"),
            "cited": bool(data.get("cited", True)),
            "origin": data.get("origin"),
            "relevance": data.get("relevance"),
        }
        if isinstance(record_id, str) and record_id:
            ref["recordId"] = record_id
        if kind == "web":
            # A page that was read: a record of something that left the
            # machine. The egress row is the link back to the log.
            ref["title"] = _clip(data.get("title"))[:200]
            if data.get("egress_id"):
                ref["egressId"] = data["egress_id"]
            if data.get("bytes_sent") is not None:
                ref["bytesSent"] = data["bytes_sent"]
        self._sources.append(ref)

    # --------------------------------------------------------------- output

    @property
    def sources(self) -> List[Dict[str, Any]]:
        return [dict(s) for s in self._sources]

    @property
    def tool_calls(self) -> List[Dict[str, Any]]:
        """Calls with a verdict, finished.

        A row still saying `running` when the stream ended did not finish, and
        the renderer marks exactly those `refuse` / "did not finish" before it
        commits the message. Doing the same here keeps a reopened transcript
        from showing a spinner for a call that stopped weeks ago.
        """
        out = []
        for call in self._calls:
            if call.get("verdict") == "running":
                call = {**call, "verdict": "refuse", "reason": "did not finish"}
            out.append(call)
        return out

    @property
    def plan(self) -> Optional[Dict[str, Any]]:
        return self._plan

    @property
    def artifact_ids(self) -> List[str]:
        return list(self._artifact_ids)

    def is_empty(self) -> bool:
        return (
            not self._calls
            and self._plan is None
            and not self._artifact_ids
            and not self._sources
        )
