"""HTTP routes for web photos.

    POST /photos/find        descriptions in, photos or reasons out
    GET  /photos/web/{name}  a cached photograph, by bare name

Mount with `app.include_router(photos_router)`. These routes add no
authentication of their own: `RequireApiSecret` covers every route, so a page
the person visits cannot reach them any more than it can reach `/memory`.

`POST /photos/find` can take as long as a person takes to answer the consent
question (up to the confirmation timeout, two minutes) because it holds the
request open while the question is pending. The question is an ordinary
pending egress confirmation, so the interface's existing dialog -- which polls
`GET /egress/pending` -- shows it and answers it through
`POST /egress/pending/{id}`; nothing new is needed on that side.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Awaitable, Callable, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .finder import CACHE_NAME, MAX_PHOTOS, PICTURE_SUFFIXES, find_photos, photos_dir
from .source import SOURCES

logger = logging.getLogger(__name__)

#: Reads the text of everything the Spine holds, for the rule-8 check.
#: Returns `[]` when there is no Spine in this process (nothing to leak) and
#: `None` when there is one and it could not be read (refuse everything).
SpineReader = Callable[[], Awaitable[Optional[list[str]]]]


async def default_spine_texts() -> Optional[list[str]]:
    """Every stored fact and passage, found through the running app's kernel.

    **Fails closed.** If the kernel cannot be found at all -- the app was
    started under a module name this does not look for -- that is "could not
    read", not "empty": reporting an empty Spine because the lookup missed
    would turn the rule-8 check into a no-op without anyone being told.
    """
    kernel = None
    for name in ("main", "__main__", "backend.main"):
        candidate = getattr(sys.modules.get(name), "kernel", None)
        if candidate is not None and hasattr(candidate, "memory_runtime"):
            kernel = candidate
            break
    if kernel is None:
        return None
    runtime = getattr(kernel, "memory_runtime", None)
    if runtime is None:
        return []
    try:
        records = await runtime._store.all_records(include_superseded=True)
    except Exception:
        logger.exception("could not read the Spine for the photo description check")
        return None
    return [r.content for r in records if getattr(r, "content", None)]


class FindRequest(BaseModel):
    #: The `photo:` descriptions found in the page, as written.
    descriptions: list[str] = Field(default_factory=list, max_length=64)
    #: The person's own request for the page. Their words are exempt from the
    #: Spine check: they typed them, so they are not recalled.
    request: str = Field(default="", max_length=4000)
    #: Also return each picture as a `data:` URI, for a sandboxed preview with
    #: no network and for a page that must carry its own pictures when saved.
    inline: bool = False


def build_router(spine_reader: SpineReader | None = None) -> APIRouter:
    router = APIRouter(prefix="/photos", tags=["photos"])
    reader: SpineReader = spine_reader or default_spine_texts

    @router.post("/find")
    async def find(body: FindRequest):
        """Resolve photo descriptions to credited, openly licensed pictures.

        One entry per description, in order: either a photograph
        (`name`, `url`, `credit`, `license_label`, ...) or `{error, code}`.
        Always HTTP 200 for an expected failure -- a declined question or an
        offline machine is an answer, and the page shows a placeholder for it.
        """
        texts = await reader()
        results = await asyncio.to_thread(
            find_photos,
            body.descriptions,
            spine_texts=texts,
            request_text=body.request,
            inline=body.inline,
        )
        found = sum(1 for r in results if "error" not in r)
        return {
            "results": results,
            "found": found,
            "failed": len(results) - found,
            "limit": MAX_PHOTOS,
            # Every source Zaram may search, in the order it tries them. Each
            # photo names the one it came from (`source`).
            "sources": [cls.name for cls in SOURCES],
        }

    @router.get("/web/{name}")
    async def web_photo(name: str):
        """A fetched photograph, by bare file name.

        Only a name of the exact shape Zaram generates, with a picture suffix:
        nothing in the URL can point anywhere else, so there is no path to
        traverse. The same shape as `GET /tools/pictures/{name}`.
        """
        safe = Path(name).name
        suffix = Path(safe).suffix.lower()
        if safe != name or suffix not in PICTURE_SUFFIXES or not CACHE_NAME.match(safe):
            raise HTTPException(status_code=404, detail="No such photo.")
        path = photos_dir() / safe
        if not path.is_file():
            raise HTTPException(
                status_code=404,
                detail="No such photo. Zaram keeps only the most recent ones.",
            )
        return FileResponse(
            str(path),
            media_type=PICTURE_SUFFIXES[suffix],
            headers={"Cache-Control": "private, max-age=3600"},
        )

    return router


router = build_router()
