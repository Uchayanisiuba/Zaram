# backend/core/planner.py
"""Runtime_Intent — intent classification and execution planning.

The IntentPlanner is the kernel's entry point for user requests.  It
classifies the user's intent, determines which capabilities are needed,
and produces an :class:`~core.contracts.ExecutionPlan` that the
scheduler can dispatch.

Intent flow:
    User prompt → classify intent → select capabilities → build plan
"""
from __future__ import annotations

import logging
import re
import os
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from typing import Any

from core.contracts import (
    ExecutionPlan,
    ExecutionStep,
    PlanState,
)
from core.query_classifier import SEARCH_MARKER, needs_search

logger = logging.getLogger(__name__)


#: Values of ``ZARAM_WEB_SEARCH`` that mean yes. Anything else present means no.
_TRUTHY = {"1", "true", "yes", "on"}

#: The host a web search is addressed to, and therefore the host whose policy
#: rule decides whether one may be sent.
#:
#: Named here so the Settings screen can show the user the rule that will
#: actually apply, instead of a switch whose effect depends on a hostname
#: nobody has told them about. It is *not* the definition — the provider builds
#: the URL it probes — so `test_search_host_matches_the_provider` asserts the
#: two agree rather than this comment claiming they do. Asserting the
#: relationship instead of describing it is the lesson the DuckDuckGo fix cost
#: this codebase once already.
SEARCH_HOST = "duckduckgo.com"


#: What a tool request plans: look at what is attached, then answer with it.
#:
#: Two steps rather than one, and shaped exactly like the search pair above,
#: because the planner cannot know which tool is wanted — only the model can,
#: and only once it has seen what the user attached. `mcp.list_tools` is
#: internal (its payload is context, never prose), and the generation step that
#: follows is where the choice is made.
#:
#: **`mcp.call` is deliberately not planned.** A plan naming the tool up front
#: would be the planner guessing, and worse, it would be a *permission* decided
#: before `policy.decide` ran. The call is dispatched by the engine after the
#: model has chosen and the gate has answered — selection is ordering, the gate
#: is the boundary, and they must not be the same step.
_TOOL_CAPABILITIES = ["mcp.list_tools", "reasoning.generate"]


#: Where the current request's model runs: ``"local"``, ``"cloud"`` or ``None``.
#:
#: A `ContextVar`, not a module global, because two chat requests naming
#: different models are in flight simultaneously the moment a second window
#: exists — with a global, one would decide the other's search policy. Under
#: asyncio each task gets its own value and nothing has to be restored.
#:
#: ``None`` is the correct default: most callers of the planner are not the
#: chat route and have no model in hand, and unknown searches.
_search_locality: ContextVar[Optional[str]] = ContextVar("zaram_search_locality", default=None)


def set_search_locality(locality: Optional[str]) -> None:
    """Record where this request's model runs, for the search decision."""
    _search_locality.set(locality)


#: Question shapes no model can answer from its weights, whatever its size.
#:
#: These are the markers of *recency* specifically, not of factuality. A
#: frontier model plausibly knows the capital of Portugal better than a 12B
#: does; neither of them knows what happened last week, because both have a
#: training cutoff and the event fell after it. Size does not help here and
#: never will.
_RECENCY_RE = re.compile(
    r"\b(today|yesterday|tonight|this\s+(?:week|month|year|morning)|"
    r"currently|current|right\s+now|just\s+(?:happened|announced|released)|"
    r"latest|newest|most\s+recent|recently|breaking|so\s+far|"
    r"last\s+(?:week|month|night)|"
    r"(?:a\s+)?few\s+(?:days|weeks|months)\s+ago|"
    r"in\s+the\s+(?:past|last)\s+(?:few\s+)?(?:days|weeks|months))\b",
    re.IGNORECASE,
)


def is_time_sensitive(prompt: str) -> bool:
    """Whether the answer changes with the calendar.

    Separate from `needs_search` deliberately. That one asks *should we look
    this up*, and matches factual shapes like "who is" and topic words like
    "election" — plenty of which a large model answers perfectly well from its
    weights. This asks the narrower question that overrides the economy below:
    **could any model possibly know this?**
    """
    return bool(_RECENCY_RE.search(prompt or ""))


def suppression_reason(wanted: bool, required: bool) -> str | None:
    """Which of the two gates refused, for a question that wanted search.

    ``None`` when nothing was refused — the question did not want search, or it
    got it. Otherwise ``"off"`` for the user's switch and ``"not_applicable"``
    for the local/cloud economy.

    Shared by both classifier paths rather than computed twice. They already
    drifted once: the semantic path did not consult `needs_search` at all, so a
    time-sensitive question could be answered from training data with nothing
    reporting a failure. Two copies of a rule is how that happens.

    Asks `web_search_enabled` again rather than taking it as an argument, since
    both callers have already called it and it reads env and settings live. A
    parameter would let a stale value in through the one door this exists to
    keep honest.
    """
    if not wanted or required:
        return None
    return "off" if not web_search_enabled() else "not_applicable"


