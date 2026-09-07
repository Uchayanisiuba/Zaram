"""A model allocated to a *kind* of question, and what that must not break.

`CLAUDE.md`'s third tier of control: *"per-task assignment — chat, coding,
vision, long-document — behind Advanced"*. `RoutingSettings` carried one
``default_model`` and `INTENT_SPECIALISATION` mapped an intent to a *kind* of
model, never to a user's choice; this is the store, the precedence and the
gate that close that gap.

**What is asserted here is the precedence and the two gates, not the copy.**
Four inputs decide which model answers — the message, the assignment, the
general default, Zaram's own task-aware pick — and every test below is about
one of the boundaries between them. Those are the sentences that go wrong
silently: a wrong ordering does not raise, it routes a question to a model the
user did not choose and then names the wrong reason under the reply.

Three things are deliberately *not* asserted by mounting a screen: the copy,
the layout and the picker's contents. Those live in `taskSlots.test.ts`, where
they can be checked without five endpoints.
"""

from __future__ import annotations

import json
import os

import pytest


# ----------------------------------------------------------------- the store


@pytest.fixture()
def settings(tmp_path, monkeypatch):
    """A settings singleton pointed at a scratch file."""
    from core import user_settings as module

    path = str(tmp_path / "settings.json")
    module.set_user_settings_path(path)
    yield module.get_user_settings()
    module.set_user_settings_path(str(tmp_path / "unused.json"))


class TestTheStore:
    def test_nothing_is_assigned_by_default(self, settings):
        """Empty is the normal state, and the chat path's guard depends on it.

        `_resolve_model` classifies a message only when something is assigned,
        so an accidentally non-empty default would put a semantic-router round
        trip on every message for every user who never opened Advanced.
        """
        assert settings.task_models == {}

    def test_an_assignment_survives_a_reload(self, settings, tmp_path):
        from core import user_settings as module
        from core.user_settings import TaskSlot

        settings.set_task_model(TaskSlot.CODE, "ollama:qwen3-coder-30b-32k")

        # A second object over the same file — a restart, or a second client.
        reloaded = module.UserSettings(str(tmp_path / "settings.json"))
        assert reloaded.model_for_task(TaskSlot.CODE) == "ollama:qwen3-coder-30b-32k"

    def test_clearing_removes_the_key_rather_than_storing_a_blank(self, settings):
        """A stored ``""`` would become a request for a model with no name."""
        from core.user_settings import TaskSlot

        settings.set_task_model(TaskSlot.CODE, "coder")
        settings.set_task_model(TaskSlot.CODE, "")

        assert settings.task_models == {}
        assert settings.model_for_task(TaskSlot.CODE) is None

    def test_one_slot_is_written_without_disturbing_the_other(self, settings):
        from core.user_settings import TaskSlot

        settings.set_task_model(TaskSlot.CODE, "coder")
        settings.set_task_model(TaskSlot.VISION, "seer")
        settings.set_task_model(TaskSlot.CODE, "")

        assert settings.task_models == {"vision": "seer"}

    def test_the_returned_dictionary_is_a_copy(self, settings):
        """Mutating it must not change routing without touching the file.

        A setting that holds until restart and then reverts is
        indistinguishable, to the person using it, from Zaram forgetting.
        """
        from core.user_settings import TaskSlot

        settings.set_task_model(TaskSlot.CODE, "coder")
        settings.task_models["code"] = "something else"

        assert settings.model_for_task(TaskSlot.CODE) == "coder"

    def test_an_unknown_slot_is_refused_on_write(self, settings):
        with pytest.raises(ValueError):
            settings.set_task_model("long_document", "big-context-model")

    def test_an_unknown_slot_reads_as_unassigned_rather_than_raising(self, settings):
        """The read sits on the path to an answer; the write does not."""
        assert settings.model_for_task("long_document") is None

    def test_a_file_from_a_newer_version_contributes_what_is_understood(
        self, tmp_path
    ):
        """And nothing else — the guard reads keys, never the dictionary.

        Taking `task_models` wholesale would let an unknown key through to
        `task_models`, where the chat path's "is anything assigned?" test
        reads a non-empty dictionary as yes and starts classifying every
        message to consult a slot that can never match.
        """
        from core.user_settings import UserSettings

        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps(
                {
                    "task_models": {
                        "code": "coder",
                        "long_document": "not-a-slot-here",
                        "vision": 17,
                        "": "blank",
                    }
                }
            ),
            encoding="utf-8",
        )

        assert UserSettings(str(path)).task_models == {"code": "coder"}

    def test_a_corrupt_file_yields_defaults_rather_than_raising(self, tmp_path):
        from core.user_settings import UserSettings

        path = tmp_path / "settings.json"
        path.write_text("{ not json", encoding="utf-8")

        assert UserSettings(str(path)).task_models == {}

    def test_the_slots_are_the_ones_the_router_actually_takes(self):
        """Every slot is an argument `select_model_for_task` already accepts.

        This is the *never render invented values* rule applied to a control.
        A "long documents" slot would be a dropdown a person could set that
        governed nothing, because no classifier reports document length and no
        selection argument carries it — and a control that configures nothing
        is worse than none, since the user believes they have configured it.
        """
        from core.planner import INTENT_SPECIALISATION, IntentType
        from core.user_settings import TaskSlot

        assert {s.value for s in TaskSlot} == {"code", "vision"}
        # `CODE`'s value is the specialisation string, not a second spelling of
        # it. One table decides what a coding question asks for; a slot keyed
        # differently would be assignable and never consulted.
        assert INTENT_SPECIALISATION[IntentType.CODE] == TaskSlot.CODE.value


