"""A second question is answered knowing what the first one was.

**Measured before it was fixed**, against the running backend on 29 August
2026, one model, one session, seconds apart:

    "What is the capital of Portugal?"        -> "Lisbon."
    "And roughly how many people live there?" -> "I don't have the place you're
                                                 referring to in this
                                                 conversation. Which city,
                                                 country, or region are you
                                                 asking about?"

Everything needed was already built. `_session_turns` recorded the exchange,
`seed_session_turns` rehydrated it from stored transcripts across a restart,
`core/transcript.fit` trimmed it to a model's window by whole turns, and
`as_prompt` rendered it — and the single caller was the *document* branch, so
none of it reached an ordinary reply. `core/transcript.as_prompt` and
`as_messages` had tests and no production caller at all, which is this
repository's signature failure arriving one more time, on the daily-driver
path.

The two branches stay distinct rather than merging, and the tests below pin
that: the document path also reports whether there was anything to resolve
against, because rule 9's refusal hangs off that flag, and an ordinary reply
carries no such duty. What must never happen is both, which would put the same
exchange in front of the model twice under two headings.

**This is not memory, and one test says so directly.** Rule 7d keeps
conversation ephemeral; the buffer dies with the process and nothing here
writes to the Spine.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from core.contracts import Capability, RuntimeMetadata, RuntimeState
from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.registry import RuntimeRegistry
from core.streaming_events import StreamEvent
from runtimes.models.engines.routed_engine import RoutedEngine
from runtimes.models.models_service import ModelsService

CLOUD_MODEL = "a-cloud-model"
LOCAL_MODEL = "a-local-model"

FIRST = "What is the capital of Portugal?"
LISBON = "Lisbon."
FOLLOW_UP = "And roughly how many people live there?"


class RecordingEngine:
    """Answers a fixed line and remembers how it was asked."""

    def __init__(self, name: str, answer: str = LISBON) -> None:
        self.name = name
        self.answer = answer
        self.calls: list[tuple[str, str, str | None]] = []
        self.default_model: str | None = None

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        images: list[str] | None = None,
    ) -> Iterator[str]:
        self.calls.append((prompt, system_prompt, model))
        yield self.answer

    @property
    def last_system_prompt(self) -> str:
        assert self.calls, f"{self.name} was never called"
        return self.calls[-1][1]


class _ModelsRuntime:
    def __init__(self, service: ModelsService) -> None:
        self._service = service

    def get_runtime_id(self):
        return "models"

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id="models",
            version="1.0.0",
            capabilities=[Capability(id="reasoning.generate", runtime_id="models")],
        )

    def get_service(self):
        return self._service

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    def get_state(self):
        return RuntimeState.READY

    def health_check(self):
        return {"state": "ready"}


class Conversation:
    """The engine with two providers and no memory runtime.

    **Deliberately no Spine.** What is being tested is the ephemeral half, and
    a recall runtime would make it impossible to tell which store answered —
    which is exactly the confusion that let this gap survive.
    """

    def __init__(self, answer: str = LISBON) -> None:
        self.local = RecordingEngine("local", answer)
        self.cloud = RecordingEngine("cloud", answer)
        registry = RuntimeRegistry(EventBus())
        registry.register(
            _ModelsRuntime(
                ModelsService(
                    RoutedEngine(
                        local=self.local,
                        cloud=self.cloud,
                        is_remote=lambda model: model == CLOUD_MODEL,
                    )
                )
            )
        )
        self.engine = ExecutionEngine(registry, EventBus())

    def ask(self, prompt: str, model: str = LOCAL_MODEL, session_id: str = "one") -> str:
        tokens: list[str] = []
        for item in self.engine.execute(prompt, model, "", session_id):
            if not isinstance(item, StreamEvent):
                tokens.append(item)
        return "".join(tokens)


@pytest.fixture
def chat() -> Conversation:
    return Conversation()


class TestTheFollowUpSeesTheExchange:
    def test_the_previous_question_and_answer_reach_the_model(self, chat):
        """The failure this file is named for, in its smallest form."""
        chat.ask(FIRST)
        chat.ask(FOLLOW_UP)

        block = chat.local.last_system_prompt
        assert FIRST in block, "the model was not shown what was asked before"
        assert LISBON in block, "the model was not shown its own previous answer"

    def test_a_first_turn_carries_no_heading(self, chat):
        """Nothing to follow, so nothing is claimed."""
        chat.ask(FIRST)

        assert "CONVERSATION SO FAR" not in chat.local.last_system_prompt

    def test_a_different_session_starts_clean(self, chat):
        """Two windows are two conversations."""
        chat.ask(FIRST, session_id="one")
        chat.ask(FOLLOW_UP, session_id="two")

        assert FIRST not in chat.local.last_system_prompt

    def test_the_oldest_turns_fall_away(self, chat):
        """`CONVERSATION_TURNS` bounds what is shown, not what is kept."""
        for i in range(6):
            chat.ask(f"Question number {i}.")
        chat.ask(FOLLOW_UP)

        block = chat.local.last_system_prompt
        assert "Question number 5." in block
        assert "Question number 0." not in block


class TestItCrossesAModelSwitch:
    def test_asked_of_one_provider_and_followed_up_on_another(self, chat):
        """The buffer is keyed on the session, never on the model.

        This is the measurement the 29 August handoff offered to run live and
        the reason it is worth having as a test instead: the property is that
        `_session_turns` has no model in it at all, and a test can say that
        about *both* engines in a second rather than three minutes.
        """
        chat.ask(FIRST, model=LOCAL_MODEL, session_id="shared")
        chat.ask(FOLLOW_UP, model=CLOUD_MODEL, session_id="shared")

        block = chat.cloud.last_system_prompt
        assert FIRST in block
        assert LISBON in block

    def test_and_back_the_other_way(self, chat):
        chat.ask(FIRST, model=CLOUD_MODEL, session_id="shared")
        chat.ask(FOLLOW_UP, model=LOCAL_MODEL, session_id="shared")

        assert FIRST in chat.local.last_system_prompt


class TestTheTwoBranchesStayApart:
    """The branch is forced rather than phrased, and that is on purpose.

    **Which prompts are document requests is a separate question, and the two
    classifiers disagree.** A bare `IntentPlanner` — what a test process gets —
    reads *"Write that up as a proposal document."* as `CONVERSATION`, while
    the semantic router the backend actually boots read *"Now add ten to that
    number."* as a document request on 29 August and silently wrote a `.docx`.
    Pinning either phrasing here would make these tests assert the classifier's
    current mood instead of the branch, so the branch is selected directly.
    """

    @staticmethod
    def _as_a_document_request(chat):
        chat.engine._is_document_request = lambda prompt: True

    def test_a_document_request_keeps_its_own_framing(self, chat):
        """The document path is unchanged, wording included.

        Rule 9's refusal hangs off `context_resolved`, which only that path
        produces, so merging the two would quietly remove the flag that decides
        whether a proposal is written or refused.
        """
        chat.ask(FIRST)
        self._as_a_document_request(chat)
        chat.ask("Write that up as a proposal.")

        block = chat.local.last_system_prompt
        assert "The document is about this:" in block

    def test_the_exchange_is_never_sent_twice(self, chat):
        """One heading or the other, never both."""
        chat.ask(FIRST)
        self._as_a_document_request(chat)
        chat.ask("Write that up as a proposal.")

        block = chat.local.last_system_prompt
        assert block.count(FIRST) == 1
        assert "CONVERSATION SO FAR" not in block


class TestItIsBounded:
    def test_one_enormous_turn_is_dropped_whole(self):
        """`fit` drops turns; it never cuts sentences.

        Half a message attributed to a person is a fabrication, so the honest
        outcome for a turn that cannot fit is that it does not appear — not a
        truncated version of it that reads as something the user said.
        """
        chat = Conversation(answer="x" * 40_000)
        chat.ask(FIRST)
        chat.ask(FOLLOW_UP)

        block = chat.local.last_system_prompt
        assert "xxxx" not in block
        assert "CONVERSATION SO FAR" not in block

    def test_the_block_stays_inside_the_smallest_window(self, chat):
        """The cap is a quarter of a 4,096-token model's input budget.

        Asserted as a number rather than a proportion because the point is the
        machine at the bottom of the range: a model loaded with Ollama's
        default must still have room for recall and the question. Turns long
        enough that three pairs would overrun it, so the cap is doing work
        rather than sitting above the traffic.
        """
        from core.context_budget import estimate_tokens

        for i in range(6):
            chat.ask(f"Question number {i}. " + "words " * 120)
        chat.ask(FOLLOW_UP)

        block = chat.local.last_system_prompt
        start = block.index("=== THE CONVERSATION SO FAR ===")

        assert estimate_tokens(block[start:]) <= 1024
        # And it kept something: a cap that admits nothing would also pass the
        # assertion above.
        assert "Question number 5." in block


class TestNoneOfThisIsMemory:
    def test_nothing_is_written_to_the_spine(self, chat):
        """Rule 7d, asserted where it would be easiest to break.

        There is no memory runtime registered here at all, so the fact that two
        turns of conversation reach the model proves the ephemeral buffer did
        it. If a future change routed this through recall instead, the engine
        would need a Spine and this test would fail.
        """
        chat.ask(FIRST)
        chat.ask(FOLLOW_UP)

        assert chat.engine._memory_runtime() is None
        assert FIRST in chat.local.last_system_prompt

    def test_the_buffer_dies_with_the_engine(self, chat):
        """A new engine over the same session id starts empty."""
        chat.ask(FIRST, session_id="shared")

        fresh = Conversation()
        fresh.ask(FOLLOW_UP, session_id="shared")

        assert FIRST not in fresh.local.last_system_prompt
