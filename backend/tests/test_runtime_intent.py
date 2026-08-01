# backend/tests/test_runtime_intent.py
"""Unit tests for the Runtime_Intent (IntentPlanner/IntentRouter)."""
from __future__ import annotations

import pytest

from core.planner import IntentPlanner, IntentRouter, IntentType, IntentClassification
from core.contracts import ExecutionPlan, PlanState, ExecutionStep


class TestIntentRouter:
    def setup_method(self):
        self.router = IntentRouter()

    def test_classify_conversation(self):
        result = self.router.classify("Explain recursion")
        assert result.intent_type == IntentType.CONVERSATION
        assert result.confidence > 0.5
        assert "reasoning.generate" in result.capabilities

    def test_classify_search(self):
        result = self.router.classify("What is the latest AI news today?")
        assert result.intent_type == IntentType.MULTI_STEP
        assert result.requires_search is True

    def test_classify_vision(self):
        result = self.router.classify("What is in this image?")
        assert result.intent_type == IntentType.VISION
        assert result.requires_vision is True

    def test_classify_speech(self):
        result = self.router.classify("Please speak this aloud")
        assert result.intent_type == IntentType.SPEECH
        assert result.requires_speech is True

    def test_classify_filesystem(self):
        result = self.router.classify("Find the config file")
        assert result.intent_type == IntentType.FILESYSTEM

    def test_classify_tool(self):
        result = self.router.classify("Run git status")
        assert result.intent_type == IntentType.TOOL

    def test_classify_multi_step(self):
        result = self.router.classify("What is the latest Unreal Engine version?")
        assert result.intent_type == IntentType.MULTI_STEP
        assert result.requires_search is True

    def test_classify_short_prompt(self):
        result = self.router.classify("hi")
        assert result.intent_type == IntentType.CONVERSATION

    def test_get_capability_for_intent(self):
        assert self.router.get_capability_for_intent(IntentType.CONVERSATION) == "reasoning.generate"
        assert self.router.get_capability_for_intent(IntentType.SEARCH) == "knowledge.search"
        assert self.router.get_capability_for_intent(IntentType.VISION) == "vision.analyze"
        assert self.router.get_capability_for_intent(IntentType.SPEECH) == "speech.tts"


class TestIntentPlanner:
    def setup_method(self):
        self.planner = IntentPlanner()

    def test_create_plan_conversation(self):
        plan = self.planner.create_plan("Explain recursion")
        assert plan.original_prompt == "Explain recursion"
        assert plan.state == PlanState.PENDING
        assert len(plan.steps) == 1
        assert plan.steps[0].capability_id == "reasoning.generate"

    def test_create_plan_search(self):
        plan = self.planner.create_plan("What is the latest AI news today?")
        assert len(plan.steps) == 2
        assert plan.steps[0].capability_id == "knowledge.search"
        assert plan.steps[1].capability_id == "reasoning.generate"
        assert plan.steps[1].depends_on == [0]

    def test_create_plan_no_search_for_timeless(self):
        plan = self.planner.create_plan("How does Python work?")
        assert len(plan.steps) == 1
        assert plan.steps[0].capability_id == "reasoning.generate"

    def test_create_plan_skips_search_with_marker(self):
        from core.query_classifier import SEARCH_MARKER
        prompt = f"{SEARCH_MARKER}\nSource: test\nWhat is the latest?"
        plan = self.planner.create_plan(prompt)
        assert len(plan.steps) == 1
        assert plan.steps[0].capability_id == "reasoning.generate"

    def test_create_plan_has_correlation_id(self):
        plan = self.planner.create_plan("test prompt")
        assert plan.correlation_id is not None
        assert len(plan.correlation_id) > 0

    def test_classify_intent(self):
        classification = self.planner.classify_intent("What is the weather today?")
        assert classification.intent_type == IntentType.MULTI_STEP
        assert classification.requires_search is True

    def test_create_plan_from_intent(self):
        classification = IntentClassification(
            intent_type=IntentType.SEARCH,
            confidence=0.9,
            capabilities=["knowledge.search", "reasoning.generate"],
            requires_search=True,
        )
        plan = self.planner.create_plan_from_intent("What is the latest news?", classification)
        assert len(plan.steps) == 2
        assert plan.steps[0].capability_id == "knowledge.search"
        assert plan.steps[1].capability_id == "reasoning.generate"
