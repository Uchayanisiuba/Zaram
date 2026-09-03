"""Asked for a picture it cannot draw, Zaram says so.

Rule 9 — *generation must fail rather than invent* — in the medium it is
easiest to break it in. "Draw me a logo" handed to an ordinary chat model comes
back as a fluent paragraph about a picture that was never made, with nothing on
screen saying the image does not exist. That is not a degraded answer; it is a
confidently wrong one, and it is silent.

Three layers have to hold for that not to happen, and each of them is tested
here because each of them failed the other way round at least once during this
work:

1. **The intent has to be recognised as a request for a picture**, and not as a
   request to *look at* one. Every phrasing that asks for an image to be drawn
   contains a word from the vision keyword set, so the two would otherwise be
   reported together and the model gates would be ANDed into an empty field.
2. **The plan must not degrade to prose.** `_drop_unavailable_steps` exists to
   turn a keyword misroute into an ordinary reply, which is right for
   `tool.terminal` and catastrophic for `image.generate`.
3. **The runtime must refuse with a reason and a remedy**, because "images are
   unavailable" is not something a person can act on and "no image model is
   installed, here is what one costs" is.

And one gate that is about *models* rather than about the local pipeline: a
model that can read an image is not a model that can draw one, and asking for
the second must never return the first.
"""

from __future__ import annotations

import pytest

from artifacts.contracts import ArtifactKind
from artifacts.records import ArtifactRecords
from artifacts.service import ArtifactService
from artifacts.store import ArtifactStore
from core.planner import IntentRouter, IntentType
from imaging.contracts import Availability, GeneratedImage, ImageProgress, ImageRequest
from providers.contracts import (
    CapabilityLocality,
    DataPolicy,
    ModelCategory,
    ModelInfo,
)
from runtimes.images.runtime import GENERATE, ImagesRuntime


# ============================================================ the intent ===


class TestDrawingIsNotLooking:
    """The two image intents are opposite directions and must not merge."""

    @pytest.fixture
    def router(self):
        # No semantic router attached, so this exercises the keyword fallback —
        # the path that runs on a machine where Ollama is unreachable, which is
        # exactly where a misroute is least recoverable.
        return IntentRouter()

    @pytest.mark.parametrize(
        "prompt",
        [
            "draw me a picture of a lighthouse",
            "generate an image of a city street",
            "make me a logo for my studio",
            "create a picture of a robot",
        ],
    )
    def test_asking_for_a_picture_routes_to_drawing(self, router, prompt):
        classification = router.classify(prompt)
        assert classification.intent_type is IntentType.IMAGE
        assert classification.requires_image_output is True

    def test_asking_about_a_picture_still_routes_to_vision(self, router):
        classification = router.classify("what is in this image")
        assert classification.intent_type is IntentType.VISION
        assert classification.requires_vision is True
        assert classification.requires_image_output is False

    def test_the_two_requirements_are_never_both_set(self, router):
        """Because they would be ANDed, and nothing satisfies both.

        "draw me a picture" contains "picture", which is a vision keyword. With
        both flags set, model selection asks for something that can read images
        *and* emit them, empties the candidate list, and refuses for a reason
        nobody asked about.
        """
        classification = router.classify("draw me a picture of a lighthouse")
        assert classification.requires_image_output is True
        assert classification.requires_vision is False

    def test_drawing_up_a_contract_is_not_drawing(self, router):
        """The false positive a bare "draw" keyword would produce."""
        assert router.classify("draw up a contract for the client").intent_type is not (
            IntentType.IMAGE
        )

    def test_the_capability_is_the_one_the_runtime_registers(self, router):
        assert router.get_capability_for_intent(IntentType.IMAGE) == GENERATE


# ================================================= the plan does not degrade ===


class TestAnImageStepIsNeverTurnedIntoProse:
    def test_image_generate_survives_having_no_runtime(self):
        """The guard that stops rule 9's failure arriving by the back door.

        Every other capability is dropped when nothing is registered for it, so
        a keyword misroute becomes an ordinary reply instead of an internal
        error. Applied to `image.generate` that same kindness produces the
        worst output the product can make: a paragraph about a picture that
        does not exist.
        """
        from core.contracts import ExecutionPlan, ExecutionStep, PlanState
        from core.execution_engine import _NEVER_DEGRADE, ExecutionEngine

        assert GENERATE in _NEVER_DEGRADE

        class NothingIsRegistered:
            def resolve(self, capability_id):
                raise KeyError(capability_id)

        engine = ExecutionEngine.__new__(ExecutionEngine)
        engine._router = NothingIsRegistered()

        plan = ExecutionPlan(
            correlation_id="c",
            original_prompt="draw me a logo",
            steps=[ExecutionStep(capability_id=GENERATE, input_data={}, depends_on=[])],
            state=PlanState.PENDING,
            priority="normal",
            created_at=0.0,
        )

        kept = engine._drop_unavailable_steps(plan)
        assert [s.capability_id for s in kept.steps] == [GENERATE]

    def test_an_ordinary_misroute_still_degrades(self):
        """The behaviour the exception must not have broken."""
        from core.contracts import ExecutionPlan, ExecutionStep, PlanState
        from core.execution_engine import ExecutionEngine

        class NothingIsRegistered:
            def resolve(self, capability_id):
                raise KeyError(capability_id)

        engine = ExecutionEngine.__new__(ExecutionEngine)
        engine._router = NothingIsRegistered()

        plan = ExecutionPlan(
            correlation_id="c",
            original_prompt="what is my secret codeword",
            steps=[
                ExecutionStep(capability_id="tool.terminal", input_data={}, depends_on=[])
            ],
            state=PlanState.PENDING,
            priority="normal",
            created_at=0.0,
        )

        kept = engine._drop_unavailable_steps(plan)
        assert [s.capability_id for s in kept.steps] == ["reasoning.generate"]


