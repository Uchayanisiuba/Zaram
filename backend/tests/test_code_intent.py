"""The `code` intent, and the wiring that makes it reach a model.

An intent is three things that have to agree: an `IntentType` member, a set of
exemplars the router can match a question against, and — for this one — an
entry in `INTENT_SPECIALISATION` saying which kind of model serves it. Any two
of the three without the third is a classification that changes nothing, which
is the shape most of this repository's dead subsystems had.

None of these assertions needs an embedder, which is the point: they check that
the parts are connected, and a routing test that needs Ollama running only ever
gets run on a machine where it passes.
"""

from __future__ import annotations

from core.planner import INTENT_SPECIALISATION, IntentType
from core.retrieval.exemplars import INTENT_EXEMPLARS, intent_candidates


class TestTheExemplarsAndTheEnumAgree:
    def test_every_exemplar_key_is_a_real_intent(self):
        """`_classify_semantically` logs a warning and hands back to keywords
        for an intent it cannot resolve, so a typo here does not fail loudly —
        it silently disables that intent's routing."""
        for name in INTENT_EXEMPLARS:
            assert IntentType(name), name

    def test_the_code_intent_has_exemplars(self):
        assert INTENT_EXEMPLARS.get("code")

    def test_the_exemplars_are_things_a_person_would_type(self):
        """The file's own rule, asserted rather than described.

        A category name measures how close the user came to *naming* the
        category, which is a different question from what they want. Bare
        labels are short, so length is a crude but real proxy — "code" and
        "coding" would fail this, "why does this function return None" passes.
        """
        for phrasing in INTENT_EXEMPLARS["code"]:
            assert len(phrasing.split()) >= 4, phrasing


class TestTheIntentReachesAModel:
    def test_code_asks_for_a_coding_model(self):
        assert INTENT_SPECIALISATION[IntentType.CODE] == "code"

    def test_the_specialisation_matches_what_model_names_produce(self):
        """The two ends of the same string.

        `INTENT_SPECIALISATION` supplies the value and
        `specialisation_from_name` derives the one stored on every model; they
        are compared with `==` inside the provider layer and nothing would
        report a mismatch. "coding" here and "code" there is a routing feature
        that silently never fires.
        """
        from providers.contracts import specialisation_from_name

        assert specialisation_from_name("qwen2.5-coder:14b") == "code"

    def test_every_specialisation_intent_can_be_reached(self):
        """A preferred model for an intent nothing can classify is dead code."""
        for intent in INTENT_SPECIALISATION:
            assert intent.value in INTENT_EXEMPLARS, intent

    def test_modality_is_not_in_the_specialisation_map(self):
        """Guarding the separation rather than describing it.

        Vision is a gate applied to the candidate set; specialisation is a
        preference applied to the ordering. The moment "vision" appears as a
        specialisation the two become one lookup, and the gate becomes
        something a larger model can outrank.
        """
        assert IntentType.VISION not in INTENT_SPECIALISATION
        assert "vision" not in set(INTENT_SPECIALISATION.values())


class TestTheRouterCanIndexIt:
    def test_the_code_intent_becomes_a_candidate(self):
        """`intent_candidates` is what the semantic index is built from, so an
        exemplar set the builder drops is one the router can never match."""
        ids = {candidate.id for candidate in intent_candidates()}

        assert "code" in ids
