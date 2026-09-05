"""Pressing "Download a model to start with", from the offer to the log.

Two claims are worth a test each and neither is about downloading.

**The model fetched is the model quoted.** The offer states a price the user
agrees to, and the route recomputes the recommendation rather than accepting a
name — so the only way these can disagree is if they read different budgets,
which is what the first test pins.

**The download is recorded before it happens.** Ollama pulls from the registry
over a socket this process does not own, so `EgressGate` never sees those
bytes and rule 3 has to be met deliberately. Recorded afterwards it would be a
log of the downloads that *finished*, which is the wrong set.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from core.readiness import model_to_offer
from providers.model_manifest import GB
from providers.pull import REGISTRY_HOST, stream_pull


class _Log:
    """The egress log's one write method, and nothing else."""

    def __init__(self) -> None:
        self.entries: list[dict] = []

    def append(self, **entry):
        self.entries.append(entry)
        return SimpleNamespace(**entry)


class _Adapter:
    """Ollama, replaying a pull that already happened."""

    def __init__(self, events, *, watching: _Log | None = None) -> None:
        self._events = events
        self._watching = watching
        self.asked_for: list[str] = []
        self.log_when_asked: int | None = None

    def pull_model(self, name, **_kw):
        self.asked_for.append(name)
        if self._watching is not None:
            self.log_when_asked = len(self._watching.entries)
        return iter(self._events)


def _drain(adapter, log, budget=None):
    return list(stream_pull(budget_bytes=budget, adapter=adapter, log=log))


class TestWhatIsFetchedIsWhatWasOffered:
    def test_the_model_pulled_is_the_one_the_offer_names(self):
        for budget in (None, 2 * GB, 12 * GB):
            adapter = _Adapter([{"status": "success"}])
            _drain(adapter, _Log(), budget)

            assert adapter.asked_for == [model_to_offer(budget).name], budget

    def test_a_bigger_machine_pulls_a_different_model(self):
        """The same wiring the offer has. If this stopped following the budget
        the screen would quote one model and fetch another."""
        small, large = _Adapter([]), _Adapter([])
        _drain(small, _Log(), 2 * GB)
        _drain(large, _Log(), 12 * GB)

        assert small.asked_for != large.asked_for


class TestTheDownloadIsRecordedBeforeItHappens:
    def test_the_entry_is_written_before_ollama_is_asked(self):
        """Not after, and not on success. A pull interrupted halfway still
        moved bytes, and a log that misses those is not the record rule 3
        describes."""
        log = _Log()
        adapter = _Adapter([{"status": "success"}], watching=log)

        _drain(adapter, log)

        assert adapter.log_when_asked == 1, "Ollama was asked before anything was logged"

    def test_the_entry_names_the_registry_and_the_expected_size(self):
        log = _Log()
        _drain(_Adapter([{"status": "success"}]), log, 12 * GB)

        entry = log.entries[0]
        assert entry["host"] == REGISTRY_HOST
        assert entry["decision"] == "allowed"
        assert entry["body"] == model_to_offer(12 * GB).name
        assert entry["meta"]["expected_bytes"] == model_to_offer(12 * GB).size_bytes

    def test_a_failed_pull_is_still_a_recorded_one(self):
        log = _Log()
        events = _drain(_Adapter([{"error": "no route to host"}]), log)

        assert len(log.entries) == 1
        assert events[-1]["error"] == "no route to host"

    def test_one_press_is_one_entry(self):
        log = _Log()
        _drain(_Adapter([{"status": "pulling manifest"}, {"status": "success"}]), log)

        assert len(log.entries) == 1


class TestWhatTheScreenIsTold:
    def test_progress_carries_bytes_and_no_model_name(self):
        """Same rule as the offer's label: the target user is not technical,
        and a progress line reading a filename is one they did not choose."""
        events = _drain(
            _Adapter(
                [
                    {"status": "pulling manifest"},
                    {"status": "pulling 8934d96d3f08", "completed": 5, "total": 10},
                    {"status": "success"},
                ]
            ),
            _Log(),
            12 * GB,
        )

        name = model_to_offer(12 * GB).name
        for event in events:
            assert name not in json.dumps(event)

        progress = [e for e in events if "total" in e]
        assert progress == [{"stage": "Downloading", "completed": 5, "total": 10}]

    def test_a_digest_never_reaches_the_stage_line(self):
        """Ollama's own words are written for a terminal — *"pulling
        8934d96d3f08"* names a digest nobody can act on."""
        events = _drain(_Adapter([{"status": "pulling 8934d96d3f08"}]), _Log())

        assert events[0] == {"stage": "Downloading"}

    def test_it_always_ends_with_exactly_one_terminal_event(self):
        for stream in (
            [{"status": "success"}],
            [],  # a server that closed without saying anything
            [{"status": "verifying sha256"}],
        ):
            events = _drain(_Adapter(stream), _Log())
            assert events[-1] == {"done": True}
            assert [e for e in events if "done" in e or "error" in e] == [events[-1]]

    def test_an_error_ends_it_and_nothing_follows(self):
        events = _drain(
            _Adapter([{"status": "pulling"}, {"error": "disk full"}, {"status": "success"}]),
            _Log(),
        )

        assert events[-1] == {"error": "disk full"}


class TestTheRouteIsMounted:
    """A complete, tested, unreachable subsystem is this repository's most
    common defect. The offer is only real if pressing it reaches something."""

    @pytest.fixture
    def client(self, monkeypatch):
        from fastapi.testclient import TestClient

        import core.egress as egress_pkg
        from providers.discoverers.ollama import OllamaAdapter

        log = _Log()
        monkeypatch.setattr(
            egress_pkg, "get_gate", lambda: SimpleNamespace(log=log), raising=False
        )
        monkeypatch.setattr(
            OllamaAdapter,
            "pull_model",
            lambda self, name, **kw: iter(
                [{"status": "pulling", "completed": 1, "total": 2}, {"status": "success"}]
            ),
        )

        from main import app

        return TestClient(app), log

    def test_pressing_it_streams_progress_and_ends(self, client):
        http, log = client

        response = http.post("/providers/pull")

        assert response.status_code == 200
        lines = [json.loads(l) for l in response.text.splitlines() if l.strip()]
        assert lines[-1] == {"done": True}
        assert any("total" in line for line in lines)
        assert len(log.entries) == 1
