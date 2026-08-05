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
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.contracts import (
    ExecutionPlan,
    ExecutionStep,
    PlanState,
)
from core.query_classifier import SEARCH_MARKER, needs_search

logger = logging.getLogger(__name__)


def web_search_enabled() -> bool:
    """Whether a request may reach the public internet.

    Default deny (rule 5). Web search stays off until the egress log and
    per-source policy exist — see the sequencing commitments in CLAUDE.md.
    Until then nothing the user can type causes a byte to leave the machine:
    inference is Ollama on localhost and the Spine is a local file.

    Read at call time rather than import time so tests can toggle it.
    """
    return os.getenv("ZARAM_WEB_SEARCH", "").strip().lower() in {"1", "true", "yes", "on"}


class IntentType(Enum):
    """High-level intent categories used for routing and planning."""
    CONVERSATION = "conversation"
    SEARCH = "search"
    VISION = "vision"
    SPEECH = "speech"
    FILESYSTEM = "filesystem"
    TOOL = "tool"
    MULTI_STEP = "multi_step"
    UNKNOWN = "unknown"


@dataclass
class IntentClassification:
    """Result of classifying a user prompt."""
    intent_type: IntentType
    confidence: float
    capabilities: list[str] = field(default_factory=list)
    requires_search: bool = False
    requires_vision: bool = False
    requires_speech: bool = False
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
        "tool.git": IntentType.TOOL,
        "tool.vscode": IntentType.TOOL,
        "tool.terminal": IntentType.TOOL,
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
    _SPEECH_KEYWORDS = {"speak", "say", "voice", "audio", "talk", "pronounce", "read aloud",
                        "out loud", "aloud"}
    _FILESYSTEM_KEYWORDS = {"file", "open", "read", "search", "find", "directory", "folder"}
    _TOOL_KEYWORDS = {"git", "commit", "push", "code", "terminal", "run", "execute"}

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

    def classify(self, prompt: str) -> IntentClassification:
        """Classify a user prompt into an intent."""
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
        search_required = search_wanted and web_search_enabled()
        if search_wanted and not search_required:
            logger.debug("Planner: search suppressed — web search is off by policy")
        signals.append(IntentSignal(
            name="search_required",
            weight=0.8,
            matched=search_required,
            detail="Query classifier detected time-sensitive or factual query",
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
        tool_hits = self._matches(prompt_lower, self._TOOL_KEYWORDS)
        tool_matched = bool(tool_hits)
        signals.append(IntentSignal(
            name="tool_keywords",
            weight=0.4,
            matched=tool_matched,
            detail=f"Tool keywords found: {tool_hits}",
        ))

        # Determine intent type based on signals
        if vision_matched:
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
            capabilities = ["tool.terminal"]
        elif search_required:
            intent_type = IntentType.MULTI_STEP
            confidence = 0.80
            capabilities = ["knowledge.search", "reasoning.generate"]
        else:
            intent_type = IntentType.CONVERSATION
            confidence = 0.90
            capabilities = ["reasoning.generate"]

        return IntentClassification(
            intent_type=intent_type,
            confidence=confidence,
            capabilities=capabilities,
            requires_search=search_required,
            requires_vision=vision_matched,
            requires_speech=speech_matched,
            metadata={
                "signals": [s.__dict__ for s in signals],
                "prompt_length": len(prompt),
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
            IntentType.TOOL: "tool.terminal",
            IntentType.MULTI_STEP: "knowledge.search",
        }
        return mapping.get(intent, "reasoning.generate")


class IntentPlanner:
    """Analyzes intent and builds an ExecutionPlan.

    This is the kernel's Runtime_Intent component.  It classifies the
    user's prompt, selects the appropriate capabilities, and produces
    an execution plan that the scheduler can dispatch.
    """

    def __init__(self, router: IntentRouter | None = None) -> None:
        self._router = router or IntentRouter()

    def classify_intent(self, prompt: str) -> IntentClassification:
        """Classify a user prompt into an intent."""
        return self._router.classify(prompt)

    def create_plan(self, prompt: str, priority: str = "normal") -> ExecutionPlan:
        """Creates an execution plan, including web search when the question likely needs current info."""
        classification = self._router.classify(prompt)
        logger.debug("IntentPlanner: classified as %s (confidence=%.2f)", classification.intent_type, classification.confidence)

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
            plan_steps = [
                ExecutionStep(
                    capability_id=classification.capabilities[0] if classification.capabilities else "reasoning.generate",
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
