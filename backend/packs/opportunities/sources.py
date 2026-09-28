"""Turning what a feed returned into `Opportunity` records.

**Parsing only. Nothing here fetches.** The fetch goes through the egress gate
like every other request, so that rule 3's log and rule 5's per-host policy
apply without a second mechanism — the same reason the web pack calls the
gate's fetch rather than `urlopen`.

**Why the adapters are declarative rather than written out.** A source adapter
is twenty lines of "this field is called that" and nothing else, and hardcoding
it means a funder renaming a JSON key is a code change, a release and a broken
install in between. `FieldMap` makes it data: a wrong guess is one line of
config, and a user can add a funder nobody has ever integrated.

**The built-in maps are UNVERIFIED and say so in each docstring.** They were
written on 25 September 2026 in a container whose egress policy blocks every
one of these hosts, so not one of them has been run against a live response.
`CLAUDE.md`'s working agreement is explicit that a number without its condition
is not a measurement, and the same goes for a schema without a response behind
it. Each map carries the one command that checks it. **Verify before shipping
any of them**; they are a starting shape, not a claim.

What *is* verified is the behaviour that matters more: a map pointed at a field
that does not exist produces an opportunity with that field empty, never a
crash and never an invented value.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

from .contracts import Feed, Opportunity

logger = logging.getLogger(__name__)

__all__ = [
    "FieldMap",
    "BUILT_IN_MAPS",
    "from_json",
    "from_rss",
    "parse_date",
    "host_of",
]


def host_of(url: str) -> str:
    """The host an egress policy is written about.

    In one place because the policy is about the host and the log is about the
    host, and re-deriving it at three call sites is three chances to derive it
    differently.
    """
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


#: Formats accepted without argument. Deliberately short.
#:
#: **A mis-read deadline is an invented commitment**, which `obligations/`
#: already names as worse than a missed one — the user reorganises around a
#: date that was never in the call. So this refuses rather than guesses: no
#: natural-language date library, no "30 days from posting" arithmetic, no
#: two-digit years. Anything not matched comes back `None`, which means
#: rolling-or-unknown and puts nothing in anybody's calendar.
#:
#: `dateparser` is in the base install and is deliberately not used here. It is
#: right for reading a date out of a user's own sentence, where a best guess
#: beats nothing; it is wrong for a field that becomes a deadline.
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d, %Y",
    "%b %d, %Y",
)

#: RFC 822, as RSS uses it. Kept apart because it is a feed-format concern
#: rather than a funder's choice of spelling.
_RSS_DATE_FORMATS = (
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%a, %d %b %Y %H:%M:%S",
)


def parse_date(value: Any) -> Optional[date]:
    """A date, or `None`. Never a guess.

    ISO-8601 with a time component is accepted because every JSON API emits it;
    the time is discarded, since a closing *date* is what a deadline is about
    and keeping a timezone-naive hour would imply a precision nobody stated.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    iso = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso).date()
    except ValueError:
        pass

    for fmt in _DATE_FORMATS + _RSS_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _dig(payload: Any, path: str) -> Any:
    """Follow a dotted path, returning `None` rather than raising.

    `None` for a missing field is the whole contract: an adapter aimed at a key
    that was renamed produces an empty field the interface can show as absent,
    which is recoverable. A crash in the poller is not, because the poller runs
    unattended and a stack trace at 06:00 is a feed that silently stopped.
    """
    current = payload
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
            continue
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
            continue
        return None
    return current


def _first(payload: Any, paths: Sequence[str]) -> Any:
    """The first path that yields something. Empty string counts as nothing."""
    for path in paths:
        found = _dig(payload, path)
        if found not in (None, "", [], {}):
            return found
    return None


def _text(payload: Any, paths: Sequence[str]) -> str:
    found = _first(payload, paths)
    if found is None:
        return ""
    if isinstance(found, (list, tuple)):
        return ", ".join(str(item) for item in found if item)
    return str(found).strip()


