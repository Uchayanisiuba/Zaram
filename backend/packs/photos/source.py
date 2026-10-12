"""Where photographs come from.

One interface and one implementation. The interface is small on purpose so that
Wikimedia Commons, or a Pexels or Unsplash key the user brings, is one more
class and one more row rather than a change to the finder: **a source says how
to ask, how to read the answer and where the bytes live; it never opens a
connection**. The finder sends every request through the egress gate, so a
source that wanted to bypass it has no way to.

Openverse
---------
`https://api.openverse.org/v1/images/` is a search over openly licensed images
run by WordPress, with no key for anonymous use. Verified against the live API
on 11 October 2026:

* A result carries `id` (a UUID), `title`, `creator`, `creator_url`, `license`
  (`by`, `by-sa`, `cc0`, `pdm`, ...), `license_version`, `license_url`,
  `foreign_landing_url` (the page to credit), `width`, `height` and `mature`.
* `license_type=commercial,modification` asks the server for licences that
  permit both uses; the finder still checks `license` itself, because a filter
  is a request and the licence on the result is the fact.
* `/v1/images/{id}/thumb/?full_size=true&compressed=true` returns the picture
  re-encoded server-side: the original size up to roughly 1280 px on the long
  side, as JPEG, typically 80-300 KB. The default (no `full_size`) is 600 px.
* Anonymous use is rate limited (20 requests a minute burst, 200 a day) and
  answers HTTP 429 beyond that. The finder reports it rather than retrying.
* Search is conjunctive: "Lagos Lekki beach at sunset" returns 2 results where
  "Lagos beach" returns 240, which is why the finder retries once with a
  shorter query.

**Every download is built from the result's `id`, on the same host as the
search, and never taken from a URL in the response.** A response is
third-party text; following a `url` field would send a request to whatever host
an image was catalogued from, which the person has not been asked about. One
host means one question.

Wikimedia Commons
-----------------
`https://commons.wikimedia.org/w/api.php`, no key. Verified against the live
API on 11 October 2026 (`action=query`, `generator=search`, `gsrnamespace=6`,
`prop=imageinfo`, `formatversion=2`):

* `query.pages` is a list whose order is **not** the relevance order -- each
  page carries an `index` (its rank) and the list must be sorted by it. A search
  with no result is `{"batchcomplete": true}` with no `query` key at all.
* `imageinfo[0]` has `width`, `height`, `size`, `mime` and `extmetadata`, whose
  values are `{"value": ...}` and are **HTML**: `Artist` is usually an `<a>`
  inside a `<bdi>`, `LicenseShortName` is `CC BY-SA 4.0` or `Public domain`,
  `LicenseUrl` is the creativecommons.org page (absent for public domain).
* Pictures live on `upload.wikimedia.org`, a **second host**, at
  `/wikipedia/commons/[thumb/]<h>/<h2>/<name>[/<width>px-<name>]` where `h` is
  the first hex digit of the MD5 of the file name (underscores for spaces) and
  `h2` the first two. A thumbnail width must be one of Wikimedia's standard
  steps (960, 1280, ...): any other answers HTTP 400.
* Errors can arrive as HTTP 200 with an `{"error": {"code": ...}}` body.

As with Openverse, **the download address is built from the file name, on a
fixed host, and never taken from a URL in the response** -- so the response
cannot send a request anywhere the person was not asked about. The two hosts
are named together in one consent question (`hosts`), because a search that may
happen without the pictures it finds being fetchable would be a half-grant.

A source also says how fast it may be asked (`requests_per_minute`) and how it
introduces itself (`headers`); the finder paces and sends. Both are rows in a
table, not branches: a third source is one more class in `SOURCES`.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.parse
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Protocol

#: Licences that allow commercial use and modification without a share-alike
#: obligation beyond credit. `by-sa` is included: a site that credits and links
#: the licence satisfies it, and excluding it would discard most of the pool.
#: `nc` and `nd` variants are absent on purpose -- a business website is a
#: commercial use and a crop or colour grade is a modification.
ALLOWED_LICENSES = frozenset({"by", "by-sa", "cc0", "pdm"})

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

#: Smaller than this reads as a thumbnail on a page that wants a hero image.
MIN_WIDTH = 640
MIN_HEIGHT = 360


@dataclass(frozen=True)
class PhotoCandidate:
    """One result, reduced to what the page needs to use and credit it."""

    id: str
    title: str
    creator: str
    creator_url: str
    license: str
    license_version: str
    license_url: str
    landing_url: str
    width: int
    height: int
    mature: bool
    provider: str
    #: The source's own wording of the licence ("CC BY-SA 4.0", "Public
    #: domain"), when it gave one. Preferred over one built from the code,
    #: which can only say what a code means, not what the source recorded.
    label: str = ""

    @property
    def license_label(self) -> str:
        return self.label or license_label(self.license, self.license_version)

    @property
    def credit(self) -> str:
        """One line a page can print. Built only from fields the source gave.

        No author is ever made up: when the source has no creator the line
        names the work and the licence and stops there.
        """
        title = self.title.strip() or "Untitled"
        by = f" by {self.creator.strip()}" if self.creator.strip() else ""
        return f"“{title}”{by}, {self.license_label}"


def license_label(code: str, version: str = "") -> str:
    code = (code or "").lower()
    version = (version or "").strip()
    if code == "cc0":
        return f"CC0 {version or '1.0'}"
    if code == "pdm":
        return f"Public Domain Mark {version or '1.0'}"
    name = "CC " + code.upper()
    return f"{name} {version}".strip()


class SourceRefused(Exception):
    """The source answered, but not with results (a rate limit or an error body).

    Raised by `parse` so that an answer which is *not* "no photos matched" is
    never read as one: a "no match" is remembered for a while, and a refusal
    must not be.
    """

    def __init__(self, reason: str, code: str):
        super().__init__(reason)
        self.reason = reason
        self.code = code


class PhotoSource(Protocol):
    """What a photo source knows. It makes no requests itself."""

    #: Shown to the person and written to the log as the name of the source.
    name: str
    #: Two to eight lowercase letters or digits, the prefix of this source's
    #: cached file names. The serving route only accepts names of this shape.
    slug: str
    #: The host the search goes to; the one the consent question is filed under.
    host: str
    #: Every host a request for this source may reach, `host` included. One
    #: consent question covers them all and names them all.
    hosts: tuple[str, ...]
    #: How many requests (searches and downloads together) the finder may make
    #: to this source in any one minute. Set under the source's published limit.
    requests_per_minute: int

    def headers(self) -> dict[str, str]:
        """Extra request headers (how the source asks to be addressed)."""
        ...

    def consent_url(self) -> str:
        """The address the consent question names (the search endpoint)."""
        ...

    def search_url(self, query: str) -> str: ...

    def parse(self, payload: bytes) -> list[PhotoCandidate]: ...

    def download_url(self, candidate: PhotoCandidate) -> str: ...

    def fallback_download_url(self, candidate: PhotoCandidate) -> str | None:
        """A smaller rendering to try when the first is over the size cap."""
        ...


class _BaseSource:
    """Defaults a single-host source with no special headers inherits."""

    host = ""
    requests_per_minute = 18

    @property
    def hosts(self) -> tuple[str, ...]:
        return (self.host,)

    def headers(self) -> dict[str, str]:
        return {}


class OpenverseSource(_BaseSource):
    name = "Openverse"
    slug = "ov"
    host = "api.openverse.org"
    #: The anonymous tier allows 20 requests a minute (and 200 a day). Two under
    #: it, because the far edge of the source's window is not visible from here.
    requests_per_minute = 18

    _BASE = "https://api.openverse.org/v1/images/"

    def consent_url(self) -> str:
        return self._BASE

    def search_url(self, query: str) -> str:
        params = {
            "q": query,
            "license_type": "commercial,modification",
            "mature": "false",
            "filter_dead": "true",
            "page_size": "12",
        }
        return f"{self._BASE}?{urllib.parse.urlencode(params, safe=',')}"

    def parse(self, payload: bytes) -> list[PhotoCandidate]:
        data = _json(payload)
        rows = data.get("results") or []
        if not isinstance(rows, list):
            return []
        found: list[PhotoCandidate] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            ident = str(row.get("id") or "").lower()
            if not _UUID.match(ident):
                continue
            found.append(
                PhotoCandidate(
                    id=ident,
                    title=_text(row.get("title")),
                    creator=_text(row.get("creator")),
                    creator_url=_web_url(row.get("creator_url")),
                    license=_text(row.get("license")).lower(),
                    license_version=_text(row.get("license_version")),
                    license_url=_web_url(row.get("license_url")),
                    landing_url=_web_url(row.get("foreign_landing_url")),
                    width=_int(row.get("width")),
                    height=_int(row.get("height")),
                    mature=bool(row.get("mature")),
                    provider=_text(row.get("provider")),
                )
            )
        return found

    def download_url(self, candidate: PhotoCandidate) -> str:
        # Built from the id alone; see the module docstring.
        return f"{self._BASE}{candidate.id}/thumb/?full_size=true&compressed=true"

    def fallback_download_url(self, candidate: PhotoCandidate) -> str:
        """The 600 px rendering, for when the larger one is over the size cap."""
        return f"{self._BASE}{candidate.id}/thumb/"


# ------------------------------------------------------------ Wikimedia Commons

#: Wikimedia answers a thumbnail width outside its standard steps with 400.
_THUMB_WIDTH = 1280
_THUMB_SMALL = 960
_MIME_OK = frozenset({"image/jpeg", "image/png", "image/webp"})
_FILE_NAME = re.compile(r"^[^/\\\x00-\x1f]{1,200}\.(?:jpe?g|png|webp)$", re.IGNORECASE)
_CC_URL = re.compile(r"creativecommons\.org/licenses/([a-z\-]+)/(\d\.\d)", re.IGNORECASE)
_CC_NAME = re.compile(r"^CC[ -]BY((?:-[A-Za-z]{2})*)[ -](\d\.\d)", re.IGNORECASE)
#: Commons holds nudity and the page is a business site. The role Openverse's
#: `mature=false` plays: a precondition, applied to the words the file's own
#: title and description use, because Commons has no flag to ask for.
_ADULT = re.compile(
    r"\b(nude|nudity|naked|nsfw|erotic\w*|porn\w*|topless|sexual\w*|fetish|genital\w*)\b",
    re.IGNORECASE,
)


class _Text(HTMLParser):
    """Visible text of a fragment of HTML, with scripts and styles dropped."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.href = ""
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "a" and not self.href:
            self.href = dict(attrs).get("href") or ""

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _read_html(fragment: object) -> _Text:
    reader = _Text()
    if isinstance(fragment, str):
        try:
            reader.feed(fragment)
            reader.close()
        except Exception:  # a malformed fragment: keep what was read
            pass
    return reader


