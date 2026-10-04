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
* **Which model answers a particular *kind* of request.** `CLAUDE.md`'s third
  tier of control, and the more specific half of the one above: a coding
  question can be sent to a coding model without that model answering
  everything else. See `TaskSlot` for why there are two slots rather than the
  four a settings screen might suggest.
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
    "TaskSlot",
    "UserSettings",
    "get_user_settings",
    "set_user_settings_path",
]

DEFAULT_FILE_NAME = "settings.json"


#: The largest context window Zaram will ask a local server for.
#:
#: Not a model limit — a guard on a number that costs VRAM quadratically
#: in the wrong direction. 131,072 covers any document somebody is
#: realistically working on; past that the KV cache is the thing using the
#: card, not the model.
MAX_CONTEXT_TOKENS = 131_072

#: How a local model's context window is decided.
#:
#: ``fit`` - as much as this model and this card allow, worked out per
#: model. The default, and the whole point: nothing to re-pick when the
#: model changes.
#: ``server`` - send no ``num_ctx`` at all. Not a limit somebody sets; an
#: **off switch for the feature**, for the case where Zaram's arithmetic
#: is wrong in a way it cannot detect - a quantised KV cache halves the
#: per-token cost this module assumes, and nothing in `model_info` says
#: so.
#:
#: **``fixed`` was removed the day after it was added**, on the
#: maintainer's question: *"if this is true do we still need the token
#: limit options in the settings, perhaps we should remove it."* It
#: honoured one typed number for every model, which is precisely the
#: chore `fit` exists to end - a figure right for the model it was chosen
#: for and wrong for every other. It was also the only branch that
#: skipped the declared-ceiling cap, and shipped asking a model declaring
#: 40,960 for 131,072. A mode with no use `fit` does not cover, and a bug
#: history, is not a setting worth keeping for symmetry.
#:
#: An older file naming it fails this check and resolves to ``fit``,
#: which is the migration.
CONTEXT_POLICIES = frozenset({"fit", "server"})

#: What happens when a conversation outgrows the window.
#:
#: ``trim`` - drop the oldest whole turns and say so, which is what Zaram
#: has always done and is the right default: a long conversation keeps
#: working, and the drop is announced rather than silent.
#: ``stop`` - refuse the turn instead, and say the conversation has
#: outgrown this model.
#:
#: **`stop` is not pedantry, it is rule 9 applied to memory.** Trimming
#: is safe for chat, where the recent end is what matters. It is not safe
#: for an answer grounded in something said at the start -- a document
#: pasted an hour ago, a constraint agreed in the first message. The
#: model does not know what was cut, so it answers confidently from a
#: premise that is no longer there, and *"generation must fail rather
#: than invent"* is the rule that covers exactly this.
OVERFLOW_POLICIES = frozenset({"trim", "stop"})

#: The fields a local model server's settings may carry, and nothing else.
#:
#: `auto_start` is whether Zaram starts the server when it opens. `path` is
#: where the person installed it, for when it is not where Zaram looks, and
#: `python` is the interpreter it runs under, for servers that are run from a
#: checkout. Anything else in a file is dropped on the way in: these values are
#: later *executed*, so the set of things that can reach that path is closed.
MODEL_SERVER_FIELDS = frozenset({"auto_start", "path", "python"})

#: A bound on how many servers a settings file can describe. Not a limit anyone
#: reaches by choosing -- it bounds what a hand-edited file can make this.
MAX_MODEL_SERVERS = 16
MAX_MODEL_SERVER_PATH = 500

#: A cap on remembered per-model windows. Not a limit anybody will reach by
#: choosing - it bounds what a settings *file* can make this dictionary,
#: for the reason the character fields are bounded.
MAX_CONTEXT_OVERRIDES = 200


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