def search_applies_to(locality: str | None, prompt: str = "") -> bool:
    """Whether a search is worth running for a model that runs *here*.

    **Recency outranks the economy, and that is the correction.** This used to
    be a blanket switch — search on local, skip on cloud — on the reasoning
    that a frontier model carries a bigger store of facts so a live result
    changes its answer less often. That holds for general knowledge and fails
    completely for the one category where search matters most: *every* model
    has a training cutoff, and none of them knows what happened last week.

    The visible cost was a silent one. Selecting a cloud model did not merely
    change who answered — it removed the search step from the plan entirely, so
    "what's the latest in AI" came back from a cutoff with no source, no
    indication that nothing had been looked up, and nothing in the interface
    saying why. The user's report was that Zaram "switched to a cloud model" to
    answer it; the switch was theirs, and the suppression was ours.

    So a time-sensitive question searches on any model. The local/cloud economy
    survives for everything else, which is what it was actually reasoning about.

    **What the economy is still for.** Where the answer does not turn on the
    calendar, search compensates for what the answering model does not know: a
    local 12B carries a smaller store of facts than a frontier model, so a live
    result changes its answer far more often. That was the maintainer's call on
    14 August 2026 and it stands for exactly that case — it was only ever wrong
    where it was applied to questions no model could answer.

    ``locality`` is ``"local"``, ``"cloud"`` or ``None``. **Unknown searches**,
    which is the deliberate direction: the cost of searching unnecessarily is
    one extra request to a host the user has already permitted, and the cost of
    skipping it is a confidently stale answer with nothing indicating why. The
    asymmetry runs the opposite way from the routing gates next door — there,
    unknown means "do not send" because the risk is the user's documents
    leaving. Here nothing of the user's is at stake beyond the question they
    just typed, which is going to a search engine either way or not at all.

    Does not consult `web_search_enabled`. Two questions — *may we search?* and
    *is it worth searching?* — and merging them would make a capability gate
    and a preference indistinguishable, which is the mistake this codebase has
    now made three times with ranking scores.
    """
    # No model knows this, so which model is answering is not the question.
    if is_time_sensitive(prompt):
        return True

    try:
        from core.user_settings import SearchScope, get_user_settings

        if get_user_settings().search_scope is SearchScope.ALWAYS:
            return True
    except Exception:
        return True

    return locality != "cloud"


def web_search_enabled() -> bool:
    """Whether a request may reach the public internet.

    Default deny (rule 5). `CLAUDE.md` sequenced this deliberately — *egress log
    → per-source policy → web search as its first governed source* — because
    bytes cannot be logged retroactively. Both of those now exist and are
    visible to the user, which is what makes the switch offerable at all.

    **The environment wins when it is set.** A variable someone exported
    deliberately, in a launch script or a test, must not be silently overridden
    by a stored preference — and every test in
    ``test_outbound_query_invariant.py`` toggles the gate that way. When it is
    unset, which is the ordinary case for anybody who has not gone looking, the
    Settings toggle decides.

    **On is not a licence.** The per-host policy still decides each request and
    its default is refuse, so this returning ``True`` means "a search step may
    be planned", never "a search may be sent". The gate is what turns search
    into the first *governed* source rather than the first exception.

    Read at call time rather than at import so both inputs stay live.
    """
    raw = os.getenv("ZARAM_WEB_SEARCH")
    if raw is not None and raw.strip():
        return raw.strip().lower() in _TRUTHY

    try:
        from core.user_settings import get_user_settings

        return get_user_settings().web_search
    except Exception:  # noqa: BLE001 - see below
        # A preference file must never be able to *open* the internet by
        # failing, so an unreadable one falls to the default, which is off.
        logger.warning("could not read the web search preference; leaving it off", exc_info=True)
        return False


def _document_body_prompt(request: str) -> str:
    """Turn "write that up as a proposal" into an instruction that writes it.

    Passing the user's words straight to the model produces a reply *about* the
    request rather than the document: asked to "write that up as a proposal"
    with no further framing, a local model answered by describing its own
    operating protocol, and that text became the file. The request is an
    instruction to Zaram; the model needs the instruction Zaram derives from it.

    Deliberately not a persona or a template. The model already has the
    conversation and whatever recall injected; this only says what shape the
    output must take and what must not be in it. A preamble like "Here is your
    proposal:" is not a formatting nuisance — it becomes the document's first
    paragraph and, through `_title_from`, its filename.
    """
    return (
        f"The user asked: {request}\n\n"
        "Write the document itself, based on what we have discussed. "
        "Output only the body text, as plain paragraphs separated by blank "
        "lines. Do not add a preamble, do not explain what you are about to "
        "write, and do not describe yourself. Start with the document's title "
        "on its own line."
    )


