"""Claude can be called in its own wire format, through the gate.

The catalogue entry for Anthropic read *"cannot call Claude directly yet"*
for as long as the catalogue existed, and the maintainer asked how to
"Claude in" on 13 September 2026. This is the adapter, and these are the
four things it must get right that the OpenAI-compatible engine gets right
for its own format:

* the body is built once and the gate sees exactly what leaves — including
  the system prompt, which on this API is a top-level field;
* a host with no policy is refused before a socket opens;
* the stream is parsed back into the engine contract: text, `<think>` tags
  for thinking, and the one-line marker for a tool call;
* images and tools travel in this API's shapes, not OpenAI's.

And the discoverer lists what the key can reach, with the window the
listing reports and no data policy it cannot know.
"""

from __future__ import annotations

import base64
import json

import pytest

from core.egress import EgressGate
from core.egress.log import EgressLog
from core.egress.policy import EgressPolicy
from core.reasoning import CLOSE_TAG, OPEN_TAG
from core.tool_loop import marker_for_native_call
from runtimes.models.engines.anthropic_engine import (
    ANTHROPIC_VERSION,
    AnthropicEngine,
    to_anthropic_tools,
)
from runtimes.models.engines.base_engine import ERROR_PREFIX

SECRET = "zzq-spine-only-marker-8f2a"
HOST = "api.anthropic.com"
PNG = base64.b64encode(bytes.fromhex("89504e470d0a1a0a") + b"\x00\x00\x00\rIHDR" + b"\x00" * 16).decode()


@pytest.fixture
def gate(tmp_path):
    """A real gate with its own log and policy — the property under test is
    that the gate is unavoidable, so a double would prove nothing."""
    return EgressGate(
        log=EgressLog(str(tmp_path / "egress.db")),
        policy=EgressPolicy(str(tmp_path / "policy.json")),
    )


@pytest.fixture
def engine(gate):
    return AnthropicEngine(api_key="sk-ant-test-not-real", default_model="claude-opus-5", gate=gate)


def _no_socket(monkeypatch) -> list[dict]:
    calls: list[dict] = []

    def fake_urlopen(request, **kwargs):
        calls.append({"url": getattr(request, "full_url", str(request))})
        raise AssertionError("a request reached the network in a test that expected a refusal")

    monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", fake_urlopen)
    return calls


def _sse(*events: dict) -> list[bytes]:
    """The wire, as the gate hands it back: one line at a time."""
    lines: list[bytes] = []
    for event in events:
        lines.append(f"event: {event['type']}".encode())
        lines.append(f"data: {json.dumps(event)}".encode())
        lines.append(b"")
    return lines


class TestTheBody:
    def test_the_system_prompt_is_a_top_level_field(self, engine):
        body = engine._body("what did I quote them?", SECRET, None)
        assert body["system"] == SECRET
        assert body["messages"] == [{"role": "user", "content": "what did I quote them?"}]
        assert body["model"] == "claude-opus-5"
        assert body["stream"] is True
        assert isinstance(body["max_tokens"], int) and body["max_tokens"] > 0
        assert "thinking" not in body  # omitted on purpose; see the module docstring

    def test_an_image_is_a_typed_block_with_its_real_media_type(self, engine):
        body = engine._body("what is this?", "", None, images=[PNG])
        content = body["messages"][0]["content"]
        assert [part["type"] for part in content] == ["image", "text"]
        assert content[0]["source"] == {"type": "base64", "media_type": "image/png", "data": PNG}
        assert engine._body_carries_images(body) is True

    def test_an_unidentifiable_image_is_refused_not_labelled(self, engine, monkeypatch):
        _no_socket(monkeypatch)
        chunks = list(engine.stream_response("x", "", images=[base64.b64encode(b"nonsense-bytes").decode()]))
        assert len(chunks) == 1 and chunks[0].startswith(ERROR_PREFIX)

    def test_openai_tools_become_anthropic_tools(self, engine):
        tools = [{"type": "function", "function": {
            "name": "code__read_lines", "description": "Read lines",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        }}, {"type": "function", "function": {"description": "nameless, dropped"}}]
        converted = to_anthropic_tools(tools)
        assert converted == [{
            "name": "code__read_lines", "description": "Read lines",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        }]
        assert engine._body("x", "", None, tools=tools)["tools"] == converted
        assert "tools" not in engine._body("x", "", None)


class TestNothingLeavesWithoutTheGate:
    def test_an_unapproved_host_is_refused_before_any_request(self, engine, monkeypatch):
        _no_socket(monkeypatch)
        chunks = list(engine.stream_response("what did I quote them?", SECRET))
        assert len(chunks) == 1
        assert chunks[0].startswith(ERROR_PREFIX)
        assert HOST in chunks[0]

    def test_the_refusal_is_in_the_log_and_the_key_is_not(self, engine, gate, monkeypatch):
        _no_socket(monkeypatch)
        list(engine.stream_response("hello", SECRET))
        (entry,) = gate.log.entries(limit=1)
        assert entry.decision == "denied"
        assert entry.host == HOST
        assert entry.url.endswith("/v1/messages")
        assert SECRET in (entry.body or "")  # what would have left is what is shown
        assert "sk-ant-test-not-real" not in json.dumps(entry.payload())


