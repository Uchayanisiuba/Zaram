"""What a plan step is called on screen, while it runs and after.

**Every step gets a row, not only tool calls — 19 September 2026.** A web
search or a page read on an ordinary turn runs as a plan step before the
model generates, and until now it reached the screen, at best, as a notice
afterwards: the person asked something, waited, and got an answer with
"4 sources" under it, never seeing the search happen. `ToolCalls` already
renders one row per call inside the tool loop, live and folding when done.
This is the vocabulary that lets the *planner's* steps use the same row —
*Searching the web for "…"* while it runs, *Searched the web · 4 results*
when it is done — with Claude's rows as the reference the maintainer named.

Two rules, and they are why this is a table rather than a format string:

* **A verb here is a claim about what happened.** "Searched the web" is only
  said for a step that searches the web. A capability this table does not
  name gets no row at all rather than a guessed one — `CLAUDE.md`: never
  render invented values, and a wrong verb on a status row is one.
* **Bookkeeping steps stay silent.** `mcp.list_tools` puts tools in front of
  the model and `reasoning.generate` *is* the answer; neither is an action a
  person would list. The tools notice already says which servers were
  offered, and the reply is the reply.

The target is what the step was aimed at — the query, the picture, the
document — bounded and rendered as text, never markup, for the same reason
`call_target` bounds a tool's target: it is the person's or the model's words.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

#: Longest a target may be on a row. A query is usually a sentence; a prompt
#: for a drawing can be a paragraph, and a row is one line.
MAX_TARGET = 80


@dataclass(frozen=True)
class StepLabel:
    #: Present tense, while the step runs: "Searching the web".
    doing: str
    #: Past tense, once it has: "Searched the web".
    done: str
    #: What it was aimed at, or "". Shown after the verb.
    target: str


#: Capability id → (doing, done). The absence of an entry is deliberate.
_VERBS: dict[str, tuple[str, str]] = {
    "knowledge.search": ("Searching the web", "Searched the web"),
    "discovery.search": ("Searching the web", "Searched the web"),
    "filesystem.search": ("Searching files", "Searched files"),
    "vision.analyze": ("Reading the image", "Read the image"),
    "image.generate": ("Drawing", "Drew"),
    "document.generate": ("Writing the document", "Wrote the document"),
}

#: Which input carries the target, per capability. A search is aimed at its
#: query; a drawing at what was asked for; a document and a picture-read at
#: nothing a row could usefully print.
_TARGET_KEY: dict[str, str] = {
    "knowledge.search": "query",
    "discovery.search": "query",
    "filesystem.search": "query",
    "image.generate": "prompt",
}


def describe_step(capability_id: str, input_data: Mapping[str, Any] | None) -> Optional[StepLabel]:
    """The row's words for this step, or ``None`` for a step that gets no row."""
    verbs = _VERBS.get(capability_id or "")
    if verbs is None:
        return None
    key = _TARGET_KEY.get(capability_id, "")
    raw = (input_data or {}).get(key) if key else ""
    return StepLabel(doing=verbs[0], done=verbs[1], target=bound_target(raw))


def bound_target(raw: Any) -> str:
    """One line, at most `MAX_TARGET` characters, cut at a word."""
    text = " ".join(str(raw or "").split())
    if len(text) <= MAX_TARGET:
        return text
    cut = text[:MAX_TARGET]
    at = cut.rfind(" ")
    return (cut[:at] if at > MAX_TARGET // 2 else cut).rstrip(" ,;:") + "…"
