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

import re
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
#: `kill` is the one addition: a tool that kills a process is destructive on any
#: server. Words like `browser`, `frame` or `end` are not -- a destructive word
#: cannot be satisfied by a grant, so `open_in_browser` carrying one asked again
#: after every "allow", which is the dialog-a-day failure rule 7j names. Where a
#: particular server needs more than the words, it is named by server below.
_LOOKS_DESTRUCTIVE = ("delete", "remove", "drop", "destroy", "purge", "truncate", "rm", "kill")

#: Names that mean "this sends something to someone". **A different hazard from
#: destruction and the same shape**: once it has gone it cannot be called back,
#: and what goes is the user's words in the user's name. Matching one forces a
#: fresh confirmation however much has been granted, for the reason the
#: destructive list does — the cost of being wrong is asymmetric — and for one
#: more that `CLAUDE.md` gives about generation: *a wrong reply is corrected in
#: the next turn; a wrong document is sent to a client.* A send is where the
#: second becomes true.
#:
#: Written 4 October 2026 from `docs/MILESTONES.md`'s draft-and-hold rule for
#: email. Without it, a mail server's `send_message` was an ordinary write: allow
#: it once and "Zaram will stop asking about this tool" applied to the one tool
#: that must never stop being asked about — including from an unattended
#: automation. Drafting is deliberately absent: `create_draft` is held by
#: definition, which is the whole point of drafting.
#:
#: One-directional like its sibling: a name here can only make a tool stricter,
#: and a send with an unrecognised name is still an unrecognised write, which
#: `decide` already treats as needing a confirmation.
_LOOKS_OUTBOUND = (
    "send", "reply", "forward", "publish", "tweet", "broadcast", "submit",
    "upload",
)

#: Words that are a send as a verb and a thing as a noun. `post_comment` sends;
#: `get_post` reads a blog post, and `list_pushes` lists. Counted as outbound
#: **only when the name has no look-word in it** -- the same one-directional
#: logic, applied where the vocabulary is genuinely ambiguous. Without this
#: split every `get_post` would have asked for confirmation, which is the
#: dialog-a-day failure rule 7j names.
_OUTBOUND_UNLESS_A_LOOK = ("post", "push", "share", "invite")


#: Shortest word that may match a token by its prefix.
#:
#: Longer words are distinctive enough that `delete_user`, `deleteAll` and
#: `deletion` all mean the same thing. Short ones are not: `rm` must be a
#: token of its own, or it matches `terminal`.
_PREFIX_MATCH_FROM = 5


def _words_in(tool_name: str) -> set:
    """A tool name as the words it is made of.

    `run_in_terminal`, `runInTerminal` and `run-in-terminal` are the same
    three words, and a server author picks which spelling. Splitting on
    separators *and* on a lower-to-upper transition covers every convention
    in use without needing to know which one this server chose.
    """
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", tool_name)
    return {w for w in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if w}


def _matches(tool_name: str, words: tuple) -> bool:
    """Whether any of `words` is a word in `tool_name`.

    **This was a substring test, and `rm` is why it is not any more.**
    Found 3 October 2026 by a terminal tool that asked for confirmation
    however much had been granted: `"rm" in "run_in_terminal"` is true,
    because *terminal* contains the letters r and m next to each other. So
    did `format_code`, `transform_mesh`, `confirm_order` and `warm_cache` —
    every one of them permanently destructive, and `destructive` is the one
    verdict a grant cannot satisfy. Rule 7j's confirm-once was broken for a
    whole class of ordinary tool names, silently, and the symptom is a
    dialog the user has already dismissed a hundred times.

    It is the second time today a word list matched inside a word: this
    morning `open_in_browser` was read as read-only because it contains
    `_browse`. Same defect, opposite direction, same afternoon — which is
    why both lists are fixed here rather than only the one that failed.
    """
    present = _words_in(tool_name)
    for word in words:
        if word in present:
            return True
        if len(word) >= _PREFIX_MATCH_FROM and any(
            _inflects(token, word) for token in present
        ):
            return True
    return False


#: The endings that make a token the same word. **Inflections, not any longer word**:
#: the prefix test this replaced read `browser` as `browse` + "r", so every
#: `browser_*` tool and `open_in_browser` were "reads only" again -- the 3 October
#: defect this function's docstring records, back through the prefix rule added to fix
#: its sibling. Found 10 October 2026 when cua-driver's `browser_navigate`, which sends
#: the person's real browser to any URL, was allowed without asking on every server.
_INFLECTIONS = ("s", "es", "d", "ed", "ing")


def _inflects(token: str, word: str) -> bool:
    """`deletes`, `deleted`, `fetching`, `removing` are `word`; `browser` is not `browse`."""
    stems = [word] + ([word[:-1]] if word.endswith("e") else [])
    return any(token == stem + ending for stem in stems for ending in _INFLECTIONS)


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
    if _matches(tool_name, _LOOKS_DESTRUCTIVE):
        return False
    # A name that sends is not a look, whatever else is in it: `fetch_and_send`.
    if _matches(tool_name, _LOOKS_OUTBOUND):
        return False
    return _matches(tool_name, _LOOKS_READ_ONLY)