class TestTheStreamIsParsed:
    def test_text_thinking_and_a_tool_call(self):
        lines = _sse(
            {"type": "message_start", "message": {"id": "msg_1"}},
            {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "weigh it"}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "abc"}},
            {"type": "content_block_stop", "index": 0},
            {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Net "}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "45."}},
            {"type": "content_block_stop", "index": 1},
            {"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "tu_1", "name": "code__read_lines", "input": {}}},
            {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": '{"path": '}},
            {"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": '"a.py"}'}},
            {"type": "content_block_stop", "index": 2},
            {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 9}},
            {"type": "message_stop"},
        )
        out = list(AnthropicEngine._tokens(lines))
        assert out[:3] == [OPEN_TAG, "weigh it", CLOSE_TAG]
        assert out[3:5] == ["Net ", "45."]
        assert out[5] == marker_for_native_call("code__read_lines", '{"path": "a.py"}')
        assert len(out) == 6

    def test_empty_thinking_leaves_no_tags(self):
        """By default the API streams thinking blocks with empty text; an empty
        pair of tags would read as a reply that was all thinking."""
        lines = _sse(
            {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": ""}},
            {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": ""}},
            {"type": "content_block_stop", "index": 0},
            {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}},
            {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "hi"}},
            {"type": "content_block_stop", "index": 1},
        )
        assert list(AnthropicEngine._tokens(lines)) == ["hi"]

    def test_an_error_event_is_reported_in_band(self):
        lines = _sse({"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}})
        (only,) = list(AnthropicEngine._tokens(lines))
        assert only == ERROR_PREFIX + "Overloaded"


class TestTheDiscoverer:
    @pytest.mark.asyncio
    async def test_it_lists_what_the_key_reaches(self, monkeypatch):
        from providers.discoverers.anthropic import AnthropicAdapter

        seen: dict = {}

        def get(self, path, *, timeout):
            seen["path"] = path
            return {"data": [
                {"id": "claude-opus-5", "display_name": "Claude Opus 5", "type": "model",
                 "created_at": "2026-04-01T00:00:00Z", "max_input_tokens": 1_000_000},
                {"id": "claude-haiku-4-5", "display_name": "Claude Haiku 4.5", "type": "model"},
            ], "has_more": False}

        monkeypatch.setattr(AnthropicAdapter, "_get", get)
        models = await AnthropicAdapter(api_key="k").discover_models()
        assert seen["path"].startswith("/v1/models")
        opus, haiku = models
        assert opus.id == "anthropic:claude-opus-5" and opus.display_name == "Claude Opus 5"
        assert opus.context_length == 1_000_000 and haiku.context_length is None
        assert all(m.supports_vision and m.supports_tools for m in models)
        assert all(m.locality.name == "CLOUD" for m in models)
        assert all(m.data_policy is None for m in models)  # not inferred from a hostname

    @pytest.mark.asyncio
    async def test_a_provider_that_will_not_answer_yields_nothing(self, monkeypatch):
        from providers.discoverers.anthropic import AnthropicAdapter

        def get(self, path, *, timeout):
            raise RuntimeError("401")

        monkeypatch.setattr(AnthropicAdapter, "_get", get)
        assert await AnthropicAdapter(api_key="bad").discover_models() == []

    def test_the_headers_are_anthropics(self, monkeypatch):
        from providers.discoverers.anthropic import AnthropicAdapter

        captured: dict = {}

        class _Gate:
            def request(self, url, *, timeout, headers, source, **kw):
                captured.update(url=url, headers=headers, source=source)
                return b'{"data": []}'

        monkeypatch.setattr("core.egress.get_gate", lambda: _Gate())
        AnthropicAdapter(api_key="k")._get("/v1/models?limit=100", timeout=1.0)
        assert captured["url"] == "https://api.anthropic.com/v1/models?limit=100"
        assert captured["headers"]["x-api-key"] == "k"
        assert captured["headers"]["anthropic-version"] == ANTHROPIC_VERSION
        assert "Authorization" not in captured["headers"]


class TestTheCatalogueAndTheWiring:
    def test_claude_is_no_longer_greyed_out(self):
        from providers import catalogue

        entry = catalogue.get("anthropic")
        assert entry.available is True

    def test_the_native_entry_gets_the_native_pair(self):
        from providers.cloud_config import CloudConnection, _engine_for, _speaks_messages_api
        from providers.discoverers.anthropic import AnthropicAdapter  # noqa: F401

        assert _speaks_messages_api("anthropic") is True
        assert _speaks_messages_api("openrouter") is False
        assert _speaks_messages_api("something-pasted") is False
        engine = _engine_for(CloudConnection(
            provider_id="anthropic", base_url="https://api.anthropic.com", api_key="k", display_name="Claude",
        ))
        assert isinstance(engine, AnthropicEngine)
        assert engine.endpoint == "https://api.anthropic.com/v1/messages"
