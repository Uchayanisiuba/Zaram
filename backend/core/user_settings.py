"""Settings the *backend* has to honour, persisted as JSON on this machine.

Most of what a settings screen holds is a rendering choice and belongs to the
frontend: theme, whether the orb or the avatar is showing, how dense a list is.
Those live in the browser's own storage and the backend neither knows nor cares.

Two do not, and this module is for those:

* **Which model answers by default.** The frontend used to decide, by sending
  ``model: "gemma3:latest"`` on every message — a name hardcoded in
  ``chatClient.ts`` that no interface control ever changed. That made every
  routing decision the backend reached unobservable, because the request
  overrode it, and it meant a second client (the phone, a browser tab) would
  disagree with the first about what "the model" is. A choice the user made
  once belongs where every client sees the same answer.
* **The routing preference.** `CLAUDE.md`'s second tier of control: *Prefer
  local · Auto · Prefer cloud*, one control in plain language. It biases
  selection; it is not a per-message override, which is tier three and travels
  on the request.

JSON, in the same directory as the egress log and policy, for the same reason
those are: it is small, it is the user's, and rule 7 says the Spine is
exportable in an open format — a settings file nobody can read is a quieter
version of the same lock-in.

**Absent is a valid state and never an error.** A missing or corrupt file
yields defaults, because the alternative is a product that will not start
because of a preference. The defaults are the conservative ones: no chosen
model, which means the provider layer's own vetted selection stands, and
``auto``.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "RoutingPreference",
    "SearchScope",
    "UserSettings",
    "get_user_settings",
    "set_user_settings_path",
]

DEFAULT_FILE_NAME = "settings.json"


class SearchScope(str, Enum):
    """When web search is worth doing, once it is switched on.

    **Search compensates for what the answering model does not know.** A local
    12B has an older, smaller store of facts than a frontier model, so a live
    result changes its answer far more often than it changes a cloud model's.
    That makes locality a genuinely useful signal for whether to search, and
    ``LOCAL_ONLY`` is the default for exactly that reason.

    One honest caveat, recorded because the obvious justification for this is
    wrong: **cloud models do not generally come with web search.** Routed
    through an OpenAI-compatible endpoint they answer from training data with a
    later cutoff, not from the live web. So this setting trades *recency* for
    *latency and noise* — a real trade, and the user's to make — rather than
    avoiding something the cloud provider was going to do anyway.
    """

    #: Search when a local model is answering. The default.
    LOCAL_ONLY = "local_only"
    #: Search whenever the question looks like it needs live information.
    ALWAYS = "always"


class RoutingPreference(str, Enum):
    """How much Zaram should lean on the cloud when nobody has said.

    Three values, not a slider, because `CLAUDE.md` asks for one control in
    plain language for a user who is not technical — and because the difference
    between 0.3 and 0.4 on a bias slider is not a thing anybody can hold an
    opinion about.

    None of these is a permission. ``PREFER_CLOUD`` shifts what gets *ranked*
    first among models the user has already consented to; it cannot promote a
    model whose data policy is unknown, because that gate lives in
    ``ModelInfo.selectable_by_default`` and is not a preference. Rule 5 is not
    something a dropdown can turn off.
    """

    PREFER_LOCAL = "prefer_local"
    AUTO = "auto"
    PREFER_CLOUD = "prefer_cloud"


class UserSettings:
    """The persisted settings, read and written under a lock."""

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._routing = RoutingPreference.AUTO
        self._default_model: Optional[str] = None
        self._web_search = False
        self._search_scope = SearchScope.LOCAL_ONLY
        # The character: what this person calls it, how they want it to write,
        # and which voice speaks. All three are theirs, all three are optional,
        # and none of them can change what Zaram says it is — see
        # `core/identity.py` and `tests/test_identity_stays_truthful.py`.
        self._assistant_name = ""
        self._manner = ""
        self._voice = ""
        self._load()

    # ------------------------------------------------------------------ read

    @property
    def routing_preference(self) -> RoutingPreference:
        return self._routing

    @property
    def web_search(self) -> bool:
        """Whether a question may reach a search engine.

        Off unless the user turned it on, which is rule 5's default deny rather
        than a cautious guess. `CLAUDE.md` sequenced this deliberately — *egress
        log → per-source policy → web search as its first governed source* —
        because bytes cannot be logged retroactively. Both of those exist and
        are user-visible, which is what makes this switch offerable at all.

        **On is not a licence.** The per-host policy still decides, and its
        default is refuse, so turning this on and asking a question produces a
        refusal until the search engine's host has a rule. That is the "first
        governed source" working as intended and not a bug — search gets no
        exemption the user has not granted it by name.
        """
        return self._web_search

    @property
    def default_model(self) -> Optional[str]:
        """The model the user chose, or ``None`` for "let Zaram decide".

        ``None`` is not "no model" — it is the provider layer's
        ``select_default_model``, which applies the data-policy and VRAM gates.
        Storing an explicit name here bypasses the *ranking*, never the gates.
        """
        return self._default_model

    @property
    def assistant_name(self) -> str:
        """What this person calls it. Empty means "Zaram", which is not a name
        they chose but the product's own — the difference matters to the
        interface, which offers to name it only while this is empty."""
        return self._assistant_name

    @property
    def manner(self) -> str:
        """How they want it to write. Style only; see `core/identity.py`."""
        return self._manner

    @property
    def voice(self) -> str:
        """A Kokoro voice id, or empty for the shipped default.

        Not validated here. The installed voice pack is the authority on which
        ids exist, `/voice/voices` is where that is read, and a settings file
        that refuses to load because a voice was uninstalled would be a
        cosmetic choice breaking the whole product.
        """
        return self._voice

    def to_dict(self) -> Dict[str, Any]:
        return {
            "routing_preference": self._routing.value,
            "default_model": self._default_model,
            "web_search": self._web_search,
            "search_scope": self._search_scope.value,
            "assistant_name": self._assistant_name,
            "manner": self._manner,
            "voice": self._voice,
        }

    # ----------------------------------------------------------------- write

    def set_routing_preference(self, value: RoutingPreference | str) -> RoutingPreference:
        with self._lock:
            self._routing = RoutingPreference(value)
            self._save()
        return self._routing

    @property
    def search_scope(self) -> SearchScope:
        """Whether search runs for every model or only for local ones."""
        return self._search_scope

    def set_search_scope(self, value: "SearchScope | str") -> SearchScope:
        with self._lock:
            self._search_scope = SearchScope(value)
            self._save()
        return self._search_scope

    def set_web_search(self, on: bool) -> bool:
        """Turn web search on or off. Returns the new state."""
        with self._lock:
            self._web_search = bool(on)
            self._save()
        return self._web_search

    def set_default_model(self, model: Optional[str]) -> Optional[str]:
        """Choose the model, or pass ``None`` to hand the choice back to Zaram.

        An empty string is treated as ``None`` rather than stored, because a
        cleared text field and "no preference" are the same intention and
        storing ``""`` would produce a request for a model with no name.
        """
        cleaned = (model or "").strip() or None
        with self._lock:
            self._default_model = cleaned
            self._save()
        return self._default_model

    def set_character(
        self,
        *,
        assistant_name: Optional[str] = None,
        manner: Optional[str] = None,
        voice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set any of the three. ``None`` leaves a field alone.

        One writer for all three because they are one thing to the user — a
        character — and three endpoints would let an interface save two of them
        and fail on the third, leaving a half-applied character nobody chose.

        Bounds are applied on the way in as well as at the prompt, so an
        oversized value never reaches disk. `identity_preamble` still bounds
        them independently: this store is not the only path to that function,
        and a guarantee enforced at one call site is a guarantee for that call
        site.
        """
        from core.identity import MAX_MANNER_CHARS, MAX_NAME_CHARS

        with self._lock:
            if assistant_name is not None:
                self._assistant_name = " ".join(assistant_name.split())[:MAX_NAME_CHARS]
            if manner is not None:
                self._manner = " ".join(manner.split())[:MAX_MANNER_CHARS]
            if voice is not None:
                self._voice = voice.strip()[:64]
            self._save()
        return {
            "assistant_name": self._assistant_name,
            "manner": self._manner,
            "voice": self._voice,
        }

    # -------------------------------------------------------------- internals

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            logger.warning("settings file unreadable, using defaults", exc_info=True)
            return

        value = raw.get("routing_preference")
        if value in {p.value for p in RoutingPreference}:
            self._routing = RoutingPreference(value)
        # Anything else is left at the default rather than raising: a
        # preference file written by a newer version must not stop an older one
        # from starting.

        model = raw.get("default_model")
        self._default_model = model.strip() or None if isinstance(model, str) else None

        # Read strictly: only an exact `true` turns it on. Anything else — a
        # truthy string, a 1, a value written by a newer version — leaves it
        # off, so a file this version does not fully understand cannot open a
        # path to the internet that the user did not open.
        self._web_search = raw.get("web_search") is True

        scope = raw.get("search_scope")
        if scope in {s.value for s in SearchScope}:
            self._search_scope = SearchScope(scope)

        # The character. Read defensively and bounded on the way in: a settings
        # file is a file, a character is meant to travel as one, and the day
        # somebody imports a stranger's character is the day this parses hostile
        # input. Anything that is not a string is ignored rather than coerced.
        from core.identity import MAX_MANNER_CHARS, MAX_NAME_CHARS

        name = raw.get("assistant_name")
        if isinstance(name, str):
            self._assistant_name = " ".join(name.split())[:MAX_NAME_CHARS]

        manner = raw.get("manner")
        if isinstance(manner, str):
            self._manner = " ".join(manner.split())[:MAX_MANNER_CHARS]

        voice = raw.get("voice")
        if isinstance(voice, str):
            self._voice = voice.strip()[:64]

    def _save(self) -> None:
        tmp = self._path + ".tmp"
        parent = os.path.dirname(os.path.abspath(self._path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        os.replace(tmp, self._path)


def default_settings_path() -> str:
    """Beside the egress policy, and overridable the same way it is.

    Derived from ``default_policy_path`` rather than recomputed, so a test or a
    packaged build that redirects one redirects both. Two modules independently
    working out "the data directory" is how they come to disagree about it.
    """
    from core.egress.runtime import default_policy_path

    return os.environ.get(
        "ZARAM_SETTINGS",
        os.path.join(os.path.dirname(os.path.abspath(default_policy_path())), DEFAULT_FILE_NAME),
    )


_settings: Optional[UserSettings] = None
_settings_path: Optional[str] = None


def set_user_settings_path(path: str) -> None:
    """Point the singleton at a file. Called by tests and by the bootstrap."""
    global _settings, _settings_path
    _settings_path = path
    _settings = None


def get_user_settings() -> UserSettings:
    """The process-wide settings.

    A singleton, matching ``get_gate()`` next door, because the alternative is
    threading a settings object through the provider manager, the chat route
    and the models runtime — three layers that have no other reason to know
    about each other.
    """
    global _settings
    if _settings is None:
        path = _settings_path or default_settings_path()
        _settings = UserSettings(path)
    return _settings
