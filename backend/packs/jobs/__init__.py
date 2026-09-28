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

What is here, and what reaches it
--------------------------------
* `posting.py` — the **parser**. A posting into fields, deterministically,
  with every field `None` until the text supports it.
* `tools.py` — the **tool**, `record_job_posting`, registered as one of
  Zaram's built-in servers in `core/bootstrapper.py`. This is what makes the
  parser reachable: an unattended run has no person to press a button, so the
  way in has to be something the model can call inside the loop.
* `letter.py` — the **output templates**, covering letter and follow-up, as
  `artifacts` blocks so they go through the one document pipeline.
* No project type. The tools register at boot and the model reaches them
  from the request — see `projects.records.ProjectType`, which gates only
  `coding`. This line used to name a `JOB_HUNT` member and claim it
  activated the pack; it never did, and it was dropped on 28 September 2026.

The **routing exemplars**, the fourth of the four, are not here yet and that
is said rather than implied: the tool's description is doing that work for
now, which is enough for a model that can call tools and not enough for one
that cannot.

The scheduled half needs no code. `core/triggers.py` already runs a weekly
question unattended; the hunt is a trigger whose question is *"find remote 3D,
technical art and animation roles posted this week that match my CV, and file
each one"* — the tool does the filing.

What it will never do
---------------------
Submit an application. That is mutative *and* egressive with no undo — an
application cannot be unsent — and job portals sit behind the bot detection
`CLAUDE.md` forbids defeating. The hunt ends at a finished, filed, tracked
draft, and the send stays the person's.
"""

from .letter import cover_letter_blocks, follow_up_blocks
from .posting import Posting, Salary, Workplace, parse_posting
from .tools import RECORD_POSTING, SERVER_ID, JobTools

__all__ = [
    "RECORD_POSTING",
    "SERVER_ID",
    "JobTools",
    "Posting",
    "Salary",
    "Workplace",
    "cover_letter_blocks",
    "follow_up_blocks",
    "parse_posting",
]
