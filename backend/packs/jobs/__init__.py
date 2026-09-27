"""The job-hunt pack — a posting read into fields, and what follows from it.

`CLAUDE.md` says a pack is four things: parsers, tools, output templates and
routing exemplars, and no screens. This is the first of them.

**It exists because the scheduler already works.** `core/triggers.py` can ask
"find remote 3D roles posted this week" every Monday morning, unattended, with
recall and the gate and a transcript. What it leaves behind is prose. A pack is
the difference between a scheduled question and a feature: the posting becomes
facts on the Spine that recall can reach six months later, the closing date
becomes an obligation that surfaces before it lapses, and the cover letter
becomes a document that knows what the last nine said.

Built in slices, and this is slice one
--------------------------------------
`posting.py` is a library with tests and **no caller yet**, which this file
says out loud because the working agreement says to assume unreachable until
the caller is seen — this codebase has found fifteen complete, tested,
unreachable subsystems. The caller is named rather than assumed: slice two adds
`ProjectType.JOB_HUNT` and routes a posting through this on ingest.

The rest, in order: the scheduled search (a weekly trigger scoped to the hunt),
the letter templates beside `render_cv`, and the obligations for closing dates
and day-seven follow-ups.

What it will never do
---------------------
Submit an application. That is mutative *and* egressive with no undo — an
application cannot be unsent — and job portals sit behind the bot detection
`CLAUDE.md` forbids defeating. The hunt ends at a finished, filed, tracked
draft, and the send stays the person's.
"""

from .posting import Posting, Salary, Workplace, parse_posting

__all__ = ["Posting", "Salary", "Workplace", "parse_posting"]
