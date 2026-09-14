"""The landing's returning line is built from counts, never estimates.

`docs/UI-SPEC.md` 6h: *"One mono line, not a dashboard: 14 new facts from 3
sources · the Meridian deploy target changed · 0 bytes left this device."*
The interface asks `GET /memory/stats?since=<epoch>` for the first number
rather than pulling the Spine to count it, and two things must hold: the
count is of facts that entered *after* the moment named, and the field is
absent when no moment was named — a count nobody asked for would read as a
claim about a moment nobody chose.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from starlette.testclient import TestClient

from runtimes.memory.contracts import MemoryRecord, MemoryStats


class _Spine:
    def __init__(self, records: list[MemoryRecord]) -> None:
        self.records = records
        self._store = self

    async def stats(self) -> MemoryStats:
        return MemoryStats(total_records=len(self.records))

    async def all_records(self, include_superseded: bool = False) -> list[MemoryRecord]:
        return list(self.records)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    main = importlib.import_module("main")
    spine = _Spine(
        [
            MemoryRecord(content="old", created_at=1_000.0),
            MemoryRecord(content="newer", created_at=2_000.0),
            MemoryRecord(content="newest", created_at=3_000.0),
        ]
    )
    monkeypatch.setattr(main.kernel, "memory_runtime", spine, raising=False)
    return TestClient(main.app)


def _stats(client: TestClient, **params: Any) -> dict[str, Any]:
    r = client.get("/memory/stats", params=params)
    assert r.status_code == 200, r.text
    return r.json()


class TestNewSince:
    def test_counts_only_what_entered_after_the_moment(self, client):
        assert _stats(client, since=1_500.0)["new_since"] == 2
        assert _stats(client, since=3_000.0)["new_since"] == 0

    def test_is_absent_when_no_moment_was_named(self, client):
        body = _stats(client)
        assert "new_since" not in body
        assert body["total_records"] == 3