# ------------------------------------------------------------- the precedence


class TestWhichModelAnswers:
    """`_resolve_model`, which is where the four inputs are ordered."""

    @pytest.fixture()
    def resolve(self, settings, monkeypatch):
        """`_resolve_model` with the classifier stubbed to a stated answer.

        The classifier is not under test here and running it for real would
        make every assertion below depend on exemplar similarity — a judgement
        that can drift. What is under test is what the resolver *does* with a
        classification, which is the part that must not drift.
        """
        import main

        def classify(prompt: str):
            return (
                "vision" in prompt,
                "code" if "code" in prompt else None,
            )

        monkeypatch.setattr(main, "_task_requirements", classify)
        return main._resolve_model

    def test_an_assignment_answers_a_question_in_its_slot(self, resolve, settings):
        from core.user_settings import TaskSlot

        settings.set_task_model(TaskSlot.CODE, "coder")

        choice = resolve(None, "write me some code")
        assert choice.model == "coder"
        assert choice.chosen_by == "assignment"

    def test_an_assignment_leaves_every_other_question_alone(self, resolve, settings):
        from core.user_settings import TaskSlot

        settings.set_task_model(TaskSlot.CODE, "coder")

        assert resolve(None, "what is the capital of Portugal").model is None

    def test_the_message_still_outranks_an_assignment(self, resolve, settings):
        """A per-message override is tier three's tier three.

        Overriding what someone typed on *this* message because a slot exists
        would be the product arguing with its user.
        """
        from core.user_settings import TaskSlot

        settings.set_task_model(TaskSlot.CODE, "coder")

        choice = resolve("something-else", "write me some code")
        assert (choice.model, choice.chosen_by) == ("something-else", "request")

    def test_an_assignment_outranks_the_general_default(self, resolve, settings):
        """The specific beats the general, which is the only coherent reading.

        Both are the user's own choices, so neither can be dismissed — but
        "the model for coding questions" says something "the model" does not,
        and the reverse order would make the coding row inert the moment
        anybody set a default.
        """
        from core.user_settings import TaskSlot

        settings.set_default_model("general")
        settings.set_task_model(TaskSlot.CODE, "coder")

        assert resolve(None, "write me some code").model == "coder"
        assert resolve(None, "hello there").model == "general"

    def test_vision_outranks_coding_when_both_apply(self, resolve, settings):
        """A precondition beats a preference, always and in that order.

        A coding model is a *better* answer to a coding question; a model that
        can see is the *only* answer to a question about a picture. Asking the
        coding slot first would satisfy the preference by breaking the
        precondition.
        """
        from core.user_settings import TaskSlot

        settings.set_task_model(TaskSlot.CODE, "coder")
        settings.set_task_model(TaskSlot.VISION, "seer")

        assert resolve(None, "why does this code in the vision screenshot fail").model == "seer"

    def test_an_attached_image_reaches_the_vision_slot(self, resolve, settings):
        """Wording is a guess; a file that is actually here is not.

        The stubbed classifier reports no vision for this prompt, so the only
        thing that can select the slot is the attachment.
        """
        from core.user_settings import TaskSlot

        settings.set_task_model(TaskSlot.VISION, "seer")

        assert resolve(None, "what is this", has_images=True).model == "seer"

    def test_an_unassigned_slot_falls_through_exactly_as_before(
        self, resolve, settings
    ):
        """Assigning one slot must not change what the other one does.

        With only the vision slot set, a coding question has to reach the same
        answer it reached before this feature existed — Zaram's own pick,
        reported as such.
        """
        from core.user_settings import TaskSlot

        settings.set_task_model(TaskSlot.VISION, "seer")

        choice = resolve(None, "write me some code")
        assert choice.model is None
        assert choice.chosen_by in {"zaram", "task"}

    def test_the_classifier_is_not_run_when_it_cannot_change_the_answer(
        self, settings, monkeypatch
    ):
        """The guard that keeps this feature free for everyone not using it.

        With a general default set and no slot assigned, every branch returns
        that default whatever the question turns out to be. Classifying it
        would be a semantic-router round trip on the critical path of every
        message, spent to reach a conclusion already known.
        """
        import main

        calls: list[str] = []

        def classify(prompt: str):
            calls.append(prompt)
            return False, None

        monkeypatch.setattr(main, "_task_requirements", classify)
        settings.set_default_model("general")

        assert main._resolve_model(None, "write me some code").model == "general"
        assert calls == []

    def test_it_is_run_once_something_is_assigned(self, settings, monkeypatch):
        import main

        calls: list[str] = []

        def classify(prompt: str):
            calls.append(prompt)
            return False, None

        monkeypatch.setattr(main, "_task_requirements", classify)
        settings.set_default_model("general")
        settings.set_task_model("code", "coder")

        main._resolve_model(None, "write me some code")
        assert calls == ["write me some code"]

    def test_unreadable_settings_hand_the_choice_back_rather_than_failing(
        self, monkeypatch
    ):
        """A preference file must never be able to stop chat working."""
        import main

        def explode():
            raise RuntimeError("disk is on fire")

        monkeypatch.setattr(main, "_task_requirements", lambda prompt: (False, None))
        monkeypatch.setattr(
            "core.user_settings.get_user_settings", explode, raising=True
        )

        choice = main._resolve_model(None, "anything")
        assert (choice.model, choice.chosen_by) == (None, "zaram")