class IntentType(Enum):
    """High-level intent categories used for routing and planning."""
    CONVERSATION = "conversation"
    SEARCH = "search"
    VISION = "vision"
    SPEECH = "speech"
    FILESYSTEM = "filesystem"
    TOOL = "tool"
    MULTI_STEP = "multi_step"
    #: "Write that up as a proposal." Produces a file, generative tier.
    DOCUMENT = "document"
    #: "Draw me a logo." Produces a picture, also generative tier.
    #:
    #: Separate from `VISION`, which is the *inbound* direction — looking at an
    #: image the user supplied. One intent covering both would have to be
    #: resolved back into two at the point of routing, from the presence of an
    #: attachment, which is a guess about what somebody meant rather than a
    #: classification of what they said.
    IMAGE = "image"
    #: "Why does this function return None." Answered by `reasoning.generate`
    #: like an ordinary question — this intent exists to select a *model*, not
    #: a capability, which is the one thing no other intent here does.
    CODE = "code"
    UNKNOWN = "unknown"


#: Intent → the model specialisation that serves it best, or absent for the
#: intents any general model answers.
#:
#: A **preference**, and the type says so: `specialisation` is compared against
#: `ModelInfo.specialisation`, which `TASK_MARKERS` derives from the model's
#: name. Nothing here is a requirement — a machine with no coding model still
#: answers coding questions, with the general model, which is the correct
#: outcome and not a degraded one.
#:
#: Modality is the opposite kind of thing and is deliberately not in this map.
#: "Can this model accept an image" gates the candidate set in
#: `ProviderManager.select_model_for_task`; keeping the two in one table is how
#: they end up as one number.
INTENT_SPECIALISATION: dict[IntentType, str] = {
    IntentType.CODE: "code",
}


@dataclass
class IntentClassification:
    """Result of classifying a user prompt."""
    intent_type: IntentType
    confidence: float
    capabilities: list[str] = field(default_factory=list)
    requires_search: bool = False
    requires_vision: bool = False
    #: The reply should be a picture rather than prose.
    #:
    #: The **other** modality question, and it is not the negation or the
    #: partner of `requires_vision` — reading an image and drawing one are
    #: different abilities, held by different models, and `CLAUDE.md` names
    #: collapsing them as the error that gets a text model asked to draw.
    #:
    #: This is a precondition, so a caller that cannot satisfy it must refuse
    #: rather than answer. That is the whole reason the field exists: without
    #: it "draw me a logo" reaches an ordinary chat model, which writes a
    #: confident paragraph about a picture it never made. Rule 9 in a new
    #: medium, and the silent version of it.
    requires_image_output: bool = False
    requires_speech: bool = False
    #: The question wanted live information and the policy refused it.
    #:
    #: Not the negation of `requires_search` — that is false for every ordinary
    #: question too, and the difference between "did not need search" and
    #: "needed it and was denied" is the whole point. `CLAUDE.md`: *disabled
    #: capabilities are visible, not silent*. Without this the reply is answered
    #: from the weights alone with nothing on screen saying so, which is the
    #: most confidently wrong answer the product can give.
    search_suppressed: bool = False
    #: *Why* it was suppressed. ``"off"``, ``"not_applicable"``, or ``None``.
    #:
    #: **One flag was standing for two reasons and the notice could only name
    #: one of them.** `search_required` is the conjunction of three conditions
    #: — the question wants search, the user's switch is on, and search is
    #: worth running for the answering model — so `search_suppressed` went true
    #: when *any* of the last two failed. The notice said "Web search is off"
    #: either way, which meant a user who had turned search on kept being told
    #: it was off. Reported by the maintainer, 31 August 2026.
    #:
    #: The two are not the same disclosure. ``"off"`` is a **disabled
    #: capability**, which `CLAUDE.md` requires be visible rather than silent.
    #: ``"not_applicable"`` is a **routing decision** — search is available and
    #: was judged not to change this answer — and it is not a question that
    #: turns on the calendar, because recency overrides the economy before this
    #: is reached. See `search_applies_to`.
    search_suppressed_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IntentSignal:
    """A single signal that contributes to intent classification."""
    name: str
    weight: float
    matched: bool
    detail: str = ""


