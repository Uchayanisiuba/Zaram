"""Which project the request in flight belongs to, by name, and whether a
question is about it.

**Reported 12 October 2026, with a screenshot.** The project picker read *Ride
Share*, the project had a repository at `C:\\RideShare`, and *"What are the
unfinished tasks in Ride Share?"* was answered with a web search -- four facts
about the Zeigarnik effect and a reply saying the sources did not cover the
project, then suggesting the person look in the folder Zaram had open. The
question read as a search (*"what are..."*), and the search plan comes before
the plan that offers the project's tools, so the folder was never read. The
person had already said which project they meant by choosing it; they should
not have to say *"look in the code"* as well.

So the open project's name is request state, carried the way the code pack
carries its root -- a `ContextVar`, because two windows can be in two projects
at once -- and `about_the_open_project` answers one narrow question: does this
message point at that project? Two ways it can:

* **By name.** Compared with spacing, case and punctuation removed, so "Ride
  Share", "rideshare" and "Ride-Share" are one name. Read off the person's
  words against the project's recorded name: a property, never a guess about
  what a name looks like.
* **By reference.** "this project", "the app", "our repo", "the codebase".
  With a project open there is only one thing those can mean.

And one way it stops: **asking for the web by name.** "Search online for ride
share prices in Lagos" mentions the name and is plainly not about the folder.
A person who says *online*, *the web* or *the internet* gets the web.

Deliberately not here: deciding *what to do* about it. The planner reads this
and keeps its own plans; this module only says whether the question is about
the project, so the answer can be tested without a router.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Optional

_OPEN_NAME: ContextVar[Optional[str]] = ContextVar("zaram_open_project_name", default=None)

#: "this project", "the app", "our repo" -- a reference that, with a project
#: open, has exactly one referent.
_POINTS_AT_IT = re.compile(
    r"\b(?:this|the|my|our)\s+(?:project|repo|repository|codebase|code\s*base|code|app|application|site|website)\b",
    re.IGNORECASE,
)

#: The person asked for the web in words. Their call outranks the project.
_ASKS_FOR_THE_WEB = re.compile(
    r"\b(?:online|on\s+the\s+(?:web|internet|net)|the\s+web|the\s+internet|google|search\s+engine|web\s+search|latest\s+news)\b",
    re.IGNORECASE,
)

#: A name shorter than this, once flattened, matches inside too many words to
#: mean anything ("ai", "go").
_MIN_NAME = 4


def set_open_project(name: Optional[str]) -> None:
    """Record the open project's name for this request; ``None`` for none.

    Called on every chat request, including the ones that clear it, for the
    reason `_open_code_project` gives: a name left over from the last request
    would make a question asked with no project open look like it was about one.
    """
    cleaned = (name or "").strip()
    _OPEN_NAME.set(cleaned or None)


def open_project_name() -> Optional[str]:
    """The open project's name, or ``None``."""
    return _OPEN_NAME.get()


def _flat(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", text.lower())


def names_the_project(text: str, name: Optional[str]) -> bool:
    """Whether ``text`` contains ``name``, ignoring case, spaces and punctuation."""
    flat_name = _flat(name or "")
    if len(flat_name) < _MIN_NAME:
        return False
    return flat_name in _flat(text or "")


def about_the_open_project(text: str) -> bool:
    """Whether the person's message points at the project that is open.

    ``False`` with no project open, and ``False`` whenever the person asked for
    the web in words. Otherwise ``True`` when the message names the project or
    refers to it as "this project", "the app" and the like.
    """
    name = open_project_name()
    if not name or not text:
        return False
    if _ASKS_FOR_THE_WEB.search(text):
        return False
    return names_the_project(text, name) or bool(_POINTS_AT_IT.search(text))