class TaskSlot(str, Enum):
    """The kinds of request a user may allocate a model to by hand.

    `CLAUDE.md`'s **third** tier of control — *"per-task assignment — chat,
    coding, vision, long-document — behind Advanced"*. Tier one is Zaram
    deciding, tier two is `RoutingPreference`.

    **There is a slot for every distinction the router actually makes, and no
    others.** That is not tidiness, it is the *never render invented values*
    rule applied to a control rather than to a readout: a "long documents" row
    would be a dropdown a person could set, that would then govern nothing,
    because nothing in `core.planner` classifies document length and no
    argument to `ProviderManager.select_model_for_task` carries it. A control
    over a decision the system does not take is worse than no control, because
    the user believes they have configured something.

    So there are exactly three, and each one is an argument the selection
    call already takes:

    * ``CODE`` is ``specialisation="code"``. Its value is deliberately the
      string `INTENT_SPECIALISATION` maps `IntentType.CODE` to — one table
      decides what a coding question is, and a second spelling here is how the
      slot would come to be assigned and never consulted.
    * ``VISION`` is ``requires_vision=True``.
    * ``DOCUMENT`` is ``specialisation="document"``, added 14 September 2026
      when `INTENT_SPECIALISATION` gained `IntentType.DOCUMENT`. The
      "long documents" row the paragraph above refused is still refused —
      nothing classifies length — but *a document request* is classified,
      it is the one job where the strongest model is worth the wait, and
      the maintainer asked for documents to be better. The slot exists
      because the router consults it, which is the only reason a slot may.

    **Chat is not a slot, and that is the point.** ``default_model`` above
    already *is* the model for a request with no task, which is what chat is.
    A second field meaning the same thing would be two sources of truth for
    one answer, and the interface would have to invent a rule for which wins.

    Drawing an image is not a slot either, for the reason the long-document row
    is not one: ``requires_image_output`` is a gate `select_model_for_task`
    implements and **nothing in the running product passes**, so a row for it
    would configure a code path that does not execute.
    """

    #: A coding question. Matches `core.planner.INTENT_SPECIALISATION`'s value.
    CODE = "code"
    #: A question about a picture — attached, or described in the wording.
    VISION = "vision"
    #: "Write that up as a proposal." Matches `INTENT_SPECIALISATION`'s value.
    DOCUMENT = "document"


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


class ImageLocality(Enum):
    """Where pictures are drawn first — the one the user chose.

    Two values and no third, because there are only two places a picture can
    be drawn and the setting is which to *try first*: the other is always the
    fallback, and the runtime says which one answered. ``LOCAL`` loads Flux
    onto the card; ``CLOUD`` never does, which is the whole reason the
    maintainer asked for it on 14 September 2026 — a picture now and then
    should not cost the VRAM the chat model is sitting in.

    Not a permission. A cloud provider still needs its key and its image
    grant; this cannot send a picture anywhere the user has not allowed.
    """

    LOCAL = "local"
    CLOUD = "cloud"