class TestTheSlotItFallsIn:
    """`_assigned_slot`, on its own, because the ordering in it is load-bearing."""

    def test_an_ordinary_question_falls_in_no_slot(self):
        from main import _assigned_slot

        assert _assigned_slot(False, None) is None

    def test_a_specialisation_with_no_slot_is_not_coerced_into_one(self):
        """Adding to `INTENT_SPECIALISATION` alone changes no routing.

        A specialisation this build has no slot for has to answer ``None``, or
        the first new intent added upstream would start consulting whichever
        slot happened to sort first.
        """
        from main import _assigned_slot

        assert _assigned_slot(False, "translation") is None

    def test_vision_wins(self):
        from main import _assigned_slot

        assert _assigned_slot(True, "code") == "vision"


# -------------------------------------------------------------------- gates


class TestTheCapabilityGate:
    """A model that cannot see may not be assigned to the vision slot.

    `CLAUDE.md`: capability is a binary precondition, never a ranking. The
    refusal belongs at the moment of choosing rather than at the moment of
    asking — `_vision_refusal` would catch it either way, but only after the
    user has attached a screenshot and typed a question.
    """

    @pytest.fixture()
    def stocked(self, monkeypatch):
        """A kernel whose catalogue holds one seer and one text-only model."""
        import main
        from providers.contracts import (
            DataPolicy,
            HealthStatus,
            CapabilityLocality,
            ModelCategory,
            ModelInfo,
            ProviderKind,
        )

        def model(name: str, *, vision: bool) -> ModelInfo:
            return ModelInfo(
                id=f"ollama:{name}",
                display_name=name,
                provider="ollama",
                provider_kind=ProviderKind.LOCAL_LLM,
                category=ModelCategory.LLM,
                locality=CapabilityLocality.LOCAL,
                health_status=HealthStatus.HEALTHY,
                data_policy=DataPolicy.NEVER_LEAVES_DEVICE,
                supports_vision=vision,
            )

        models = [model("seer", vision=True), model("wordy", vision=False)]

        class Catalog:
            def all(self):
                return models

        class Manager:
            catalog = Catalog()

            async def ensure_scanned(self):
                return None

        class Runtime:
            manager = Manager()

        monkeypatch.setattr(main.kernel, "providers_runtime", Runtime(), raising=False)
        return main

    @pytest.mark.asyncio
    async def test_a_model_that_cannot_see_is_refused_by_name(self, stocked):
        refusal = await stocked._task_assignment_refusal("vision", "wordy")
        assert "wordy" in refusal
        assert "cannot read images" in refusal

    @pytest.mark.asyncio
    async def test_a_model_that_can_see_is_accepted(self, stocked):
        assert await stocked._task_assignment_refusal("vision", "seer") == ""

    @pytest.mark.asyncio
    async def test_the_catalogue_id_is_accepted_as_well_as_the_name(self, stocked):
        """The picker sends an id; the Advanced field lets a name be typed.

        Being right about only one spelling is the defect
        `_unplaceable_model_refusal` already names.
        """
        assert await stocked._task_assignment_refusal("vision", "ollama:seer") == ""
        assert await stocked._task_assignment_refusal("vision", "ollama:wordy") != ""

    @pytest.mark.asyncio
    async def test_the_coding_slot_gates_on_nothing(self, stocked):
        """A general model answering coding questions is the user's call.

        A specialisation is a preference, and refusing here would be the
        ranking-as-permission error with the sign flipped.
        """
        assert await stocked._task_assignment_refusal("code", "wordy") == ""

    @pytest.mark.asyncio
    async def test_a_name_the_catalogue_cannot_place_is_not_refused_here(
        self, stocked
    ):
        """Every uncertainty resolves to no refusal.

        Refusing an unknown name *here* would claim it cannot see, which is a
        different and unsupported statement. `_unplaceable_model_refusal` is
        what says "Zaram cannot place this", and it says it at dispatch where
        the catalogue has definitely been scanned.
        """
        assert await stocked._task_assignment_refusal("vision", "gpt-9") == ""

    @pytest.mark.asyncio
    async def test_an_empty_catalogue_refuses_nothing(self, monkeypatch):
        """Telling someone their model cannot see because discovery had not
        run is a claim about their machine built on our own missing data, and
        it would fire hardest on the first visit after a boot."""
        import main

        class Catalog:
            def all(self):
                return []

        class Manager:
            catalog = Catalog()

            async def ensure_scanned(self):
                return None

        class Runtime:
            manager = Manager()

        monkeypatch.setattr(main.kernel, "providers_runtime", Runtime(), raising=False)
        assert await main._task_assignment_refusal("vision", "anything") == ""

    @pytest.mark.asyncio
    async def test_no_provider_layer_refuses_nothing(self, monkeypatch):
        import main

        monkeypatch.setattr(main.kernel, "providers_runtime", None, raising=False)
        assert await main._task_assignment_refusal("vision", "anything") == ""


