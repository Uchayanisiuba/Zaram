"""Code Zaram writes reaches the Spine, tagged as Zaram's.

**The gap was argued *for* by the code that had it.** `core/transcript.py`
justifies dropping the oldest turns rather than summarising them like this:

    Everybody else compacts aggressively because the transcript is their only
    memory. Zaram has a second store: facts from an old turn are in the Spine,
    with provenance, and recall brings them back when they are relevant.

True of what the user said. False of what Zaram said — `_remember` stores the
user's words and never the reply. So when a code exchange fell out of the
window it was gone: not summarised, not recalled, not recoverable. The second
store did not cover the case the maintainer reported, which was a code answer
followed by "fix the bug in it".

**Why this is safe, and it is not that the blocks are small.** Rule 7b:
*"generated artifacts are indexed by default — the protection against Zaram
citing its own restatements is origin tagging, not exclusion"*. That protection
is wired: `Origin.GENERATED` is persisted and migrated, and `MemoryRanker`
subtracts `GENERATED_PENALTY`, so a user source saying the same thing wins.
Storing generated text without that tag would recreate the exact failure that
made this codebase stop storing whole exchanges — Zaram citing itself.

**Fenced blocks only.** Prose in a reply is the model restating what it was
told, which is the material that caused the failure above. A fenced block is an
artifact that happens to have no file, and rule 7b already indexes generated
artifacts by default.

**Independent of the fact gate**, which is the structural point one test below
pins directly: "write me a function" is an *instruction*, and
`_carries_new_information` refuses instructions — correctly, since it is not a
fact about the user. Downstream of that gate this would never run on the exact
turn it exists for.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from core.contracts import Capability, RuntimeMetadata, RuntimeState
from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.registry import RuntimeRegistry
from runtimes.memory.contracts import Origin
from runtimes.models.engines.routed_engine import RoutedEngine
from runtimes.models.models_service import ModelsService

MODEL = "a-local-model"

CODE = "\n".join(f"    line_{i} = compute(i)  # step {i}" for i in range(40))
REPLY_WITH_CODE = "Here you go:\n```python\n" + CODE + "\n```\nThat should do it."


@dataclass
class _Stored:
    content: str
    origin: Any
    tags: tuple[str, ...]


class _Engine:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        images: list[str] | None = None,
    ) -> Iterator[str]:
        yield self.answer


class _Memory:
    def __init__(self) -> None:
        self.stored: list[_Stored] = []

    async def retrieve(self, query: str, max_results: int = 5, **kw):
        return []

    async def remember(self, content: str, **kw):
        self.stored.append(
            _Stored(
                content=content,
                origin=kw.get("origin"),
                tags=tuple(kw.get("tags") or ()),
            )
        )
        return content


class _MemoryRuntime:
    def __init__(self, service: _Memory) -> None:
        self._service = service

    async def retrieve(self, *a, **kw):
        return await self._service.retrieve(*a, **kw)

    async def remember(self, *a, **kw):
        return await self._service.remember(*a, **kw)

    def get_runtime_id(self):
        return "memory"

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id="memory",
            version="1.0.0",
            capabilities=[Capability(id="memory.retrieve", runtime_id="memory")],
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


def _engine(answer: str) -> tuple[ExecutionEngine, _Memory]:
    memory = _Memory()
    registry = RuntimeRegistry(EventBus())
    model = _Engine(answer)
    registry.register(
        _ModelsRuntime(
            ModelsService(RoutedEngine(local=model, cloud=model, is_remote=lambda m: False))
        )
    )
    registry.register(_MemoryRuntime(memory))
    return ExecutionEngine(registry, EventBus()), memory


def _generated(memory: _Memory) -> list[_Stored]:
    return [s for s in memory.stored if s.origin is Origin.GENERATED]


class TestItReachesTheSpine:
    def test_a_code_answer_is_stored(self):
        """**The assertion this file exists for.**

        The extraction working is not evidence that anything was kept — a
        helper that returns blocks nobody stores is this repository's signature
        failure, and every test about the regex would pass under it.
        """
        engine, memory = _engine(REPLY_WITH_CODE)

        list(engine.execute("write me a function that computes this", MODEL, "", "s"))

        kept = _generated(memory)
        assert kept, "the code Zaram wrote never reached the Spine"
        assert "line_39" in kept[0].content

    def test_it_is_tagged_as_zarams_own(self):
        """`Origin.GENERATED` is the whole safety argument. Untagged, this
        would recreate the failure that made storing exchanges stop: Zaram
        citing its own restatements back at the user as a source."""
        engine, memory = _engine(REPLY_WITH_CODE)

        list(engine.execute("write me a function", MODEL, "", "s"))

        kept = _generated(memory)
        assert kept[0].origin is Origin.GENERATED
        assert "generated" in kept[0].tags

    def test_the_request_travels_with_the_block(self):
        """A later query is prose — "fix the bug in adjust_quantity" — and a
        bare block gives the embedder nothing prose-shaped to match on."""
        engine, memory = _engine(REPLY_WITH_CODE)

        list(engine.execute("write me an InventoryLedger class", MODEL, "", "s"))

        assert "InventoryLedger" in _generated(memory)[0].content


class TestItDoesNotWaitForTheFactGate:
    def test_an_instruction_still_keeps_its_code(self):
        """**The structural point.**

        "write me a function" is an instruction, and
        `_carries_new_information` refuses instructions — rightly, it is not a
        fact about the user. That refusal is also the commonest way to ask for
        code, so a version of this placed after the gate would never run on the
        turn it was built for.
        """
        engine, memory = _engine(REPLY_WITH_CODE)

        assert not engine._carries_new_information("write me a function that sums a list")

        list(engine.execute("write me a function that sums a list", MODEL, "", "s"))

        assert _generated(memory), "the fact gate swallowed the generated block"

    def test_a_question_still_keeps_its_code(self):
        engine, memory = _engine(REPLY_WITH_CODE)

        list(engine.execute("how would I write this in Python?", MODEL, "", "s"))

        assert _generated(memory)


class TestItStoresLittleAndRarely:
    def test_prose_replies_store_nothing(self):
        """Most replies contain no code and must add nothing to the Spine."""
        engine, memory = _engine("Lisbon is the capital of Portugal.")

        list(engine.execute("what is the capital of Portugal?", MODEL, "", "s"))

        assert _generated(memory) == []

    def test_a_one_line_block_is_noise(self):
        engine, memory = _engine("Run this:\n```bash\npip install zaram\n```")

        list(engine.execute("how do I install it?", MODEL, "", "s"))

        assert _generated(memory) == []

    def test_a_reply_full_of_variations_is_capped(self):
        """Three renderings of one function should not become three
        near-identical records."""
        block = "```python\n" + CODE + "\n```\n"
        engine, memory = _engine("Options:\n" + block * 5)

        list(engine.execute("show me some options", MODEL, "", "s"))

        assert len(_generated(memory)) <= ExecutionEngine.GENERATED_PER_TURN

    def test_an_enormous_block_is_skipped_rather_than_cut(self):
        """Half a function is the fabrication half a message is, and
        `transcript.fit` refuses that for the same reason."""
        huge = "x = 1\n" * 4000
        engine, memory = _engine("```python\n" + huge + "```")

        list(engine.execute("write me something long", MODEL, "", "s"))

        assert _generated(memory) == []


class TestItCannotCostTheAnswer:
    def test_a_failing_write_still_replies(self):
        """A Spine that will not take the block costs the block, never the
        reply the user is waiting for."""
        engine, memory = _engine(REPLY_WITH_CODE)

        async def _boom(*a, **kw):
            raise RuntimeError("disk is full")

        memory.remember = _boom  # type: ignore[assignment]

        events = list(engine.execute("write me a function", MODEL, "", "s"))

        assert events, "the reply must survive a failed artifact write"
