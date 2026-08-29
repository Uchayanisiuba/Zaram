"""Per-source egress policy. Default deny.

Rule 5 of the project contract: *nothing leaves the device without an explicit,
per-item policy. Default deny.* This module holds those decisions.

A policy is keyed by **host and data class**, not by feature. "Wikipedia may be
searched" is a statement the user can understand and audit; "the discovery
runtime is enabled" is not, because it does not say where anything goes. Keying
on host also means a new provider pointed at an already-approved host inherits
the existing decision rather than silently acquiring a new one — and a new
provider pointed somewhere new is denied until the user says otherwise, which is
the behaviour Rule 5 asks for.

**The second dimension is rule 7j, and it was missing until 29 August 2026.**
The rule reads *"consent given deliberately for a destination is consent"* and
grants it "per destination **and data class**" — but this module only ever knew
about destinations, so connecting a provider to answer chat questions silently
read as permission to send it anything at all. `CLAUDE.md` is explicit about why
that is wrong: a chat message is a couple of kilobytes and a photograph is a few
megabytes of something far more personal, so *"connecting a provider for text is
not consent to send it a photograph."*

`RoutedEngine` had been refusing every image bound for the cloud outright, with
a comment saying the question was not being asked yet. This is that question,
asked once per destination and then remembered — which is the other half of 7j,
the half that stops confirm-before-send becoming forty dialogs a day.

**Inheritance runs one way only.** A plain host rule covers `PROMPT` and nothing
else. Every other class must be granted for that host in its own right, and a
broader permission never implies a narrower, more sensitive one. That asymmetry
is the whole point — see ``_INHERITS_HOST_RULE``.

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


class DataClass(str, Enum):
    """*What kind of thing* is leaving, as distinct from where it is going.

    Three, and each is named in `CLAUDE.md` rather than invented here. Adding a
    fourth is a decision about consent, not a refactor: every new member is a
    question some user will have to answer, so the bar is that the rule text
    already distinguishes it.

    ``PROMPT``
        The ordinary case — a chat message, a search query, a model discovery
        call. Kilobytes of text the user just typed or asked for.
    ``IMAGE``
        A picture. Megabytes, far more personal, and its own consent class
        under rule 7j by name.
    ``SPINE``
        Facts recalled from the user's own knowledge base. `CLAUDE.md` keeps a
        hard stop here — *"the first time facts recalled from the Spine go to a
        destination that has not had them before"* — and a class is what makes
        that expressible rather than aspirational.
    """

    PROMPT = "prompt"
    IMAGE = "image"
    SPINE = "spine"


#: Classes a plain host rule covers. Exactly one, and the fact that it is a set
#: rather than an ``if`` is the point: adding a member is a visible, reviewable
#: widening of what "I connected this provider" is taken to mean.
#:
#: `PROMPT` inherits because that *is* what connecting a provider was for — rule
#: 7j says asking a second time for the thing the user just deliberately set up
#: "reads as the product being broken". Nothing else inherits, because a
#: broader consent must never imply a narrower and more sensitive one. That is
#: the same shape as the residency relaxation in `ProviderManager`: the
#: permission filter is the one thing that never loosens.
_INHERITS_HOST_RULE: frozenset["DataClass"] = frozenset({DataClass.PROMPT})


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


def _needs_own_grant(host: str, data_class: "DataClass") -> Decision:
    """A host the user approved, for a class they have not approved for it.

    The wording matters more than usual. "Blocked" would be wrong — nobody
    blocked anything — and a bare default-deny reason would send the user
    looking for a rule that does not exist. This says which permission is
    missing and implies the shape of the fix, because the user *has* already
    made a decision about this destination and is entitled to know that the
    refusal is about the cargo rather than the address.
    """
    return Decision(
        Mode.DENY,
        f"you allowed requests to {host}, but not {data_class.value} — "
        f"that is a separate decision and has not been made",
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
        #: host → class → mode, for the classes a host rule does not speak for.
        #: Separate from `_rules` rather than folded into it so that an
        #: existing policy file stays valid and keeps meaning exactly what it
        #: meant: permission for chat, and for nothing else.
        self._class_rules: dict[str, dict[DataClass, Mode]] = {}
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
            # Read defensively, member by member. An unknown class name in a
            # hand-edited or newer file is skipped rather than raising, because
            # the `except` below falls back to *no rules at all* — safe for the
            # request and terrible for the user, who would silently lose every
            # decision they had made.
            self._class_rules = {}
            for host, by_class in (raw.get("classes") or {}).items():
                if not isinstance(by_class, dict):
                    continue
                kept = {
                    DataClass(c): Mode(m)
                    for c, m in by_class.items()
                    if c in {d.value for d in DataClass}
                    and m in {mo.value for mo in Mode}
                }
                if kept:
                    self._class_rules[host] = kept
            self._kill_switch = raw.get("kill_switch") is True
        except Exception:
            # A corrupt policy file must not fail open. Falling back to an empty
            # rule set means every host is unknown, and every unknown host is
            # denied — the safe direction to fail in.
            self._rules = {}
            self._class_rules = {}

    def _save(self) -> None:
        tmp = self._path + ".tmp"
        parent = os.path.dirname(os.path.abspath(self._path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "hosts": {h: m.value for h, m in sorted(self._rules.items())},
                    "classes": {
                        h: {c.value: m.value for c, m in sorted(by_class.items())}
                        for h, by_class in sorted(self._class_rules.items())
                        if by_class
                    },
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

    def decide(
        self, host: str, data_class: DataClass = DataClass.PROMPT
    ) -> Decision:
        """What should happen to a request addressed to ``host``.

        ``data_class`` defaults to ``PROMPT`` so every existing caller keeps its
        behaviour exactly. That default is deliberate and is also the only safe
        direction for one: a caller that forgets to say what it is sending is
        treated as sending the *least* sensitive thing, and the classes that
        matter are the ones a caller has to name on purpose. A default of "the
        most sensitive" would be safer in the abstract and would in practice
        deny the ordinary chat path, which nobody would ship.
        """
        # First, and before the rules are consulted at all. An `allow` rule
        # must not survive the switch, or "cut all outbound traffic" would mean
        # "cut the traffic you had not already permitted", which is not what
        # the words say and not what someone reaching for it wants.
        if self._kill_switch:
            return KILL_SWITCH_DECISION

        cls = DataClass(data_class)
        host_l = host.lower()

        # An explicit rule for this exact (host, class) wins over everything
        # below it, in both directions: it can permit a class the host rule
        # would not reach, and it can deny one the host rule would.
        mode = self._class_rules.get(host_l, {}).get(cls)
        if mode is not None:
            return self._describe(mode, host, cls)

        host_mode = self._rules.get(host_l)
        if host_mode is None:
            return DEFAULT_DECISION

        # The one-way inheritance. A host rule speaks for `PROMPT` and stays
        # silent about everything else, so a more sensitive class falls through
        # to a refusal that says which decision is missing.
        if cls not in _INHERITS_HOST_RULE:
            if host_mode is Mode.DENY:
                return Decision(Mode.DENY, f"you blocked requests to {host}")
            return _needs_own_grant(host, cls)

        return self._describe(host_mode, host, cls)

    @staticmethod
    def _describe(mode: Mode, host: str, cls: DataClass) -> Decision:
        """One place where a mode becomes a sentence.

        The class is named only when it is not the ordinary one. "You allowed
        requests to api.example.com" is what a person expects to read about
        their chat provider; "you allowed prompt to api.example.com" is the
        same fact in the product's vocabulary rather than theirs.
        """
        what = "requests" if cls in _INHERITS_HOST_RULE else f"{cls.value}s"
        if mode is Mode.ALLOW:
            return Decision(Mode.ALLOW, f"you allowed {what} to {host}")
        if mode is Mode.ASK:
            return Decision(Mode.ASK, f"you asked to confirm each {what[:-1]} to {host}")
        return Decision(Mode.DENY, f"you blocked {what} to {host}")

    def has_rule(
        self, host: str, data_class: DataClass = DataClass.PROMPT
    ) -> bool:
        """Whether the user has expressed an opinion about this host.

        The distinction `decide` cannot make: it collapses "denied because you
        blocked it" and "denied because nobody has said" into the same `DENY`,
        which is right for the request and wrong for anything asking whether a
        *decision* exists. A search-result grant may cover the second and must
        never override the first — a host somebody deliberately blocked stays
        blocked when it turns up in a search result.

        The kill switch is deliberately not consulted. It is a state, not a
        rule about a host, and it is checked ahead of this by `decide`.
        """
        with self._lock:
            host_l = host.lower()
            cls = DataClass(data_class)
            if cls in self._class_rules.get(host_l, {}):
                return True
            # A host rule is an opinion about `PROMPT` and about nothing else,
            # for the same reason `decide` will not let it permit anything
            # else. `SearchReadGrant` leans on this: it may cover a host nobody
            # has an opinion about, and must never cover one they blocked.
            return cls in _INHERITS_HOST_RULE and host_l in self._rules

    def rules(self) -> dict[str, str]:
        """Every host rule, for the privacy pane.

        Unchanged in shape. The per-class rules are a separate accessor rather
        than a nesting of this one, because this return value is already
        rendered by the interface and served over the API, and quietly changing
        a shape that something else parses is how a privacy pane comes to show
        nothing at all.
        """
        with self._lock:
            return {h: m.value for h, m in sorted(self._rules.items())}

    def class_rules(self) -> dict[str, dict[str, str]]:
        """Every per-class rule, host → class → mode."""
        with self._lock:
            return {
                h: {c.value: m.value for c, m in sorted(by_class.items())}
                for h, by_class in sorted(self._class_rules.items())
                if by_class
            }

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

    def set(
        self,
        host: str,
        mode: Mode | str,
        data_class: DataClass = DataClass.PROMPT,
    ) -> None:
        with self._lock:
            cls = DataClass(data_class)
            if cls in _INHERITS_HOST_RULE:
                self._rules[host.lower()] = Mode(mode)
            else:
                self._class_rules.setdefault(host.lower(), {})[cls] = Mode(mode)
            self._save()

    def forget(self, host: str, data_class: DataClass | None = None) -> None:
        """Remove a rule. What is removed reverts to the default, which is deny.

        ``data_class=None`` forgets the host entirely — every class with it.
        That is what "forget this destination" has to mean: leaving an image
        grant behind after the user removed the provider it belonged to would
        be a permission outliving the decision that created it, and it would be
        invisible, because the privacy pane lists the host rule.
        """
        with self._lock:
            host_l = host.lower()
            if data_class is None:
                self._rules.pop(host_l, None)
                self._class_rules.pop(host_l, None)
            elif DataClass(data_class) in _INHERITS_HOST_RULE:
                self._rules.pop(host_l, None)
            else:
                by_class = self._class_rules.get(host_l)
                if by_class:
                    by_class.pop(DataClass(data_class), None)
                    if not by_class:
                        self._class_rules.pop(host_l, None)
            self._save()