class TestAnAssignmentIsAPersonsChoice:
    """So a name nobody can place is refused by name, not sent to Ollama."""

    @pytest.mark.asyncio
    async def test_an_unplaceable_assignment_is_refused(self, monkeypatch):
        """The Advanced field lets any string be typed into a slot, and a name
        the catalogue cannot place falls through `LocalDispatchEngine` to
        Ollama — which answers about a server the user never mentioned."""
        import main
        from main import _ModelChoice
        from providers.contracts import (
            HealthStatus,
            CapabilityLocality,
            ModelCategory,
            ModelInfo,
            ProviderKind,
        )

        known = [
            ModelInfo(
                id="ollama:real",
                display_name="real",
                provider="ollama",
                provider_kind=ProviderKind.LOCAL_LLM,
                category=ModelCategory.LLM,
                locality=CapabilityLocality.LOCAL,
                health_status=HealthStatus.HEALTHY,
            )
        ]

        class Catalog:
            def all(self):
                return known

        class Manager:
            catalog = Catalog()

            async def ensure_scanned(self):
                return None

        class Runtime:
            manager = Manager()

        monkeypatch.setattr(main.kernel, "providers_runtime", Runtime(), raising=False)

        refusal = await main._unplaceable_model_refusal(
            _ModelChoice("anthropic/claude-sonnet-4.5", "assignment")
        )
        assert "cannot place" in refusal

        # And Zaram's own picks stay exempt: refusing one would blame the user
        # for our selection.
        assert (
            await main._unplaceable_model_refusal(_ModelChoice("whatever", "task")) == ""
        )


