# backend/tests/test_kernel_flow.py
"""Regression tests for the Sprint 3 Kernel execution flow.

These tests validate the IntentPlanner -> CapabilityRouter ->
ExecutionDispatcher -> RuntimeService wiring without requiring a live
Ollama server, plus security/robustness checks for the audio endpoint.
"""
import sys
from pathlib import Path

from fastapi import HTTPException

# Ensure backend root is importable when run directly (not via pytest).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from core.bootstrapper import KernelBootstrapper
from core.contracts import Capability, Runtime, RuntimeMetadata, RuntimeState
from core.execution_engine import ExecutionEngine


class _FakeService:
    def generate_response(self, user_text, personality_context=""):
        yield "hello "
        yield "world"


class _FakeRuntime:
    """A minimal Runtime that satisfies the Runtime protocol."""

    capability_id = "reasoning.generate"

    def __init__(self):
        self._state = RuntimeState.UNINITIALIZED
        self._service = _FakeService()

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


def _build_engine() -> ExecutionEngine:
    kernel = KernelBootstrapper()
    kernel.registry.register(_FakeRuntime())
    return ExecutionEngine(kernel.registry, kernel.event_bus)


def test_execution_engine_flow_streams_tokens():
    tokens = list(_build_engine().execute("test prompt"))
    assert tokens == ["hello ", "world"]


def test_execution_engine_emits_plan_events():
    kernel = KernelBootstrapper()
    kernel.registry.register(_FakeRuntime())
    engine = ExecutionEngine(kernel.registry, kernel.event_bus)

    events = []
    kernel.event_bus.subscribe("execution.plan_created", events.append)
    list(engine.execute("x"))

    assert any(e.event_type == "execution.plan_created" for e in events)


def test_unknown_capability_raises():
    from core.capability_router import CapabilityRouter

    kernel = KernelBootstrapper()
    kernel.registry.register(_FakeRuntime())
    router = CapabilityRouter(kernel.registry)

    try:
        router.resolve("does.not.exist")
        assert False, "Expected KeyError for unknown capability"
    except KeyError:
        pass


def test_audio_endpoint_rejects_path_traversal():
    import main

    for malicious in ("../secret.txt", "..\\..\\etc\\passwd", "foo/../../bar.wav"):
        try:
            main.get_audio(malicious)
            assert False, f"Expected HTTPException for {malicious!r}"
        except HTTPException as exc:
            assert exc.status_code == 400


def test_audio_endpoint_missing_file_returns_404():
    import main

    try:
        main.get_audio("nonexistent.wav")
        assert False, "Expected HTTPException 404"
    except HTTPException as exc:
        assert exc.status_code == 404


def test_main_module_imports_cleanly():
    import main

    assert hasattr(main, "app")
    paths = {r.path for r in main.app.routes if hasattr(r, "path")}
    assert "/api/chat" in paths
    assert "/audio/{filename}" in paths


class _FakeLLM:
    def stream_response(self, prompt, model):
        for token in ["Hello", " world", ".", " This is one sentence.", " This is another."]:
            yield token


def test_legacy_conversation_terminates_without_tts():
    """Conversation must complete cleanly when speech is unavailable."""
    from services.conversation_manager import ConversationManager
    from voice.voice_manager import VoiceManager

    manager = ConversationManager(_FakeLLM(), VoiceManager())
    events = list(manager.run_conversation("hi", "gemma3:latest", "default"))

    assert events, "conversation produced no events"
    assert events[-1] == {"type": "done"}, "must terminate with a 'done' event"
    assert not any(e.get("type") == "error" for e in events), "no error events expected"
    assert any(e.get("type") == "token" for e in events), "expected token events"
    assert not any(e.get("type") == "audio" for e in events), "no audio when speech disabled"