def looks_destructive(tool_name: str, annotations: Optional[Mapping[str, Any]] = None) -> bool:
    """Whether this tool destroys rather than merely changes.

    Public because a *run* the person let go without stopping still may not
    delete on its own: "run without stopping" is consent to the plan's changes,
    never to its removals, and the engine needs the same answer `decide` uses
    rather than a second copy of the word list. One-directional like its
    sibling above — anything unrecognised is not called destructive, because
    `decide` already treats an unrecognised write as needing a confirmation.
    """
    if _annotation_says_destructive(annotations):
        return True
    return _matches(tool_name, _LOOKS_DESTRUCTIVE)


def looks_outbound(tool_name: str) -> bool:
    """Whether this tool sends something to someone.

    Public for the same reason `looks_destructive` is: the engine's "let this
    plan run without stopping" must not cover a send, and the permission card
    must not offer to remember one. One word list, three readers.
    """
    if _matches(tool_name, _LOOKS_OUTBOUND):
        return True
    return _matches(tool_name, _OUTBOUND_UNLESS_A_LOOK) and not _matches(
        tool_name, _LOOKS_READ_ONLY
    )


#: cua-driver's tools by exact name. Keyed to the server and never to the name
#: alone: `decide` once answered "reads only" for any server's `get_config`, ahead
#: of that server's own `destructiveHint`, which is a name widening a permission.
_CUA_READ_ONLY = frozenset({
    "get_browser_state", "get_window_state", "get_desktop_state",
    "get_screen_size", "get_cursor_position", "get_accessibility_tree",
    "get_config", "get_session", "list_sessions", "get_agent_cursor_state",
    "get_recording_state", "check_permissions", "health_report",
    "list_windows", "list_apps", "list_files", "zoom",
})
_CUA_MUTATIVE = frozenset({
    "start_session", "end_session", "start_recording", "stop_recording",
    "replay_trajectory", "install_extension", "set_config", "install_ffmpeg",
    "set_agent_cursor_enabled", "set_agent_cursor_motion", "set_agent_cursor_theme",
    "set_window_frame", "clipboard_write", "browser_download", "browser_set_input_files",
    "kill_app", "invoke_menu", "bring_to_front", "launch_app", "drag",
    "click", "double_click", "right_click", "type_text", "press_key",
    "hotkey", "scroll", "set_value", "browser_click", "browser_type",
    "browser_pointer", "browser_dialog", "run_actions",
})
#: Asked every time, whatever has been granted: they destroy, or move something
#: off the machine or onto the clipboard.
_CUA_ALWAYS_CONFIRM = frozenset({
    "kill_app", "end_session", "stop_recording", "clipboard_write",
    "browser_download", "browser_set_input_files",
    # Sends the person's own browser, signed in as them, to a URL the model chose.
    # A URL can carry anything in its query, so this is a send as well as a change.
    "browser_navigate",
})
#: Refused outright, on any mode and any grant. Each one makes the driver reach the
#: internet itself -- GitHub for an update check, a download for ffmpeg or an
#: extension -- where Zaram's egress gate cannot see it and its log cannot record it
#: (rule 3), or rewrites the driver's own settings, which is where its telemetry
#: switch lives. Zaram installs and configures the driver; the model does not.
_CUA_REFUSED = {
    "check_for_update": "contacts GitHub on its own, outside Zaram's egress log",
    "install_ffmpeg": "downloads a program on its own, outside Zaram's egress log",
    "install_extension": "downloads an extension on its own, outside Zaram's egress log",
    "set_config": "rewrites the driver's own settings, including its telemetry switch",
}
_CUA_MUTATIVE = _CUA_MUTATIVE | {"browser_navigate", "page", "move_cursor", "escalate_session"}
_CUA_READ_ONLY = _CUA_READ_ONLY | {"verify_state", "parse_visual_regions", "debug_window_info", "get_session_state"}


def _is_cua_server(server_id: str) -> bool:
    return "cua" in (server_id or "").lower()


def always_asks(server_id: str, tool_name: str) -> bool:
    """Whether no grant can ever settle this tool -- so a card must not offer one.

    cua-driver's always-confirm tools ask on every call by name, and the runtime's
    `grantable` read only the generic word lists, so the card offered "always allow"
    for `kill_app` and `browser_navigate` and the gate then ignored the answer.
    """
    if _is_self_server(server_id) and tool_name in _SELF_ALWAYS_ASK:
        return True
    if _is_github_server(server_id) and tool_name in _GITHUB_ALWAYS_ASK:
        return True
    return _is_cua_server(server_id) and tool_name in _CUA_ALWAYS_CONFIRM


#: Zaram's own settings tools that ask every time. `grant_tool` because a model
#: must never be able to widen its own permissions off one card allowed once;
#: `set_web_search` because turning it on lets questions leave the computer, and
#: that is the person's decision each time (rule 5). Kept in step with
#: `zaram_self.ALWAYS_ASK` by test rather than imported, so this module keeps no
#: dependency on a server.
_SELF_ALWAYS_ASK = frozenset({"grant_tool", "set_web_search"})