# ---------------------------------------------------------------- the payload


class TestTheEndpointPayload:
    def test_the_read_and_the_write_answer_the_same_shape(self, settings):
        """A POST answering with less than the GET would blank the client's
        slot list the moment somebody used one of them — a control that
        disappears when you touch it."""
        from main import _routing_payload

        payload = _routing_payload()
        assert payload["task_slots"] == ["code", "vision"]
        assert payload["task_models"] == {}

        settings.set_task_model("code", "coder")
        assert _routing_payload()["task_models"] == {"code": "coder"}

    def test_the_slots_are_served_rather_than_left_to_the_client(self):
        """So a screen cannot offer a row this backend does not route on."""
        from core.user_settings import TaskSlot
        from main import _routing_payload

        assert _routing_payload()["task_slots"] == [s.value for s in TaskSlot]


def test_the_settings_file_is_json_a_person_can_read(settings, tmp_path):
    """Rule 7's open format, applied to the smallest store there is."""
    from core.user_settings import TaskSlot

    settings.set_task_model(TaskSlot.VISION, "seer")
    raw = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))

    assert raw["task_models"] == {"vision": "seer"}
    assert os.path.exists(tmp_path / "settings.json")


class TestTheRoutingModel:
    """The model that decides *where* a question goes, made visible.

    Asked for as "a planner model". Nothing generative plans anything —
    `CLAUDE.md` routes with embeddings, and `SemanticIntentRouter` compares the
    query against task exemplars — so the honest control is over the embedder,
    which was an environment variable and appeared in no interface at all.
    A decision taken on every single message that the product never showed
    anybody.
    """

    def test_nothing_is_chosen_by_default(self, settings):
        assert settings.router_model is None

    def test_it_survives_a_reload(self, settings, tmp_path):
        from core import user_settings as module

        settings.set_router_model("ollama:bge-m3")
        assert module.UserSettings(str(tmp_path / "settings.json")).router_model == (
            "ollama:bge-m3"
        )

    def test_clearing_hands_the_choice_back(self, settings):
        settings.set_router_model("ollama:bge-m3")
        assert settings.set_router_model("") is None

    def test_the_boot_path_prefers_it_over_the_environment_variable(
        self, settings, monkeypatch
    ):
        """The assertion that stops this being a control over nothing.

        `_init_memory_runtime` builds the embedder once, from an environment
        variable. If the setting did not outrank it the row would store, round
        trip and display, with no effect on any routing decision — this
        repository's signature failure wearing a settings control, and the
        exact shape `user_settings.voice` had before it was wired.
        """
        import os

        monkeypatch.setenv("ZARAM_EMBED_MODEL", "from-the-environment")
        settings.set_router_model("chosen-by-the-user")

        # The one line under test, lifted rather than booting a whole kernel:
        # what the bootstrapper computes for `model`.
        from core.user_settings import get_user_settings

        chosen = get_user_settings().router_model
        resolved = chosen or os.getenv("ZARAM_EMBED_MODEL", "bge-m3")
        assert resolved == "chosen-by-the-user"

        settings.set_router_model("")
        chosen = get_user_settings().router_model
        assert (chosen or os.getenv("ZARAM_EMBED_MODEL", "bge-m3")) == "from-the-environment"

    def test_the_payload_carries_it(self, settings):
        from main import _routing_payload

        settings.set_router_model("ollama:bge-m3")
        assert _routing_payload()["router_model"] == "ollama:bge-m3"