def strip_html(fragment: object) -> str:
    """The text of an HTML fragment: no tags, entities decoded, spaces collapsed."""
    return " ".join(html.unescape("".join(_read_html(fragment).parts)).split())


def _first_link(fragment: object) -> str:
    """The first https link in a fragment (``//host/..`` made https), else ''."""
    href = _read_html(fragment).href.strip()
    if href.startswith("//"):
        href = "https:" + href
    return href if href.lower().startswith("https://") else ""


def commons_license(short_name: str, url: str) -> tuple[str, str]:
    """(code, version) in the same vocabulary as Openverse, or ('', '').

    Read from the licence's own address first, then its short name. Anything
    not recognised is ('', ''), which `usable` rejects: a licence Zaram cannot
    name is not one it can credit. `by-nc` and the like come back as themselves
    and are rejected there as well.
    """
    m = _CC_URL.search(url or "")
    if m:
        return m.group(1).lower(), m.group(2)
    lowered = (url or "").lower()
    if "publicdomain/zero" in lowered:
        return "cc0", "1.0"
    if "publicdomain/mark" in lowered:
        return "pdm", "1.0"
    name = (short_name or "").strip()
    if re.match(r"^CC0\b", name, re.IGNORECASE):
        return "cc0", "1.0"
    m = _CC_NAME.match(name)
    if m:
        return ("by" + m.group(1)).lower(), m.group(2)
    if re.match(r"^(public domain|pd\b|pd-)", name, re.IGNORECASE):
        return "pdm", "1.0"
    return "", ""