class IntentRouter:
    """Classifies user prompts into intent types.

    The router uses a combination of keyword matching, regex patterns,
    and the existing :func:`~core.query_classifier.needs_search` classifier.
    """

    # Capability capability_id → intent type
    _CAPABILITY_INTENTS: dict[str, IntentType] = {
        "reasoning.generate": IntentType.CONVERSATION,
        "knowledge.search": IntentType.SEARCH,
        "vision.analyze": IntentType.VISION,
        "vision.screen": IntentType.VISION,
        "vision.camera": IntentType.VISION,
        "speech.tts": IntentType.SPEECH,
        "speech.stream": IntentType.SPEECH,
        "filesystem.search": IntentType.FILESYSTEM,
        "filesystem.open": IntentType.FILESYSTEM,
        # `tool.*` used to be three entries here — git, vscode, terminal — and
        # no runtime provided any of them. What serves this intent is whatever
        # MCP server the user attached, which is the point of being a client.
        "mcp.list_tools": IntentType.TOOL,
        "mcp.call": IntentType.TOOL,
    }

    # Keywords for intent detection.
    #
    # Matched on word boundaries, never as substrings — see `_matches` below.
    # These sets were previously tested with `kw in prompt_lower`, which routed
    # "invoice" to speech because it contains "voice", "essay" to speech because
    # it contains "say", "profile" to filesystem via "file", and "research" to
    # filesystem via "search". Every invoice prompt in the business layer went
    # to text-to-speech.
    _VISION_KEYWORDS = {"image", "photo", "picture", "screenshot", "see", "look", "visual"}
    #: Asking for a picture to be *made*, which every one of these overlaps
    #: with `_VISION_KEYWORDS` on — "draw me a picture" contains "picture" —
    #: so this set is checked first and every entry is a phrase rather than a
    #: word.
    #:
    #: Phrases, and tightly, for the same reason `_CODE_KEYWORDS` is tight:
    #: this only runs when the embedder is unavailable, and a false positive
    #: sends an ordinary request to a refusal about image models. Bare "draw"
    #: is the one that would do it — "draw up a contract" is a document, and
    #: this must not take it.
    _IMAGE_KEYWORDS = {
        "draw me", "draw a picture", "draw an image",
        "generate an image", "generate a picture", "generate an illustration",
        "create an image", "create a picture",
        "make me an image", "make me a picture",
        "illustration of", "logo for", "paint me", "photorealistic",
    }
    _SPEECH_KEYWORDS = {"speak", "say", "voice", "audio", "talk", "pronounce", "read aloud",
                        "out loud", "aloud"}
    _FILESYSTEM_KEYWORDS = {"file", "open", "read", "search", "find", "directory", "folder"}
    #: "code" is deliberately absent, and its removal is the point.
    #:
    #: Tool intent is *acting on* a repository — committing, running, executing.
    #: "code" names a subject, not an action, so it sent "is there a cleaner way
    #: to write this code" to `tool.terminal`. Harmless while no coding intent
    #: existed; actively wrong once one did, because the keyword path is what
    #: runs when the embedder is unavailable — exactly the machine where a
    #: coding question most needs to reach a coding model rather than a
    #: terminal.
    _TOOL_KEYWORDS = {"git", "commit", "push", "terminal", "run", "execute"}

    #: Chosen for precision over reach, because this set only runs when
    #: semantic routing is unavailable and a false positive here sends an
    #: ordinary question to a coding fine-tune — the category error
    #: `is_general_purpose` exists to prevent, arriving by another road.
    #: Every word below is one that a non-coding question rarely contains.
    _CODE_KEYWORDS = {"code", "function", "bug", "refactor", "debug", "syntax",
                      "compile", "exception", "traceback", "stack trace"}

    #: Compiled word-boundary matchers, keyed by the keyword set itself.
    #:
    #: Keyed by content, not by ``id()``. An id-keyed cache looked fine and was
    #: wrong: a caller passing a set literal gets a temporary object whose id is
    #: reused after collection, so a later call with different keywords silently
    #: received the earlier compiled pattern. Caught by a test asserting
    #: "(voice)" matches "voice", which returned nothing.
    _MATCHERS: dict[frozenset, "re.Pattern[str]"] = {}

    @classmethod
    def _matcher(cls, keywords: frozenset | set) -> "re.Pattern[str]":
        key = frozenset(keywords)
        cached = cls._MATCHERS.get(key)
        if cached is None:
            # Longest first so "read aloud" wins over "read" when both could match.
            alternation = "|".join(
                re.escape(kw) for kw in sorted(keywords, key=len, reverse=True)
            )
            cached = re.compile(rf"\b(?:{alternation})\b", re.IGNORECASE)
            cls._MATCHERS[key] = cached
        return cached

    @classmethod
    def _matches(cls, prompt_lower: str, keywords: set) -> list[str]:
        """Keywords present as whole words, in the order they appear.

        Whole words, because a keyword list is a list of words the user typed —
        not of letter sequences that happen to occur inside longer ones. The
        substring version had no way to distinguish "voice" the request from
        "invoice" the noun.
        """
        return cls._matcher(keywords).findall(prompt_lower)

    def __init__(
        self,
        event_bus: Any | None = None,
        semantic_router: Any | None = None,
        tool_vocabulary: Any | None = None,
    ) -> None:
        """`semantic_router` is optional so every existing caller still works.

        CLAUDE.md routes with embeddings; this class was keyword-based. Rather
        than replacing it, embeddings run *first* and keywords remain the
        fallback — because the embedder degrades to a hash backend when Ollama
        is unreachable, and a keyword router is predictable where similarity
        over hash vectors is arbitrary. Deleting the keywords would have made
        an Ollama outage into a broken product rather than a duller one.

        `tool_vocabulary` is a callable returning the names of the servers the
        user has attached, and it is what makes the tool route reachable in
        practice rather than only in principle. `_TOOL_KEYWORDS` was written
        for a terminal capability — git, commit, push, run — so with Blender
        attached, *"what is in my blender scene"* matched nothing and the
        attached server was never consulted. The route existed and almost
        nothing travelled it.

        It is deliberately **not** a question put to the user, and not a fixed
        list of applications Zaram has heard of. Attaching a server is already
        the user saying they want it; reading the names back is rule 7e's
        "never ask what the system can answer from behaviour", and it means a
        server nobody at Zaram has heard of works on the day it is written.

        Injected rather than imported, like `McpRuntime`'s ranker, so `core/`
        keeps no import-time dependency on a runtime. Absent is a supported
        state and degrades to the old keyword set.
        """
        self._event_bus = event_bus
        self._semantic = semantic_router
        self._tool_vocabulary = tool_vocabulary

    def _tool_keywords(self) -> set[str]:
        """The tool words for *this* machine: the fixed set plus what is attached."""
        if self._tool_vocabulary is None:
            return self._TOOL_KEYWORDS
        try:
            attached = {
                str(name).lower().strip()
                for name in (self._tool_vocabulary() or ())
                if str(name).strip()
            }
        except Exception:
            # Classification must never be the thing that fails a request; a
            # broken config means duller routing, not no answer.
            logger.exception("Could not read the attached tool vocabulary")
            return self._TOOL_KEYWORDS
        return self._TOOL_KEYWORDS | attached

    def classify(self, prompt: str) -> IntentClassification:
        """Classify a user prompt into an intent.

        Embeddings first, keywords second. The semantic router returns None
        when it is not confident or not running semantically, which is a
        deliberate handback rather than a failure — see `core.retrieval.router`.
        """
        semantic = self._classify_semantically(prompt)
        if semantic is not None:
            return semantic

        # Strip search marker so keyword matching doesn't pick up "search" from the marker
        search_prompt = prompt
        if SEARCH_MARKER in prompt:
            search_prompt = prompt.split(SEARCH_MARKER)[-1]
        prompt_lower = search_prompt.lower().strip()
        signals: list[IntentSignal] = []

        # Check for search requirement. Gated: the classifier may want search,
        # but nothing leaves the machine until the egress log and per-source
        # policy exist. See web_search_enabled() and CLAUDE.md.
        search_wanted = needs_search(prompt)
        # Two gates, kept separate: *may* we search (rule 5, the user's switch)
        # and *is it worth* searching for the model that is about to answer.
        # Merging them would make a capability gate indistinguishable from a
        # preference.
        search_required = (
            search_wanted
            and web_search_enabled()
            and search_applies_to(_search_locality.get(), prompt)
        )
        if search_wanted and not search_required:
            # Also carried on the classification, because a debug line is not a
            # disclosure. This log stays for the developer; `search_suppressed`
            # is what reaches the person who asked.
            logger.debug("Planner: search suppressed — web search is off by policy")
        signals.append(IntentSignal(
            name="search_required",
            weight=0.8,
            matched=search_required,
            detail="Query classifier detected time-sensitive or factual query",
        ))

        # Check for image-generation phrases. Before vision, because every one
        # of them contains a vision keyword.
        image_hits = self._matches(prompt_lower, self._IMAGE_KEYWORDS)
        image_matched = bool(image_hits)
        signals.append(IntentSignal(
            name="image_phrases",
            weight=0.7,
            matched=image_matched,
            detail=f"Image-generation phrases found: {image_hits}",
        ))

        # Check for vision keywords
        vision_hits = self._matches(prompt_lower, self._VISION_KEYWORDS)
        vision_matched = bool(vision_hits)
        signals.append(IntentSignal(
            name="vision_keywords",
            weight=0.6,
            matched=vision_matched,
            detail=f"Vision keywords found: {vision_hits}",
        ))

        # Check for speech keywords
        speech_hits = self._matches(prompt_lower, self._SPEECH_KEYWORDS)
        speech_matched = bool(speech_hits)
        signals.append(IntentSignal(
            name="speech_keywords",
            weight=0.5,
            matched=speech_matched,
            detail=f"Speech keywords found: {speech_hits}",
        ))

        # Check for filesystem keywords
        fs_hits = self._matches(prompt_lower, self._FILESYSTEM_KEYWORDS)
        fs_matched = bool(fs_hits)
        signals.append(IntentSignal(
            name="filesystem_keywords",
            weight=0.4,
            matched=fs_matched,
            detail=f"Filesystem keywords found: {fs_hits}",
        ))

        # Check for tool keywords
        tool_hits = self._matches(prompt_lower, self._tool_keywords())
        tool_matched = bool(tool_hits)
        signals.append(IntentSignal(
            name="tool_keywords",
            weight=0.4,
            matched=tool_matched,
            detail=f"Tool keywords found: {tool_hits}",
        ))

        # Check for coding keywords
        code_hits = self._matches(prompt_lower, self._CODE_KEYWORDS)
        code_matched = bool(code_hits)
        signals.append(IntentSignal(
            name="code_keywords",
            weight=0.4,
            matched=code_matched,
            detail=f"Coding keywords found: {code_hits}",
        ))

        # Determine intent type based on signals
        if image_matched:
            # Ahead of vision deliberately: "draw me a picture" matches both,
            # and only one of the two readings is what anybody meant.
            intent_type = IntentType.IMAGE
            confidence = 0.85
            capabilities = ["image.generate"]
        elif vision_matched:
            intent_type = IntentType.VISION
            confidence = 0.85
            capabilities = ["vision.analyze"]
        elif speech_matched:
            intent_type = IntentType.SPEECH
            confidence = 0.80
            capabilities = ["speech.tts"]
        elif fs_matched:
            intent_type = IntentType.FILESYSTEM
            confidence = 0.70
            capabilities = ["filesystem.search"]
        elif tool_matched:
            intent_type = IntentType.TOOL
            confidence = 0.65
            capabilities = _TOOL_CAPABILITIES
        elif search_required:
            intent_type = IntentType.MULTI_STEP
            confidence = 0.80
            capabilities = ["knowledge.search", "reasoning.generate"]
        elif code_matched:
            # Below search, above conversation. A coding question that also
            # wants current information needs the search more than it needs the
            # specialist — the model can reason about code it is shown, and
            # cannot reason about a release it has never heard of.
            #
            # Confidence is the lowest here on purpose: this branch exists only
            # as the fallback for a machine with no embedder, and the exemplars
            # are the path that should normally answer.
            intent_type = IntentType.CODE
            confidence = 0.60
            capabilities = ["reasoning.generate"]
        else:
            intent_type = IntentType.CONVERSATION
            confidence = 0.90
            capabilities = ["reasoning.generate"]

        return IntentClassification(
            intent_type=intent_type,
            confidence=confidence,
            capabilities=capabilities,
            requires_search=search_required,
            # Not both. Every image-generation phrase contains a vision
            # keyword, so without this exclusion "draw me a picture" reports
            # that it needs a model which can *read* images as well as draw
            # them — two gates ANDed together, and a candidate set that empties
            # for a reason nobody asked for.
            requires_vision=vision_matched and not image_matched,
            requires_image_output=image_matched,
            requires_speech=speech_matched,
            search_suppressed=search_wanted and not search_required,
            search_suppressed_reason=suppression_reason(search_wanted, search_required),
            metadata={
                "signals": [s.__dict__ for s in signals],
                "prompt_length": len(prompt),
            },
        )

    #: Intent name from the exemplar set → the capabilities that serve it.
    #: The exemplar file is data a user may edit, so a name that no longer maps
    #: to anything must not take the request down — see the `.get` below.
    _SEMANTIC_CAPABILITIES: dict[str, list[str]] = {
        "document": ["document.generate"],
        "image": ["image.generate"],
        "vision": ["vision.analyze"],
        "speech": ["speech.tts"],
        "filesystem": ["filesystem.search"],
        "tool": _TOOL_CAPABILITIES,
        "search": ["knowledge.search", "reasoning.generate"],
        "conversation": ["reasoning.generate"],
        #: Same capability as conversation, on purpose. A coding question is
        #: answered by generating text; what differs is which model generates
        #: it, and that is decided by `INTENT_SPECIALISATION`, not here.
        "code": ["reasoning.generate"],
    }

    def _classify_semantically(self, prompt: str) -> IntentClassification | None:
        """Route by similarity to task exemplars, or hand back to keywords.

        Returns None for every case the caller should handle the old way: no
        router configured, the embedder not running semantically, nothing above
        the floor, or two intents too close to separate. That is a handback,
        not an error — see `core.retrieval.router`.
        """
        if self._semantic is None:
            return None

        try:
            decision = self._semantic.route(prompt)
        except Exception:
            # Routing must never be the thing that fails a request. A broken
            # index means duller classification, not no answer.
            logger.exception("Semantic routing failed; falling back to keywords")
            return None

        if decision is None:
            return None

        try:
            intent_type = IntentType(decision.intent)
        except ValueError:
            logger.warning(
                "Exemplars name intent %r, which is not an IntentType", decision.intent
            )
            return None

        capabilities = self._SEMANTIC_CAPABILITIES.get(
            decision.intent, ["reasoning.generate"]
        )

        # **Wanting live information is a property of the question, not a rival
        # intent.** This read `decision.intent == "search"` alone, and because
        # `classify` returns the moment this method returns non-None, the
        # keyword classifier was never consulted on the semantic path at all.
        # So a question could be time-sensitive, say so unambiguously, and be
        # answered from training data.
        #
        # Measured, which is how it was found: "Who is the current president of
        # the United States?" routes to **`conversation` at 0.022 confidence**,
        # while `needs_search` matches it on three separate patterns — "who
        # is", "current", and "president". Zaram answered "Joe Biden", with web
        # search switched on, `duckduckgo.com` allowed, and no search step in
        # the plan and no source in the stream. Nothing reported a failure,
        # because from the planner's point of view nothing failed.
        #
        # The two classifiers are not alternatives here. `conversation` and
        # `search` are not exclusive: "who is the current president" is a
        # perfectly conversational question whose answer changes. So the
        # signals are unioned rather than switched between — the intent decides
        # *what kind of work* the request is, and this decides whether that
        # work needs facts newer than the weights.
        #
        # Gating is unchanged and stays after the union: routing more
        # accurately must never become a route around rule 5.
        wants_search = decision.intent == "search" or needs_search(prompt)
        requires_search = (
            wants_search
            and web_search_enabled()
            and search_applies_to(_search_locality.get(), prompt)
        )
        if decision.intent == "search" and not requires_search:
            capabilities = ["reasoning.generate"]
        elif requires_search and "knowledge.search" not in capabilities:
            # `create_plan` builds the steps from `requires_search` directly, so
            # this does not change the plan. It keeps the reported capabilities
            # honest for `create_plan_from_intent` and for anything reading the
            # classification to explain the routing decision — a classification
            # that requires a search and does not list it is the kind of
            # near-truth that costs an afternoon later.
            capabilities = ["knowledge.search", *capabilities]

        return IntentClassification(
            intent_type=intent_type,
            confidence=decision.confidence,
            capabilities=capabilities,
            requires_search=requires_search,
            requires_vision=decision.intent == "vision",
            requires_image_output=decision.intent == "image",
            requires_speech=decision.intent == "speech",
            search_suppressed=wants_search and not requires_search,
            search_suppressed_reason=suppression_reason(wants_search, requires_search),
            metadata={
                "router": "semantic",
                # The legible half. CLAUDE.md: show routing decisions in plain
                # language, with the evidence behind them.
                "reason": decision.reason,
                "exemplar": decision.exemplar,
                "runner_up": decision.runner_up,
                "runner_up_score": decision.runner_up_score,
                "scores": decision.scores,
            },
        )

    def get_capability_for_intent(self, intent: IntentType) -> str:
        """Return the primary capability for an intent type."""
        mapping = {
            IntentType.CONVERSATION: "reasoning.generate",
            IntentType.SEARCH: "knowledge.search",
            IntentType.VISION: "vision.analyze",
            IntentType.SPEECH: "speech.tts",
            IntentType.FILESYSTEM: "filesystem.search",
            IntentType.TOOL: "mcp.list_tools",
            IntentType.MULTI_STEP: "knowledge.search",
            IntentType.CODE: "reasoning.generate",
            IntentType.IMAGE: "image.generate",
        }
        return mapping.get(intent, "reasoning.generate")