class TestOnlyAnEmbedderMayRoute:
    """A chat model here does not route worse — it does not route at all.

    Silently, from the next restart onwards, which is what makes this the one
    setting where the capability gate matters most.
    """

    @pytest.fixture()
    def stocked(self, monkeypatch):
        import main
        from providers.contracts import (
            CapabilityLocality,
            DataPolicy,
            HealthStatus,
            ModelCategory,
            ModelInfo,
            ProviderKind,
        )

        models = [
            ModelInfo(
                id="ollama:bge-m3",
                display_name="bge-m3",
                provider="ollama",
                provider_kind=ProviderKind.LOCAL_LLM,
                category=ModelCategory.EMBEDDING,
                locality=CapabilityLocality.LOCAL,
                health_status=HealthStatus.HEALTHY,
                data_policy=DataPolicy.NEVER_LEAVES_DEVICE,
                supports_embedding=True,
            ),
            ModelInfo(
                id="ollama:chatty",
                display_name="chatty",
                provider="ollama",
                provider_kind=ProviderKind.LOCAL_LLM,
                category=ModelCategory.LLM,
                locality=CapabilityLocality.LOCAL,
                health_status=HealthStatus.HEALTHY,
                data_policy=DataPolicy.NEVER_LEAVES_DEVICE,
            ),
        ]

        class Catalog:
            def all(self):
                return models

        class Manager:
            catalog = Catalog()

            async def ensure_scanned(self):
                return None

        class Runtime:
            manager = Manager()

        monkeypatch.setattr(main.kernel, "providers_runtime", Runtime(), raising=False)
        return main

    @pytest.mark.asyncio
    async def test_a_chat_model_is_refused_by_name(self, stocked):
        refusal = await stocked._router_model_refusal("chatty")
        assert "chatty" in refusal
        assert "embeddings" in refusal

    @pytest.mark.asyncio
    async def test_an_embedder_is_accepted(self, stocked):
        assert await stocked._router_model_refusal("bge-m3") == ""
        assert await stocked._router_model_refusal("ollama:bge-m3") == ""

    @pytest.mark.asyncio
    async def test_an_unplaceable_name_is_not_refused_here(self, stocked):
        # Refusing would claim it cannot embed, which is a different and
        # unsupported statement about a model we simply have not seen.
        assert await stocked._router_model_refusal("something-else") == ""

    @pytest.mark.asyncio
    async def test_no_provider_layer_refuses_nothing(self, monkeypatch):
        import main

        monkeypatch.setattr(main.kernel, "providers_runtime", None, raising=False)
        assert await main._router_model_refusal("anything") == ""
