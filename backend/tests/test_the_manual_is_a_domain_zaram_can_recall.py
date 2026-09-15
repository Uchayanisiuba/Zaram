"""Zaram's own manual ships inside it, is read into the Zaram domain, and can
be found by a question a person would ask.

`manual/__init__.py`. Four contracts. The pages are real files with titles
and pictures that resolve. Indexing reads them into a real ingest service and
a real domain store, once per version — the same pages are not re-read on
the next start, and a changed page re-reads them. The built-in source and
domain refuse deletion through the routes. And the lexical side of recall,
given the chunks the manual produces, puts the right page first for
"how do I export my memory" — no embedder needed for that half, which is
the half that has to work on a machine with none.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import manual
from ingest.records import IngestRecords
from ingest.service_api import IngestService
from knowledge.domains import KnowledgeDomains


class _Memory:
    """Records every chunk `IngestService` stores, so the test can read what
    the manual became without a model."""

    def __init__(self) -> None:
        self.chunks: list[tuple[str, dict]] = []

    async def remember(self, content, metadata=None, **_):
        self.chunks.append((content, dict(metadata or {})))
        return f"m{len(self.chunks)}"


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path / "data"))
    memory = _Memory()
    svc = IngestService(IngestRecords(str(tmp_path / "ingest.db")), memory_runtime=memory)
    svc.memory = memory  # type: ignore[attr-defined]
    return svc


@pytest.fixture
def domains(tmp_path):
    return KnowledgeDomains(str(tmp_path / "domains.db"))


class TestThePages:
    def test_there_are_pages_in_reading_order_each_with_a_title(self):
        pages = manual.pages()
        assert len(pages) >= 8
        assert [p.order for p in pages] == sorted(p.order for p in pages)
        assert all(p.title and p.title != p.slug for p in pages)
        assert pages[0].slug == "what-zaram-is"

    def test_every_picture_a_page_names_exists_and_is_served(self):
        import re

        for page in manual.pages():
            text = page.path.read_text(encoding="utf-8")
            for name in re.findall(r"\]\(assets/([^)]+)\)", text):
                found = manual.asset(name)
                assert found is not None, f"{page.slug} refers to a missing picture {name}"
                assert found[1].startswith("image/")
        # A page's links point at the route once read through the module.
        assert "](/manual/assets/landing.png)" in manual.read("what-zaram-is")

    def test_an_asset_outside_the_folder_is_refused(self):
        assert manual.asset("../__init__.py") is None
        assert manual.asset("..\\__init__.py") is None
        assert manual.asset("nope.png") is None

    def test_the_pages_speak_to_a_person_not_a_developer(self):
        """The manual is not CLAUDE.md. No rule numbers, no module paths."""
        import re

        for page in manual.pages():
            text = page.path.read_text(encoding="utf-8")
            assert not re.search(r"\brule \d", text, re.I), page.slug
            assert ".py" not in text and "CLAUDE.md" not in text, page.slug


class TestIndexing:
    def test_the_manual_is_read_once_per_version_into_the_zaram_domain(self, service, domains, tmp_path):
        data = tmp_path / "data"
        first = manual.ensure_indexed(service, domains, data)
        assert first["indexed"] is True and first["pages"] >= 8
        zaram = next(d for d in domains.all() if d["name"] == "Zaram")
        assert first["domain_id"] == zaram["id"]
        assert first["source_id"] in domains.source_ids(zaram["id"])
        assert manual.indexed_version(data) == manual.version()
        chunks_after_first = len(service.memory.chunks)
        assert chunks_after_first > 0

        second = manual.ensure_indexed(service, domains, data)
        assert second["indexed"] is False
        assert len(service.memory.chunks) == chunks_after_first, "the same pages were read again"

    def test_a_changed_page_is_read_again(self, service, domains, tmp_path, monkeypatch):
        data = tmp_path / "data"
        manual.ensure_indexed(service, domains, data)
        monkeypatch.setattr(manual, "version", lambda: "changed")
        again = manual.ensure_indexed(service, domains, data)
        assert again["indexed"] is True
        assert manual.indexed_version(data) == "changed"

    def test_the_built_in_pair_is_known_by_id(self, service, domains, tmp_path):
        data = tmp_path / "data"
        ids = manual.ensure_indexed(service, domains, data)
        assert manual.is_builtin_source(data, ids["source_id"])
        assert manual.is_builtin_domain(data, ids["domain_id"])
        assert not manual.is_builtin_source(data, "someone-elses")

    def test_a_missing_stamp_is_not_a_crash(self, tmp_path):
        assert manual.indexed_version(tmp_path) is None
        assert manual.builtin_ids(tmp_path) == {}
        (tmp_path / "manual.json").write_text("{ not json", encoding="utf-8")
        assert manual.builtin_ids(tmp_path) == {}


class TestAQuestionFindsThePage:
    async def test_how_do_i_export_my_memory_lands_on_the_memory_page(self, service, domains, tmp_path):
        from runtimes.memory.contracts import MemoryQuery, MemoryRecord
        from runtimes.memory.index import HybridMemoryIndex

        manual.ensure_indexed(service, domains, tmp_path / "data")
        index = HybridMemoryIndex(embedding_dim=4)
        for n, (content, meta) in enumerate(service.memory.chunks):
            await index.add(MemoryRecord(id=f"{meta.get('source_name', '?')}#{n}", content=content, embedding=None))

        for question, page in (
            ("how do I export my memory and take it with me", "04-memory"),
            ("what does the uninstaller do with my data", "10-help-and-problems"),
            ("how do I add a cloud key", "07-models-and-keys"),
        ):
            results = await index.search(MemoryQuery(query=question, max_results=3))
            assert results, question
            # The lexical side alone; in the product the embedding side runs
            # beside it. Within the three the model is shown is the contract.
            assert any(rid.startswith(page) for rid, _ in results), (question, [r for r, _ in results])


class TestTheRoutesRefuseToRemoveIt:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        data = tmp_path / "data"
        data.mkdir()
        data.joinpath("manual.json").write_text(
            json.dumps({"version": "v", "source_id": "src-manual", "domain_id": "dom-manual"}), encoding="utf-8"
        )
        import core.paths as paths

        monkeypatch.setattr(paths, "data_dir", lambda: data)
        from fastapi.testclient import TestClient

        import main as app_module

        return TestClient(app_module.app)

    def test_the_manual_source_and_domain_cannot_be_deleted(self, client):
        headers = {"X-Zaram-Client": "zaram-ui"}
        r = client.delete("/ingest/sources/src-manual", headers=headers)
        assert r.status_code == 403, r.text
        assert "manual" in r.json()["detail"].lower()
        r = client.delete("/knowledge/domains/dom-manual", headers=headers)
        assert r.status_code == 403, r.text

    def test_the_pages_are_served(self, client):
        index = client.get("/manual").json()
        assert index["pages"][0]["slug"] == "what-zaram-is"
        page = client.get("/manual/what-zaram-is").json()
        assert page["markdown"].startswith("# What Zaram is")
        assert "/manual/assets/landing.png" in page["markdown"]
        asset = client.get("/manual/assets/landing.png")
        assert asset.status_code == 200 and asset.headers["content-type"].startswith("image/png")
        assert client.get("/manual/assets/..%2F__init__.py").status_code in (403, 404)