class WikimediaSource(_BaseSource):
    name = "Wikimedia Commons"
    slug = "wm"
    host = "commons.wikimedia.org"
    hosts = ("commons.wikimedia.org", "upload.wikimedia.org")
    #: Wikimedia publishes no anonymous limit for a descriptive client; this is
    #: a courtesy figure (one a second), not a measured threshold.
    requests_per_minute = 60

    _API = "https://commons.wikimedia.org/w/api.php"
    _UPLOAD = "https://upload.wikimedia.org/wikipedia/commons/"
    #: Wikimedia's user-agent policy asks for a descriptive one, and throttles
    #: a bare library name harder.
    USER_AGENT = "Zaram/0.1 (local app; photo search)"

    def headers(self) -> dict[str, str]:
        return {"User-Agent": self.USER_AGENT}

    def consent_url(self) -> str:
        return self._API

    def search_url(self, query: str) -> str:
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "generator": "search",
            "gsrsearch": f"{query} filetype:bitmap",
            "gsrnamespace": "6",
            "gsrlimit": "12",
            "prop": "imageinfo",
            "iiprop": "size|mime|extmetadata",
            "iiextmetadatafilter": (
                "LicenseShortName|LicenseUrl|Artist|ImageDescription|ObjectName|NonFree|Restrictions"
            ),
        }
        return f"{self._API}?{urllib.parse.urlencode(params, safe='|')}"

    def parse(self, payload: bytes) -> list[PhotoCandidate]:
        data = _json(payload)
        err = data.get("error")
        if err:
            code = str(err.get("code") if isinstance(err, dict) else err)
            if "ratelimit" in code or code == "maxlag":
                raise SourceRefused("Wikimedia Commons asked for fewer requests.", "rate_limited")
            raise SourceRefused("Wikimedia Commons could not answer the search.", "unavailable")
        pages = (data.get("query") or {}).get("pages") or []
        if not isinstance(pages, list):
            return []
        # Not in relevance order as delivered; `index` is the rank.
        ranked = sorted(
            (p for p in pages if isinstance(p, dict)),
            key=lambda p: p["index"] if isinstance(p.get("index"), int) else 10**6,
        )
        found: list[PhotoCandidate] = []
        for page in ranked:
            candidate = self._candidate(page)
            if candidate is not None:
                found.append(candidate)
        return found

    def _candidate(self, page: dict) -> PhotoCandidate | None:
        title = str(page.get("title") or "")
        if not title.startswith("File:"):
            return None
        name = title[5:].strip().replace(" ", "_")
        if not _FILE_NAME.match(name):
            return None
        infos = page.get("imageinfo")
        info = infos[0] if isinstance(infos, list) and infos and isinstance(infos[0], dict) else None
        if info is None or info.get("mime") not in _MIME_OK:
            return None
        meta = info.get("extmetadata") if isinstance(info.get("extmetadata"), dict) else {}

        def raw(key: str) -> object:
            item = meta.get(key)
            return item.get("value") if isinstance(item, dict) else None

        # A file Commons itself marks non-free, or restricts (trademark,
        # personality rights), is not one to put on a business site.
        if strip_html(raw("NonFree")).lower() in ("true", "1") or strip_html(raw("Restrictions")):
            return None
        short = strip_html(raw("LicenseShortName"))
        licence_url = _web_url(strip_html(raw("LicenseUrl")))
        if licence_url.lower().startswith("http://creativecommons.org/"):
            licence_url = "https://" + licence_url[len("http://"):]  # the credits line links https only
        code, version = commons_license(short, licence_url)
        if code and code != "pdm" and not licence_url:
            licence_url = f"https://creativecommons.org/licenses/{code}/{version}/"
        object_name = strip_html(raw("ObjectName")) or name.rsplit(".", 1)[0].replace("_", " ")
        description = strip_html(raw("ImageDescription"))
        quoted = urllib.parse.quote(name, safe="()!,~'-._")
        return PhotoCandidate(
            id=name,
            title=object_name[:160],
            creator=strip_html(raw("Artist"))[:120],
            creator_url=_first_link(raw("Artist")),
            license=code,
            license_version=version,
            license_url=licence_url,
            landing_url=f"https://commons.wikimedia.org/wiki/File:{quoted}",
            width=_int(info.get("width")),
            height=_int(info.get("height")),
            mature=bool(_ADULT.search(f"{object_name} {description}")),
            provider="wikimedia",
            label=short[:60],
        )

    def _path(self, name: str) -> tuple[str, str]:
        # Wikimedia's own sharding scheme, not a security use of MD5.
        digest = hashlib.md5(name.encode("utf-8")).hexdigest()  # noqa: S324
        return f"{digest[0]}/{digest[:2]}", urllib.parse.quote(name, safe="")

    def _thumb(self, name: str, width: int) -> str:
        shard, quoted = self._path(name)
        return f"{self._UPLOAD}thumb/{shard}/{quoted}/{width}px-{quoted}"

    def download_url(self, candidate: PhotoCandidate) -> str:
        # Built from the file name on the fixed upload host; see the docstring.
        # A picture no wider than the large step is fetched as it is: a
        # thumbnail wider than the original is not a request Wikimedia serves.
        if candidate.width > _THUMB_WIDTH:
            return self._thumb(candidate.id, _THUMB_WIDTH)
        shard, quoted = self._path(candidate.id)
        return f"{self._UPLOAD}{shard}/{quoted}"

    def fallback_download_url(self, candidate: PhotoCandidate) -> str | None:
        return self._thumb(candidate.id, _THUMB_SMALL) if candidate.width > _THUMB_SMALL else None


