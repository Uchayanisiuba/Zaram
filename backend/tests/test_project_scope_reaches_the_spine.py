"""M8's missing caller: does a project scope actually get written and read?

M8 built the `scope` field, the recall filter, the migration and the promotion
evidence, and shipped with none of it reachable — nothing told the engine which
project was active. Every fact landed `global`, so `promotion_candidates()`
could only ever return an empty list and rule 7i's promotion half was inert
while looking complete.

That is the same defect shape as `apply_decay` reading a private field: the
policy was right and nothing invoked it. So these tests are about *reach*, not
about scoping policy — `test_memory_scope.py` already grades the policy and
has always passed.
"""
from __future__ import annotations

from typing import Any

import pytest

from core.execution_engine import ExecutionEngine, _scope_for
from runtimes.memory.contracts import GLOBAL_SCOPE, project_scope


class _RecordingMemoryRuntime:
    """Captures the arguments the engine passes, and nothing else."""

    def __init__(self):
        self.retrieve_calls: list[dict[str, Any]] = []
        self.remember_calls: list[dict[str, Any]] = []

    async def retrieve(self, **kwargs):
        self.retrieve_calls.append(kwargs)
        return []

    async def remember(self, **kwargs):
        self.remember_calls.append(kwargs)
        return "fact-1"


class _Engine(ExecutionEngine):
    """The recall and capture paths, without booting a kernel."""

    def __init__(self, runtime):
        self._runtime = runtime
        self._event_bus = None
        self._provider_manager = None

    def _memory_runtime(self):
        return self._runtime

    def _publish(self, *args, **kwargs):
        pass


class TestTheScopeSpelling:
    def test_a_project_id_becomes_a_project_scope(self):
        assert _scope_for("harbour") == project_scope("harbour")
        assert _scope_for("harbour").startswith("project:")

    def test_no_project_is_none_and_not_global(self):
        """`None` and `global` are different instructions, not synonyms.

        As a *recall* filter, `None` means "every scope" — right when the user
        is not inside a project. `global` would mean "only facts about the
        user", which would hide their own project material from them. The two
        must not be collapsed, and the storage path converts `None` separately.
        """
        assert _scope_for(None) is None
        assert _scope_for("") is None
        assert _scope_for("   ") is None
        assert _scope_for(None) != GLOBAL_SCOPE


class TestRecallIsScoped:
    def test_recall_passes_the_project_scope(self):
        runtime = _RecordingMemoryRuntime()
        _Engine(runtime)._recall("what is the day rate?", "session-1", "harbour")

        assert runtime.retrieve_calls, "recall never reached the memory runtime"
        assert runtime.retrieve_calls[0]["scope"] == project_scope("harbour"), (
            "recall did not narrow to the active project — rule 7i's filter is "
            "in place but nothing is telling it which project"
        )

    def test_recall_without_a_project_asks_for_every_scope(self):
        runtime = _RecordingMemoryRuntime()
        _Engine(runtime)._recall("what is the day rate?", "session-1", None)

        assert runtime.retrieve_calls[0]["scope"] is None, (
            "a question asked outside a project must still see the user's own "
            "material; scoping it to `global` would hide their projects from them"
        )


class TestCaptureIsScoped:
    def test_a_fact_captured_in_a_project_carries_that_scope(self):
        runtime = _RecordingMemoryRuntime()
        _Engine(runtime)._remember(
            "My day rate is 425,000 naira.", "Noted.", "session-1", None, "harbour",
        )

        assert runtime.remember_calls, "nothing was captured at all"
        assert runtime.remember_calls[0]["scope"] == project_scope("harbour"), (
            "the fact landed unscoped, so `recalled_in` can never accumulate "
            "evidence across projects and promotion stays inert"
        )

    def test_a_fact_captured_outside_a_project_is_not_given_one(self):
        """Rule 7i: inventing a project would be a value nobody entered."""
        runtime = _RecordingMemoryRuntime()
        _Engine(runtime)._remember(
            "I prefer short emails.", "Noted.", "session-1", None, None,
        )

        assert runtime.remember_calls[0]["scope"] is None, (
            "a project was invented for a fact captured with none active"
        )


class TestTheEngineSignatureCarriesIt:
    def test_execute_accepts_a_project_id(self):
        """The seam that was missing. Asserted on the signature because the
        whole defect was that this parameter did not exist to be passed."""
        import inspect

        params = inspect.signature(ExecutionEngine.execute).parameters
        assert "project_id" in params, (
            "ExecutionEngine.execute has no project_id, so no caller can scope "
            "an exchange and every fact lands global — M8's gap, exactly"
        )
        assert params["project_id"].default is None

    def test_the_chat_router_forwards_it(self):
        import inspect

        from core.chat_router import ChatRouter

        assert "project_id" in inspect.signature(ChatRouter.route).parameters, (
            "the chat path drops project_id before it reaches the engine"
        )
