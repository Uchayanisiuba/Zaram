"""The whole path, from what the user typed to what the card is drawn from.

Every piece of this was tested on its own before this file existed, and that is
exactly the state in which this repository has repeatedly shipped a complete,
tested subsystem nothing reaches. The pieces here are: the planner recognising
a request for a picture, the engine keeping that step rather than degrading it
to prose, the dispatcher streaming progress while the sampler runs, the runtime
writing an artifact, and the engine converting both marker lines into
`StreamEvent`s the conversation can render.

Five joins, and a failure at any one of them looks identical from either side —
which is why the assertion here is on the **event stream**, the thing the
frontend actually consumes, rather than on any of the five.

No model is involved and none is needed. An image request plans a single
`image.generate` step, so nothing asks a language model anything; that is a
property worth having and it is asserted below, because the moment a reasoning
step creeps into this plan, a text model is being given the opportunity to
describe a picture.
"""

from __future__ import annotations

import pytest

from artifacts.contracts import ArtifactKind
from artifacts.records import ArtifactRecords
from artifacts.service import ArtifactService
from artifacts.store import ArtifactStore
from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.registry import RuntimeRegistry
from core.streaming_events import EventType, StreamEvent
from imaging.contracts import Availability, GeneratedImage, ImageProgress
from runtimes.images.runtime import GENERATE, ImagesRuntime

#: A 1x1 PNG. Real bytes, so the data-URI round trip through `ChartExporter` is
#: exercised rather than mocked.
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000100ffff030000060005"
    "573f2c2c0000000049454e44ae426082"
)


class _Draws:
    name = "fake-sdxl"

    def availability(self):
        return Availability(ok=True)

    def describe(self):
        return "fake-sdxl"

    def generate(self, request, on_progress=None):
        for step in range(1, request.steps + 1):
            if on_progress:
                on_progress(
                    ImageProgress(
                        step=step,
                        total_steps=request.steps,
                        index=1,
                        count=request.count,
                    )
                )
        return [GeneratedImage(png=PIXEL, width=1, height=1, seed=99)]


class _CannotDraw:
    name = "nothing"

    def availability(self):
        return Availability(
            ok=False,
            reason="No image model is installed on this machine.",
            remedy="Put an SDXL checkpoint in the models folder (6.9 GB, one time)",
        )

    def generate(self, request, on_progress=None):  # pragma: no cover
        raise AssertionError("nothing should ask a provider that cannot draw")


def _engine(tmp_path, provider):
    """An engine wired exactly as the bootstrapper wires it, minus the models.

    `ImagesRuntime` is registered through the real `RuntimeRegistry`, so the
    capability is resolved by the real `CapabilityRouter` — the join that has
    been missing in every unreachable subsystem this repository has found.
    """
    registry = RuntimeRegistry(EventBus())
    service = ArtifactService(
        ArtifactRecords(str(tmp_path / "artifacts.db")),
        ArtifactStore(tmp_path / "out"),
    )
    runtime = ImagesRuntime(service, provider)
    registry.register(runtime)
    return ExecutionEngine(registry, EventBus()), service


def _events(engine, prompt="draw me a picture of a lighthouse at dawn"):
    """Run one exchange and collect what the conversation would receive."""
    return list(engine.execute(prompt, session_id="test-session"))


