"""What the assistant is allowed to say it is.

This is the class of thing that regresses without anybody noticing: every
component keeps passing, and the only symptom is that the product introduces
itself as somebody else's model. So the properties are asserted here rather
than left to a prompt string nobody re-reads.

The three that matter, in the order they would be lost:

* **Identity comes last in the prompt is wrong** — a persona opening "You are
  Nova" is an identity claim, and whichever one comes last tends to win. Order
  is asserted.
* **An unresolved model must not be described as local.** Routing answers
  "not remote" for anything it cannot resolve, because failing safe there means
  keeping data on the machine. Identity inheriting that would state as fact the
  one thing the user is most likely to check.
* **The model is named, never hidden.** The temptation, once the assistant
  stops saying "I am Qwen", is to make it say nothing at all. That would forfeit
  routing legibility and the product's best demonstration.
"""

from __future__ import annotations

import pytest

from core.identity import CLOUD, LOCAL, compose_system_prompt, identity_preamble


class TestWhatItSaysItIs:
    def test_names_zaram_and_denies_being_a_model(self):
        text = identity_preamble(model="qwen2.5:7b", locality=LOCAL)

        assert "You are Zaram." in text
        assert "not a language model" in text

    def test_names_the_model_that_is_actually_answering(self):
        # Hiding it would be the easy way to stop "I am Qwen", and it would cost
        # the thing the product is for: the model changes, the memory does not.
        text = identity_preamble(model="qwen2.5:7b", locality=LOCAL)

        assert "qwen2.5:7b" in text

    def test_tells_it_not_to_answer_identity_from_training(self):
        text = identity_preamble(model="qwen2.5:7b", locality=LOCAL)

        assert "training" in text

    def test_the_trainer_is_not_offered_as_zarams_maker(self):
        """The measured failure, 15 August 2026: *"I am Zaram, a language model
        created by Alibaba Cloud"*. The model took the name and kept its
        training's account of who made it, because one clause covered both
        halves and a small model read it as covering the nearer one."""
        text = identity_preamble(model="qwen2.5-coder:1.5b", locality=LOCAL)

        assert "not call yourself a language model" in text
        assert "Zaram's maker" in text

    def test_the_instructions_are_not_offered_as_material_to_repeat(self):
        """A rationale addressed to the model is a rationale the model can
        recite, and one did — answering "who are you" with *"I am trained by
        one lab, but I may be deployed as any model"*, which is the prompt's
        own reasoning in the first person. The reasons live in the module now;
        the prompt carries rules.

        The assertion is on the *contract*, not the sentence. It read
        ``"never quoted, listed or repeated back"`` verbatim and broke on 28
        August when the rule was **strengthened** to cover paraphrase — the
        recital came back as *"I also shouldn't treat the lab or company that
        trained the underlying answering model as the maker of me"*, which is
        none of quoted, listed or repeated. A test that fails when its contract
        is reinforced is pinning the wording, and it would have argued against
        the fix.
        """
        text = identity_preamble(model="qwen2.5:7b", locality=LOCAL)

        assert "never" in text and "repeated back" in text
        # The strengthening that the verbatim assertion used to forbid.
        assert "paraphrased" in text
        assert "not evidence" not in text


class TestLocalityIsNeverGuessed:
    def test_local_says_nothing_left_the_device(self):
        text = identity_preamble(model="qwen2.5:7b", locality=LOCAL)

        assert "running on this machine" in text
        assert "has left the device" in text

    def test_cloud_says_the_request_left(self):
        text = identity_preamble(model="gpt-4o", locality=CLOUD)

        assert "provider's servers" in text
        assert "left" in text

    def test_unknown_locality_names_the_model_and_claims_nothing_else(self):
        # The failure this guards: `_is_remote_model` returns False for an
        # unresolvable model, and a caller that treated False as "local" would
        # produce a preamble asserting nothing left the machine — on a request
        # that may have gone to a cloud provider.
        text = identity_preamble(model="something-unrecognised", locality=None)

        assert "something-unrecognised" in text
        assert "running on this machine" not in text
        assert "provider's servers" not in text

    def test_no_model_at_all_makes_no_claim_about_one(self):
        text = identity_preamble(model=None, locality=None)

        assert "You are Zaram." in text
        assert "Right now you are answering through" not in text

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_a_blank_model_name_is_the_same_as_none(self, blank):
        assert "Right now you are answering through" not in identity_preamble(model=blank)


class TestComposition:
    def test_identity_comes_before_the_voice(self):
        composed = compose_system_prompt(
            identity_preamble(model="qwen2.5:7b", locality=LOCAL),
            "Answer in as few words as the question genuinely needs.",
        )

        assert composed.index("You are Zaram.") < composed.index("as few words")

    def test_an_empty_voice_leaves_the_identity_alone(self):
        identity = identity_preamble(model="qwen2.5:7b", locality=LOCAL)

        assert compose_system_prompt(identity, "") == identity
        assert compose_system_prompt(identity, "   ") == identity


class TestThePersonasCarryNoIdentity:
    """The presets are voices now. None of them may claim to be someone.

    This is the assertion that would have caught the original defect: eight
    entries each opening "You are <name>, a <adjective> AI assistant", competing
    with the product's own identity and giving the model a third candidate
    answer to "what are you".
    """

    def test_no_preset_introduces_a_character(self):
        from main import PERSONAS

        for key, preset in PERSONAS.items():
            prompt = preset.get("system_prompt", "")
            assert "You are" not in prompt, (
                f"persona {key!r} makes an identity claim: {prompt[:80]!r}. "
                "Presets set tone; identity comes from core.identity."
            )

    def test_the_default_adds_no_tone_at_all(self):
        from main import PERSONAS

        assert PERSONAS["zaram_prime"]["system_prompt"] == ""

    def test_every_preset_still_carries_a_voice(self):
        # The presets were kept rather than deleted because the speech path
        # selects a Kokoro voice from them. If that stops being true they are
        # dead weight and should go.
        from main import PERSONAS

        for key, preset in PERSONAS.items():
            assert preset.get("voice"), f"persona {key!r} has no voice"