class IntentPlanner:
    """Analyzes intent and builds an ExecutionPlan.

    This is the kernel's Runtime_Intent component.  It classifies the
    user's prompt, selects the appropriate capabilities, and produces
    an execution plan that the scheduler can dispatch.
    """

    def __init__(
        self,
        router: IntentRouter | None = None,
        semantic_router: Any | None = None,
        tool_vocabulary: Any | None = None,
    ) -> None:
        self._router = router or IntentRouter(
            semantic_router=semantic_router,
            tool_vocabulary=tool_vocabulary,
        )

    def set_tool_vocabulary(self, vocabulary: Any | None) -> None:
        """Tell the router which servers are attached.

        A setter as well as a constructor argument because the MCP runtime is
        registered *after* the engine is built — servers are not connected at
        boot, since putting a stranger's `npx` subprocess on the critical path
        of Zaram launching costs tens of seconds. Late binding is what lets the
        vocabulary follow the user attaching a server without a restart.
        """
        self._router._tool_vocabulary = vocabulary

    def classify_intent(self, prompt: str) -> IntentClassification:
        """Classify a user prompt into an intent."""
        return self._router.classify(prompt)

    def create_plan(
        self,
        prompt: str,
        priority: str = "normal",
        *,
        has_images: bool = False,
    ) -> ExecutionPlan:
        """Creates an execution plan, including web search when the question likely needs current info.

        **`has_images` is a fact and the classifier is a guess, so the fact
        wins.** Without it this planner reads the *word* "image" and emits a
        `vision.analyze` step — and the dispatcher's vision branch reads
        ``input_data["image"]``, singular, while `ExecutionEngine` writes
        ``input_data["images"]``, plural, onto the **generation** step only. Two
        names for one thing, chosen by a keyword.

        Measured 28 August 2026. A PNG attached to *"What shapes and colours
        are in this image?"* routed correctly to a vision-capable model, then
        answered::

            [ERROR] No valid image provided for vision analysis.

        The picture was three layers up, intact, on a step nobody ran.

        `main.py` already had this right for *model selection* —
        ``requires_vision = requires_vision or has_images``, an attachment
        outranking wording — and the planner never learned the same lesson.

        So when an image is genuinely attached the plan stays an ordinary
        generation, because that path carries images to whichever model was
        routed, passes the residency and consent gates, and is logged.

        **And when one is not attached, a `vision.*` step is always wrong.**
        This used to say `vision.analyze` remained "for the capability route —
        `/vision/analyze`, screen and camera — which supplies its own singular
        ``image``". No such caller existed: the endpoint reached an ungated
        engine method against a hardcoded, uninstalled model, through a
        `_parse_legacy_sse` that was never defined, and it was deleted on 28
        August 2026. So the only `vision.*` step this planner can now produce
        is one the keywords invented, and `Dispatcher` refuses it rather than
        letting it fall through to generation — a model asked to describe a
        picture nobody supplied writes a confident description of nothing.
        """
        classification = self._router.classify(prompt)
        logger.debug("IntentPlanner: classified as %s (confidence=%.2f)", classification.intent_type, classification.confidence)

        plan_steps: list[ExecutionStep] = []

        if classification.intent_type is IntentType.DOCUMENT:
            # Two steps, in this order, because the document is made *from the
            # answer* rather than from the request. Generating straight from
            # the prompt would write up the user's own question.
            #
            # `answer` is left empty because the planner cannot know it yet;
            # the engine fills it from the first step's output. The empty
            # string is the signal that there is something to fill.
            plan_steps = [
                ExecutionStep(
                    capability_id="reasoning.generate",
                    input_data={"prompt": _document_body_prompt(prompt)},
                    depends_on=[],
                ),
                ExecutionStep(
                    # The *user's* words, not the rewritten instruction: the
                    # runtime reads them to decide whether "spreadsheet" or
                    # "invoice" was asked for, and the instruction below would
                    # match none of them.
                    capability_id="document.generate",
                    input_data={"prompt": prompt, "answer": ""},
                    depends_on=[0],
                ),
            ]
        elif classification.requires_search:
            plan_steps = [
                ExecutionStep(
                    capability_id="knowledge.search",
                    input_data={"query": prompt, "persona": "zaram_prime"},
                    depends_on=[],
                ),
                ExecutionStep(
                    capability_id="reasoning.generate",
                    input_data={"prompt": prompt},
                    depends_on=[0],
                ),
            ]
        elif classification.intent_type is IntentType.TOOL:
            # Same shape as the search pair above: gather, then answer with
            # what was gathered. The list step is what puts the user's attached
            # servers in front of the model at all.
            #
            # It degrades well by construction, which is what makes it safe to
            # route here on keywords as noisy as "run" and "execute". With no
            # servers attached the list comes back empty, nothing is added to
            # the prompt, and the second step answers the question as an
            # ordinary reply — the same graceful direction `_drop_unavailable_steps`
            # takes, reached without needing a runtime to be missing.
            plan_steps = [
                ExecutionStep(
                    capability_id="mcp.list_tools",
                    input_data={"query": prompt},
                    depends_on=[],
                ),
                ExecutionStep(
                    capability_id="reasoning.generate",
                    input_data={"prompt": prompt},
                    depends_on=[0],
                ),
            ]
        else:
            capability = (
                classification.capabilities[0]
                if classification.capabilities
                else "reasoning.generate"
            )
            # An attached image is answered by generating *with* it, never by
            # the capability side door. See the docstring for the measured
            # failure this prevents.
            if has_images and capability.startswith("vision."):
                capability = "reasoning.generate"
            plan_steps = [
                ExecutionStep(
                    capability_id=capability,
                    input_data={"prompt": prompt},
                    depends_on=[],
                ),
            ]

        return ExecutionPlan(
            correlation_id=str(uuid.uuid4()),
            original_prompt=prompt,
            steps=plan_steps,
            state=PlanState.PENDING,
            priority=priority,
            created_at=time.time(),
        )

    def create_plan_from_intent(
        self,
        prompt: str,
        classification: IntentClassification,
        priority: str = "normal",
    ) -> ExecutionPlan:
        """Create a plan from a pre-classified intent."""
        plan_steps: list[ExecutionStep] = []

        if classification.requires_search:
            plan_steps = [
                ExecutionStep(
                    capability_id="knowledge.search",
                    input_data={"query": prompt, "persona": "zaram_prime"},
                    depends_on=[],
                ),
                ExecutionStep(
                    capability_id="reasoning.generate",
                    input_data={"prompt": prompt},
                    depends_on=[0],
                ),
            ]
        else:
            for cap in classification.capabilities:
                plan_steps.append(ExecutionStep(
                    capability_id=cap,
                    input_data={"prompt": prompt},
                    depends_on=[],
                ))

        return ExecutionPlan(
            correlation_id=str(uuid.uuid4()),
            original_prompt=prompt,
            steps=plan_steps,
            state=PlanState.PENDING,
            priority=priority,
            created_at=time.time(),
        )
