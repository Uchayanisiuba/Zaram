# backend/tests/test_execution_tokens.py
"""Unit tests for StreamEvent (Execution Tokens)."""
from __future__ import annotations

import json

import pytest

from core.streaming_events import StreamEvent, EventType
from core.contracts import ExecutionToken


class TestStreamEventCreation:
    def test_token_event(self):
        event = StreamEvent.token("hello", seq=1)
        assert event.type == EventType.TOKEN
        assert event.data["content"] == "hello"
        assert event.seq == 1

    def test_status_event(self):
        event = StreamEvent.status("complete", "test.cap")
        assert event.type == EventType.STATUS
        assert event.data["state"] == "complete"
        assert event.data["capability_id"] == "test.cap"

    def test_source_event(self):
        event = StreamEvent.source("web", url="https://example.com", title="Test")
        assert event.type == EventType.SOURCE
        assert event.data["kind"] == "web"
        assert event.data["url"] == "https://example.com"

    def test_error_event(self):
        event = StreamEvent.error("something went wrong")
        assert event.type == EventType.ERROR
        assert event.data["content"] == "something went wrong"

    def test_done_event(self):
        event = StreamEvent.done()
        assert event.type == EventType.DONE

    def test_start_event(self):
        event = StreamEvent.start("test.cap")
        assert event.type == EventType.START
        assert event.data["capability_id"] == "test.cap"

    def test_step_start_event(self):
        event = StreamEvent.step_start("test.cap", 0)
        assert event.type == EventType.STEP_START
        assert event.data["step_index"] == 0

    def test_step_complete_event(self):
        event = StreamEvent.step_complete("test.cap", 0, success=True)
        assert event.type == EventType.STEP_COMPLETE
        assert event.data["success"] is True

    def test_plan_start_event(self):
        event = StreamEvent.plan_start("corr-1", 3)
        assert event.type == EventType.PLAN_START
        assert event.data["step_count"] == 3

    def test_plan_complete_event(self):
        event = StreamEvent.plan_complete("corr-1", "completed")
        assert event.type == EventType.PLAN_COMPLETE
        assert event.data["state"] == "completed"

    def test_retry_event(self):
        event = StreamEvent.retry("test.cap", 1, 0.5)
        assert event.type == EventType.RETRY
        assert event.data["attempt"] == 1
        assert event.data["delay"] == 0.5

    def test_cancel_event(self):
        event = StreamEvent.cancel("corr-1", "user cancelled")
        assert event.type == EventType.CANCEL
        assert event.data["reason"] == "user cancelled"


class TestStreamEventSerialization:
    def test_to_ipc(self):
        event = StreamEvent.token("hello", seq=1, correlation_id="corr-1")
        ipc = event.to_ipc()
        data = json.loads(ipc)
        assert data["type"] == "token"
        assert data["data"]["content"] == "hello"
        assert data["seq"] == 1
        assert data["correlation_id"] == "corr-1"
        assert "ts" in data

    def test_to_ipc_done(self):
        event = StreamEvent.done()
        ipc = event.to_ipc()
        data = json.loads(ipc)
        assert data["type"] == "done"
        assert data["data"] == {}

    def test_to_ipc_error(self):
        event = StreamEvent.error("test error")
        ipc = event.to_ipc()
        data = json.loads(ipc)
        assert data["type"] == "error"
        assert data["data"]["content"] == "test error"


class TestExecutionTokenConversion:
    def test_to_execution_token(self):
        event = StreamEvent.token("hello world", seq=5)
        token = event.to_execution_token()
        assert token.token == "hello world"
        assert token.sequence == 5
        assert token.final is False

    def test_done_to_execution_token(self):
        event = StreamEvent.done()
        token = event.to_execution_token()
        assert token.final is True

    def test_token_metadata(self):
        event = StreamEvent.token("test", seq=1)
        token = event.to_execution_token()
        assert token.metadata["type"] == "token"
        assert "ts" in token.metadata