#: The sources Zaram knows, in the order they are tried. Adding one is a class
#: above and a name here.
SOURCES: tuple[type, ...] = (OpenverseSource, WikimediaSource)


def default_sources() -> list[PhotoSource]:
    return [cls() for cls in SOURCES]


def usable(candidates: list[PhotoCandidate], used: set[str]) -> list[PhotoCandidate]:
    """The results that may be put on a page, in the source's own relevance order.

    Order is the source's; this only filters. A filter is a precondition (a
    non-commercial licence cannot go on a business site however relevant it is)
    and relevance then decides among what survives -- not the other way round.
    """
    keep: list[PhotoCandidate] = []
    for c in candidates:
        if c.id in used or c.mature:
            continue
        if c.license not in ALLOWED_LICENSES:
            continue
        if c.width < MIN_WIDTH or c.height < MIN_HEIGHT:
            continue
        keep.append(c)
    return keep


def choose(candidates: list[PhotoCandidate], used: set[str]) -> PhotoCandidate | None:
    """The best usable result, or None."""
    options = usable(candidates, used)
    return options[0] if options else None


def _json(payload: bytes) -> dict:
    """The payload as a JSON object, or `SourceRefused`.

    An answer that is not JSON (a proxy's error page, a truncated body) is not
    "no photos matched" and is not allowed to look like it.
    """
    try:
        data = json.loads(payload.decode("utf-8", "replace"))
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise SourceRefused("The photo source sent an answer Zaram could not read.", "unavailable")
    return data


def _text(value: object) -> str:
    return " ".join(str(value).split()) if isinstance(value, (str, int, float)) else ""


def _web_url(value: object) -> str:
    """A link the page may print: http(s) only, anything else becomes empty."""
    text = _text(value)
    return text if text.lower().startswith(("https://", "http://")) else ""


def _int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
