"""The `translate` intent, and the instruction that makes it worth having.

Translating is one of the five jobs a local model does well, and the one a
bare prompt serves worst: asked to translate, a model explains its choices,
offers alternatives and prefaces the result — which the person then trims
before pasting. The intent exists so the request reaches the model as an
instruction for the translation alone. Same capability, same model, a
different sentence in front of it; the pattern `document` already uses.

Same three-part agreement `test_code_intent.py` asserts: an `IntentType`
member, exemplars the router can match, and a plan that does something the
default plan does not. None of these needs an embedder.
"""

from __future__ import annotations

from core.capability_router import IntentBasedRouter
from core.planner import IntentClassification, IntentType, _translation_prompt
from core.retrieval.exemplars import INTENT_EXEMPLARS


class TestTheIntentExists:
    def test_the_enum_the_exemplars_and_the_router_agree(self):
        assert IntentType("translate") is IntentType.TRANSLATE
        assert INTENT_EXEMPLARS.get("translate")
        assert IntentBasedRouter.get_capability_candidates("translate") == ["reasoning.generate"]

    def test_the_exemplars_are_things_a_person_would_type_and_name_a_language_or_the_act(self):
        for phrasing in INTENT_EXEMPLARS["translate"]:
            assert len(phrasing.split()) >= 4, phrasing
            assert "translat" in phrasing or any(
                lang in phrasing for lang in ("French", "Spanish", "German", "Yoruba", "English", "Portuguese")
            ), phrasing


class TestTheInstruction:
    def test_it_asks_for_the_translation_and_nothing_else(self):
        text = _translation_prompt("translate this into French: the invoice is due on Friday")
        assert "Output only the translation" in text
        assert "No preamble" in text
        assert "the invoice is due on Friday" in text

    def test_a_missing_language_is_asked_for_not_guessed(self):
        """Rule 9, one surface earlier."""
        assert "ask which" in _translation_prompt("translate this")


class TestThePlan:
    def _planner(self):
        from core.planner import IntentPlanner

        planner = IntentPlanner.__new__(IntentPlanner)
        planner._router = type(
            "R",
            (),
            {
                "classify": staticmethod(
                    lambda prompt: IntentClassification(
                        intent_type=IntentType.TRANSLATE,
                        confidence=0.9,
                        capabilities=["reasoning.generate"],
                    )
                )
            },
        )()
        planner._coding_project_is_open = lambda: False
        return planner

    def test_a_translation_request_is_one_step_with_the_derived_instruction(self):
        plan = self._planner().create_plan("translate this into French: see you Monday")
        assert len(plan.steps) == 1
        step = plan.steps[0]
        assert step.capability_id == "reasoning.generate"
        assert step.input_data["prompt"] == _translation_prompt("translate this into French: see you Monday")

    def test_a_picture_keeps_the_generic_path(self):
        """The instruction assumes text the model can already see; a picture
        has to reach the model first, by the attachment path."""
        plan = self._planner().create_plan("translate this into French", has_images=True)
        assert plan.steps[0].input_data["prompt"] == "translate this into French"


# ---------------------------------------------------- measured, with bge-m3


def _live_router():
    """The real router over the real embedder, or a skip — a hash backend
    would produce routes that look like data and are not."""
    import json
    import os
    import urllib.request

    import pytest

    try:
        host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        with urllib.request.urlopen(f"{host}/api/tags", timeout=2) as response:
            names = {m["name"] for m in json.loads(response.read())["models"]}
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Ollama is not reachable ({type(exc).__name__})")
    if not any(n.startswith("bge-m3") for n in names):  # pragma: no cover
        pytest.skip("bge-m3 is not installed")

    from core.retrieval import SemanticIndex, SemanticIntentRouter
    from runtimes.memory.embeddings import create_embedding_service

    service = create_embedding_service(backend="ollama", dim=1024, ollama_model="bge-m3")
    router = SemanticIntentRouter(SemanticIndex(service))
    assert router.is_semantic()
    return router, service


class TestItRoutesOnTheRealEmbedder:
    """Measured, not assumed: a new intent can steal from its neighbours,
    and `translate` sits nearest `document` ("write this up") and
    `conversation`. Skipped where bge-m3 is not resident."""

    def test_translation_requests_route_to_translate(self):
        router, service = _live_router()
        for prompt in (
            "translate this into French",
            "can you put this email in Spanish",
            "what's that in German",
        ):
            decision = router.route(prompt)
            assert not service._degraded
            assert decision is not None and decision.intent == "translate", (prompt, decision)

    def test_its_neighbours_keep_their_routes(self):
        router, _ = _live_router()
        for prompt, intent in (
            ("write that up as a proposal", "document"),
            ("why does this function return None", "code"),
            ("what is in this image", "vision"),
        ):
            decision = router.route(prompt)
            assert decision is not None and decision.intent == intent, (prompt, decision)
