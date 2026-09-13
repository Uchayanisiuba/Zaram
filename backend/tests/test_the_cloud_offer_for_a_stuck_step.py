"""When the local model is stuck, the cloud model is offered — for this step.

`CLAUDE.md`: *"This is too hard for the local model" is not decidable in
advance, so Zaram does not predict it — it reacts to it with an offer under the
reply.* The signal is the project's own tests: run at least twice in one reply
and still failing at the end. The offer is one notice, `action: cloud`, naming
the model and what would leave; it is absent when the tests passed, when the
answering model is already remote, when nothing remote is connected, and when
the engine cannot place the model at all.
"""

from __future__ import annotations

import pytest

from core.streaming_events import EventType, StreamEvent
from tests.test_the_tool_loop_is_bounded import (
    _McpDouble,
    _ModelRuntime,
    _call,
    _engine,
    _events,
    a_generous_window,  # noqa: F401 - fixture
)


class _Cloud:
    def __init__(self, id="gpt-x", provider="openrouter"):
        self.id = id
        self.display_name = id
        self.provider = provider


class _Manager:
    def __init__(self, cloud=_Cloud()):
        self._cloud = cloud
        self.asked = []

    def best_cloud_model(self, specialisation=None):
        self.asked.append(specialisation)
        return self._cloud


RUN = {"server": "code", "name": "run_command", "description": "run", "input_schema": {}}
EDIT = {"server": "code", "name": "edit_file", "description": "edit", "input_schema": {}}


def _stuck_engine(locality="local", manager=None, *, passes_at_the_end=False):
    last = {"ok": True, "output": "1 passed"} if passes_at_the_end else {"ok": False, "output": "1 failed"}
    mcp = _McpDouble(
        tools=[RUN, EDIT],
        results=[
            {"success": True, "result": {"ok": False, "output": "1 failed"}},
            {"success": True, "result": {"commit": "abc"}},
            {"success": True, "result": last},
        ],
    )
    engine, model = _engine(
        [
            _call("run_command", runner="pytest"),
            _call("edit_file", path="calc.py", find="-", replace="+"),
            _call("run_command", runner="pytest"),
            "I could not make it pass.",
        ],
        mcp,
    )
    # The models runtime is what places a model; the harness's reasoning
    # runtime stands in for it here.
    model.locality_of = lambda m: locality
    if manager is not None:
        engine.set_provider_manager(manager)
    return engine


def _offers(events):
    return [e for e in _events(events, EventType.NOTICE) if e.data.get("action") == "cloud"]


class TestTheOffer:
    def test_two_failed_runs_and_a_cloud_model_make_an_offer(self, a_generous_window):  # noqa: F811
        manager = _Manager()
        engine = _stuck_engine(manager=manager)

        out = list(engine.execute("use the code tools to fix the failing test"))

        offers = _offers(out)
        assert len(offers) == 1
        notice = offers[0].data
        assert notice["model"] == "gpt-x" and notice["provider"] == "openrouter"
        assert "failed 2 times" in notice["content"]
        # What leaves is on the card, not behind it.
        assert "repository map" in notice["content"] and "openrouter" in notice["content"]
        assert manager.asked == ["code"]

    def test_a_passing_final_run_is_not_stuck(self, a_generous_window):  # noqa: F811
        engine = _stuck_engine(manager=_Manager(), passes_at_the_end=True)
        assert _offers(list(engine.execute("use the code tools to fix the failing test"))) == []

    def test_no_cloud_model_connected_means_no_offer(self, a_generous_window):  # noqa: F811
        engine = _stuck_engine(manager=_Manager(cloud=None))
        assert _offers(list(engine.execute("use the code tools to fix the failing test"))) == []

    def test_already_on_cloud_means_no_offer(self, a_generous_window):  # noqa: F811
        engine = _stuck_engine(locality="cloud", manager=_Manager())
        assert _offers(list(engine.execute("use the code tools to fix the failing test"))) == []

    def test_an_unplaceable_model_means_no_offer(self, a_generous_window):  # noqa: F811
        """`locality_of` answering None is "unknown", and no offer is made on
        a guess — the same three-valued discipline `vram_bytes` keeps."""
        engine = _stuck_engine(locality=None, manager=_Manager())
        assert _offers(list(engine.execute("use the code tools to fix the failing test"))) == []

    def test_a_broken_manager_never_fails_the_reply(self, a_generous_window):  # noqa: F811
        class Broken:
            def best_cloud_model(self, specialisation=None):
                raise RuntimeError("no")

        engine = _stuck_engine(manager=Broken())
        out = list(engine.execute("use the code tools to fix the failing test"))
        assert "I could not make it pass." in "".join(i for i in out if isinstance(i, str))
        assert _offers(out) == []


class TestZaramsPickIsResolvedBeforeItIsSized:
    """`model=None` is "Zaram's pick" on the way in, and the engine used to
    size and place it as `None` — the 4,096 fallback on a 65k model, and no
    locality, so no offer. Seen on screen: a finished task told it had
    stopped at half of 4,096."""

    def test_the_offer_reaches_a_zarams_pick_reply(self, a_generous_window):  # noqa: F811
        manager = _Manager()
        engine = _stuck_engine(manager=manager)
        runtime = engine._router.try_resolve("reasoning.generate")
        runtime.health_check = lambda: {"state": "ready", "model": "qwen-picked"}
        runtime.locality_of = lambda m: "local" if m == "qwen-picked" else None

        out = list(engine.execute("use the code tools to fix the failing test"))

        offers = _offers(out)
        assert len(offers) == 1
        assert "qwen-picked" in offers[0].data["content"]

    def test_the_budget_is_sized_against_the_picked_model(self, monkeypatch):
        from core import execution_engine
        from core.context_budget import ContextBudget

        asked = []

        def fake_budget(model=None, **kw):
            asked.append(model)
            return ContextBudget(total_tokens=65536, measured=True, reply_reserve_tokens=8192)

        monkeypatch.setattr(execution_engine, "budget_for", fake_budget)
        engine = _stuck_engine(manager=_Manager())
        runtime = engine._router.try_resolve("reasoning.generate")
        runtime.health_check = lambda: {"state": "ready", "model": "qwen-picked"}

        list(engine.execute("use the code tools to fix the failing test"))

        assert asked and all(m == "qwen-picked" for m in asked), asked
