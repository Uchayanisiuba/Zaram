"""The manual — Zaram's own pages, shipped inside it, read by people and by
recall alike.

**Why it is a domain and not only a Help page.** A person asks *how do I
export my memory?* and, until 15 September 2026, the answer came from the
model's training — a guess about a product it has never seen. The pages in
`manual/pages/` are indexed at start into a built-in Knowledge domain called
**Zaram**, so that question is answered from the manual, with a citation,
whatever model is answering — a 7B on this machine included. The same pages
are readable in Settings → Help, because sometimes a person wants the page
rather than the answer.

**Built in, visible, not deletable.** The domain and its source are listed
in Knowledge like any other; hiding them would make them the one thing in
Knowledge a person cannot check. They refuse deletion (rule 4 is about the
person's own facts; these are Zaram's text and would return on the next
update anyway) and are re-read whenever the pages change, which `VERSION`
detects from their contents rather than from a number someone forgot to
bump.

**Nothing here is about the person.** The pages are ordinary documents to
the Spine — origin *document*, source the manual folder — and recall treats
them exactly like a folder the person added. They never leave the machine
except as any recalled passage does, through the gate, logged.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
PAGES = HERE / "pages"
ASSETS = HERE / "assets"

DOMAIN_NAME = "Zaram"
DOMAIN_DESCRIPTION = (
    "How Zaram itself works: what it remembers, what leaves the machine, "
    "documents, pictures, voice, packs, tools, and what to do when something goes wrong."
)

_ASSET_TYPES = {".png": "image/png", ".svg": "image/svg+xml", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


@dataclass(frozen=True)
class Page:
    slug: str
    title: str
    order: int
    path: Path

    def to_json(self) -> Dict[str, Any]:
        return {"slug": self.slug, "title": self.title, "order": self.order}


def _title_of(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def pages() -> List[Page]:
    """The pages in reading order — the numeric prefix on the filename."""
    out: List[Page] = []
    for path in sorted(PAGES.glob("*.md")):
        m = re.match(r"^(\d+)-(.+)\.md$", path.name)
        if not m:
            continue
        out.append(Page(slug=m.group(2), title=_title_of(path), order=int(m.group(1)), path=path))
    return out


def read(slug: str) -> Optional[str]:
    """One page's markdown, or ``None``. Image links are rewritten to the
    route that serves them, so the page reads the same in the app as in the
    folder."""
    page = next((p for p in pages() if p.slug == slug), None)
    if page is None:
        return None
    text = page.path.read_text(encoding="utf-8", errors="replace")
    return text.replace("](assets/", "](/manual/assets/")


def asset(name: str) -> Optional[tuple[Path, str]]:
    """A picture the pages refer to, confined to the assets folder."""
    if "/" in name or "\\" in name or name.startswith("."):
        return None
    path = (ASSETS / name).resolve()
    try:
        path.relative_to(ASSETS.resolve())
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path, _ASSET_TYPES.get(path.suffix.lower(), "application/octet-stream")


def version() -> str:
    """A fingerprint of the pages' contents: the thing that decides whether
    the domain is re-read. A version number would have to be remembered."""
    h = hashlib.sha256()
    for page in pages():
        h.update(page.path.name.encode())
        h.update(page.path.read_bytes())
    return h.hexdigest()[:16]


# ------------------------------------------------------------------ indexing


def _stamp_path(data_dir: Path) -> Path:
    return data_dir / "manual.json"


def indexed_version(data_dir: Path) -> Optional[str]:
    try:
        return json.loads(_stamp_path(data_dir).read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        return None


def builtin_ids(data_dir: Path) -> Dict[str, str]:
    """``{"source_id": ..., "domain_id": ...}`` of the built-in pair, or empty."""
    try:
        raw = json.loads(_stamp_path(data_dir).read_text(encoding="utf-8"))
        return {k: str(raw[k]) for k in ("source_id", "domain_id") if raw.get(k)}
    except (OSError, ValueError):
        return {}


def is_builtin_source(data_dir: Path, source_id: str) -> bool:
    return builtin_ids(data_dir).get("source_id") == source_id


def is_builtin_domain(data_dir: Path, domain_id: str) -> bool:
    return builtin_ids(data_dir).get("domain_id") == domain_id


def ensure_indexed(ingest_service: Any, domains: Any, data_dir: Path) -> Dict[str, Any]:
    """Read the manual into the Spine and the Zaram domain, once per version.

    Idempotent: the same pages are not re-read on every start, and a change
    to any page re-reads them all — a manual that says what last week's
    build did is the failure this guards. Returns what was done, for the log.
    """
    current = version()
    stamp = _stamp_path(data_dir)
    known = builtin_ids(data_dir)
    if indexed_version(data_dir) == current and known.get("source_id") and known.get("domain_id"):
        return {"indexed": False, "version": current, **known}

    source_id, report = ingest_service.scan(str(PAGES))
    domain = next((d for d in domains.all() if d.get("name") == DOMAIN_NAME), None)
    if domain is None:
        domain = domains.create(DOMAIN_NAME, DOMAIN_DESCRIPTION)
    domain_id = str(domain["id"])
    domains.link(domain_id, source_id)

    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(
        json.dumps({"version": current, "source_id": source_id, "domain_id": domain_id}),
        encoding="utf-8",
    )
    indexed = sum(1 for o in report.outcomes if getattr(o, "status", None) and str(getattr(o.status, "value", o.status)) == "indexed")
    logger.info("manual: read %d page(s) into the %s domain (version %s)", indexed, DOMAIN_NAME, current)
    return {"indexed": True, "version": current, "source_id": source_id, "domain_id": domain_id, "pages": indexed}


def ensure_indexed_in_background(ingest_service: Any, domains: Any, data_dir: Path) -> threading.Thread:
    """The same, off the startup path: reading ten pages costs a few seconds
    of embedding, and the window should not wait on it."""

    def run() -> None:
        try:
            ensure_indexed(ingest_service, domains, data_dir)
        except Exception:  # noqa: BLE001 - the manual must never stop Zaram starting
            logger.exception("manual: could not index the pages")

    thread = threading.Thread(target=run, name="zaram-manual", daemon=True)
    thread.start()
    return thread
