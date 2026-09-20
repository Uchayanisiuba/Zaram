"""The provider layer has a real tool-call channel, and the loop cannot tell.

`core/tool_loop.py` called the text marker "the honest intermediate" and said
the marker parser would be the one function to change when the provider layer
grew a native channel. Built 12 September 2026, with a different cut: **the
engines put the tools on the wire and re-emit any call as the marker**, so
`parse_call`, the gate, the budget, the stripper and every test double see
exactly what they saw before. What changed is who writes the call — the
server's template and grammar rather than the model's memory of an example.

Three engines, one contract:

* Ollama: ``tools`` sends the request through ``/api/chat`` (``/api/generate``
  has no such field), only for a model whose capabilities include ``tools``;
  ``message.tool_calls`` become markers after ``message.content``.
* OpenAI-compatible (TabbyAPI, LM Studio, OpenRouter, the paid providers):
  ``tools`` goes in the body; ``delta.tool_calls`` arrive split across frames
  by ``index`` and are assembled, then emitted at ``[DONE]``.
* The wrappers — routed, local-dispatch, cloud fan-out — pass ``tools`` (and,
  fixed on the way past, ``images``) through unchanged.

And the plumbing: the execution engine converts the offered tools once and
puts them on the generation step and on every follow-up in the loop, and the
dispatcher hands them to the service only when there are some.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from core.tool_loop import (
    TOOL_CALL_MARKER,
    marker_for_native_call,
    native_tool_specs,
    parse_call,
    split_native_name,
)


OFFERED = [
    {
        "server": "code",
        "name": "read_lines",
        "description": "Read a range of lines from a file.\nMore text.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "start": {"type": "integer"}},
            "required": ["path"],
        },
    },
    {"server": "blender", "name": "list_objects", "description": "List scene objects."},
]


class TestTheWireShape:
    def test_specs_are_openai_functions_named_server__tool(self):
        specs = native_tool_specs(OFFERED)
        assert [s["type"] for s in specs] == ["function", "function"]
        assert specs[0]["function"]["name"] == "code__read_lines"
        assert specs[1]["function"]["name"] == "blender__list_objects"

    def test_the_mcp_schema_travels_as_parameters(self):
        specs = native_tool_specs(OFFERED)
        assert specs[0]["function"]["parameters"]["required"] == ["path"]
        # No schema: an empty object, which is "no arguments" in that vocabulary.
        assert specs[1]["function"]["parameters"] == {"type": "object", "properties": {}}

    def test_the_description_is_flattened_and_bounded(self):
        long = [{"server": "s", "name": "t", "description": "x " * 1000}]
        spec = native_tool_specs(long)[0]["function"]
        assert "\n" not in spec["description"]
        assert len(spec["description"]) <= 400
        assert native_tool_specs(OFFERED)[0]["function"]["description"] == (
            "Read a range of lines from a file. More text."
        )

    def test_a_name_with_the_separator_is_left_off_rather_than_encoded_wrongly(self):
        specs = native_tool_specs([{"server": "my__server", "name": "t"}, {"server": "ok", "name": "t"}])
        assert [s["function"]["name"] for s in specs] == ["ok__t"]

    def test_names_are_sanitised_to_what_the_provider_accepts(self):
        spec = native_tool_specs([{"server": "code", "name": "read.lines/v2"}])[0]["function"]
        assert spec["name"] == "code__read-lines-v2"

    def test_split_round_trips(self):
        assert split_native_name("code__read_lines") == ("code", "read_lines")
        assert split_native_name("code__read__lines") == ("code", "read__lines")
        assert split_native_name("nosep") is None
        assert split_native_name("__t") is None


class TestTheMarkerIsWhatComesOut:
    def test_a_native_call_becomes_the_marker_the_loop_already_parses(self):
        marker = marker_for_native_call("code__read_lines", {"path": "a.py", "start": 1})
        call = parse_call(marker)
        assert call is not None
        assert (call.server, call.tool, call.arguments) == ("code", "read_lines", {"path": "a.py", "start": 1})

    def test_string_arguments_from_the_openai_wire_are_decoded(self):
        marker = marker_for_native_call("code__read_lines", '{"path": "a.py"}')
        assert parse_call(marker).arguments == {"path": "a.py"}

    def test_unparseable_arguments_become_an_empty_object_not_a_dropped_call(self):
        marker = marker_for_native_call("code__read_lines", "{not json")
        call = parse_call(marker)
        assert call is not None and call.arguments == {}

    def test_an_unplaceable_name_yields_nothing(self):
        assert marker_for_native_call("nosep", {}) == ""

    def test_the_marker_is_on_its_own_line(self):
        marker = marker_for_native_call("s__t", {})
        assert marker.startswith("\n" + TOOL_CALL_MARKER) and marker.endswith("\n")


# --------------------------------------------------------------------- Ollama


class _Resp:
    def __init__(self, payload: Any, status: int = 200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(str(self.status_code))

    def json(self):
        return self._payload


class _Chunked(_Resp):
    """`/api/chat` as Ollama streams it: one JSON object per line."""

    def __init__(self, chunks):
        super().__init__({})
        self._chunks = chunks

    def iter_lines(self):
        import json as _json

        for chunk in self._chunks:
            yield _json.dumps(chunk).encode()


class TestOllamaUsesApiChat:
    def _engine(self, monkeypatch, capabilities, reply):
        """`reply` is either one whole message (streamed here as content
        deltas of a few characters, then the calls, then `done`) or an
        explicit list of chunks."""
        import runtimes.models.engines.ollama_engine as mod

        sent: list[dict] = []

        def chunks_for(message: dict) -> list[dict]:
            out = []
            content = message.get("content") or ""
            for i in range(0, len(content), 4):
                out.append({"message": {"role": "assistant", "content": content[i:i + 4]}, "done": False})
            if message.get("tool_calls"):
                out.append({"message": {"role": "assistant", "content": "", "tool_calls": message["tool_calls"]}, "done": False})
            out.append({"message": {"role": "assistant", "content": ""}, "done": True})
            return out

        def fake_post(url, json=None, timeout=None, stream=False):
            if url.endswith("/api/show"):
                return _Resp({"capabilities": capabilities})
            if url.endswith("/api/chat"):
                sent.append({"url": url, **json})
                assert stream is True, "the tools path must stream"
                return _Chunked(reply if isinstance(reply, list) else chunks_for(reply["message"]))
            if url.endswith("/api/generate"):
                sent.append({"url": url, **json})
                raise AssertionError("the tools path must not use /api/generate")
            raise AssertionError(url)

        monkeypatch.setattr(mod.requests, "post", fake_post)
        engine = mod.OllamaEngine()
        engine.default_model = "qwen3"
        monkeypatch.setattr(engine, "_is_resident", lambda model: True)
        return engine, sent

    def test_tools_go_to_api_chat_and_calls_come_back_as_markers(self, monkeypatch):
        engine, sent = self._engine(
            monkeypatch,
            ["completion", "tools"],
            {"message": {
                "content": "Let me look.",
                "tool_calls": [{"function": {"name": "code__read_lines", "arguments": {"path": "a.py"}}}],
            }},
        )
        specs = native_tool_specs(OFFERED)
        pieces = list(engine.stream_response("q", "sys", "qwen3", tools=specs))
        out = "".join(pieces)

        assert sent[0]["url"].endswith("/api/chat")
        assert sent[0]["tools"] == specs
        assert sent[0]["messages"][0] == {"role": "system", "content": "sys"}
        assert sent[0]["messages"][1]["content"] == "q"
        # Streamed since 19 September 2026: the content arrives as it is
        # written, in pieces, and the call follows it as a marker.
        assert sent[0]["stream"] is True
        assert len([p for p in pieces if p and not p.startswith("[TOOL_CALL]")]) >= 3
        assert out.startswith("Let me look.")
        call = parse_call(out)
        assert call is not None and call.tool == "read_lines" and call.arguments == {"path": "a.py"}

    def test_thinking_then_a_call_with_no_prose_still_closes_the_tag(self, monkeypatch):
        """A model that reasons and then only calls: the think tag must close
        before the marker, or the splitter files the call as thinking and the
        loop never runs it."""
        from core.reasoning import CLOSE_TAG, OPEN_TAG

        engine, _ = self._engine(
            monkeypatch,
            ["completion", "tools", "thinking"],
            [
                {"message": {"role": "assistant", "thinking": "I should read ", "content": ""}, "done": False},
                {"message": {"role": "assistant", "thinking": "the file.", "content": ""}, "done": False},
                {"message": {"role": "assistant", "content": "", "tool_calls": [
                    {"function": {"name": "code__read_lines", "arguments": {"path": "a.py"}}},
                ]}, "done": False},
                {"message": {"role": "assistant", "content": ""}, "done": True},
            ],
        )
        out = "".join(engine.stream_response("q", "sys", "qwen3", tools=native_tool_specs(OFFERED)))

        assert out.startswith(OPEN_TAG + "I should read the file." + CLOSE_TAG)
        call = parse_call(out)
        assert call is not None and call.tool == "read_lines"

    def test_a_model_without_the_capability_takes_the_ordinary_path(self, monkeypatch):
        import runtimes.models.engines.ollama_engine as mod

        used: list[str] = []

        def fake_post(url, json=None, timeout=None, stream=False):
            if url.endswith("/api/show"):
                return _Resp({"capabilities": ["completion"]})
            used.append(url)

            class _Stream(_Resp):
                def iter_lines(self):
                    yield b'{"response": "plain", "done": true}'

            return _Stream({})

        monkeypatch.setattr(mod.requests, "post", fake_post)
        engine = mod.OllamaEngine()
        engine.default_model = "gemma"
        monkeypatch.setattr(engine, "_is_resident", lambda model: True)

        out = "".join(engine.stream_response("q", "sys", "gemma", tools=native_tool_specs(OFFERED)))

        assert used and used[0].endswith("/api/generate")
        assert out == "plain"

    def test_no_tools_means_no_capability_probe_for_tools_and_no_chat_route(self, monkeypatch):
        import runtimes.models.engines.ollama_engine as mod

        used: list[str] = []

        def fake_post(url, json=None, timeout=None, stream=False):
            used.append(url)
            if url.endswith("/api/show"):
                return _Resp({"capabilities": ["completion"]})

            class _Stream(_Resp):
                def iter_lines(self):
                    yield b'{"response": "plain", "done": true}'

            return _Stream({})

        monkeypatch.setattr(mod.requests, "post", fake_post)
        engine = mod.OllamaEngine()
        engine.default_model = "gemma"
        monkeypatch.setattr(engine, "_is_resident", lambda model: True)

        "".join(engine.stream_response("q", "sys", "gemma"))
        assert not any(u.endswith("/api/chat") for u in used)


# ----------------------------------------------------------- OpenAI-compatible


class TestOpenAICompatibleAssemblesDeltas:
    def _frames(self, *deltas: dict) -> list[bytes]:
        out = [
            ("data: " + json.dumps({"choices": [{"delta": d}]})).encode() for d in deltas
        ]
        return out + [b"data: [DONE]"]

    def test_tool_calls_split_across_frames_are_assembled_and_emitted_at_done(self):
        from runtimes.models.engines.openai_compatible_engine import OpenAICompatibleEngine

        lines = self._frames(
            {"content": "Looking. "},
            {"tool_calls": [{"index": 0, "function": {"name": "code__read_lines", "arguments": ""}}]},
            {"tool_calls": [{"index": 0, "function": {"arguments": '{"path": '}}]},
            {"tool_calls": [{"index": 0, "function": {"arguments": '"a.py"}'}}]},
        )
        out = "".join(OpenAICompatibleEngine._tokens(lines))

        assert out.startswith("Looking.")
        call = parse_call(out)
        assert call is not None
        assert (call.server, call.tool, call.arguments) == ("code", "read_lines", {"path": "a.py"})

    def test_two_calls_keep_their_order(self):
        from runtimes.models.engines.openai_compatible_engine import OpenAICompatibleEngine

        lines = self._frames(
            {"tool_calls": [
                {"index": 1, "function": {"name": "blender__list_objects", "arguments": "{}"}},
                {"index": 0, "function": {"name": "code__read_lines", "arguments": '{"path":"x"}'}},
            ]},
        )
        out = "".join(OpenAICompatibleEngine._tokens(lines))
        first = out.index("code__read_lines") if "code__read_lines" in out else out.index('"tool": "read_lines"')
        second = out.index('"tool": "list_objects"')
        assert first < second

    def test_the_body_carries_tools_only_when_given(self):
        from runtimes.models.engines.openai_compatible_engine import OpenAICompatibleEngine

        engine = OpenAICompatibleEngine(base_url="http://127.0.0.1:1234/v1", api_key="k", default_model="m")
        specs = native_tool_specs(OFFERED)
        assert engine._body("q", "s", "m", None, specs)["tools"] == specs
        assert "tools" not in engine._body("q", "s", "m")


# ------------------------------------------------------------------ wrappers


class _Recording:
    def __init__(self):
        self.calls: list[dict] = []
        self.default_model = "m"

    def stream_response(self, prompt, system_prompt="", model=None, images=None, tools=None):
        self.calls.append({"model": model, "images": images, "tools": tools})
        yield "ok"


class TestTheWrappersPassToolsThrough:
    def test_routed_engine_local_and_cloud(self):
        from runtimes.models.engines.routed_engine import RoutedEngine

        local, cloud = _Recording(), _Recording()
        engine = RoutedEngine(local=local, cloud=cloud, is_remote=lambda m: m == "cloudy")
        specs = native_tool_specs(OFFERED)
        "".join(engine.stream_response("q", "s", "local-m", ["img"], tools=specs))
        "".join(engine.stream_response("q", "s", "cloudy", ["img"], tools=specs))
        assert local.calls[0]["tools"] == specs and local.calls[0]["images"] == ["img"]
        assert cloud.calls[0]["tools"] == specs and cloud.calls[0]["images"] == ["img"]

    def test_cloud_fanout_passes_images_and_tools(self):
        """`images` was accepted and dropped here — a picture sent to a cloud
        model went nowhere and the model answered about what it never saw."""
        from runtimes.models.engines.cloud_fanout import CloudFanout

        target = _Recording()
        fanout = CloudFanout.__new__(CloudFanout)
        fanout._resolve = lambda model: (target, "wire-name")  # type: ignore[attr-defined]
        specs = native_tool_specs(OFFERED)
        "".join(CloudFanout.stream_response(fanout, "q", "s", "any", ["img"], tools=specs))
        assert target.calls[0] == {"model": "wire-name", "images": ["img"], "tools": specs}


# ---------------------------------------------------------------- dispatcher


class TestTheDispatcherHandsThemOver:
    def test_tools_on_input_data_reach_the_service(self):
        from core.dispatcher import ExecutionDispatcher
        from core.contracts import ExecutionStep

        seen: list[dict] = []

        class _Service:
            def generate_response(self, prompt, system_prompt="", model=None, images=None, tools=None):
                seen.append({"images": images, "tools": tools})
                yield "ok"

        class _Runtime:
            def get_service(self):
                return _Service()

            def get_runtime_id(self):
                return "models"

        class _Router:
            def resolve(self, capability_id):
                return _Runtime()

            def try_resolve(self, capability_id):
                return _Runtime()

        dispatcher = ExecutionDispatcher(_Router())
        specs = native_tool_specs(OFFERED)
        step = ExecutionStep(
            capability_id="reasoning.generate",
            input_data={"prompt": "q", "tools": specs},
            depends_on=[],
        )
        "".join(dispatcher.execute_step(step, "m", "s"))
        assert seen and seen[0]["tools"] == specs

    def test_without_tools_the_old_three_argument_call_is_made(self):
        """A dozen doubles implement the three-argument form. Unchanged."""
        from core.dispatcher import ExecutionDispatcher
        from core.contracts import ExecutionStep

        class _Service:
            def generate_response(self, prompt, system_prompt="", model=None):
                yield "three-arg ok"

        class _Runtime:
            def get_service(self):
                return _Service()

            def get_runtime_id(self):
                return "models"

        class _Router:
            def resolve(self, capability_id):
                return _Runtime()

            def try_resolve(self, capability_id):
                return _Runtime()

        dispatcher = ExecutionDispatcher(_Router())
        step = ExecutionStep(capability_id="reasoning.generate", input_data={"prompt": "q"}, depends_on=[])
        assert "".join(dispatcher.execute_step(step, "m", "s")) == "three-arg ok"