class TestTheImageReachesTheConversation:
    @pytest.fixture
    def drawn(self, tmp_path):
        engine, service = _engine(tmp_path, _Draws())
        return _events(engine), service, tmp_path

    def test_the_progress_bar_is_fed_while_it_draws(self, drawn):
        """The events the card's bar is drawn from, on the real stream.

        This is the join the first implementation got wrong in a way nothing
        would have caught: progress was published on the event bus, and the
        one place that could have forwarded it was blocked waiting for the
        generation to finish. Complete, tested, and reaching nobody.
        """
        events, _, _ = drawn
        progress = [
            e
            for e in events
            if isinstance(e, StreamEvent) and e.type is EventType.IMAGE_PROGRESS
        ]

        assert progress, "no progress reached the stream; the bar would never move"
        assert [e.data["step"] for e in progress] == list(
            range(1, len(progress) + 1)
        )
        assert progress[-1].data["percent"] == 100

    def test_no_event_carries_a_time_remaining(self, drawn):
        """The decision, asserted rather than described.

        Percentage and step count are measured off the sampler; seconds-left
        would be an extrapolation from nothing at the moment it would first be
        shown, and a confident wrong number is worse than no number.
        """
        events, _, _ = drawn
        for event in events:
            if isinstance(event, StreamEvent) and event.type is EventType.IMAGE_PROGRESS:
                assert not any(
                    "eta" in key or "remaining" in key or "seconds" in key
                    for key in event.data
                )

    def test_the_picture_arrives_as_an_artifact_card(self, drawn):
        events, _, _ = drawn
        artifacts = [
            e for e in events if isinstance(e, StreamEvent) and e.type is EventType.ARTIFACT
        ]

        assert len(artifacts) == 1
        card = artifacts[0].data
        assert card["kind"] == ArtifactKind.IMAGE.value
        assert card["filename"].endswith(".png")
        assert card["exists"] is True
        # What lets the preview open itself: the picture *was* the request.
        assert card["deliberate"] is True

    def test_the_bar_arrives_before_the_picture(self, drawn):
        """Order is the whole point of streaming progress at all."""
        events, _, _ = drawn
        kinds = [
            e.type
            for e in events
            if isinstance(e, StreamEvent)
            and e.type in (EventType.IMAGE_PROGRESS, EventType.ARTIFACT)
        ]
        assert kinds[0] is EventType.IMAGE_PROGRESS
        assert kinds[-1] is EventType.ARTIFACT

    def test_no_marker_line_reaches_the_reader(self, drawn):
        """A raw `[IMAGE_PROGRESS]` or `[ARTIFACT]` on screen is a visible bug.

        Both travel as marked strings because the dispatcher is typed as
        yielding strings; the engine converts them. If either survives as text
        that conversion is missing, and the user sees the plumbing.
        """
        events, _, _ = drawn
        text = "".join(e for e in events if isinstance(e, str))
        assert "[IMAGE_PROGRESS]" not in text
        assert "[ARTIFACT]" not in text

    def test_the_file_on_disk_is_a_png(self, drawn):
        _, _, tmp_path = drawn
        written = list((tmp_path / "out").iterdir())
        assert len(written) == 1
        assert written[0].read_bytes()[:8] == bytes.fromhex("89504e470d0a1a0a")

    def test_no_language_model_was_asked_anything(self, drawn):
        """The property that makes rule 9 structurally hard to break here.

        An image request plans one step and it is not a generation step, so
        there is no point at which a text model is given the chance to write
        about a picture. If a `reasoning.generate` step ever joins this plan,
        this fails — and it should, because that is the failure returning.
        """
        events, _, _ = drawn
        started = [
            e
            for e in events
            if isinstance(e, StreamEvent) and e.type is EventType.STEP_START
        ]
        for event in started:
            assert event.data.get("capability_id") != "reasoning.generate"


class TestNothingCanDrawOnThisMachine:
    def test_the_reason_and_the_remedy_reach_the_reader(self, tmp_path):
        """A refusal is only useful if it says what would fix it.

        And it must be *visible*: the whole failure being prevented is the
        silent one, where a picture is not made and nothing says so.
        """
        engine, _ = _engine(tmp_path, _CannotDraw())
        events = _events(engine)

        text = "".join(e for e in events if isinstance(e, str))
        errors = "".join(
            str(e.data.get("content", ""))
            for e in events
            if isinstance(e, StreamEvent) and e.type is EventType.ERROR
        )
        said = text + errors

        assert "No image model is installed" in said
        assert "6.9 GB" in said

    def test_nothing_was_written(self, tmp_path):
        engine, _ = _engine(tmp_path, _CannotDraw())
        _events(engine)
        assert list((tmp_path / "out").iterdir()) == []

    def test_no_artifact_card_is_claimed(self, tmp_path):
        """Under-claiming is recoverable; over-claiming is not. A card for a
        picture that was never drawn is the second."""
        engine, _ = _engine(tmp_path, _CannotDraw())
        events = _events(engine)
        assert not [
            e for e in events if isinstance(e, StreamEvent) and e.type is EventType.ARTIFACT
        ]
