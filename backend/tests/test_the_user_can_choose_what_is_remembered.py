"""An override the user drives, on top of the capture that already runs.

Asked for on 3 September 2026: *"a save to memory button — Zaram shouldn't save
all the conversations but what the user chooses."*

**The half of that this implements, and the half it deliberately does not.**
Rule 7b already ships the negative override — *"a 'Don't remember this'
override exists on file cards; it is an override, never a gate"* — and this is
the same shape pointing the other way. What it is not is the only way in.
Making the button the gate would ask people to predict at capture time which
sentence matters in November, which is rule 7e in as many words, and a Spine
that only holds what someone remembered to save is a note-taking app — the
thing `CLAUDE.md` says is abandoned because *"project tools require you to type
the data"*.

So automatic capture is untouched, `SpineMaintenance` still decays what is
never used, and this adds certainty for the cases a heuristic cannot be trusted
with: a rate, a term, a decision already made.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from starlette.testclient import TestClient


class _Spine:
    """A memory runtime that records what it was asked to keep."""

    def __init__(self) -> None:
        self.written: list[dict[str, Any]] = []
        self._store = self

    async def remember(self, **kwargs: Any) -> str:
        self.written.append(kwargs)
        return f"fact-{len(self.written)}"

    async def get(self, record_id: str):
        class _Record:
            id = record_id
            scope = None
            created_at = 0.0

        return _Record()

    @property
    def last(self) -> dict[str, Any]:
        assert self.written, "nothing was written to the Spine"
        return self.written[-1]


@pytest.fixture
def client(tmp_path, monkeypatch):
    from projects.records import ProjectRecords

    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))

    main = importlib.import_module("main")
    monkeypatch.setattr(
        main, "project_records", ProjectRecords(str(tmp_path / "projects.db"))
    )

    spine = _Spine()
    monkeypatch.setattr(main.kernel, "memory_runtime", spine, raising=False)

    test_client = TestClient(main.app)
    test_client.spine = spine  # type: ignore[attr-defined]
    test_client.projects = main.project_records  # type: ignore[attr-defined]
    test_client.main = main  # type: ignore[attr-defined]
    return test_client


class TestWhatTheUserChoosesIsKept:
    def test_a_chosen_fact_reaches_the_spine(self, client):
        response = client.post("/memory", json={"text": "Harbour Lane pays on the 30th."})

        assert response.status_code == 200
        assert client.spine.last["content"] == "Harbour Lane pays on the 30th."

    def test_it_is_stored_as_a_fact_rather_than_as_traffic(self, client):
        """`SEMANTIC`, not `CONVERSATION`.

        The turn is traffic; the sentence the user lifted out of it is a fact.
        The contract has always had words for both — the engine is what
        collapsed them — and a deliberate save is the one case where there is
        no ambiguity about which it is.
        """
        from runtimes.memory.contracts import MemoryType

        client.post("/memory", json={"text": "Our payment terms are 30 days."})

        assert client.spine.last["memory_type"] is MemoryType.SEMANTIC

    def test_it_outranks_something_merely_mentioned(self, client):
        """Chosen deliberately, so it starts above the ordinary capture.

        Not immortal — that is what pinning is for and pinning already exists.
        Against the 90-day half life this stays above the low-importance line
        for about three months and falls away at roughly six if it is never
        recalled, which is rule 7e's bargain rather than an exemption from it.
        """
        client.post("/memory", json={"text": "The retainer is 200,000 a month."})

        assert client.spine.last["importance"] == client.main.REMEMBERED_IMPORTANCE
        assert client.spine.last["importance"] > 0.5


class TestItCarriesWhatRecallNeedsToRankItHonestly:
    def test_saving_a_zaram_reply_is_marked_as_zaram_s_own_words(self, client):
        """Rule 7b. Recall deprioritises Zaram's restatements where a user
        source says the same thing, and it can only do that if the save says
        which this was."""
        from runtimes.memory.contracts import Origin

        client.post(
            "/memory",
            json={"text": "The rate works out at 1,200 a week.", "origin": "generated"},
        )

        assert client.spine.last["origin"] is Origin.GENERATED

    def test_the_users_own_words_are_the_default_and_the_fallback(self, client):
        """An unrecognised origin resolves to the user, not to Zaram.

        The error runs in the safe direction on purpose: labelling a user's own
        note as Zaram's output would have recall quietly rank down the more
        trustworthy of the two.
        """
        from runtimes.memory.contracts import Origin

        client.post("/memory", json={"text": "Ashgrove pays on the 30th."})
        assert client.spine.last["origin"] is Origin.CONVERSATION

        client.post("/memory", json={"text": "Northwind renews in March.", "origin": "nonsense"})
        assert client.spine.last["origin"] is Origin.CONVERSATION

    def test_it_belongs_to_the_project_it_was_saved_in(self, client):
        project = client.projects.create("Harbour Lane")

        client.post(
            "/memory",
            json={"text": "Two rounds of revisions are included.", "project_id": project.id},
        )

        assert client.spine.last["scope"] == f"project:{project.id}"

    def test_saved_outside_a_project_carries_no_project(self, client):
        client.post("/memory", json={"text": "I prefer short emails."})
        assert client.spine.last["scope"] is None


class TestItRefusesRatherThanGuessing:
    def test_an_unknown_project_is_refused(self, client):
        """Same rule the import path follows: nothing records which save wrote
        a fact, so a wrong scope cannot be found again and undone."""
        response = client.post(
            "/memory", json={"text": "A rate.", "project_id": "no-such-project"}
        )

        assert response.status_code == 404
        assert client.spine.written == []

    def test_empty_text_is_refused(self, client):
        response = client.post("/memory", json={"text": "   "})

        assert response.status_code == 400
        assert client.spine.written == []

    def test_a_whole_transcript_is_refused_rather_than_stored(self, client):
        """The failure mode this button invites.

        Selecting everything and pressing save is "L0" — persisting raw
        dialogue — which `CLAUDE.md` rejects outright, and its recorded cost is
        duplicate citations and Zaram quoting its own replies. The cap is the
        cheap guard: it refuses with a sentence that says what to do instead.
        """
        response = client.post("/memory", json={"text": "x" * 4001})

        assert response.status_code == 413
        assert "the part that matters" in response.json()["detail"]
        assert client.spine.written == []