# =========================================================== the refusal ===


class _CannotDraw:
    name = "nothing"

    def availability(self):
        return Availability(
            ok=False,
            reason="No image model is installed on this machine.",
            remedy="Put an SDXL checkpoint in the models folder (6.9 GB, one time)",
        )

    def generate(self, request, on_progress=None):  # pragma: no cover - never reached
        raise AssertionError("generate must not be called when nothing can draw")


class _Draws:
    """A provider that reports progress and hands back one real PNG."""

    name = "fake-sdxl"

    #: A 1x1 PNG. Real bytes, so the exporter's data-URI round trip is exercised
    #: rather than mocked — a made-up string would be refused for the wrong
    #: reason entirely.
    PIXEL = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000100ffff03000006000"
        "5573f2c2c0000000049454e44ae426082"
    )

    def availability(self):
        return Availability(ok=True)

    def describe(self):
        return "fake-sdxl"

    def generate(self, request: ImageRequest, on_progress=None):
        for step in range(1, request.steps + 1):
            if on_progress:
                on_progress(
                    ImageProgress(
                        step=step, total_steps=request.steps, index=1, count=request.count
                    )
                )
        return [
            GeneratedImage(png=self.PIXEL, width=1, height=1, seed=7 + i)
            for i in range(request.count)
        ]


@pytest.fixture
def service(tmp_path):
    return ArtifactService(
        ArtifactRecords(str(tmp_path / "artifacts.db")),
        ArtifactStore(tmp_path / "out"),
    )


class TestNothingCanDraw:
    @pytest.mark.asyncio
    async def test_it_refuses_rather_than_producing_anything(self, service):
        runtime = ImagesRuntime(service, _CannotDraw())
        result = await runtime.execute(GENERATE, {"prompt": "a logo for my studio"})

        assert result["success"] is False
        assert "artifact" not in result and "artifacts" not in result

    @pytest.mark.asyncio
    async def test_the_refusal_names_the_fix_and_its_size(self, service):
        """Disabled capabilities are visible, and a remedy without a cost is
        not a choice somebody on metered data can make."""
        runtime = ImagesRuntime(service, _CannotDraw())
        result = await runtime.execute(GENERATE, {"prompt": "a logo"})

        assert "No image model is installed" in result["error"]
        assert "GB" in result["remedy"]

    @pytest.mark.asyncio
    async def test_it_is_marked_as_cannot_rather_than_went_wrong(self, service):
        """So the caller can offer instead of apologising.

        The dispatcher reads this to choose `[ERROR]` over `[FALLBACK]`, and
        the difference matters: a fallback invites the engine to answer some
        other way, and the only other way available is prose.
        """
        runtime = ImagesRuntime(service, _CannotDraw())
        result = await runtime.execute(GENERATE, {"prompt": "a logo"})
        assert result["unavailable"] is True

    @pytest.mark.asyncio
    async def test_no_provider_at_all_refuses_the_same_way(self, service):
        """The state a machine is in before anything is installed."""
        runtime = ImagesRuntime(service, None)
        result = await runtime.execute(GENERATE, {"prompt": "a logo"})
        assert result["success"] is False
        assert result["unavailable"] is True

    @pytest.mark.asyncio
    async def test_an_empty_prompt_is_refused_before_anything_loads(self, service):
        runtime = ImagesRuntime(service, _Draws())
        result = await runtime.execute(GENERATE, {"prompt": "   "})
        assert result["success"] is False
        assert "nothing to draw" in result["error"]