@dataclass(frozen=True)
class FieldMap:
    """Where each `Opportunity` field lives in one source's payload.

    Every entry is a *list* of paths tried in order, because sources commonly
    carry the same thing under two names across versions and an alternative
    costs nothing.

    `records` is the path to the list of items inside the response envelope —
    `"data"`, `"jobs"`, `"results"`. Empty means the response *is* the list.
    """

    #: Where the list of items sits inside the response.
    records: str = ""
    id: Tuple[str, ...] = ("id",)
    title: Tuple[str, ...] = ("title",)
    organisation: Tuple[str, ...] = ("organisation", "organization")
    url: Tuple[str, ...] = ("url",)
    summary: Tuple[str, ...] = ("summary", "description")
    body: Tuple[str, ...] = ("content",)
    closes: Tuple[str, ...] = ("close_date",)
    posted: Tuple[str, ...] = ("posted_date",)
    location: Tuple[str, ...] = ("location",)
    #: Appended to a relative `url`, for sources that return a path.
    url_prefix: str = ""

    def records_in(self, payload: Any) -> List[Any]:
        found = _dig(payload, self.records) if self.records else payload
        if isinstance(found, list):
            return found
        if isinstance(found, dict):
            return [found]
        return []


def from_json(payload: Any, feed: Feed, fieldmap: FieldMap) -> List[Opportunity]:
    """Every item in one response, as opportunities.

    An item with neither a title nor a URL is dropped with a log line rather
    than stored: it is not a quieter opportunity, it is a parse that went
    somewhere unintended, and keeping it would put a blank row in front of
    somebody as though it meant something.
    """
    out: List[Opportunity] = []
    for index, record in enumerate(fieldmap.records_in(payload)):
        title = _text(record, fieldmap.title)
        url = _text(record, fieldmap.url)
        if url and fieldmap.url_prefix and not url.lower().startswith("http"):
            url = fieldmap.url_prefix.rstrip("/") + "/" + url.lstrip("/")
        if not title and not url:
            logger.debug("feed %s: item %d had neither title nor url", feed.id, index)
            continue

        identifier = _text(record, fieldmap.id) or f"{feed.id}:{index}"
        out.append(
            Opportunity(
                id=f"{feed.id}:{identifier}",
                kind=feed.produces,
                title=title,
                organisation=_text(record, fieldmap.organisation),
                url=url,
                feed_id=feed.id,
                summary=_text(record, fieldmap.summary),
                body=_text(record, fieldmap.body),
                closes=parse_date(_first(record, fieldmap.closes)),
                posted=parse_date(_first(record, fieldmap.posted)),
                location=_text(record, fieldmap.location),
                raw=record if isinstance(record, dict) else {"value": record},
            )
        )
    return out


#: RSS and Atom in one pass. Both are standards rather than one vendor's
#: choice, so unlike the JSON maps below this is not a guess — which is why
#: RSS is the feed kind a user can add for a board nobody has integrated.
_ATOM = "{http://www.w3.org/2005/Atom}"


def _rss_items(root: ET.Element) -> List[ET.Element]:
    items = root.findall(".//item")
    if items:
        return items
    return root.findall(f".//{_ATOM}entry")


def _rss_field(item: ET.Element, *names: str) -> str:
    for name in names:
        found = item.find(name)
        if found is None:
            found = item.find(f"{_ATOM}{name}")
        if found is None:
            continue
        if (found.text or "").strip():
            return (found.text or "").strip()
        # Atom's <link href="..."/> carries no text.
        href = found.get("href")
        if href:
            return href.strip()
    return ""


