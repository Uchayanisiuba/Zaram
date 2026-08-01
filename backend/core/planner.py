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

    # Keywords for intent detection
    _VISION_KEYWORDS = {"image", "photo", "picture", "screenshot", "see", "look", "visual"}
    _SPEECH_KEYWORDS = {"speak", "say", "voice", "audio", "talk", "pronounce", "read aloud"}
    _FILESYSTEM_KEYWORDS = {"file", "open", "read", "search", "find", "directory", "folder"}
    _TOOL_KEYWORDS = {"git", "commit", "push", "code", "terminal", "run", "execute"}

    def classify(self, prompt: str) -> IntentClassification:
        """Classify a user prompt into an intent."""
        # Strip search marker so keyword matching doesn't pick up "search" from the marker
        search_prompt = prompt
        if SEARCH_MARKER in prompt:
            search_prompt = prompt.split(SEARCH_MARKER)[-1]
        prompt_lower = search_prompt.lower().strip()
        signals: list[IntentSignal] = []

        # Check for search requirement
        search_required = needs_search(prompt)
        signals.append(IntentSignal(
            name="search_required",
            weight=0.8,
            matched=search_required,
            detail="Query classifier detected time-sensitive or factual query",
        ))

        # Check for vision keywords
        vision_matched = any(kw in prompt_lower for kw in self._VISION_KEYWORDS)
        signals.append(IntentSignal(
            name="vision_keywords",
            weight=0.6,
            matched=vision_matched,
            detail=f"Vision keywords found: {[kw for kw in self._VISION_KEYWORDS if kw in prompt_lower]}",
        ))

        # Check for speech keywords
        speech_matched = any(kw in prompt_lower for kw in self._SPEECH_KEYWORDS)
        signals.append(IntentSignal(
            name="speech_keywords",
            weight=0.5,
            matched=speech_matched,
            detail=f"Speech keywords found: {[kw for kw in self._SPEECH_KEYWORDS if kw in prompt_lower]}",
        ))

        # Check for filesystem keywords
        fs_matched = any(kw in prompt_lower for kw in self._FILESYSTEM_KEYWORDS)
        signals.append(IntentSignal(
            name="filesystem_keywords",
            weight=0.4,
            matched=fs_matched,
            detail=f"Filesystem keywords found: {[kw for kw in self._FILESYSTEM_KEYWORDS if kw in prompt_lower]}",
        ))

        # Check for tool keywords
        tool_matched = any(kw in prompt_lower for kw in self._TOOL_KEYWORDS)
        signals.append(IntentSignal(
            name="tool_keywords",
            weight=0.4,
            matched=tool_matched,
            detail=f"Tool keywords found: {[kw for kw in self._TOOL_KEYWORDS if kw in prompt_lower]}",
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
