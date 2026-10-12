"""Pictures asked for from the web are found there, never drawn.

**Asked for 12 October 2026:** *"If users say source images or get images
online, as part of a prompt for a website, an app or a document, it should
source the images from the web, not try to generate them."* It followed a resort
site that Zaram began drawing instead of building.

Three layers, each pinned:

* **the words** -- `asks_to_source_pictures` recognises the ways people say it,
  typos included, and not "draw" or "generate";
* **the plan** -- a request that says so is never `image.generate`; a page stays
  a page, a document becomes a document whose body is told how to name photos;
* **the file** -- the documents runtime finds those photos, places them and
  credits them (see `test_a_document_carries_photos_from_the_web` below).

The keyword planner is used where no router is named (deterministic). The
measured class runs the same prompts through the real bge-m3 router, because
that is what classifies in the running app, and skips where it is not resident.
"""

from __future__ import annotations

import pytest

from core.open_project import set_open_project
from core.planner import IntentPlanner
from core.sourced_pictures import asks_to_source_pictures, document_photo_guidance


@pytest.fixture(autouse=True)
def _search_on_no_project(monkeypatch):
    monkeypatch.setenv("ZARAM_WEB_SEARCH", "1")
    set_open_project(None)


# ------------------------------------------------------------------ the words


@pytest.mark.parametrize("text", [
    "source the internet for images you need",
    "sorce the internet for photos you need",
    "Get images online and build me a website",
    "find pictures online for each dish",
    "use photos from the web",
    "with images from the internet",
    "source images for it",
    "use stock photos",
    "real photos of the hotel",
    "search the web for pictures of Lagos",
])
def test_the_ways_people_ask_for_web_pictures(text):
    assert asks_to_source_pictures(text), text


@pytest.mark.parametrize("text", [
    "draw a dog",
    "generate an image of a cat",
    "make a logo for my web app",
    "build a website for my resort",
    "what is in this image",
    "find my photos from last summer",
])
def test_and_what_is_not_asking_for_them(text):
    assert not asks_to_source_pictures(text), text


# ------------------------------------------------------------------- the plan


def _plan(text: str, router=None):
    planner = IntentPlanner(semantic_router=router) if router is not None else IntentPlanner()
    planner.set_code_project_open(lambda: False)
    return planner.create_plan(text)


def capabilities(text: str, router=None) -> list[str]:
    return [s.capability_id for s in _plan(text, router).steps]


SOURCING = [
    "Get images online and build me a website for my resort",
    "Source images from the web and make a landing page for my bakery",
    "build a recipe app, find pictures online for each dish",
    "Write a brochure document about Lagos tourism, source images online",
    "Create a PDF report on electric cars with images from the internet",
    "find an image of a dog online",
]


@pytest.mark.parametrize("text", SOURCING)
def test_a_request_for_web_pictures_is_never_a_drawing(text):
    assert "image.generate" not in capabilities(text), text


#: A semantic router that answers one intent, the way bge-m3 can read "images"
#: as a drawing request whatever else the sentence says.
from tests.test_asking_for_a_picture_reaches_the_image_runtime import FakeRouter as _Routes  # noqa: E402


def test_a_document_read_as_a_drawing_becomes_a_document_with_photo_guidance():
    text = "Write a brochure document about Lagos tourism, source images online"
    plan = _plan(text, router=_Routes("image"))

    assert [s.capability_id for s in plan.steps][-1] == "document.generate"
    body = plan.steps[0].input_data["prompt"]
    assert "photo:" in body and "never draw or invent a picture" in body


def test_a_page_read_as_a_drawing_stays_a_page():
    plan = _plan("Get images online and build me a website for my resort", router=_Routes("image"))
    assert [s.capability_id for s in plan.steps] == ["reasoning.generate"]


def test_a_drawing_is_still_a_drawing():
    assert capabilities("draw a dog", router=_Routes("image")) == ["image.generate"]


def test_a_document_without_web_pictures_gets_no_photo_guidance():
    plan = _plan("write that up as a proposal", router=_Routes("document"))
    assert "photo:" not in plan.steps[0].input_data["prompt"]


def test_the_document_guidance_names_the_contract():
    text = document_photo_guidance()
    assert "](photo:" in text
    assert "never put a person's name" in text


# ----------------------------------------------- measured, on the real router


def _live_router():
    from tests.test_a_translation_is_asked_for_as_a_translation import _live_router as live

    return live()[0]