class UserSettings:
    """The persisted settings, read and written under a lock."""

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._routing = RoutingPreference.AUTO
        self._default_model: Optional[str] = None
        #: `TaskSlot` value → model name. Absent keys mean "not assigned",
        #: which is not the same as "no model": an unassigned slot falls
        #: through to `default_model` and then to Zaram's own pick, exactly as
        #: every request did before this field existed.
        self._task_models: Dict[str, str] = {}
        #: The embedding model that decides where a question goes. `None` means
        #: whatever the Spine is using — see `router_model`.
        self._router_model: Optional[str] = None
        self._web_search = False
        self._search_scope = SearchScope.LOCAL_ONLY
        # The character: what this person calls it, how they want it to write,
        # and which voice speaks. All three are theirs, all three are optional,
        # and none of them can change what Zaram says it is — see
        # `core/identity.py` and `tests/test_identity_stays_truthful.py`.
        self._assistant_name = ""
        #: How much context to ask a local model for, in tokens, or ``0``
        #: for whatever the server does by default.
        #:
        #: **This exists because the maintainer had to use another tool to
        #: change it** — 4 October 2026. Ollama serves a default `num_ctx`
        #: regardless of what a model advertises, measured on this machine
        #: at 4,096 for a model reporting a 262,144-token maximum, and the
        #: only way to raise it was a Modelfile. Zaram could *read* the
        #: loaded window (`core/context_budget.py`) and could not set it.
        #:
        #: **How the window is decided, rather than what it is.** Revised
        #: 4 October 2026 from one sentence: *"I don't want users to need
        #: to switch token limits every time they switch or download a new
        #: model."* A single number cannot be right for two models - the
        #: binding constraint is the card, not the model's limit, and
        #: measured on the maintainer's machine `qwen3-14b-16k` costs
        #: 160 KiB per cached token, so 128k of it is 21.5 GB on a 12 GB
        #: card. So the stored value is an intent and
        #: `context_budget.resolve_context_window` works out the figure per
        #: model, per launch.
        #:
        #: `fit` is the default and the reason this is not a chore:
        #: as much as this model and this card allow, recomputed whenever
        #: either changes, with nothing to re-pick.
        self._context_policy = "fit"
        #: A number somebody set **for one model**, keyed by model name.
        #: Global was the bug: one figure is wrong for every model but the
        #: one it was chosen for, which is what made this a chore.
        self._context_overrides: Dict[str, int] = {}
        #: See `OVERFLOW_POLICIES`. `trim` is what Zaram did before there
        #: was a choice, so it stays the default.
        self._overflow_policy = "trim"
        #: Local model servers Zaram may start, by id -> `MODEL_SERVER_FIELDS`.
        #: Empty means *every server is on its defaults*, and the default is to
        #: start one that is installed and not running -- see
        #: `providers/model_servers.py` for why that is the default.
        self._model_servers: Dict[str, Dict[str, Any]] = {}
        #: The longest a single reply may run, or ``0`` for *as much as
        #: the window reserves*.
        #:
        #: **Separate from the context window, and the pair is easy to
        #: confuse.** The window is the whole pool - prompt, history and
        #: reply together. This is a ceiling on the reply alone, and a
        #: small one cuts a model off mid-sentence however much room is
        #: left. LM Studio keeps them as two controls for that reason and
        #: so does this.
        #:
        #: ``0`` rather than a number, because Zaram already reserves a
        #: quarter of the window for the reply. A default here would
        #: compete with an arithmetic that is already right.
        self._max_reply_tokens = 0
        self._manner = ""
        self._voice = ""
        # Local first, as everything is: CLAUDE.md's "local is the fallback
        # for everything" is also its default. The person flips it.
        self._image_locality = ImageLocality.LOCAL
        #: Which installed pipeline draws, by folder name. ``None`` means "the
        #: first usable one", which is what every machine with exactly one
        #: model wants and what nobody should have to choose.
        self._image_model: Optional[str] = None
        # Whether a model that can think is asked to. On by default, because
        # the thinking is where a 27B earns its keep on a hard question; off
        # is for the person writing an email who does not want to wait 10–40 s
        # for it. `docs/PLAN.md` E2b. Applied by the local engines — Ollama's
        # `think` and TabbyAPI's `enable_thinking` — and left alone for cloud
        # providers, whose controls differ per vendor and are not guessed at.
        self._thinking = True
        self._load()

    @property
    def thinking(self) -> bool:
        """Whether a thinking model is asked to think. Read at request time by
        the local engines."""
        return self._thinking

    def set_thinking(self, on: bool) -> bool:
        with self._lock:
            self._thinking = bool(on)
            self._save()
        return self._thinking

    @property
    def image_locality(self) -> ImageLocality:
        return self._image_locality

    def set_image_locality(self, value: "ImageLocality | str") -> ImageLocality:
        with self._lock:
            self._image_locality = ImageLocality(value)
            self._save()
        return self._image_locality

    @property
    def image_model(self) -> Optional[str]:
        return self._image_model

    def set_image_model(self, name: Optional[str]) -> Optional[str]:
        """Which installed pipeline draws, by folder name, or ``None`` for
        whichever is first.

        **Not validated against what is installed here.** A name is checked at
        the moment it is used, by `find_model`, which falls back when the
        folder has gone. Validating at write time would refuse a model on a
        removable drive that happens to be unplugged, and would make the
        setting a worse record of what the person actually chose.
        """
        cleaned = (name or "").strip() or None
        with self._lock:
            self._image_model = cleaned
            self._save()
        return self._image_model

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
    def router_model(self) -> Optional[str]:
        """The model that decides where a question goes, or ``None`` for the
        one Zaram picks.

        **This is an embedding model, and naming it "the planner" would be the
        product's own misunderstanding written into a setting.** `CLAUDE.md` is
        explicit — *"Route with embeddings, not a generative model. Task
        classification is a similarity problem: embed the query, compare
        against task exemplars, take the nearest"* — and that is what runs:
        `SemanticIntentRouter` over `SemanticIndex`, built in
        `core/bootstrapper.py` from whichever embedder the Spine is using.
        Nothing generative plans anything, so a slot offering a chat model for
        it would be a control over a code path that does not execute.

        What it *is* is the thing the user was asking about: the model that
        decides, under Auto, where a question goes. Until now it was an
        environment variable and appeared in no interface at all, which is the
        opposite failure — a real decision, taken on every message, that the
        product never showed anybody.

        **It takes effect on restart, and the interface has to say so.** The
        embedder is constructed once during boot and handed to the Spine; a
        setting that silently applied to nothing until the next launch would be
        indistinguishable from one that does not work.
        """
        return self._router_model

    def set_router_model(self, model: Optional[str]) -> Optional[str]:
        """Choose it, or pass ``None``/``""`` to hand the choice back.

        Not validated here. This module has no catalogue and loads before
        discovery has run; the endpoint refuses a model that cannot embed,
        which is where the catalogue lives.
        """
        cleaned = (model or "").strip() or None
        with self._lock:
            self._router_model = cleaned
            self._save()
        return self._router_model

    @property
    def task_models(self) -> Dict[str, str]:
        """The per-task assignments, as a copy.

        A copy rather than the dictionary itself, because a caller that mutated
        it would change routing without the file on disk ever being written —
        a setting that survives until restart and then silently reverts, which
        is indistinguishable from Zaram forgetting.

        **Empty is the normal state and the one that must stay free.** The chat
        path only classifies a message when this has something in it, so a user
        who never opens Advanced pays nothing for the feature existing.
        """
        return dict(self._task_models)

    def model_for_task(self, slot: "TaskSlot | str") -> Optional[str]:
        """The model assigned to ``slot``, or ``None``.

        An unknown slot answers ``None`` rather than raising: this is read on
        the path to an answer, and a settings lookup must never be able to cost
        the user their reply.
        """
        try:
            key = TaskSlot(slot).value
        except ValueError:
            return None
        return self._task_models.get(key)

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
            "task_models": dict(self._task_models),
            "router_model": self._router_model,
            "web_search": self._web_search,
            "search_scope": self._search_scope.value,
            "assistant_name": self._assistant_name,
            "manner": self._manner,
            "voice": self._voice,
            "image_locality": self._image_locality.value,
            "image_model": self._image_model,
            "thinking": self._thinking,
            "context_policy": self._context_policy,
            "context_overrides": dict(self._context_overrides),
            "overflow_policy": self._overflow_policy,
            "model_servers": {k: dict(v) for k, v in self._model_servers.items()},
            "overflow_policies": sorted(OVERFLOW_POLICIES),
            "max_reply_tokens": self._max_reply_tokens,
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

    def set_task_model(
        self, slot: "TaskSlot | str", model: Optional[str]
    ) -> Dict[str, str]:
        """Assign a model to one task, or clear it. Returns every assignment.

        An empty string or ``None`` **removes** the key rather than storing a
        blank, for the same reason `set_default_model` does: a cleared field
        and "no preference" are one intention, and a stored ``""`` would become
        a request for a model with no name.

        Raises ``ValueError`` for a slot that is not a `TaskSlot`. This one
        *does* raise where `model_for_task` does not, and the asymmetry is
        deliberate: a bad write is a caller bug worth surfacing at the API
        boundary, while a bad read sits on the path to an answer.

        **Nothing here checks that the model can do the job**, and that is not
        an oversight. This module has no catalogue and must load before
        discovery has run; the capability precondition is enforced where the
        catalogue lives — at the endpoint on the way in, and by
        `_vision_refusal` on the way out, which already refuses a model that
        cannot see when a picture is attached no matter how it was chosen.
        """
        key = TaskSlot(slot).value
        cleaned = (model or "").strip()
        with self._lock:
            if cleaned:
                self._task_models[key] = cleaned
            else:
                self._task_models.pop(key, None)
            self._save()
        return dict(self._task_models)

    def set_context_policy(self, value: str) -> str:
        """How the window is decided. Anything unrecognised is ``fit``.

        Unrecognised resolves to the default rather than raising, which is
        the posture every reader of this file keeps: a settings value that
        will not parse must not be able to stop a model answering.
        """
        with self._lock:
            self._context_policy = value if value in CONTEXT_POLICIES else "fit"
            self._save()
        return self._context_policy

    def model_server(self, server_id: str) -> Dict[str, Any]:
        """One server's settings, or ``{}`` for a server on its defaults."""
        with self._lock:
            return dict(self._model_servers.get(server_id, {}))

    def set_model_server(
        self,
        server_id: str,
        *,
        auto_start: Optional[bool] = None,
        path: Optional[str] = None,
        python: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Change one server's settings; ``None`` leaves a field alone.

        An empty string for ``path`` or ``python`` clears it, which is what
        emptying the box means to the person doing it. The id is not
        validated here -- the store does not know which servers exist -- but
        whatever is stored can only be one of `MODEL_SERVER_FIELDS`.
        """
        rid = (server_id or "").strip()
        if not rid or len(rid) > 40:
            return {}
        with self._lock:
            entry = dict(self._model_servers.get(rid, {}))
            if auto_start is not None:
                entry["auto_start"] = bool(auto_start)
            for name, value in (("path", path), ("python", python)):
                if value is None:
                    continue
                value = value.strip()[:MAX_MODEL_SERVER_PATH]
                if value:
                    entry[name] = value
                else:
                    entry.pop(name, None)
            if entry:
                if rid not in self._model_servers and len(self._model_servers) >= MAX_MODEL_SERVERS:
                    return {}
                self._model_servers[rid] = entry
            else:
                self._model_servers.pop(rid, None)
            self._save()
            return dict(entry)

    def set_overflow_policy(self, value: str) -> str:
        """What to do when the conversation outgrows the window.

        Anything unrecognised resolves to ``trim``, the posture every
        reader here keeps: a settings value that will not parse must not
        be able to stop a model answering.
        """
        with self._lock:
            self._overflow_policy = value if value in OVERFLOW_POLICIES else "trim"
            self._save()
        return self._overflow_policy

    def set_max_reply_tokens(self, value: int) -> int:
        """The longest a single reply may run. ``0`` lifts the cap.

        Bounded by the same ceiling a context window is, which is
        generous rather than meaningful here - a reply cannot exceed the
        window it is generated inside, and the engine clamps it to what
        the window actually reserves. This only stops a hand-edited file
        asking for something absurd.
        """
        with self._lock:
            self._max_reply_tokens = max(0, min(int(value), MAX_CONTEXT_TOKENS))
            self._save()
        return self._max_reply_tokens

    def set_context_override(self, model: str, tokens: int) -> Dict[str, int]:
        """Remember a window **for one model**, or forget it.

        ``0`` removes the entry rather than storing a zero, so "no opinion
        about this model" and "this model should use the server default"
        stay different things - the first falls through to the policy and
        the second is `set_context_policy("server")`.
        """
        name = (model or "").strip()
        if not name:
            return dict(self._context_overrides)
        with self._lock:
            if tokens and tokens > 0:
                if (
                    name not in self._context_overrides
                    and len(self._context_overrides) >= MAX_CONTEXT_OVERRIDES
                ):
                    return dict(self._context_overrides)
                self._context_overrides[name] = min(int(tokens), MAX_CONTEXT_TOKENS)
            else:
                self._context_overrides.pop(name, None)
            self._save()
        return dict(self._context_overrides)

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

        where = raw.get("image_locality")
        if where in {p.value for p in ImageLocality}:
            self._image_locality = ImageLocality(where)

        drawer = raw.get("image_model")
        if isinstance(drawer, str) and drawer.strip():
            self._image_model = drawer.strip()
        # Anything else is left at the default rather than raising: a
        # preference file written by a newer version must not stop an older one
        # from starting.

        model = raw.get("default_model")
        self._default_model = model.strip() or None if isinstance(model, str) else None

        # Per-task assignments. Read key by key against the enum rather than
        # taken wholesale, so a file written by a newer version — or by hand —
        # contributes the slots this build understands and silently drops the
        # rest. Taking the dictionary as it stands would let an unknown key
        # reach `task_models`, where the chat path's "is anything assigned?"
        # guard would read it as yes and start classifying every message to
        # consult a slot that can never match.
        router = raw.get("router_model")
        self._router_model = router.strip() or None if isinstance(router, str) else None

        tasks = raw.get("task_models")
        if isinstance(tasks, dict):
            known = {s.value for s in TaskSlot}
            for key, value in tasks.items():
                if key in known and isinstance(value, str) and value.strip():
                    self._task_models[key] = value.strip()

        # Read strictly: only an exact `true` turns it on. Anything else — a
        # truthy string, a 1, a value written by a newer version — leaves it
        # off, so a file this version does not fully understand cannot open a
        # path to the internet that the user did not open.
        self._web_search = raw.get("web_search") is True

        scope = raw.get("search_scope")
        if scope in {s.value for s in SearchScope}:
            self._search_scope = SearchScope(scope)

        # Only an exact `false` turns thinking off; anything else keeps the
        # default. The safe direction is the opposite of `web_search`'s — a
        # misread here costs a wait, not a byte leaving.
        self._thinking = raw.get("thinking") is not False

        # The character. Read defensively and bounded on the way in: a settings
        # file is a file, a character is meant to travel as one, and the day
        # somebody imports a stranger's character is the day this parses hostile
        # input. Anything that is not a string is ignored rather than coerced.
        from core.identity import MAX_MANNER_CHARS, MAX_NAME_CHARS

        # **A `context_tokens` left in an older file is read and
        # discarded, deliberately.** The only route past Ollama's 4,096
        # used to be that field, so a number in it is evidence that the
        # default was wrong rather than that one figure was wanted for
        # every model - the maintainer's own store held 131,072, which
        # `qwen3-14b-16k` cannot hold at all. Honouring it would preserve
        # a workaround for the thing that was fixed.
        #
        # Everyone lands on `fit`, which cannot produce a window past what
        # the model declares or the card affords, so the change can only
        # be in the safe direction. Somebody who wants a particular window
        # for a particular model sets it against that model.
        policy = raw.get("context_policy")
        if isinstance(policy, str) and policy in CONTEXT_POLICIES:
            self._context_policy = policy

        runtimes = raw.get("model_servers")
        if isinstance(runtimes, dict):
            # Read defensively, because these values are later executed. A key
            # that is not a short string, a field outside the closed set, or a
            # value of the wrong type is dropped rather than coerced.
            cleaned: Dict[str, Dict[str, Any]] = {}
            for rid, entry in list(runtimes.items())[:MAX_MODEL_SERVERS]:
                if not (isinstance(rid, str) and 0 < len(rid) <= 40 and isinstance(entry, dict)):
                    continue
                keep: Dict[str, Any] = {}
                if isinstance(entry.get("auto_start"), bool):
                    keep["auto_start"] = entry["auto_start"]
                for field_name in ("path", "python"):
                    value = entry.get(field_name)
                    if isinstance(value, str) and value.strip():
                        keep[field_name] = value.strip()[:MAX_MODEL_SERVER_PATH]
                if keep:
                    cleaned[rid] = keep
            self._model_servers = cleaned

        overflow = raw.get("overflow_policy")
        if isinstance(overflow, str) and overflow in OVERFLOW_POLICIES:
            self._overflow_policy = overflow

        reply_cap = raw.get("max_reply_tokens")
        if isinstance(reply_cap, int):
            self._max_reply_tokens = max(0, min(reply_cap, MAX_CONTEXT_TOKENS))

        overrides = raw.get("context_overrides")
        if isinstance(overrides, dict):
            # Bounded on the way in, as the character is: a settings file is
            # a file, and a key that is not a string is ignored rather than
            # coerced.
            self._context_overrides = {
                name: max(0, min(int(value), MAX_CONTEXT_TOKENS))
                for name, value in list(overrides.items())[:MAX_CONTEXT_OVERRIDES]
                if isinstance(name, str) and name.strip() and isinstance(value, int)
            }

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
