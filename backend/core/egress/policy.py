"""Per-source egress policy. Default deny.

Rule 5 of the project contract: *nothing leaves the device without an explicit,
per-item policy. Default deny.* This module holds those decisions.

A policy is keyed by **host**, not by feature. "Wikipedia may be searched" is a
statement the user can understand and audit; "the discovery runtime is enabled"
is not, because it does not say where anything goes. Keying on host also means a
new provider pointed at an already-approved host inherits the existing decision
rather than silently acquiring a new one — and a new provider pointed somewhere
new is denied until the user says otherwise, which is the behaviour Rule 5 asks
for.

Three modes:

``DENY``
    Nothing goes. This is what an unknown host gets.
``ASK``
    The user is shown the literal text about to leave and chooses. The contract
    calls confirm-before-send "a headline feature, not an option", so this is
    the mode a host should normally be promoted *to* when first approved.
``ALLOW``
    Goes without asking. Still logged — Rule 3 is not conditional on Rule 5.

Loopback is not covered here at all. A request to 127.0.0.1 never leaves the
machine, so it is not egress and there is nothing for a policy to govern. The
gate classifies that before it consults policy.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from enum import Enum


class Mode(str, Enum):
    DENY = "deny"
    ASK = "ask"
    ALLOW = "allow"


@dataclass(frozen=True)
class Decision:
    mode: Mode
    #: Plain-language reason, shown to the user and written to the log. The
    #: contract asks for routing decisions in plain language; this is that.
    reason: str


#: What an unknown host gets. Named rather than inlined so the default is
#: greppable and a change to it is visible in a diff.
DEFAULT_DECISION = Decision(
    Mode.DENY,
    "no policy exists for this destination, and the default is to refuse",
)

#: What every host gets while the kill switch is on.
#:
#: Phrased as something the user did, because they did it, and because a
#: blocked request needs to be distinguishable at a glance from one blocked by
#: an ordinary rule — otherwise the log reads as a fault and the fix is
#: un-findable.
KILL_SWITCH_DECISION = Decision(
    Mode.DENY,
    "the kill switch is on, so nothing may leave this device",
)


class EgressPolicy:
    """Host → mode, persisted as JSON next to the egress log.

    JSON rather than SQLite because this file is something a user might
    reasonably want to read, diff or check into their own backup. It is small,
    it is theirs, and its legibility is worth more than query performance on a
    table that will hold tens of rows.
    """

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._rules: dict[str, Mode] = {}
        #: One switch that denies everything, whatever the per-host rules say.
        #:
        #: It lives *here* rather than in the API layer or the chat path so
        #: that it covers every caller of :meth:`decide` — tool traffic, model
        #: discovery, an update check somebody adds next year. A kill switch
        #: enforced at one call site is a kill switch for that call site, and
        #: the whole value of the control is that the user does not have to
        #: know how many outbound paths exist.
        #:
        #: It also cannot be worked around by allowing a host, which is the
        #: property that makes it worth having beside a per-host policy: it is
        #: a single action whose effect the user can state without reading a
        #: rule list.
        self._kill_switch = False
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self._rules = {
                host: Mode(mode)
                for host, mode in (raw.get("hosts") or {}).items()
                if mode in {m.value for m in Mode}
            }
            # Persisted, because a kill switch that forgets itself on restart
            # is worse than none: the user believes the machine is sealed and
            # it is not. Read defensively — anything that is not exactly `true`
            # leaves it off, so a hand-edited file cannot silently seal the app
            # either.
            self._kill_switch = raw.get("kill_switch") is True
        except Exception:
            # A corrupt policy file must not fail open. Falling back to an empty
            # rule set means every host is unknown, and every unknown host is
            # denied — the safe direction to fail in.
            self._rules = {}

    def _save(self) -> None:
        tmp = self._path + ".tmp"
        parent = os.path.dirname(os.path.abspath(self._path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "hosts": {h: m.value for h, m in sorted(self._rules.items())},
                    "kill_switch": self._kill_switch,
                },
                f,
                indent=2,
            )
        os.replace(tmp, self._path)

    # ------------------------------------------------------------------ read

    def kill_switch(self) -> bool:
        """Whether everything outbound is currently refused."""
        return self._kill_switch

    def decide(self, host: str) -> Decision:
        """What should happen to a request addressed to ``host``."""
        # First, and before the rules are consulted at all. An `allow` rule
        # must not survive the switch, or "cut all outbound traffic" would mean
        # "cut the traffic you had not already permitted", which is not what
        # the words say and not what someone reaching for it wants.
        if self._kill_switch:
            return KILL_SWITCH_DECISION

        mode = self._rules.get(host.lower())
        if mode is None:
            return DEFAULT_DECISION
        if mode is Mode.ALLOW:
            return Decision(Mode.ALLOW, f"you allowed requests to {host}")
        if mode is Mode.ASK:
            return Decision(Mode.ASK, f"you asked to confirm each request to {host}")
        return Decision(Mode.DENY, f"you blocked requests to {host}")

    def rules(self) -> dict[str, str]:
        """Every rule, for the privacy pane."""
        with self._lock:
            return {h: m.value for h, m in sorted(self._rules.items())}

    # ----------------------------------------------------------------- write

    def set_kill_switch(self, on: bool) -> bool:
        """Turn the master refusal on or off. Returns the new state.

        Turning it *off* restores the per-host rules exactly as they were —
        nothing is forgotten. That matters because the alternative design,
        clearing the rules, would make the switch a destructive action wearing
        the costume of a toggle, and someone would lose their allow-list by
        being careful.
        """
        with self._lock:
            self._kill_switch = bool(on)
            self._save()
        return self._kill_switch

    def set(self, host: str, mode: Mode | str) -> None:
        with self._lock:
            self._rules[host.lower()] = Mode(mode)
            self._save()

    def forget(self, host: str) -> None:
        """Remove a rule. The host reverts to the default, which is deny."""
        with self._lock:
            self._rules.pop(host.lower(), None)
            self._save()
