"""The web pack: reading a page the person points at.

`docs/MILESTONES.md`, 13 September 2026: search existed and could read the
pages it returned (`runtimes/internet/deep_read.py`), but nothing could open
a page a *person* named — *"pmnewsnigeria.com, tell me what is on this
page"* answered, honestly, that Zaram could not reach it. This is the tool
that can: `read_page`, on Zaram's own built-in server, offered to the model
through the same loop, gate and log as every other tool.

**Consent is the interesting part, and it is rule 7j exactly.** *Consent
given deliberately for a destination is consent*: a URL the person typed
into their own message is a destination they named, so the fetch may go
past default-deny — as a `SearchReadGrant` of that exact URL, the same
capability search results already travel on. A URL the *model* produces —
invented, or lifted from a tool description, which is third-party text and
may never widen permission — gets no grant and meets the per-host policy
like any other request: allowed, asked, or refused, and the refusal comes
back as the tool's answer with the sentence that says so. The two are told
apart by where the URL came from, never by who claims to be asking.

Deterministic, no model: fetch, strip the furniture, hand back the prose.
Bounded (`MAX_CHARS`) so one page cannot become the whole window.
"""

from .active import named_urls, set_named_urls
from .tools import READ_PAGE, SERVER_ID, WebTools

__all__ = ["WebTools", "READ_PAGE", "SERVER_ID", "set_named_urls", "named_urls"]