def _is_self_server(server_id: str) -> bool:
    return (server_id or "") == "zaram-self"


#: Zaram's GitHub tools that change something there, by name. A push puts a whole
#: project in front of whoever can read the repository; a pull request or an issue
#: is public words in the person's name -- so none of them can be settled by a
#: standing yes. Kept in step with `packs/github/tools.WRITE_TOOLS` by test rather
#: than imported, as `_SELF_ALWAYS_ASK` is, so this module keeps no dependency on a pack.
_GITHUB_ALWAYS_ASK = frozenset({
    "github_push_branch", "github_open_pull_request", "github_create_issue", "github_create_repository",
})


def _is_github_server(server_id: str) -> bool:
    return (server_id or "") == "github"


def _cua_decision(
    tool_name: str,
    mode: WriteMode,
    granted: Set[str],
    annotations: Optional[Mapping[str, Any]],
) -> Optional[Decision]:
    """The verdict for a cua-driver tool by exact name, or ``None`` to fall through.

    One-directional like the rest of this module: the read-only set is skipped
    when the server's own hint says the tool writes, so a name can only ever
    loosen what the server has not contradicted.
    """
    if tool_name in _CUA_REFUSED:
        return Decision(Verdict.REFUSE, f"{tool_name} {_CUA_REFUSED[tool_name]}, so Zaram does not run it.")
    if tool_name in _CUA_READ_ONLY:
        if _annotation_says_destructive(annotations):
            return None
        return Decision(Verdict.ALLOW, "reads only")
    if tool_name in _CUA_MUTATIVE:
        if mode is WriteMode.READ_ONLY:
            return Decision(
                Verdict.REFUSE,
                f"{tool_name} changes something, and this server is read-only "
                f"because nothing here can undo it. Mark the server as backed by "
                f"an app with its own undo to permit it.",
            )
        if tool_name in _CUA_ALWAYS_CONFIRM:
            return Decision(Verdict.CONFIRM, f"{tool_name} always asks; cannot be called back")
        if mode is WriteMode.GRANTED or tool_name in granted:
            return Decision(Verdict.ALLOW, "you granted this tool")
        return Decision(
            Verdict.CONFIRM,
            f"{tool_name} changes something. Its app can undo it, and Zaram will "
            f"stop asking about this tool once you allow it.",
        )
    return None


def decide(
    *,
    tool_name: str,
    mode: WriteMode,
    granted_tools: Optional[Set[str]] = None,
    annotations: Optional[Mapping[str, Any]] = None,
    not_read_only: bool = False,
    server_id: str = "",
) -> Decision:
    """Whether this call runs, asks, or is refused.

    `granted_tools` holds qualified names the user has already approved. It is
    what makes 7j's "then remember" real: the second call to a tool somebody
    has already permitted does not ask again, which is the difference between
    a product opened twice and one opened once.

    `not_read_only` overrides the name guess below and nothing else. It is
    how a caller that *knows* — one of Zaram's own built-ins, never a
    stranger's server — says that a tool whose name reads like a look is
    not one. Deliberately separate from `readOnlyHint: False`, which also
    marks a tool destructive and so makes it ask however much is granted:
    needing the grant and asking every single time are different verdicts,
    and merging them costs 7j's confirm-once. See
    `McpRuntime._builtin_says_not_read_only` for the case that found it.
    """
    granted = granted_tools or set()

    # cua-driver names its tools exactly and a stranger's server must not borrow
    # them, so these apply to that server only.
    if _is_cua_server(server_id):
        settled = _cua_decision(tool_name, mode, granted, annotations)
        if settled is not None:
            return settled

    if _is_self_server(server_id) and tool_name in _SELF_ALWAYS_ASK:
        return Decision(Verdict.CONFIRM, f"{tool_name} always asks; a standing yes is never kept for it")

    if _is_github_server(server_id) and tool_name in _GITHUB_ALWAYS_ASK:
        return Decision(
            Verdict.CONFIRM,
            f"{tool_name} changes something on GitHub, in your name. It asks every time; a standing yes is never kept for it.",
        )

    destructive = looks_destructive(tool_name, annotations)

    # Reading is always permitted. It is the tier that needs no undo, no
    # sandbox and no rollback, which is the whole reason read-only ships first.
    if not not_read_only and looks_read_only(tool_name, annotations):
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

    # A send stays a question however much has been granted, for the same
    # reason a delete does. Placed after the read-only refusal so a server that
    # may not change anything still says so, and before the grant so that
    # "allow this tool" cannot settle it.
    if looks_outbound(tool_name):
        return Decision(
            Verdict.CONFIRM,
            f"{tool_name} sends something to someone, and it cannot be called "
            "back; this always asks. Drafts are held until you send them.",
        )

    if mode is WriteMode.GRANTED or tool_name in granted:
        return Decision(Verdict.ALLOW, "you granted this tool")

    return Decision(
        Verdict.CONFIRM,
        f"{tool_name} changes something. Its app can undo it, and Zaram will "
        f"stop asking about this tool once you allow it.",
    )