@pytest.mark.measure
class TestOnTheRealRouter:
    @pytest.mark.parametrize("text", SOURCING)
    def test_never_a_drawing(self, text):
        assert "image.generate" not in capabilities(text, router=_live_router()), text

    def test_a_drawing_request_still_draws(self):
        assert capabilities("generate an image of a blue dog", router=_live_router()) == ["image.generate"]

    @pytest.mark.parametrize("text", [
        "Write a brochure document about Lagos tourism, source images online",
        "Create a PDF report on electric cars with images from the internet",
    ])
    def test_a_document_asking_for_web_photos_is_a_document_told_to_name_them(self, text):
        plan = _plan(text, router=_live_router())
        assert [s.capability_id for s in plan.steps][-1] == "document.generate", text
        assert "](photo:" in plan.steps[0].input_data["prompt"], text


# ------------------------------------------------------------------- the file


class TestADocumentCarriesPhotosFromTheWeb:
    """The real documents runtime makes the real file; only the web search is
    replaced, by a stand-in for `find_photos` that writes a real PNG into the
    photo cache the way the finder does."""

    ANSWER = (
        "# Lagos for visitors\n\n"
        "![Lekki beach](photo:Lagos Lekki beach at sunset)\n\n"
        "Lagos is a coastal city.\n\n"
        "![market](photo:Lagos street food market)\n"
    )

    @pytest.fixture
    def runtime(self, tmp_path, monkeypatch):
        from artifacts.records import ArtifactRecords
        from artifacts.service import ArtifactService
        from artifacts.store import ArtifactStore
        from runtimes.documents.runtime import DocumentsRuntime

        cache = tmp_path / "photos"
        cache.mkdir()
        asked: list = []

        def fake_find(descriptions, *, spine_texts, request_text="", **kw):
            asked.append((list(descriptions), spine_texts, request_text))
            out = []
            for i, d in enumerate(descriptions):
                if "market" in d:
                    out.append({"description": d, "error": "nothing found", "code": "none"})
                    continue
                name = f"openverse-{i}.png"
                (cache / name).write_bytes(_png())
                out.append({
                    "description": d, "name": name, "mime": "image/png", "title": "Lekki Beach",
                    "creator": "A. Photographer", "license_label": "CC BY 2.0", "source": "Openverse",
                    "source_url": "https://example.org/photo/1",
                })
            return out

        async def no_spine():
            return []

        import packs.photos.api as api
        import packs.photos.finder as finder

        monkeypatch.setattr(finder, "find_photos", fake_find)
        monkeypatch.setattr(finder, "photos_dir", lambda: cache)
        monkeypatch.setattr(api, "default_spine_texts", no_spine)
        service = ArtifactService(ArtifactRecords(str(tmp_path / "a.db")), ArtifactStore(tmp_path / "out"))
        rt = DocumentsRuntime(service)
        rt.asked = asked
        return rt

    def _make(self, runtime, answer, fmt="html"):
        import asyncio

        from runtimes.documents.runtime import GENERATE

        return asyncio.run(runtime.execute(GENERATE, {
            "prompt": "Write a brochure document about Lagos tourism, source images online",
            "answer": answer, "session_id": "s1", "format": fmt,
        }))

    def test_a_found_photo_is_in_the_file_with_its_credit(self, runtime):
        import base64

        result = self._make(runtime, self.ANSWER)
        assert result["success"], result
        html = open(result["artifact"]["path"], encoding="utf-8").read()
        assert base64.b64encode(_png()).decode() in html
        assert "Photo credits" in html and "A. Photographer" in html and "CC BY 2.0" in html

    def test_one_search_for_every_photo_with_the_persons_words_exempt(self, runtime):
        self._make(runtime, self.ANSWER)
        (descriptions, spine, request), = runtime.asked
        assert descriptions == ["Lagos Lekki beach at sunset", "Lagos street food market"]
        assert spine == [] and "source images online" in request

    def test_a_photo_not_found_is_left_as_its_words_and_not_invented(self, runtime):
        result = self._make(runtime, self.ANSWER)
        html = open(result["artifact"]["path"], encoding="utf-8").read()
        assert html.count("data:image/png;base64") == 1
        assert "market" in html

    def test_each_placed_photo_is_a_web_source(self, runtime):
        result = self._make(runtime, self.ANSWER)
        web = [s for s in result["artifact"]["sources"] if s["kind"] == "web"]
        assert web and web[0]["url"] == "https://example.org/photo/1"

    def test_the_word_file_carries_it_too(self, runtime):
        import zipfile

        result = self._make(runtime, self.ANSWER, fmt="docx")
        assert result["success"], result
        assert [n for n in zipfile.ZipFile(result["artifact"]["path"]).namelist() if "media/" in n]

    def test_an_answer_with_no_photo_references_searches_nothing(self, runtime):
        self._make(runtime, "# Lagos\n\nA coastal city.")
        assert runtime.asked == []


def _png() -> bytes:
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (8, 8), "teal").save(out, format="PNG")
    return out.getvalue()
