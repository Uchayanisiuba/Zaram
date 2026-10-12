"""Resolve photo descriptions into pictures on disk, through the egress gate.

The feature this serves: a page is written with `photo:<description>`
references (see `page.py`), and *after* it is written Zaram turns each
description into a real, openly licensed, credited photograph. This module is
that step. It is synchronous and meant to run on a worker thread -- the reason
is below, and it is the part most likely to be "simplified" into a bug.

Consent, and why it is asked here
---------------------------------
`EgressPolicy` denies a host nobody has an opinion about, and the gate's
confirm hook is only reached for a host that already has a rule. So an unknown
photo source could never produce the question rule 7j needs ("confirm once per
destination, then remember"); the gate would simply refuse. This module asks it
itself, once, **before any request to that source**, through the same
`PendingConfirmations` store the chat path uses -- the interface's existing
confirmation dialog shows it with no change -- and shows the person every
description exactly as it will be sent, on one question for the whole page
rather than one per photo.

* **Yes** writes a host rule (`Mode.ALLOW`, the ordinary `PROMPT` class) for
  every host the source uses and records the decision in the egress log; every
  request after that goes through `EgressGate.request` and is logged
  individually, whether or not it asks again. The rules are visible and
  revocable in Settings like any other.
* **No, silence, or "could not ask"** writes nothing and is logged as
  cancelled. It is not remembered as a refusal: the person said no to this
  page, not to every page, and a "never" is the existing Block control.
* **A host the person already blocked, or the kill switch,** skips the question
  and goes straight to the gate, which refuses and logs it.

**Each source is its own destination.** Saying yes to Openverse says nothing
about Wikimedia Commons: the second is asked separately, with its own question,
and only if it is needed at all -- it is a fallback, tried for the descriptions
the first source could not serve (no usable result, only dead links, or its
rate limit). Those descriptions are asked about in one question, after the first
pass, so the person sees every one of them. A source that uses more than one host
(Wikimedia searches on one and serves pictures from another) names all of them in
its one question and the yes grants all of them, because a grant for the search
alone would be a source that could find a picture it could not fetch. A host the
person had already blocked is never overridden by that grant.

The question blocks a thread until it is answered, and `PendingConfirmations.ask`
refuses outright on a thread running an event loop (it would freeze the server
that must deliver the question). Hence: synchronous code, a worker thread, and
the synchronous `EgressGate.request` rather than the async `gated_session` --
which checks on the loop thread and so could only ever refuse a question.

What leaves, and what does not
------------------------------
Search requests carry a cleaned description (`guard.prepare`: capped, no
addresses or numbers, checked against the Spine -- rule 8). Downloads are
requests for a picture by an opaque id or file name and carry nothing of the
person's. Both are `DataClass.PROMPT` rather than `BROWSE`: a standing browse
allowance must not silently cover sending a person's words, and photographs are
fetched because somebody asked for a page, not because they are browsing.

Pacing, and a budget
--------------------
A free source allows a few requests a minute and one page can need more. Every
request, search or download, first takes a slot from `pacing.RequestPacer`
(a sliding window per source, set under the source's own limit): when a short
wait is enough it waits, and when it is not it stops asking *that source* and
says so. The whole find also has `TIME_BUDGET` seconds, counted from the end of
the consent question rather than including it, so a page never holds for
minutes; what is left when it runs out is reported as `busy`, and both `busy`
and `rate_limited` are retried by the interface's "Find photos again". To spend
fewer requests: a repeat of a description is answered from `index.py` with none,
the same search is never asked twice in one find, the place-less generic search
is made only when nothing usable turned up before it, and no further candidate
is downloaded once the budget is nearly gone.

Retention
---------
Pictures are a **cache**, not the Spine, and nothing here is indexed into
memory. They live in `<data dir>/photos/web/`, are named by a hash of the
source's id (so the same photograph is never fetched twice), and only the
newest `CACHE_KEPT` are kept: after every fetch the rest are deleted. A page
saved with a photo in it must therefore carry the bytes itself (the interface
should ask for `inline` and embed them) rather than point at this folder. The
only other thing kept is `index.py`'s small file, which remembers what a
description resolved to for exactly as long as the picture is cached (and
"nothing matched" for an hour), and holds no description text. Beyond that the
only record is the egress log, which has its own retention control.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
import threading
import time
import urllib.error
import uuid
from pathlib import Path
from typing import Any, Sequence

from core.egress import (
    DataClass,
    EgressDenied,
    EgressGate,
    EgressRequest,
    Mode,
    PendingConfirmations,
    get_gate,
    get_pending,
)

from .guard import (
    DescriptionRefused,
    content_words,
    description_key,
    lines_to_queries,
    clean_description,
    prepare,
)
from .index import PhotoIndex, index_for
from .pacing import RequestPacer, default_pacer
from .source import PhotoCandidate, PhotoSource, SourceRefused, default_sources, usable

logger = logging.getLogger(__name__)

#: What the egress log and the confirmation dialog call this caller.
SOURCE = "photos"
#: Per call. A page that wants more gets a plain "limit" on the rest.
MAX_PHOTOS = 8
#: A hard ceiling on one downloaded picture. The source renders to ~1280 px so
#: real files are a fraction of this; it is the line past which a response is
#: not a photograph for a web page.
MAX_BYTES = 4 * 1024 * 1024
#: How many cached pictures survive. See "Retention" above.
CACHE_KEPT = 80
SEARCH_TIMEOUT = 15.0
DOWNLOAD_TIMEOUT = 25.0
#: How many candidates one description may try before giving up.
#: Five rather than three: on a live page two of three descriptions met only
#: dead catalogue entries (424) within three tries.
MAX_TRIES = 5
#: The longest one request waits for its slot. Past it the source is left alone
#: for now: twenty seconds is a pause, a minute is a page that looks broken.
MAX_WAIT = 20.0
#: The whole find, once the person has answered. Long enough for a page that
#: needs a full minute's allowance twice over; short enough that a page is never
#: held for minutes. What is not done by then is reported, not abandoned silently.
TIME_BUDGET = 60.0
#: Below this many seconds left, no further candidate is tried for a photo that
#: already has one failure: a download that may not finish is the thing that
#: would use up the budget the remaining photos need.
LOW_BUDGET = 10.0
#: How long a 429 keeps a source quiet when it does not say.
DEFAULT_RETRY_AFTER = 60.0

_STOP = frozenset(
    "a an the of in on at by with and or for to from near view photo picture image shot scene".split()
)

#: One lock around the consent question, so two pages asking at once produce
#: one dialog, and the second finds the answer instead of asking again.
_CONSENT_LOCK = threading.Lock()

#: The only shape a cached file name takes, and the only shape the API serves.
CACHE_NAME = re.compile(r"^[a-z0-9]{2,8}-[0-9a-f]{16,40}\.(?:jpg|png|webp)$")
PICTURE_SUFFIXES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


class _Fail(Exception):
    """This photo could not be had; the others may still be."""

    def __init__(self, reason: str, code: str):
        super().__init__(reason)
        self.reason = reason
        self.code = code
        #: Set on a clean "nothing usable" answer, the only failure worth
        #: remembering for a while (see `index.py`).
        self.remember = False


class _Abort(_Fail):
    """No photo can be had from this source right now (blocked, offline, limited)."""


def photos_dir() -> Path:
    """Where fetched photographs are cached: the data directory, never a project."""
    from core.paths import data_dir

    return Path(data_dir()) / "photos" / "web"


def sniff_photo(data: bytes) -> tuple[str, str] | None:
    """(media type, suffix) read from the bytes, or None if not a web photo.

    The type comes from the content, never from a header or a name: it ends up
    in a file name and in a `data:` URI a browser will honour.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def prune_cache(folder: Path, keep: int = CACHE_KEPT) -> int:
    """Delete all but the newest ``keep`` cached photographs. Returns how many went."""
    try:
        files = sorted(
            (p for p in folder.iterdir() if CACHE_NAME.match(p.name)),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return 0
    removed = 0
    for old in files[keep:]:
        try:
            old.unlink()
            removed += 1
        except OSError:
            pass
    return removed


# --------------------------------------------------------------------- results


def _error(raw: str, reason: str, code: str) -> dict[str, Any]:
    return {"description": raw, "error": reason, "code": code}


def _success(raw: str, query: str, c: PhotoCandidate, source: PhotoSource,
             name: str, mime: str, size: int) -> dict[str, Any]:
    return {
        "description": raw,
        "query": query,
        "name": name,
        "url": f"/photos/web/{name}",
        "mime": mime,
        "bytes": size,
        "title": c.title,
        "creator": c.creator,
        "creator_url": c.creator_url,
        "license": c.license,
        "license_label": c.license_label,
        "license_url": c.license_url,
        # Each photo carries its own source, so a page that mixes two credits
        # each honestly.
        "source": source.name,
        "source_url": c.landing_url,
        # The size the source reports for the original; the cached copy is at
        # most about 1280 px on its long side.
        "width": c.width,
        "height": c.height,
        "credit": c.credit,
    }


# --------------------------------------------------------------- one find's state


class _Run:
    """What one `find_photos` call shares between its descriptions and sources."""

    def __init__(self, gate: EgressGate, pacer: RequestPacer, folder: Path,
                 index: PhotoIndex, budget: float):
        self.gate = gate
        self.pacer = pacer
        self.folder = folder
        self.index = index
        self.budget = budget
        self.deadline = pacer.now() + budget
        #: Ids already placed on this page: two photos are never the same one.
        self.used: set[str] = set()
        #: Searches already made in this find, so the same text is asked once.
        self.searched: dict[tuple[str, str], list[PhotoCandidate]] = {}
        #: Sources that are done for this find, and why.
        self.out: dict[str, _Abort] = {}
        #: Set when nothing more can be asked of anyone (offline, out of time).
        self.stopped: _Abort | None = None

    def remaining(self) -> float:
        return self.deadline - self.pacer.now()

    def extend(self, seconds: float) -> None:
        """Give back time spent waiting for the person rather than a source."""
        if seconds > 0:
            self.deadline += seconds

    def low(self) -> bool:
        return self.remaining() < LOW_BUDGET

    def note_abort(self, source: PhotoSource, abort: _Abort) -> None:
        self.out[source.slug] = abort
        if abort.code in ("offline", "busy") or (
            abort.code == "blocked" and self.gate.policy.kill_switch()
        ):
            self.stopped = abort

    def search(self, source: PhotoSource, text: str) -> list[PhotoCandidate]:
        key = (source.slug, text.lower())
        if key in self.searched:
            return self.searched[key]
        payload = _search(self, source, text)
        try:
            found = source.parse(payload)
        except SourceRefused as refused:
            if refused.code == "rate_limited":
                self.pacer.penalise(source.slug, DEFAULT_RETRY_AFTER)
                raise _Abort(f"{refused.reason} Try again in a minute.", "rate_limited") from refused
            raise _Abort(refused.reason, refused.code) from refused
        self.searched[key] = found
        return found


# ------------------------------------------------------------------ the gateway


def _pace(run: _Run, source: PhotoSource) -> None:
    """Take this source's next slot, waiting if a short wait is enough."""
    if run.remaining() <= 0:
        raise _Abort(_busy(run), "busy")
    cap = min(MAX_WAIT, run.remaining())
    waited = run.pacer.acquire(source.slug, source.requests_per_minute, max_wait=cap)
    if waited is not None:
        return
    needed = run.pacer.wait_needed(source.slug, source.requests_per_minute)
    if needed > MAX_WAIT:
        raise _Abort(
            f"{source.name}’s free limit is being kept to, so Zaram stopped asking it for now. "
            "Try again in a minute.",
            "rate_limited",
        )
    raise _Abort(_busy(run), "busy")


def _busy(run: _Run) -> str:
    return (
        f"Zaram stopped looking for photos after {int(run.budget)} seconds so the page "
        "would not be held up. Press Find photos again for the rest."
    )


def _retry_after(exc: urllib.error.HTTPError) -> float:
    headers = getattr(exc, "headers", None)
    try:
        value = float(headers.get("Retry-After")) if headers is not None else 0.0
    except (TypeError, ValueError, AttributeError):
        value = 0.0
    return min(max(value, 0.0), 300.0) or DEFAULT_RETRY_AFTER


def _fetch(run: _Run, source: PhotoSource, url: str, timeout: float) -> bytes:
    """One request, through the gate. Raises `_Fail` / `_Abort`, never anything else."""
    _pace(run, source)
    try:
        return run.gate.request(
            url,
            timeout=timeout,
            source=SOURCE,
            data_class=DataClass.PROMPT,
            headers={"Accept": "application/json, image/*", **source.headers()},
        )
    except EgressDenied as exc:
        raise _Abort(str(exc), "blocked") from exc
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            # Held back for everything that follows, not only this page.
            run.pacer.penalise(source.slug, _retry_after(exc))
            raise _Abort(
                f"{source.name}’s free limit was reached. Try again in a minute.",
                "rate_limited",
            ) from exc
        if exc.code >= 500:
            raise _Abort(f"{source.name} is not answering right now ({exc.code}).", "unavailable") from exc
        raise _Fail(f"{source.name} refused the request ({exc.code}).", "unavailable") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise _Abort(
            f"Zaram could not reach {source.name}. Check the connection and try again.",
            "offline",
        ) from exc


# --------------------------------------------------------------------- consent


def _hosts_to_ask(gate: EgressGate, source: PhotoSource) -> list[str]:
    """The source's hosts nobody has a rule for (and nothing has sealed).

    Empty when there is nothing to ask: every host has an opinion already, the
    kill switch is on, or one host was deliberately blocked -- in which case the
    source cannot work and the gate, not a question, is what says so.
    """
    policy = gate.policy
    if policy.kill_switch():
        return []
    if any(policy.has_rule(h) and policy.decide(h).mode is Mode.DENY for h in source.hosts):
        return []
    return [h for h in source.hosts if not policy.has_rule(h) and policy.decide(h).mode is Mode.DENY]


def _ask_once(
    gate: EgressGate,
    pending: PendingConfirmations,
    source: PhotoSource,
    work: list[tuple[str, str, str]],
) -> tuple[list[tuple[str, str, str]], dict[str, dict[str, Any]]]:
    """The one question per destination. Returns (work to do, errors by key).

    ``work`` is `(key, raw description, query)`. The body shown is the queries,
    one per line, which is exactly what goes in the searches; the person may
    strike or edit lines, and an edit is what is searched.
    """
    errors: dict[str, dict[str, Any]] = {}
    with _CONSENT_LOCK:
        if not _hosts_to_ask(gate, source):
            return work, errors

        # Every host the grant covers is named in the question. The dialog
        # reads `host` for its headline and for what a yes is remembered for,
        # so for a two-host source it says both; the log keeps the search host.
        hosts_text = " and ".join(source.hosts)
        body = "\n".join(q for _, _, q in work)
        request = EgressRequest(
            host=hosts_text,
            method="GET",
            url=source.consent_url(),
            body=body,
            source=SOURCE,
            data_class=DataClass.PROMPT,
            remember=True,
        )
        approved = pending.ask(request)

        if not approved:
            reason = request.refusal_reason
            gate.log.append(
                host=source.host, method="GET", url=request.url, body=body,
                decision="cancelled",
                reason=reason or "you chose not to send this",
                source=SOURCE, byte_count=0,
                meta={"consent": True, "descriptions": len(work), "hosts": list(source.hosts)},
            )
            message = (
                f"Zaram did not search {source.name}: {reason}."
                if reason
                else f"You chose not to let Zaram search {source.name} for photos."
            )
            code = "consent_unanswered" if reason else "consent_declined"
            for key, raw, _ in work:
                errors[key] = _error(raw, message, code)
            return [], errors

        kept = _apply_edit(work, body, request.body or "")
        for key, raw, _ in work:
            if not any(k == key for k, _, _ in kept):
                errors[key] = _error(
                    raw, f"You removed this description before it was sent to {source.name}.", "removed"
                )

        # Only the hosts still without a rule: an explicit rule is never
        # overwritten by a consent that was about something else.
        for host in _hosts_to_ask(gate, source):
            gate.policy.set(host, Mode.ALLOW)
        gate.log.append(
            host=source.host, method="GET", url=request.url, body=request.body,
            decision="allowed",
            reason=(
                f"you confirmed searching {source.name} for photos; requests to "
                f"{hosts_text} are allowed from now on"
            ),
            source=SOURCE, byte_count=0,
            meta={"consent": True, "descriptions": len(kept), "hosts": list(source.hosts)},
        )
        return kept, errors


def _apply_edit(
    work: list[tuple[str, str, str]], original: str, edited: str
) -> list[tuple[str, str, str]]:
    """Fold the person's edit of the shown body back into the work.

    Same number of lines: a line is the same photo, reworded, and is cleaned
    again (never trusted) before it is searched. Fewer or more: only lines that
    still match a shown query survive, because a changed count cannot say which
    photo a changed line meant. Anything not matched is simply not sent.
    """
    if edited == original:
        return work
    lines = lines_to_queries(edited)
    if len(lines) == len(work):
        out: list[tuple[str, str, str]] = []
        for (key, raw, _), line in zip(work, lines):
            try:
                out.append((key, raw, clean_description(line)))
            except DescriptionRefused:
                continue
        return out
    shown = {q: (k, r) for k, r, q in work}
    return [(shown[line][0], shown[line][1], line) for line in lines if line in shown]


# ------------------------------------------------------------------ one photo


def _cache_stem(source: PhotoSource, candidate_id: str) -> str:
    digest = hashlib.sha256(f"{source.name}:{candidate_id}".encode()).hexdigest()[:20]
    return f"{source.slug}-{digest}"


def _cached(folder: Path, stem: str) -> Path | None:
    for suffix in PICTURE_SUFFIXES:
        path = folder / f"{stem}{suffix}"
        if path.is_file():
            return path
    return None


def _download(run: _Run, source: PhotoSource, c: PhotoCandidate) -> bytes:
    urls = [source.download_url(c)]
    smaller = source.fallback_download_url(c)
    if smaller and smaller not in urls:
        urls.append(smaller)
    for url in urls:
        try:
            data = _fetch(run, source, url, DOWNLOAD_TIMEOUT)
        except _Abort as stop:
            # A download that timed out or met a server error is this
            # picture's problem -- the source renders each one on request and
            # some take too long -- not proof the connection is gone. Seen
            # live: one slow render was reported as "could not reach" and the
            # remaining photos of the page were abandoned with it. Only a
            # refusal, the rate limit and the pacing still stop everything.
            if stop.code in ("blocked", "rate_limited", "busy"):
                raise
            raise _Fail(f"{source.name} could not send that photo in time.", "unavailable") from stop
        if len(data) <= MAX_BYTES:
            return data
    raise _Fail("The photo was larger than Zaram will download.", "too_large")


def _search(run: _Run, source: PhotoSource, query: str) -> bytes:
    """One search, asked a second time if the first cannot be reached.

    Seen live: a single slow answer was taken for "offline" and every photo on
    the page was given up, while the next request a minute later took 2.7 s. A
    connection that is really down fails twice, quickly; one that stalled once
    usually answers the second time. A refusal or the rate limit is not retried.
    """
    try:
        return _fetch(run, source, source.search_url(query), SEARCH_TIMEOUT)
    except _Abort as stop:
        if stop.code != "offline":
            raise
    time.sleep(1.0)
    return _fetch(run, source, source.search_url(query), SEARCH_TIMEOUT)


def _attempts(query: str) -> list[tuple[str, str]]:
    """The searches to try for a description, in order: (kind, text)."""
    attempts = [("full", query)]
    words = content_words(query, _STOP)
    short = " ".join(words[:3])
    if short and short.lower() != query.lower():
        attempts.append(("short", short))
    # Last, the same picture without the place: a catalogue holds few photos
    # of "Lagos beach" and many of "beach". A page about the place is better
    # served by a beach than by a grey card -- and the credit names what it is.
    generic = " ".join(w for w in words if not w[:1].isupper())
    generic = " ".join(generic.split()[:3])
    if generic and generic.lower() not in {a.lower() for _, a in attempts}:
        attempts.append(("generic", generic))
    return attempts


def _resolve_one(
    run: _Run,
    source: PhotoSource,
    query: str,
) -> tuple[PhotoCandidate, str, str, int, bytes | None]:
    """Search, choose, fetch and cache. Returns (candidate, name, mime, size, bytes)."""
    # The best result is not always retrievable: a catalogue lists pictures
    # whose original has since gone (the thumbnail service answers 424 for
    # those -- seen against the live API). Try the next few rather than
    # failing the photo on the first dead link, and when every result for the
    # full description is dead, the shorter query's. Bounded across both,
    # because each try is a request and the free tier is a limit shared with
    # the person's next page.
    failure: _Fail | None = None
    tried: set[str] = set()
    saw_usable = False  # anything usable at all, even if another photo took it
    cut_short = False  # stopped before every search was made
    for kind, attempt in _attempts(query):
        # The place-less search is for when nothing usable turned up. If an
        # earlier search found candidates, they were tried: asking for
        # a different picture would only spend another request.
        if kind == "generic" and tried:
            break
        found = run.search(source, attempt)
        if usable(found, set()):
            saw_usable = True
        for chosen in usable(found, run.used | tried):
            if len(tried) >= MAX_TRIES or (tried and run.low()):
                cut_short = True
                break
            tried.add(chosen.id)
            try:
                return _keep(run, source, chosen)
            except _Abort:
                raise
            except _Fail as fail:
                failure = fail
        if len(tried) >= MAX_TRIES or (tried and run.low()):
            cut_short = True
            break
    if failure is not None:
        raise failure
    none = _Fail(f"No openly licensed photo matched “{query}” on {source.name}.", "no_match")
    none.remember = not saw_usable and not cut_short
    raise none


def _keep(
    run: _Run, source: PhotoSource, chosen: PhotoCandidate
) -> tuple[PhotoCandidate, str, str, int, bytes | None]:
    """Make sure one chosen result is on disk. Returns what `_resolve_one` does."""
    folder = run.folder
    stem = _cache_stem(source, chosen.id)
    existing = _cached(folder, stem)
    if existing is not None:
        # Already on this machine: nothing to download. Touched so it counts as
        # recent and survives the next prune.
        try:
            os.utime(existing, None)
        except OSError:
            pass
        mime = PICTURE_SUFFIXES[existing.suffix]
        return chosen, existing.name, mime, existing.stat().st_size, None

    data = _download(run, source, chosen)
    kind = sniff_photo(data)
    if kind is None:
        raise _Fail("What came back was not a photograph, so it was not kept.", "not_a_picture")
    mime, suffix = kind

    folder.mkdir(parents=True, exist_ok=True)
    final = folder / f"{stem}{suffix}"
    tmp = folder / f".{uuid.uuid4().hex}.tmp"
    try:
        tmp.write_bytes(data)
        os.replace(tmp, final)
    except OSError as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise _Fail("Zaram could not save the photo on this machine.", "disk") from exc
    if prune_cache(folder, CACHE_KEPT):
        run.index.drop_missing(folder)
    return chosen, final.name, mime, len(data), data


# ------------------------------------------------------------------- the entry


#: Capitalised words that start an instruction rather than name a place.
_NOT_PLACES = frozenset(
    "i build make create write design generate give add put please can could would "
    "html css javascript js zaram website site page web landing home".split()
)
_CAPITALISED = re.compile(r"[A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)*")


def place_in(request_text: str) -> str:
    """The first place the person's own request names, or ``""``.

    A model told to begin every description with the place does it some of the
    time -- seen live: one run named Lagos in every description, the next only
    in the first, and the gallery came back as Tokyo nightlife and a Mexican
    beach. So the place is read from the person's request, deterministically,
    for any model. Only their words: a capitalised run that does not open a
    sentence and is not an instruction word. "Build a tourism website for
    Lagos, Nigeria" gives "Lagos"; "Cape Town" stays two words.
    """
    for m in _CAPITALISED.finditer(request_text or ""):
        before = request_text[: m.start()].rstrip()
        if not before or before[-1] in ".!?:\n":
            continue  # opens a sentence: a capital that says nothing
        words = [w for w in m.group(0).split() if w.lower() not in _NOT_PLACES]
        if words and not any(w.isupper() and len(w) > 1 for w in words):
            return " ".join(words)
    return ""


def _with_place(query: str, place: str) -> str:
    """``query`` led by ``place`` when it does not already mention it."""
    if not place or place.lower() in query.lower():
        return query
    return f"{place} {query}"


#: When several sources failed for one description, the reason worth showing:
#: the ones a retry can change come first.
_PRIORITY = {"rate_limited": 0, "busy": 1, "offline": 2}


def _final_error(raw: str, fails: list[_Fail], notes: list[str]) -> dict[str, Any]:
    if not fails:
        return _error(raw, "No photo was found.", "no_match")
    best = min(fails, key=lambda f: _PRIORITY.get(f.code, 9))
    reason = " ".join([best.reason, *notes])
    return _error(raw, reason, best.code)


def find_photos(
    descriptions: Sequence[str],
    *,
    spine_texts: Sequence[str] | None,
    request_text: str = "",
    source: PhotoSource | None = None,
    sources: Sequence[PhotoSource] | None = None,
    gate: EgressGate | None = None,
    pending: PendingConfirmations | None = None,
    folder: Path | None = None,
    inline: bool = False,
    pacer: RequestPacer | None = None,
    time_budget: float | None = None,
) -> list[dict[str, Any]]:
    """One entry per description, in the order given: a photo or a reason.

    ``spine_texts`` is **required** and has no default: it is the text of what
    the Spine holds, for the rule-8 check in `guard`. Pass `[]` when there is
    nothing stored and `None` when the Spine could not be read (which refuses
    every description, because a check that cannot look has not passed).
    ``request_text`` is the person's own request for the page, whose words are
    exempt from that check.

    ``sources`` are tried in order, each only for what the one before could not
    serve; ``source`` is shorthand for a list of one. The default is every
    source Zaram knows.

    Never raises for an expected failure. A refused description, a declined
    question, an offline machine and a rate limit each come back as
    `{description, error, code}` so a page can show a labelled placeholder;
    nothing is invented in their place, and nothing is written to disk unless a
    photograph was actually received and recognised.

    Blocking: it may wait for the person to answer the consent question, so call
    it on a worker thread (`asyncio.to_thread`), never on the event loop.
    """
    chain: list[PhotoSource] = list(sources) if sources else ([source] if source else default_sources())
    gate = gate or get_gate()
    pending = pending or get_pending()
    folder = folder or photos_dir()

    by_key: dict[str, dict[str, Any]] = {}
    work: list[tuple[str, str, str]] = []  # (key, raw, query)
    place = place_in(request_text)
    order: list[tuple[str, str]] = []  # (key, raw) per input

    for raw in descriptions:
        raw_text = raw if isinstance(raw, str) else str(raw)
        key = description_key(raw_text) or f"\0{len(order)}"
        order.append((key, raw_text))
        if key in by_key or any(k == key for k, _, _ in work):
            continue
        try:
            query = prepare(raw_text, spine_texts, request_text)
        except DescriptionRefused as refused:
            by_key[key] = _error(raw_text, refused.reason, refused.code)
            continue
        if len(work) >= MAX_PHOTOS:
            by_key[key] = _error(
                raw_text, f"Zaram fetches at most {MAX_PHOTOS} photos for one page.", "limit"
            )
            continue
        work.append((key, raw_text, _with_place(query, place)))

    run = _Run(gate, pacer or default_pacer(), folder, index_for(folder), time_budget or TIME_BUDGET)
    resolved: dict[str, tuple[dict[str, Any], str, str, bytes | None]] = {}
    failures: dict[str, list[_Fail]] = {}
    notes: dict[str, list[str]] = {}

    # What is already known costs no request, and so needs no question.
    for key, raw_text, query in work:
        for src in chain:
            hit = run.index.lookup(src, query, folder, run.used)
            if hit is not None:
                run.used.add(hit.candidate.id)
                result = _success(raw_text, query, hit.candidate, src, hit.name, hit.mime, hit.size)
                resolved[key] = (result, hit.name, hit.mime, None)
                break

    for n, src in enumerate(chain):
        todo = [w for w in work if w[0] not in resolved and w[0] not in by_key]
        if not todo or run.stopped is not None:
            break
        live: list[tuple[str, str, str]] = []
        for key, raw_text, query in todo:
            if run.index.known_empty(src, query):
                failures.setdefault(key, []).append(
                    _Fail(f"No openly licensed photo matched “{query}” on {src.name}.", "no_match")
                )
            else:
                live.append((key, raw_text, query))
        if not live:
            continue

        asked_at = run.pacer.now()
        live, declined = _ask_once(gate, pending, src, live)
        run.extend(run.pacer.now() - asked_at)  # waiting for the person is not the source's time
        if n == 0:
            by_key.update(declined)
        else:
            # A later source is a fallback: its being declined leaves the
            # earlier reason standing and adds one sentence, not a verdict.
            for key, err in declined.items():
                notes.setdefault(key, []).append(err["error"])

        for key, raw_text, query in live:
            if run.stopped is not None:
                failures.setdefault(key, []).append(run.stopped)
                continue
            if src.slug in run.out:
                failures.setdefault(key, []).append(run.out[src.slug])
                continue
            try:
                c, name, mime, size, blob = _resolve_one(run, src, query)
            except _Abort as abort:
                run.note_abort(src, abort)
                failures.setdefault(key, []).append(abort)
                continue
            except _Fail as fail:
                failures.setdefault(key, []).append(fail)
                if fail.remember:
                    run.index.remember_none(src, query)
                continue
            run.used.add(c.id)
            run.index.remember(src, query, c, name, mime, size)
            resolved[key] = (_success(raw_text, query, c, src, name, mime, size), name, mime, blob)

    # One entry per input, so a page that used the same description twice finds
    # it under both spellings without a second request having been made.
    out: list[dict[str, Any]] = []
    for key, raw_text in order:
        if key in resolved:
            result, name, mime, blob = resolved[key]
            entry = dict(result)
            if inline:
                try:
                    data = blob if blob is not None else (folder / name).read_bytes()
                    entry["data_uri"] = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
                except OSError:
                    pass
        elif key in by_key:
            entry = dict(by_key[key])
        else:
            entry = _final_error(raw_text, failures.get(key, []), notes.get(key, []))
        entry["description"] = raw_text
        out.append(entry)
    return out
