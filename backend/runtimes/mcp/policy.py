"""What a tool is allowed to do, and who decided.

The rule this implements
------------------------
**Zaram may change things in applications that can undo them, and may only
look at applications that cannot.** That is the maintainer's rule, 1 September
2026, and it is a better rule than the one it replaces — "writes need undo,
confirm and sandbox" was written for arbitrary tools and applied unchanged to
host applications that already solve undo themselves. Driving Blender through
its own API puts the change on Blender's undo stack; requiring Zaram to build a
second one was asking for a thing that already exists.

**Zaram cannot work out for itself which applications those are.** The MCP
specification is explicit — clients "must treat tool annotations as untrusted
unless they originate from a trusted server source" — so a server that says it
is safe has said nothing, and `CLAUDE.md`'s rule that third-party text may
never widen permission says the same in stronger terms. There is no probe that
answers it either: undo is a property of the application behind the server, not
of the protocol.

So it is **declared, once, by the person attaching the server**, recorded, and
revocable. That is not rule 7e's forbidden question. 7e forbids asking a user
to predict something the system could observe; this is the system asking for a
fact only the user holds, at the one moment they are already thinking about it.

Three grades, and the default is the strict one
-----------------------------------------------
`WriteMode.READ_ONLY` is what an unconfigured server gets, because rule 5's
posture is default deny and an unknown server is exactly the case that must
not be given the benefit of the doubt.

Untrusted text may narrow, never widen
--------------------------------------
Annotations are read, and they are only ever allowed to make the verdict
*stricter*. A tool that declares itself destructive is confirmed even on a
host-undo server. A tool that declares itself read-only earns nothing — that is
precisely the claim a hostile server would make, and believing it would turn a
description into a permission, which is the failure `CLAUDE.md` records having
paid for three times.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Set


class WriteMode(str, Enum):
    """What the user has said this server's application can do."""

    #: Nothing may change. The default, and what an application with no undo
    #: of its own gets — a filesystem server, a database, an HTTP API.
    READ_ONLY = "read_only"

    #: The user has declared this server is driven by an application with its
    #: own undo stack: Blender, Unreal, an editor. Writes are permitted, still
    #: one confirmation per tool, because undo only helps someone who knows
    #: there is something to undo.
    HOST_UNDO = "host_undo"

    #: Writes permitted with no confirmation, per tool, after the user has
    #: granted that tool by name. The end state of 7j's "confirm once per
    #: destination and data class, then remember" — never a default, and never
    #: reachable except through a grant the user made deliberately.
    GRANTED = "granted"


class Verdict(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    REFUSE = "refuse"


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    #: Shown to the user, so it says what happened and what would change it.
    #: A refusal that does not say how to permit the thing reads as a broken
    #: product, which is the note `CLAUDE.md` makes about disabled capabilities
    #: being visible rather than silent.
    reason: str


#: Names that mean "this only looks". Used to *narrow* — a tool matching none
#: of these is treated as mutative, which is the safe direction. Never used to
#: widen: matching one of these does not make a tool read-only, because a
#: server author picks the names.
_LOOKS_READ_ONLY = (
    "list", "get", "read", "search", "find", "query", "describe", "inspect",
    "stat", "info", "show", "fetch", "resolve", "count", "exists", "browse",
)

#: Names that mean "this destroys". Matching one is enough to force a
#: confirmation even where the server is otherwise granted, because the cost of
#: being wrong is asymmetric and unrecoverable.
_LOOKS_DESTRUCTIVE = ("delete", "remove", "drop", "destroy", "purge", "truncate", "rm")


def _annotation_says_destructive(annotations: Optional[Mapping[str, Any]]) -> bool:
    """Read the server's own hints, in the one direction they may be believed."""
    if not annotations:
        return False
    if annotations.get("destructiveHint") is True:
        return True
    # `readOnlyHint: False` is the server volunteering that it writes. Believed
    # for the same reason: it makes the verdict stricter, never looser.
    if annotations.get("readOnlyHint") is False:
        return True
    return False


def looks_read_only(tool_name: str, annotations: Optional[Mapping[str, Any]] = None) -> bool:
    """A conservative guess, used only to decide what needs no confirmation.

    Deliberately naive and deliberately one-directional. `CLAUDE.md`'s rule is
    that a score built for ranking is not a score for deciding; this is not a
    score at all, and it may only ever move a tool from "runs freely" to
    "asks". Anything it cannot recognise is treated as a write.
    """
    if _annotation_says_destructive(annotations):
        return False
    name = tool_name.lower()
    if any(word in name for word in _LOOKS_DESTRUCTIVE):
        return False
    return any(name.startswith(word) or f"_{word}" in name for word in _LOOKS_READ_ONLY)


def decide(
    *,
    tool_name: str,
    mode: WriteMode,
    granted_tools: Optional[Set[str]] = None,
    annotations: Optional[Mapping[str, Any]] = None,
) -> Decision:
    """Whether this call runs, asks, or is refused.

    `granted_tools` holds qualified names the user has already approved. It is
    what makes 7j's "then remember" real: the second call to a tool somebody
    has already permitted does not ask again, which is the difference between
    a product opened twice and one opened once.
    """
    granted = granted_tools or set()
    destructive = _annotation_says_destructive(annotations) or any(
        w in tool_name.lower() for w in _LOOKS_DESTRUCTIVE
    )

    # Reading is always permitted. It is the tier that needs no undo, no
    # sandbox and no rollback, which is the whole reason read-only ships first.
    if looks_read_only(tool_name, annotations):
        return Decision(Verdict.ALLOW, "reads only")

    if mode is WriteMode.READ_ONLY:
        return Decision(
            Verdict.REFUSE,
            f"{tool_name} changes something, and this server is read-only "
            f"because nothing here can undo it. Mark the server as backed by "
            f"an app with its own undo to permit it.",
        )

    # Destructive stays a question however much has been granted. Undo does not
    # help with a delete in most applications, and a grant made for "edit the
    # scene" was not consent to empty it.
    if destructive:
        return Decision(Verdict.CONFIRM, f"{tool_name} deletes or overwrites; this always asks")

    if mode is WriteMode.GRANTED or tool_name in granted:
        return Decision(Verdict.ALLOW, "you granted this tool")

    return Decision(
        Verdict.CONFIRM,
        f"{tool_name} changes something. Its app can undo it, and Zaram will "
        f"stop asking about this tool once you allow it.",
    )