def from_rss(xml_text: str, feed: Feed) -> List[Opportunity]:
    """An RSS or Atom document, as opportunities.

    Malformed XML returns an empty list rather than raising, for the same
    reason `_dig` returns `None`: this runs unattended, and one funder serving
    a truncated document must not be the reason the whole cycle stops.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("feed %s: could not parse the feed document: %s", feed.id, exc)
        return []

    out: List[Opportunity] = []
    for index, item in enumerate(_rss_items(root)):
        title = _rss_field(item, "title")
        url = _rss_field(item, "link", "id")
        if not title and not url:
            continue
        identifier = _rss_field(item, "guid", "id") or url or str(index)
        out.append(
            Opportunity(
                id=f"{feed.id}:{identifier}",
                kind=feed.produces,
                title=title,
                organisation=_rss_field(item, "author", "dc:creator"),
                url=url,
                feed_id=feed.id,
                summary=_rss_field(item, "description", "summary"),
                body=_rss_field(item, "content"),
                posted=parse_date(_rss_field(item, "pubDate", "published", "updated")),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Built-in maps. Every one UNVERIFIED — see the module docstring.
# --------------------------------------------------------------------------- #

#: Simpler.Grants.gov. Read-only by design: the API's own documentation states
#: that write operations are unsupported and that applications cannot be
#: submitted through it, which is the whole reason this pack stops at a review
#: queue rather than at a send button.
#:
#: Needs a key, obtained through their web interface. Rate limits are 60
#: requests a minute and 10,000 a day, which is far more than a twelve-hour
#: poll uses.
#:
#: UNVERIFIED. Check with:
#:     curl -H "X-Auth: $KEY" -X POST \
#:       https://api.simpler.grants.gov/v1/opportunities/search \
#:       -d '{"pagination":{"page_size":1,"page_offset":1}}'
GRANTS_GOV = FieldMap(
    records="data",
    id=("opportunity_id", "legacy_opportunity_id"),
    title=("opportunity_title", "summary.opportunity_title"),
    organisation=("agency_name", "agency", "top_level_agency_name"),
    url=("opportunity_id",),
    url_prefix="https://simpler.grants.gov/opportunity",
    summary=("summary.summary_description", "summary_description"),
    closes=("summary.close_date", "close_date"),
    posted=("summary.post_date", "post_date"),
)

#: EU Funding & Tenders Portal search API. Public data on calls, topics,
#: tenders and organisations; no submission endpoint.
#:
#: UNVERIFIED. The portal's API support page documents the current request
#: shape; check a single result before trusting these paths.
EU_PORTAL = FieldMap(
    records="results",
    id=("reference", "identifier", "metadata.identifier"),
    title=("title", "metadata.title"),
    organisation=("metadata.programmePeriod", "programme"),
    url=("url",),
    summary=("summary", "metadata.description"),
    closes=("metadata.deadlineDate", "deadlineDate"),
    posted=("metadata.startDate", "startDate"),
)

#: Greenhouse's public per-company job board. One board token per company,
#: no key. This is the upstream route: much of what appears on the large
#: aggregators is syndicated from boards like this one, so polling it gets the
#: same role earlier and with a direct apply link.
#:
#: UNVERIFIED. Check with:
#:     curl https://boards-api.greenhouse.io/v1/boards/<token>/jobs
GREENHOUSE = FieldMap(
    records="jobs",
    id=("id",),
    title=("title",),
    organisation=("company_name",),
    url=("absolute_url",),
    location=("location.name",),
    posted=("updated_at", "first_published"),
)

#: Lever's public postings endpoint. Same shape of arrangement as Greenhouse.
#:
#: UNVERIFIED. Check with:
#:     curl https://api.lever.co/v0/postings/<token>?mode=json
LEVER = FieldMap(
    records="",
    id=("id",),
    title=("text",),
    organisation=("categories.team",),
    url=("hostedUrl", "applyUrl"),
    summary=("descriptionPlain", "description"),
    location=("categories.location",),
    posted=("createdAt",),
)

BUILT_IN_MAPS: Dict[str, FieldMap] = {
    "grants_gov": GRANTS_GOV,
    "eu_portal": EU_PORTAL,
    "greenhouse": GREENHOUSE,
    "lever": LEVER,
}


#: **Not a feed of open calls.** UKRI's Gateway to Research is a database of
#: funding that has *already been awarded* — completed and ongoing projects.
#: An integration against it looks entirely reasonable, returns thousands of
#: well-formed records, matches the user against grants that closed years ago,
#: and passes every test anybody would write for it. Open UKRI opportunities
#: are published elsewhere.
#:
#: This constant exists so that the next person to reach for GtR finds this
#: comment before they find the endpoint. It is referenced by
#: `tests/test_the_opportunity_gate_filters.py`.
GATEWAY_TO_RESEARCH_IS_AWARDED_FUNDING_NOT_OPEN_CALLS = True