class TestAPictureIsAnArtifactLikeAnyOther:
    @pytest.mark.asyncio
    async def test_it_lands_in_the_output_directory_with_a_record(self, service):
        runtime = ImagesRuntime(service, _Draws())
        result = await runtime.execute(
            GENERATE, {"prompt": "a lighthouse", "steps": 3}
        )

        assert result["success"] is True
        card = result["artifacts"][0]
        assert card["kind"] == ArtifactKind.IMAGE.value
        assert card["filename"].endswith(".png")
        assert card["exists"] is True

        # The record is what Work reads, and it has to describe the same file.
        stored = service.records.get(card["id"])
        assert stored is not None
        assert stored.kind is ArtifactKind.IMAGE

    @pytest.mark.asyncio
    async def test_the_file_on_disk_is_the_picture(self, service, tmp_path):
        """Not the HTML. The `.png` a user opens has to be a PNG.

        `ChartExporter` pulls the image back out of the artifact's HTML, so
        this is also the assertion that an image kind travels that path
        correctly rather than needing an exporter of its own.
        """
        runtime = ImagesRuntime(service, _Draws())
        result = await runtime.execute(GENERATE, {"prompt": "a lighthouse", "steps": 2})

        written = tmp_path / "out" / result["artifacts"][0]["filename"]
        assert written.read_bytes()[:8] == bytes.fromhex("89504e470d0a1a0a")

    @pytest.mark.asyncio
    async def test_the_prompt_the_model_and_the_seed_are_recorded(self, service):
        """An image's provenance. It has no sentences to trace, so what is
        traceable is what it was drawn from, by what, where, and with which
        seed — the only thing that makes the same picture askable for twice."""
        runtime = ImagesRuntime(service, _Draws())
        result = await runtime.execute(GENERATE, {"prompt": "a lighthouse", "steps": 2})

        html = service.records.get(result["artifacts"][0]["id"]).html
        assert "a lighthouse" in html
        assert "fake-sdxl" in html
        assert "nothing left the device" in html
        assert "Seed" in html

    @pytest.mark.asyncio
    async def test_a_batch_returns_every_picture(self, service):
        runtime = ImagesRuntime(service, _Draws())
        result = await runtime.execute(
            GENERATE, {"prompt": "a lighthouse", "steps": 2, "count": 3}
        )
        assert len(result["artifacts"]) == 3
        # Distinct files, not one record listed three times.
        assert len({a["id"] for a in result["artifacts"]}) == 3

    @pytest.mark.asyncio
    async def test_a_batch_larger_than_the_grid_is_clamped_not_refused(self, service):
        """Four is what the card's 2x2 grid holds and what the wait is worth."""
        runtime = ImagesRuntime(service, _Draws())
        result = await runtime.execute(
            GENERATE, {"prompt": "a lighthouse", "steps": 1, "count": 99}
        )
        assert len(result["artifacts"]) == 4

    @pytest.mark.asyncio
    async def test_progress_reaches_the_sink(self, service):
        """The channel the bar is drawn from.

        Asserted end to end through `execute` rather than against the provider,
        because the first version of this published events on the bus that
        nothing subscribed to — a complete, tested, unreachable channel, which
        is the failure shape this repository keeps finding.
        """
        seen: list[dict] = []
        runtime = ImagesRuntime(service, _Draws())
        await runtime.execute(
            GENERATE,
            {"prompt": "a lighthouse", "steps": 4, "progress_sink": seen.append},
        )

        assert [u["step"] for u in seen] == [1, 2, 3, 4]
        assert seen[-1]["percent"] == 100
        # And nothing that could hold a prediction.
        assert not any(
            "eta" in key or "remaining" in key or "seconds" in key
            for update in seen
            for key in update
        )

    @pytest.mark.asyncio
    async def test_the_card_says_the_picture_was_the_point(self, service):
        """What lets the preview open itself. This capability only runs when
        somebody asked for an image, so it is always true here — and it is
        transport only, never stored on the record."""
        runtime = ImagesRuntime(service, _Draws())
        result = await runtime.execute(GENERATE, {"prompt": "a lighthouse", "steps": 1})

        assert result["artifacts"][0]["deliberate"] is True
        stored = service.records.get(result["artifacts"][0]["id"])
        assert "deliberate" not in stored.to_dict()


# ================================================== reading is not drawing ===


def _model(model_id: str, *, category=ModelCategory.LLM, emits=(), vision=False):
    return ModelInfo(
        id=model_id,
        display_name=model_id,
        provider="test",
        category=category,
        supports_vision=vision,
        available=True,
        locality=CapabilityLocality.CLOUD,
        data_policy=DataPolicy.YOUR_KEY_NO_TRAINING,
        metadata={"output_modalities": list(emits)} if emits else {},
    )


class TestTheEmitImageGate:
    """`emits_image` is a precondition, and it is not `supports_vision`."""

    def test_a_model_that_only_reads_images_does_not_emit_them(self):
        assert _model("seer", vision=True).emits_image is False

    def test_output_modalities_are_what_decides(self):
        assert _model("drawer", emits=("image",)).emits_image is True

    def test_a_model_that_emits_both_still_counts(self):
        """It stays an `LLM` — it can hold the conversation — and it can still
        draw, so a category check alone would miss it."""
        model = _model("both", emits=("text", "image"))
        assert model.category is ModelCategory.LLM
        assert model.emits_image is True

    def test_a_dedicated_image_model_counts_without_metadata(self):
        assert _model("sdxl-api", category=ModelCategory.IMAGE).emits_image is True

    def test_a_plain_chat_model_does_not(self):
        assert _model("chatty").emits_image is False

    def test_it_is_reported_alongside_reading_rather_than_merged_with_it(self):
        payload = _model("seer", vision=True).to_dict()
        assert payload["supports_vision"] is True
        assert payload["emits_image"] is False
