"""A file that gave nothing back is mentioned in the conversation.

This is the seam M7's second half turns on, and it is the kind that unit tests
miss: `IngestRecords` can produce a perfect notice and `ChatSurface` can render
one beautifully while nothing connects them. Every real bug in this codebase so
far has lived in exactly that gap.

Knowledge showing a failure only helps a user who opens Knowledge, and someone
whose document was silently skipped has no reason to.
"""

from __future__ import annotations

from pathlib import Path

from core.bootstrapper import KernelBootstrapper
from core.contracts import Capability, Runtime, RuntimeMetadata, RuntimeState
from core.execution_engine import ExecutionEngine
from core.streaming_events import EventType, StreamEvent
from ingest.contracts import IngestOutcome, IngestStatus
from ingest.records import IngestRecords
from ingest.service_api import IngestService


class _Service:
    def generate_response(self, user_text, personality_context="", model=None):
        yield "Your day rate is 425,000."


class _Runtime:
    capability_id = "reasoning.generate"

    def __init__(self):
        self._state = RuntimeState.UNINITIALIZED
        self._service = _Service()

    def get_runtime_id(self):
        return "fake"

    def get_version(self):
        return "0.0.1"

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id="fake",
            version="0.0.1",
            priority="normal",
            capabilities=[Capability(id=self.capability_id, runtime_id="fake")],
        )

    async def initialize(self):
        self._state = RuntimeState.READY

    async def shutdown(self):
        self._state = RuntimeState.STOPPED

    def get_state(self):
        return self._state

    def health_check(self):
        return {"state": self._state.value}

    def get_service(self):
        return self._service


def _engine() -> ExecutionEngine:
    kernel = KernelBootstrapper()
    kernel.registry.register(_Runtime())
    return ExecutionEngine(kernel.registry, kernel.event_bus)


def _with_a_failed_file(tmp_path: Path) -> IngestService:
    records = IngestRecords(str(tmp_path / "ingest.db"))
    source_id = records.upsert_source(str(tmp_path / "harbour"))
    records.record_outcomes(source_id, [
        IngestOutcome(
            path=str(tmp_path / "harbour" / "scan-04.pdf"),
            status=IngestStatus.EMPTY,
            reason="No text layer — 2 pages of images (997 KB per page). It is a scan or a photo.",
            remedy="Reading scans needs OCR: pip install zaram[ingest] (321 MB, one time).",
        )
    ])
    return IngestService(records)


def _notices(items) -> list[StreamEvent]:
    return [
        i for i in items
        if isinstance(i, StreamEvent) and i.type is EventType.NOTICE
    ]


def test_the_unreadable_file_is_mentioned_in_the_reply(tmp_path: Path):
    engine = _engine()
    engine.set_notice_source(_with_a_failed_file(tmp_path).notice_text)

    items = list(engine.execute("what is my day rate"))

    notices = _notices(items)
    assert len(notices) == 1
    content = notices[0].data["content"]
    assert "scan-04.pdf" in content
    assert "321 MB" in content, "the remedy has to carry its cost"
    assert notices[0].data["action"] == "knowledge", "a notice needs somewhere to go"


def test_the_notice_comes_after_the_answer(tmp_path: Path):
    """The user asked a question; the answer is what they are waiting for.

    Interrupting with housekeeping first is how a warning gets trained away.
    """
    engine = _engine()
    engine.set_notice_source(_with_a_failed_file(tmp_path).notice_text)

    items = list(engine.execute("what is my day rate"))

    first_notice = next(i for i, x in enumerate(items) if x in _notices(items))
    last_token = max(i for i, x in enumerate(items) if isinstance(x, str))
    assert first_notice > last_token


def test_it_is_said_once_not_on_every_reply(tmp_path: Path):
    engine = _engine()
    engine.set_notice_source(_with_a_failed_file(tmp_path).notice_text)

    first = list(engine.execute("what is my day rate"))
    second = list(engine.execute("and my payment terms"))

    assert len(_notices(first)) == 1
    assert _notices(second) == [], "a warning that repeats is one the user skips"


def test_a_clean_ingest_says_nothing(tmp_path: Path):
    records = IngestRecords(str(tmp_path / "ingest.db"))
    source_id = records.upsert_source(str(tmp_path))
    records.record_outcomes(source_id, [
        IngestOutcome(path=str(tmp_path / "a.md"), status=IngestStatus.INDEXED, chars=900)
    ])
    engine = _engine()
    engine.set_notice_source(IngestService(records).notice_text)

    assert _notices(list(engine.execute("hello"))) == []


def test_no_notice_source_is_the_ordinary_case(tmp_path: Path):
    """Every test in the suite constructs an engine without one."""
    engine = _engine()

    items = list(engine.execute("hello"))

    assert _notices(items) == []
    assert any(isinstance(i, str) for i in items), "the answer still arrives"


def test_a_broken_notice_source_never_costs_the_answer(tmp_path: Path):
    """Housekeeping must not be able to take down a reply."""
    engine = _engine()

    def boom():
        raise RuntimeError("records exploded")

    engine.set_notice_source(boom)

    items = list(engine.execute("what is my day rate"))

    assert _notices(items) == []
    assert "".join(i for i in items if isinstance(i, str)).strip(), "the answer survived"


def test_the_notice_serialises_for_the_frontend(tmp_path: Path):
    """The wire shape the chat client parses."""
    import json

    engine = _engine()
    engine.set_notice_source(_with_a_failed_file(tmp_path).notice_text)

    notice = _notices(list(engine.execute("hi")))[0]
    payload = json.loads(notice.to_ipc())

    assert payload["type"] == "notice"
    assert payload["data"]["content"]
    assert payload["data"]["action"] == "knowledge"
