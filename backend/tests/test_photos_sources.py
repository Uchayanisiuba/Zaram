"""Two photo sources, the index, and the pacing that keeps a page under the limit.

Same method as `test_photos_finder.py`: the real `EgressGate`, `EgressPolicy`,
`EgressLog` and `PendingConfirmations`, with only `urlopen` replaced. Time is a
fake clock that the "network" and the pacer's sleeping both advance, so nothing
here really waits.

What these hold, in the order of the file:

* Wikimedia Commons is read correctly (licences, credit, order, the download
  address) and cannot send a request anywhere but the two hosts it names.
* It is asked about separately, only when the first source could not serve a
  description, and a yes for one source is never a yes for the other.
* A description that was resolved once is not searched for again; a failure is
  not remembered as a success; the index keeps no description text.
* A page stays under a source's limit by waiting a little, and says plainly when
  waiting is not enough or when the time is up.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import threading
import time
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

from core.egress import EgressGate, EgressLog, EgressPolicy, Mode, PendingConfirmations
from packs.photos import finder
from packs.photos.finder import find_photos
from packs.photos.index import INDEX_NAME, MAX_ENTRIES, NO_MATCH_TTL, PhotoIndex, entry_key
from packs.photos.pacing import RequestPacer, default_pacer
from packs.photos.source import (
    OpenverseSource,
    PhotoCandidate,
    SourceRefused,
    WikimediaSource,
    commons_license,
    strip_html,
    usable,
)

OV = "api.openverse.org"
COMMONS = "commons.wikimedia.org"
UPLOAD = "upload.wikimedia.org"
AGENT = "Zaram/0.1 (local app; photo search)"
SECRET = "zzq-spine-only-marker-8f2a"

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 600


def http_error(code: int, host: str = OV, headers=None) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(host, code, "x", headers or {}, io.BytesIO(b""))


# ----------------------------------------------------------------- the two catalogues


def ov_row(n: int, *, license="by", width=1024, height=768):
    ident = f"00000000-0000-4000-8000-{n:012d}"
    return {
        "id": ident,
        "title": f"Photo {n}",
        "creator": f"Creator {n}",
        "creator_url": f"https://flickr.example/people/{n}",
        "license": license,
        "license_version": "2.0",
        "license_url": f"https://creativecommons.org/licenses/{license}/2.0/",
        "foreign_landing_url": f"https://flickr.example/photos/{n}",
        "width": width,
        "height": height,
        "mature": False,
        "provider": "flickr",
    }


def ov_results(*rows) -> bytes:
    return json.dumps({"result_count": len(rows), "results": list(rows)}).encode()


def wm_page(
    n: int,
    *,
    index: int | None = None,
    name: str | None = None,
    short="CC BY-SA 4.0",
    url="https://creativecommons.org/licenses/by-sa/4.0",
    artist='<bdi><a href="//commons.wikimedia.org/wiki/User:Jane" title="User:Jane">Jane Doe</a></bdi>',
    width=3000,
    height=2000,
    mime="image/jpeg",
    description="A quiet harbour",
    extra=None,
):
    file_name = name or f"Harbour {n}.jpg"
    meta = {
        "ObjectName": {"value": f"Harbour number {n}"},
        "ImageDescription": {"value": description},
        "Artist": {"value": artist},
        "LicenseShortName": {"value": short},
    }
    if url:
        meta["LicenseUrl"] = {"value": url}
    meta.update(extra or {})
    return {
        "pageid": 1000 + n,
        "ns": 6,
        "title": f"File:{file_name}",
        "index": n if index is None else index,
        "imageinfo": [{"size": 100000, "width": width, "height": height, "mime": mime, "extmetadata": meta}],
    }


def wm_results(*pages) -> bytes:
    if not pages:
        return b'{"batchcomplete":true}'
    return json.dumps({"batchcomplete": True, "query": {"pages": list(pages)}}).encode()


# ------------------------------------------------------------------------- the clock


class Clock:
    """A clock that only moves when told to, by the test or by sleeping."""

    def __init__(self):
        self.t = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


class _Resp:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._data


class Net:
    """Stands in for `urlopen`, answering for all three hosts.

    Optionally enforces a server-side limit (`limit_per_minute` requests to
    Openverse in any trailing 60 fake seconds, else HTTP 429), so a test can
    prove a page *stayed under* the limit rather than merely that it was told.
    """

    def __init__(self, gate: EgressGate, clock: Clock | None = None):
        self.gate = gate
        self.clock = clock
        self.tick = 0.0
        self.calls: list[str] = []
        self.hosts: list[str] = []
        self.agents: list[str | None] = []
        self.logged_before: list[int] = []
        self.ov_search: object = ov_results(ov_row(1))
        self.wm_search: object = wm_results(wm_page(1))
        self.ov_picture: object = JPEG
        self.wm_picture: object = JPEG
        self.ov_picture_for: dict[str, object] = {}
        self.limit_per_minute: int | None = None
        self.limit_hit = False
        self._ov_times: list[float] = []

    @staticmethod
    def _answer(value, url):
        if callable(value):
            value = value(url)
        if isinstance(value, list):
            value = value.pop(0) if len(value) > 1 else value[0]
        if isinstance(value, Exception):
            raise value
        return _Resp(value)

    def __call__(self, request, timeout=None, **kw):
        url = request.full_url
        host = urllib.parse.urlparse(url).hostname
        self.calls.append(url)
        self.hosts.append(host)
        self.agents.append(request.get_header("User-agent"))
        self.logged_before.append(self.gate.log.count())
        now = self.clock() if self.clock else 0.0
        if self.clock and self.tick:
            self.clock.advance(self.tick)
        if host == OV and self.limit_per_minute is not None:
            self._ov_times = [t for t in self._ov_times if t > now - 60.0]
            if len(self._ov_times) >= self.limit_per_minute:
                self.limit_hit = True
                raise http_error(429)
            self._ov_times.append(now)
        if host == OV and "/thumb/" in url:
            value = self.ov_picture
            for needle, special in self.ov_picture_for.items():
                if needle in url:
                    value = special
            return self._answer(value, url)
        if host == OV:
            return self._answer(self.ov_search, url)
        if host == COMMONS:
            return self._answer(self.wm_search, url)
        if host == UPLOAD:
            return self._answer(self.wm_picture, url)
        raise AssertionError(f"a request to an unexpected host: {url}")

    def to(self, host: str) -> list[str]:
        return [u for u, h in zip(self.calls, self.hosts) if h == host]

    def searches(self, host: str) -> list[str]:
        return [u for u in self.to(host) if "/thumb/" not in u and host != UPLOAD]


@pytest.fixture(autouse=True)
def _fresh_allowance():
    default_pacer().reset()
    yield
    default_pacer().reset()


@pytest.fixture
def gate(tmp_path):
    return EgressGate(
        log=EgressLog(str(tmp_path / "egress.db")),
        policy=EgressPolicy(str(tmp_path / "policy.json")),
    )


@pytest.fixture
def pending():
    p = PendingConfirmations(timeout=5.0)
    yield p
    p.cancel_all()


@pytest.fixture
def net(gate, monkeypatch):
    n = Net(gate)
    monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", n)
    return n


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def folder(tmp_path):
    return tmp_path / "photos" / "web"


@pytest.fixture
def ov_allowed(gate):
    gate.policy.set(OV, Mode.ALLOW)
    return gate


@pytest.fixture
def both_allowed(gate):
    gate.policy.set(OV, Mode.ALLOW)
    gate.policy.set(COMMONS, Mode.ALLOW)
    gate.policy.set(UPLOAD, Mode.ALLOW)
    return gate


def find(gate, pending, folder, descriptions, **kw):
    kw.setdefault("spine_texts", [])
    return find_photos(descriptions, gate=gate, pending=pending, folder=folder, **kw)


def files(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


class Answerer:
    """Answers every question that appears, the way the dialog would.

    ``decisions`` maps the question's host text to yes or no (default yes).
    ``jump`` moves the fake clock when a question is answered: a person who
    takes their time.
    """

    def __init__(self, pending, decisions=None, *, clock: Clock | None = None, jump: float = 0.0):
        self.pending = pending
        self.decisions = decisions or {}
        self.clock = clock
        self.jump = jump
        self.seen: list[dict] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        done: set[str] = set()
        while not self._stop.is_set():
            for waiting in self.pending.pending():
                if waiting["id"] in done:
                    continue
                done.add(waiting["id"])
                self.seen.append(waiting)
                if self.clock and self.jump:
                    self.clock.advance(self.jump)
                self.pending.decide(waiting["id"], approved=self.decisions.get(waiting["host"], True))
            time.sleep(0.005)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(5)
        return False


# =============================================================== reading Wikimedia


class TestReadingWikimediaCommons:
    source = WikimediaSource()

    def parse(self, *pages):
        return self.source.parse(wm_results(*pages))

    def test_results_come_back_in_the_rank_the_source_gave_not_the_order_delivered(self):
        found = self.parse(wm_page(3), wm_page(1), wm_page(2))
        assert [c.title for c in found] == ["Harbour number 1", "Harbour number 2", "Harbour number 3"]

    def test_a_search_with_no_result_is_an_empty_list(self):
        assert self.source.parse(wm_results()) == []

    def test_the_credit_is_built_from_what_the_source_said_with_the_html_removed(self):
        artist = (
            '<bdi><a href="//commons.wikimedia.org/wiki/User:Jane" title="User:Jane">'
            "<span title='photographer'>Jane &amp; Co</span></a></bdi><script>alert(1)</script>"
        )
        c = self.parse(wm_page(1, artist=artist))[0]
        assert c.creator == "Jane & Co"
        assert "<" not in c.creator and "alert" not in c.creator
        assert c.creator_url == "https://commons.wikimedia.org/wiki/User:Jane"
        assert c.license == "by-sa" and c.license_label == "CC BY-SA 4.0"
        assert c.license_url == "https://creativecommons.org/licenses/by-sa/4.0"
        assert c.landing_url == "https://commons.wikimedia.org/wiki/File:Harbour_1.jpg"
        assert c.credit == "“Harbour number 1” by Jane & Co, CC BY-SA 4.0"

    def test_a_file_without_an_artist_is_credited_without_inventing_one(self):
        c = self.parse(wm_page(1, artist=""))[0]
        assert c.creator == ""
        assert c.credit == "“Harbour number 1”, CC BY-SA 4.0"

    @pytest.mark.parametrize(
        "short,url",
        [
            ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0"),
            ("CC BY-SA 3.0", "https://creativecommons.org/licenses/by-sa/3.0/deed.en"),
            ("CC BY-SA 2.5", ""),
            ("CC0", "http://creativecommons.org/publicdomain/zero/1.0/deed.en"),
            ("Public domain", ""),
            ("PD-old-70", ""),
        ],
    )
    def test_the_licences_that_allow_commercial_use_and_changes_are_accepted(self, short, url):
        found = self.parse(wm_page(1, short=short, url=url))
        assert len(usable(found, set())) == 1, found

    @pytest.mark.parametrize(
        "short,url",
        [
            ("CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0"),
            ("CC BY-ND 2.0", "https://creativecommons.org/licenses/by-nd/2.0"),
            ("CC BY-NC-SA 3.0", ""),
            ("GFDL", "https://www.gnu.org/copyleft/fdl.html"),
            ("Copyrighted free use", ""),
            ("Attribution", ""),
            ("", ""),
        ],
    )
    def test_any_other_licence_is_not_used(self, short, url):
        found = self.parse(wm_page(1, short=short, url=url))
        assert usable(found, set()) == []

    def test_what_commons_restricts_or_calls_non_free_is_dropped(self):
        found = self.parse(
            wm_page(1, extra={"NonFree": {"value": "true"}}),
            wm_page(2, extra={"Restrictions": {"value": "personality"}}),
            wm_page(3),
        )
        assert [c.title for c in found] == ["Harbour number 3"]

    def test_only_photographs_of_a_kind_a_page_can_show_are_kept(self):
        found = self.parse(
            wm_page(1, mime="image/svg+xml", name="Map.svg"),
            wm_page(2, mime="image/tiff", name="Scan.tif"),
            wm_page(3, name="Strange.gif", mime="image/gif"),
            wm_page(4, mime="image/png", name="Plan.png"),
            wm_page(5, mime="image/webp", name="Pic.webp"),
        )
        assert [c.id for c in found] == ["Plan.png", "Pic.webp"]

    def test_nudity_and_tiny_pictures_are_not_chosen(self):
        found = self.parse(
            wm_page(1, description="Nude bather on the beach"),
            wm_page(2, width=300, height=200),
            wm_page(3),
        )
        assert [c.title for c in usable(found, set())] == ["Harbour number 3"]

    def test_a_file_name_that_could_point_elsewhere_is_ignored(self):
        found = self.parse(wm_page(1, name="../../etc/passwd.jpg"), wm_page(2, name="a\\b.jpg"), wm_page(3))
        assert [c.title for c in found] == ["Harbour number 3"]

    def test_an_error_body_is_a_refusal_not_an_empty_result(self):
        with pytest.raises(SourceRefused) as limited:
            self.source.parse(b'{"error": {"code": "ratelimited", "info": "slow down"}}')
        assert limited.value.code == "rate_limited"
        with pytest.raises(SourceRefused) as other:
            self.source.parse(b'{"error": {"code": "internal_api_error"}}')
        assert other.value.code == "unavailable"

    def test_an_answer_that_is_not_json_is_not_read_as_no_match(self):
        for source in (self.source, OpenverseSource()):
            with pytest.raises(SourceRefused):
                source.parse(b"<html>Bad gateway</html>")

    def test_the_search_asks_for_files_that_are_bitmaps_and_names_a_user_agent(self):
        url = self.source.search_url("Lagos beach")
        assert url.startswith("https://commons.wikimedia.org/w/api.php?")
        assert "generator=search" in url and "gsrnamespace=6" in url
        assert "gsrsearch=Lagos+beach+filetype%3Abitmap" in url
        assert self.source.headers() == {"User-Agent": AGENT}

    def test_html_is_stripped_to_its_text(self):
        assert strip_html('<p onclick="x()">a <b>b</b> &amp; c</p><style>p{}</style>') == "a b & c"
        assert strip_html(None) == ""

    @pytest.mark.parametrize(
        "short,url,expected",
        [
            ("CC BY-SA 4.0", "", ("by-sa", "4.0")),
            ("CC BY 2.0", "https://creativecommons.org/licenses/by/2.0/", ("by", "2.0")),
            ("CC0", "", ("cc0", "1.0")),
            ("Public domain", "", ("pdm", "1.0")),
            ("GFDL", "", ("", "")),
        ],
    )
    def test_licences_are_read_into_the_vocabulary_openverse_uses(self, short, url, expected):
        assert commons_license(short, url) == expected


class TestWhereWikimediaPicturesAreFetchedFrom:
    source = WikimediaSource()

    def candidate(self, name="A_lady_by_the_Lagos_Jetty.jpg", width=4000):
        return PhotoCandidate(
            id=name, title="t", creator="", creator_url="", license="by", license_version="4.0",
            license_url="", landing_url="", width=width, height=2000, mature=False, provider="wikimedia",
        )

    def shard(self, name):
        digest = hashlib.md5(name.encode()).hexdigest()
        return f"{digest[0]}/{digest[:2]}"

    def test_a_wide_picture_is_fetched_as_a_standard_thumbnail_on_the_upload_host(self):
        c = self.candidate()
        assert self.source.download_url(c) == (
            f"https://upload.wikimedia.org/wikipedia/commons/thumb/{self.shard(c.id)}/{c.id}/1280px-{c.id}"
        )
        assert self.source.fallback_download_url(c).endswith(f"/960px-{c.id}")

    def test_a_narrow_picture_is_fetched_as_it_is_never_as_a_wider_thumbnail(self):
        c = self.candidate(width=1000)
        assert self.source.download_url(c) == (
            f"https://upload.wikimedia.org/wikipedia/commons/{self.shard(c.id)}/{c.id}"
        )
        assert self.source.fallback_download_url(c).endswith(f"/960px-{c.id}")
        assert self.source.fallback_download_url(self.candidate(width=800)) is None

    def test_the_address_is_built_from_the_name_alone_and_is_encoded(self):
        c = self.candidate(name="Rügen,_Beach_(1)_&_x.jpg")
        url = self.source.download_url(c)
        assert urllib.parse.urlparse(url).hostname == UPLOAD
        assert "R%C3%BCgen%2C_Beach_%281%29_%26_x.jpg" in url

    def test_nothing_in_a_response_can_change_the_host_a_picture_is_fetched_from(self):
        page = wm_page(1)
        page["imageinfo"][0]["url"] = "https://evil.example/x.jpg"
        page["imageinfo"][0]["thumburl"] = "https://evil.example/t.jpg"
        found = self.source.parse(wm_results(page))
        for url in (self.source.download_url(found[0]), self.source.fallback_download_url(found[0])):
            assert urllib.parse.urlparse(url).hostname == UPLOAD


# =========================================================== a second source, asked


class TestTheFallbackSourceIsAskedSeparately:
    def test_when_the_first_source_serves_the_second_is_never_asked_or_called(
        self, gate, pending, net, folder
    ):
        gate.policy.set(OV, Mode.ALLOW)
        out = find(gate, pending, folder, ["river at dawn"])
        assert out[0]["source"] == "Openverse"
        assert pending.pending() == []
        assert net.to(COMMONS) == [] and net.to(UPLOAD) == []
        assert gate.policy.has_rule(COMMONS) is False

    def test_no_usable_result_falls_back_with_its_own_question_naming_both_hosts(
        self, gate, pending, net, folder
    ):
        gate.policy.set(OV, Mode.ALLOW)
        net.ov_search = ov_results()
        with Answerer(pending) as answers:
            out = find(gate, pending, folder, ["river at dawn"])
        photo = out[0]
        assert "error" not in photo
        assert photo["source"] == "Wikimedia Commons"
        assert photo["license_label"] == "CC BY-SA 4.0"
        assert photo["creator"] == "Jane Doe"
        assert photo["source_url"] == "https://commons.wikimedia.org/wiki/File:Harbour_1.jpg"
        assert photo["credit"].endswith("by Jane Doe, CC BY-SA 4.0")

        assert len(answers.seen) == 1
        asked = answers.seen[0]
        assert asked["host"] == f"{COMMONS} and {UPLOAD}"
        assert asked["data_class"] == "prompt" and asked["remember"] is True
        assert asked["literal_text"] == "https://commons.wikimedia.org/w/api.php\n\nriver at dawn"

    def test_the_yes_grants_both_hosts_and_logs_the_consent_with_both_named(
        self, gate, pending, net, folder
    ):
        gate.policy.set(OV, Mode.ALLOW)
        net.ov_search = ov_results()
        with Answerer(pending):
            find(gate, pending, folder, ["river at dawn"])
        assert gate.policy.decide(COMMONS).mode is Mode.ALLOW
        assert gate.policy.decide(UPLOAD).mode is Mode.ALLOW
        consent = [e for e in gate.log.entries() if e.meta.get("consent")]
        assert len(consent) == 1
        assert consent[0].meta["hosts"] == [COMMONS, UPLOAD]
        assert COMMONS in consent[0].reason and UPLOAD in consent[0].reason

    def test_a_yes_for_one_source_is_not_a_yes_for_the_other(self, gate, pending, net, folder):
        net.ov_search = ov_results()
        with Answerer(pending, {OV: True}) as answers:
            find(gate, pending, folder, ["river at dawn"])
        assert [s["host"] for s in answers.seen] == [OV, f"{COMMONS} and {UPLOAD}"]
        assert gate.policy.decide(OV).mode is Mode.ALLOW

    def test_a_no_to_the_fallback_sends_nothing_there_and_keeps_the_first_reason(
        self, gate, pending, net, folder
    ):
        gate.policy.set(OV, Mode.ALLOW)
        net.ov_search = ov_results()
        with Answerer(pending, {f"{COMMONS} and {UPLOAD}": False}):
            out = find(gate, pending, folder, ["river at dawn"])
        assert net.to(COMMONS) == [] and net.to(UPLOAD) == []
        assert out[0]["code"] == "no_match"
        assert "Openverse" in out[0]["error"] and "chose not to let Zaram search Wikimedia Commons" in out[0]["error"]
        assert gate.policy.has_rule(COMMONS) is False and gate.policy.has_rule(UPLOAD) is False

    def test_a_no_to_the_first_source_ends_the_find_and_does_not_ask_about_the_second(
        self, gate, pending, net, folder
    ):
        with Answerer(pending, {OV: False}) as answers:
            out = find(gate, pending, folder, ["river at dawn"])
        assert [s["host"] for s in answers.seen] == [OV]
        assert net.calls == []
        assert out[0]["code"] == "consent_declined"

    def test_every_description_that_needs_the_fallback_is_shown_in_one_question(
        self, ov_allowed, pending, net, folder
    ):
        net.ov_search = [ov_results(ov_row(1)), http_error(429), http_error(429)]
        net.wm_search = [wm_results(wm_page(1)), wm_results(wm_page(2))]
        with Answerer(pending) as answers:
            out = find(ov_allowed, pending, folder, ["red door", "blue door", "green door"])
        assert [o["source"] for o in out] == ["Openverse", "Wikimedia Commons", "Wikimedia Commons"]
        assert len(answers.seen) == 1
        assert answers.seen[0]["literal_text"].endswith("\n\nblue door\ngreen door")

    def test_a_rate_limited_first_source_is_not_called_again_for_the_rest_of_the_page(
        self, ov_allowed, pending, net, folder
    ):
        net.ov_search = http_error(429)
        net.wm_search = [wm_results(wm_page(1)), wm_results(wm_page(2))]
        with Answerer(pending):
            out = find(ov_allowed, pending, folder, ["red door", "blue door"])
        assert len(net.searches(OV)) == 1
        assert [o["source"] for o in out] == ["Wikimedia Commons", "Wikimedia Commons"]

    def test_only_dead_links_in_the_first_source_fall_back(self, ov_allowed, pending, net, folder):
        net.ov_search = ov_results(ov_row(1), ov_row(2))
        net.ov_picture = http_error(424)
        with Answerer(pending):
            out = find(ov_allowed, pending, folder, ["red door"])
        assert out[0]["source"] == "Wikimedia Commons"

    def test_when_both_fail_the_reason_a_retry_could_change_is_the_one_shown(
        self, ov_allowed, pending, net, folder
    ):
        net.ov_search = http_error(429)
        net.wm_search = wm_results()
        with Answerer(pending):
            out = find(ov_allowed, pending, folder, ["red door"])
        assert out[0]["code"] == "rate_limited"
        assert "minute" in out[0]["error"]

    def test_offline_does_not_go_on_to_ask_about_another_source(self, ov_allowed, pending, net, folder, monkeypatch):
        monkeypatch.setattr(finder.time, "sleep", lambda _s: None)
        net.ov_search = urllib.error.URLError("unreachable")
        out = find(ov_allowed, pending, folder, ["red door", "blue door"])
        assert [o["code"] for o in out] == ["offline", "offline"]
        assert pending.pending() == [] and net.to(COMMONS) == []

    def test_a_host_the_person_blocked_is_never_overridden_by_a_yes(
        self, ov_allowed, pending, net, folder
    ):
        ov_allowed.policy.set(UPLOAD, Mode.DENY)
        net.ov_search = ov_results()
        out = find(ov_allowed, pending, folder, ["red door"])
        # No question (the source cannot work), the search to the other host is
        # refused by the gate, and the blocked host stays blocked.
        assert pending.pending() == []
        assert ov_allowed.policy.decide(UPLOAD).mode is Mode.DENY
        assert net.to(UPLOAD) == []
        assert "error" in out[0]

    def test_a_person_who_allowed_only_the_search_host_is_asked_about_the_picture_host(
        self, ov_allowed, pending, net, folder
    ):
        ov_allowed.policy.set(COMMONS, Mode.ALLOW)
        net.ov_search = ov_results()
        with Answerer(pending) as answers:
            out = find(ov_allowed, pending, folder, ["red door"])
        assert len(answers.seen) == 1
        assert out[0]["source"] == "Wikimedia Commons"
        assert ov_allowed.policy.decide(UPLOAD).mode is Mode.ALLOW

    def test_the_kill_switch_asks_nothing_of_either_source(self, gate, pending, net, folder):
        gate.policy.set_kill_switch(True)
        out = find(gate, pending, folder, ["red door", "blue door"])
        assert pending.pending() == [] and net.calls == []
        assert [o["code"] for o in out] == ["blocked", "blocked"]


class TestWikimediaIsGatedLikeEverythingElse:
    def test_every_request_to_every_host_is_logged_before_it_is_made(
        self, both_allowed, pending, net, folder
    ):
        net.ov_search = ov_results()
        find(both_allowed, pending, folder, ["red door", "blue door"])
        assert set(net.hosts) == {OV, COMMONS, UPLOAD}
        entries = list(reversed(both_allowed.log.entries()))
        assert [e.url for e in entries] == net.calls
        assert [e.host for e in entries] == net.hosts
        assert all(e.decision == "allowed" and e.source == finder.SOURCE for e in entries)
        # The log already held the request when the "network" received it.
        for i, seen in enumerate(net.logged_before):
            assert seen == i + 1
        assert both_allowed.log.verify() is True

    def test_wikimedia_is_addressed_with_a_descriptive_user_agent_and_openverse_is_not_changed(
        self, both_allowed, pending, net, folder
    ):
        net.ov_search = ov_results()
        find(both_allowed, pending, folder, ["red door"])
        for host, agent in zip(net.hosts, net.agents):
            if host in (COMMONS, UPLOAD):
                assert agent == AGENT
            else:
                assert agent == "Zaram/1.0"

    def test_a_description_from_memory_is_never_sent_to_either_source(
        self, both_allowed, pending, net, folder
    ):
        spine = [f"The user's private note: {SECRET}"]
        net.ov_search = ov_results()
        out = find(both_allowed, pending, folder, [f"beach {SECRET}", "river at dawn"], spine_texts=spine)
        assert out[0]["code"] == "spine_derived"
        assert "error" not in out[1]
        assert net.to(COMMONS)  # the second description did reach Wikimedia
        assert all(SECRET not in u and "zzq" not in u for u in net.calls)
        assert all(SECRET not in (e.url + (e.body or "")) for e in both_allowed.log.entries())

    def test_an_unreadable_spine_sends_nothing_to_either(self, both_allowed, pending, net, folder):
        out = find(both_allowed, pending, folder, ["river at dawn"], spine_texts=None)
        assert out[0]["code"] == "spine_unreadable" and net.calls == []

    def test_the_fallback_searches_only_what_was_shown_to_the_person(self, ov_allowed, pending, net, folder):
        net.ov_search = ov_results()
        with Answerer(pending):
            find(ov_allowed, pending, folder, ["red door"], request_text="a site for Lagos")
        assert "gsrsearch=Lagos+red+door+filetype%3Abitmap" in net.searches(COMMONS)[0]

    def test_the_picture_comes_from_the_upload_host_by_the_computed_address(
        self, both_allowed, pending, net, folder
    ):
        net.ov_search = ov_results()
        find(both_allowed, pending, folder, ["red door"])
        (download,) = net.to(UPLOAD)
        assert download.startswith("https://upload.wikimedia.org/wikipedia/commons/thumb/")
        assert download.endswith("/1280px-Harbour_1.jpg")


# =================================================================== the index


class TestRememberingWhatADescriptionResolvedTo:
    def test_a_repeated_description_costs_no_request_and_keeps_its_credit(
        self, ov_allowed, pending, net, folder
    ):
        first = find(ov_allowed, pending, folder, ["river at dawn"])[0]
        net.calls.clear()
        again = find(ov_allowed, pending, folder, ["River at DAWN"])[0]
        assert net.calls == []
        for key in ("name", "credit", "source", "source_url", "license_label", "creator", "title"):
            assert again[key] == first[key], key

    def test_a_picture_that_came_from_the_fallback_is_remembered_too(self, ov_allowed, pending, net, folder):
        net.ov_search = ov_results()
        with Answerer(pending):
            first = find(ov_allowed, pending, folder, ["river at dawn"])[0]
        net.calls.clear()
        # No answerer this time: nothing is asked and nothing is requested.
        again = find(ov_allowed, pending, folder, ["river at dawn"])[0]
        assert net.calls == [] and pending.pending() == []
        assert again["source"] == "Wikimedia Commons" and again["name"] == first["name"]

    def test_an_index_hit_asks_no_consent_because_nothing_leaves(self, gate, pending, net, folder):
        gate.policy.set(OV, Mode.ALLOW)
        find(gate, pending, folder, ["river at dawn"])
        gate.policy.forget(OV)
        out = find(gate, pending, folder, ["river at dawn"])
        assert "error" not in out[0] and pending.pending() == []

    def test_inline_pictures_are_served_from_the_index_too(self, ov_allowed, pending, net, folder):
        find(ov_allowed, pending, folder, ["river at dawn"])
        net.calls.clear()
        out = find(ov_allowed, pending, folder, ["river at dawn"], inline=True)
        assert out[0]["data_uri"].startswith("data:image/jpeg;base64,") and net.calls == []

    def test_a_failure_is_not_remembered_as_a_success(self, ov_allowed, pending, net, folder):
        net.ov_search = ov_results(ov_row(1))
        net.ov_picture = http_error(424)
        out = find(ov_allowed, pending, folder, ["river at dawn"], sources=[OpenverseSource()])
        assert "error" in out[0]
        net.ov_picture = JPEG
        net.calls.clear()
        again = find(ov_allowed, pending, folder, ["river at dawn"], sources=[OpenverseSource()])
        assert "error" not in again[0] and net.calls  # looked again, and found

    def test_a_rate_limit_is_not_remembered_at_all(self, ov_allowed, pending, net, folder):
        net.ov_search = http_error(429)
        find(ov_allowed, pending, folder, ["river at dawn"], sources=[OpenverseSource()])
        assert not (folder.parent / INDEX_NAME).exists()

    def test_nothing_matched_is_remembered_for_a_while_then_searched_again(
        self, ov_allowed, pending, net, folder
    ):
        net.ov_search = ov_results()
        sources = [OpenverseSource()]
        first = find(ov_allowed, pending, folder, ["river at dawn"], sources=sources)
        assert first[0]["code"] == "no_match"
        searched = len(net.calls)
        find(ov_allowed, pending, folder, ["river at dawn"], sources=sources)
        assert len(net.calls) == searched  # remembered: no new search

        path = folder.parent / INDEX_NAME
        data = json.loads(path.read_text())
        for entry in data["entries"].values():
            entry["at"] -= NO_MATCH_TTL + 5
        path.write_text(json.dumps(data))
        net.ov_search = ov_results(ov_row(1))
        out = find(ov_allowed, pending, folder, ["river at dawn"], sources=sources)
        assert "error" not in out[0]

    def test_no_match_because_the_only_candidate_was_taken_by_another_photo_is_not_remembered(
        self, ov_allowed, pending, net, folder
    ):
        net.ov_search = ov_results(ov_row(1))
        out = find(ov_allowed, pending, folder, ["red door", "blue door"], sources=[OpenverseSource()])
        assert out[0]["title"] == "Photo 1" and out[1]["code"] == "no_match"
        index = PhotoIndex(folder.parent / INDEX_NAME)
        assert index.known_empty(OpenverseSource(), "blue door") is False

    def test_an_entry_goes_with_its_picture(self, ov_allowed, pending, net, folder):
        first = find(ov_allowed, pending, folder, ["river at dawn"])[0]
        (folder / first["name"]).unlink()
        net.calls.clear()
        again = find(ov_allowed, pending, folder, ["river at dawn"])[0]
        assert "error" not in again and net.searches(OV)  # it had to look again
        assert (folder / again["name"]).exists()

    def test_pruning_the_cache_prunes_the_index(self, ov_allowed, pending, net, folder, monkeypatch):
        monkeypatch.setattr(finder, "CACHE_KEPT", 2)
        for n in range(1, 6):
            net.ov_search = ov_results(ov_row(n))
            find(ov_allowed, pending, folder, [f"picture number {n} here"])
            time.sleep(0.02)
        data = json.loads((folder.parent / INDEX_NAME).read_text())
        remembered = [e for e in data["entries"].values() if not e.get("none")]
        assert len([p for p in folder.iterdir() if p.suffix == ".jpg"]) == 2
        assert len(remembered) == 2
        assert {e["name"] for e in remembered} == {p.name for p in folder.iterdir()}

    def test_no_description_text_is_written_to_disk(self, ov_allowed, pending, net, folder):
        find(ov_allowed, pending, folder, ["Zebra crossing at dawn"])
        text = (folder.parent / INDEX_NAME).read_text().lower()
        assert "zebra" not in text and "dawn" not in text
        assert "photo 1" in text  # the credit the page needs is there

    def test_a_tampered_index_cannot_point_a_lookup_outside_the_cache(self, ov_allowed, pending, net, folder):
        find(ov_allowed, pending, folder, ["river at dawn"])
        path = folder.parent / INDEX_NAME
        data = json.loads(path.read_text())
        for entry in data["entries"].values():
            entry["name"] = "../../egress.db"
        path.write_text(json.dumps(data))
        net.calls.clear()
        out = find(ov_allowed, pending, folder, ["river at dawn"])
        assert "error" not in out[0] and net.calls  # ignored, and looked up afresh

    @pytest.mark.parametrize("garbage", ["", "not json", "[]", '{"version": 99, "entries": {}}', '{"entries": 5}'])
    def test_a_damaged_index_is_an_empty_one(self, ov_allowed, pending, net, folder, garbage):
        folder.parent.mkdir(parents=True, exist_ok=True)
        (folder.parent / INDEX_NAME).write_text(garbage)
        assert "error" not in find(ov_allowed, pending, folder, ["river at dawn"])[0]

    def test_the_index_is_capped(self, tmp_path):
        index = PhotoIndex(tmp_path / INDEX_NAME, clock=iter(range(10**6)).__next__)
        source = OpenverseSource()
        for n in range(MAX_ENTRIES + 25):
            index.remember_none(source, f"query {n}")
        data = json.loads((tmp_path / INDEX_NAME).read_text())
        assert len(data["entries"]) == MAX_ENTRIES
        assert entry_key(source, "query 0") not in data["entries"]
        assert entry_key(source, f"query {MAX_ENTRIES + 24}") in data["entries"]

    def test_two_descriptions_of_one_page_never_share_a_remembered_photograph(
        self, ov_allowed, pending, net, folder
    ):
        find(ov_allowed, pending, folder, ["red door"])  # remembers Photo 1 for "red door"
        net.ov_search = ov_results(ov_row(1), ov_row(2))
        out = find(ov_allowed, pending, folder, ["red door", "blue door"])
        assert [o["title"] for o in out] == ["Photo 1", "Photo 2"]


# ==================================================================== the pacing


class TestThePacer:
    def test_a_burst_goes_through_then_the_next_waits_for_the_oldest_to_age_out(self):
        clock = Clock()
        pacer = RequestPacer(clock=clock, sleep=clock.sleep)
        start = clock()
        for _ in range(18):
            assert pacer.acquire("ov", 18, max_wait=20) == 0
        clock.advance(45)
        waited = pacer.acquire("ov", 18, max_wait=20)
        assert waited == pytest.approx(15)
        assert clock() - start == pytest.approx(60)

    def test_it_refuses_rather_than_waiting_longer_than_it_was_told_to(self):
        clock = Clock()
        pacer = RequestPacer(clock=clock, sleep=clock.sleep)
        for _ in range(3):
            pacer.acquire("ov", 3, max_wait=20)
        before = clock()
        assert pacer.acquire("ov", 3, max_wait=20) is None
        assert clock() == before and clock.sleeps == []
        assert pacer.wait_needed("ov", 3) == pytest.approx(60)

    def test_no_sixty_second_window_ever_holds_more_than_the_limit(self):
        clock = Clock()
        pacer = RequestPacer(clock=clock, sleep=clock.sleep)
        sent: list[float] = []
        for i in range(120):
            clock.advance((i * 7) % 5)  # an irregular caller
            if pacer.acquire("ov", 5, max_wait=100) is not None:
                sent.append(clock())
        assert len(sent) == 120
        for i, t in enumerate(sent):
            assert len([s for s in sent if t - 60 < s <= t]) <= 5

    def test_each_source_has_its_own_allowance(self):
        clock = Clock()
        pacer = RequestPacer(clock=clock, sleep=clock.sleep)
        for _ in range(2):
            pacer.acquire("ov", 2, max_wait=0)
        assert pacer.acquire("ov", 2, max_wait=0) is None
        assert pacer.acquire("wm", 2, max_wait=0) == 0

    def test_a_penalty_holds_a_source_back_for_everything_after(self):
        clock = Clock()
        pacer = RequestPacer(clock=clock, sleep=clock.sleep)
        pacer.penalise("ov", 90)
        assert pacer.acquire("ov", 18, max_wait=20) is None
        clock.advance(80)
        assert pacer.acquire("ov", 18, max_wait=20) == pytest.approx(10)


class _Tiny(OpenverseSource):
    def __init__(self, per_minute):
        self.requests_per_minute = per_minute


class TestAPageStaysUnderTheLimit:
    def test_it_waits_a_little_instead_of_meeting_a_429(self, ov_allowed, pending, net, folder, clock):
        net.clock = clock
        net.tick = 25.0
        net.limit_per_minute = 2
        net.ov_search = [ov_results(ov_row(1)), ov_results(ov_row(2)), ov_results(ov_row(3))]
        pacer = RequestPacer(clock=clock, sleep=clock.sleep)
        out = find(
            ov_allowed, pending, folder, ["red door", "blue door", "green door"],
            sources=[_Tiny(2)], pacer=pacer, time_budget=10_000,
        )
        assert [o["title"] for o in out] == ["Photo 1", "Photo 2", "Photo 3"]
        assert net.limit_hit is False
        assert clock.sleeps and max(clock.sleeps) <= finder.MAX_WAIT

    def test_a_wait_longer_than_a_pause_is_a_clear_reason_and_costs_no_request(
        self, ov_allowed, pending, net, folder, clock
    ):
        net.clock = clock
        pacer = RequestPacer(clock=clock, sleep=clock.sleep)
        out = find(
            ov_allowed, pending, folder, ["red door", "blue door"],
            sources=[_Tiny(1)], pacer=pacer,
        )
        # One search used the whole allowance; the download would wait a minute.
        assert [o["code"] for o in out] == ["rate_limited", "rate_limited"]
        assert "minute" in out[0]["error"]
        assert len(net.calls) == 1 and clock.sleeps == []

    def test_a_429_holds_the_source_back_for_the_next_page_too(self, ov_allowed, pending, net, folder, clock):
        net.clock = clock
        net.ov_search = http_error(429, headers={"Retry-After": "120"})
        pacer = RequestPacer(clock=clock, sleep=clock.sleep)
        find(ov_allowed, pending, folder, ["red door"], sources=[OpenverseSource()], pacer=pacer)
        net.calls.clear()
        out = find(ov_allowed, pending, folder, ["blue door"], sources=[OpenverseSource()], pacer=pacer)
        assert net.calls == []
        assert out[0]["code"] == "rate_limited"

    def test_downloads_count_against_the_allowance_as_well_as_searches(
        self, ov_allowed, pending, net, folder, clock
    ):
        net.clock = clock
        pacer = RequestPacer(clock=clock, sleep=clock.sleep)
        find(ov_allowed, pending, folder, ["red door"], sources=[OpenverseSource()], pacer=pacer)
        assert pacer.wait_needed("ov", 18) == 0
        for _ in range(16):
            pacer.acquire("ov", 18, max_wait=0)
        assert pacer.acquire("ov", 18, max_wait=0) is None  # 2 requests + 16 reserved = 18


class TestTheTimeBudget:
    def test_when_time_is_up_the_rest_say_so_and_nothing_more_is_asked_of_anyone(
        self, both_allowed, pending, net, folder, clock
    ):
        net.clock = clock
        net.tick = 30.0
        net.ov_search = [ov_results(ov_row(1)), ov_results(ov_row(2)), ov_results(ov_row(3))]
        pacer = RequestPacer(clock=clock, sleep=clock.sleep)
        out = find(
            both_allowed, pending, folder, ["red door", "blue door", "green door"],
            pacer=pacer, time_budget=50,
        )
        assert "error" not in out[0]
        assert [o["code"] for o in out[1:]] == ["busy", "busy"]
        assert "50 seconds" in out[1]["error"] and "Find photos again" in out[1]["error"]
        assert len(net.calls) == 2  # a search and a download, then it stopped
        assert net.to(COMMONS) == [] and pending.pending() == []

    def test_time_spent_waiting_for_the_person_is_not_the_sources(
        self, gate, pending, net, folder, clock
    ):
        net.clock = clock
        net.tick = 10.0
        pacer = RequestPacer(clock=clock, sleep=clock.sleep)
        with Answerer(pending, clock=clock, jump=600.0):
            out = find(
                gate, pending, folder, ["red door"], sources=[OpenverseSource()],
                pacer=pacer, time_budget=50,
            )
        assert "error" not in out[0]

    def test_with_little_time_left_no_further_candidate_is_tried(
        self, ov_allowed, pending, net, folder, clock
    ):
        net.clock = clock
        net.tick = 10.0
        net.ov_search = ov_results(*[ov_row(n) for n in range(1, 8)])
        net.ov_picture = http_error(424)
        pacer = RequestPacer(clock=clock, sleep=clock.sleep)
        out = find(
            ov_allowed, pending, folder, ["red door"], sources=[OpenverseSource()],
            pacer=pacer, time_budget=25,
        )
        assert len(net.to(OV)) == 2  # the search and one download; 5 left would not finish
        assert out[0]["code"] == "unavailable"


class TestFewerRequestsPerPhoto:
    def test_the_place_less_search_is_made_only_when_nothing_usable_turned_up(
        self, ov_allowed, pending, net, folder
    ):
        net.ov_search = ov_results(ov_row(1))
        net.ov_picture = http_error(424)
        out = find(
            ov_allowed, pending, folder, ["Lagos beach with palm trees at sunset"],
            sources=[OpenverseSource()],
        )
        assert out[0]["code"] == "unavailable"
        assert len(net.searches(OV)) == 2  # the full and the shorter; not the place-less one

    def test_the_same_search_is_not_asked_twice_in_one_find(self, ov_allowed, pending, net, folder):
        def answer(url):
            if "q=beach+dusk" in url:
                return ov_results(ov_row(1), ov_row(2))
            return ov_results()

        net.ov_search = answer
        out = find(
            ov_allowed, pending, folder, ["Lagos beach at dusk", "Accra beach at dusk"],
            sources=[OpenverseSource()],
        )
        assert [o["title"] for o in out] == ["Photo 1", "Photo 2"]
        generic = [u for u in net.searches(OV) if "q=beach+dusk" in u]
        assert len(generic) == 1

    def test_the_search_for_each_description_is_not_repeated_after_a_dead_link(
        self, ov_allowed, pending, net, folder
    ):
        net.ov_search = ov_results(ov_row(1), ov_row(2))
        net.ov_picture_for = {"000000000001": http_error(424)}
        out = find(ov_allowed, pending, folder, ["red door"], sources=[OpenverseSource()])
        assert out[0]["title"] == "Photo 2" and len(net.searches(OV)) == 1
