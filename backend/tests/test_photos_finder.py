"""Resolving photo descriptions: consent, the gate, the log, and what is kept.

No real network. The real `EgressGate`, `EgressPolicy`, `EgressLog` and
`PendingConfirmations` are used, with only `urlopen` replaced, so these tests
grade the property that matters -- every request that would leave passed the
gate and was logged *before* it was made -- rather than a mock of it.
"""

from __future__ import annotations

import io
import json
import threading
import time
import urllib.error
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.egress import EgressGate, EgressLog, EgressPolicy, Mode, PendingConfirmations
from packs.photos import finder
from packs.photos.api import build_router
from packs.photos.index import INDEX_NAME
from packs.photos.pacing import default_pacer
from packs.photos.source import OpenverseSource
from packs.photos.finder import (
    CACHE_KEPT,
    MAX_BYTES,
    MAX_PHOTOS,
    find_photos,
    prune_cache,
    sniff_photo,
)

HOST = "api.openverse.org"
SECRET = "zzq-spine-only-marker-8f2a"

#: Enough of a JPEG for the sniffer, which reads the first bytes only.
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 600
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100


def ident(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


def row(n: int, *, license="by", width=1024, height=768, mature=False, **extra):
    base = {
        "id": ident(n),
        "title": f"Photo {n}",
        "creator": f"Creator {n}",
        "creator_url": f"https://flickr.example/people/{n}",
        "license": license,
        "license_version": "2.0",
        "license_url": f"https://creativecommons.org/licenses/{license}/2.0/",
        "foreign_landing_url": f"https://flickr.example/photos/{n}",
        "width": width,
        "height": height,
        "mature": mature,
        "provider": "flickr",
        # Present in the real response and deliberately never followed.
        "url": f"https://elsewhere.example/{n}.jpg",
        "thumbnail": f"https://api.openverse.org/v1/images/{ident(n)}/thumb/",
    }
    base.update(extra)
    return base


def results(*rows) -> bytes:
    return json.dumps({"result_count": len(rows), "results": list(rows)}).encode()


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
    """Stands in for `urlopen`. Answers by URL and records what was asked."""

    def __init__(self, gate: EgressGate):
        self.gate = gate
        self.calls: list[str] = []
        #: How many log entries existed at the moment each request was made.
        self.logged_before: list[int] = []
        self.search_answers: list[bytes | Exception] = []
        self.search_default: bytes | Exception = results(row(1))
        self.picture: bytes | Exception = JPEG
        self.picture_for: dict[str, bytes | Exception] = {}

    def __call__(self, request, timeout=None, **kw):
        url = request.full_url
        self.calls.append(url)
        self.logged_before.append(self.gate.log.count())
        if "/thumb/" in url:
            answer = self.picture
            for needle, special in self.picture_for.items():
                if needle in url:
                    answer = special
            if isinstance(answer, Exception):
                raise answer
            return _Resp(answer)
        answer = self.search_answers.pop(0) if self.search_answers else self.search_default
        if isinstance(answer, Exception):
            raise answer
        return _Resp(answer)

    @property
    def searches(self) -> list[str]:
        return [u for u in self.calls if "/thumb/" not in u]

    @property
    def downloads(self) -> list[str]:
        return [u for u in self.calls if "/thumb/" in u]


@pytest.fixture(autouse=True)
def _fresh_allowance():
    """The request allowance is per process; each test starts with a full one."""
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
    p = PendingConfirmations(timeout=2.0)
    yield p
    p.cancel_all()


@pytest.fixture
def net(gate, monkeypatch):
    n = Net(gate)
    monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", n)
    return n


@pytest.fixture
def folder(tmp_path):
    return tmp_path / "photos" / "web"


@pytest.fixture
def allowed(gate):
    """A person who has already said yes to the destination."""
    gate.policy.set(HOST, Mode.ALLOW)
    return gate


def find(gate, pending, folder, descriptions, **kw):
    kw.setdefault("spine_texts", [])
    # One source here: these tests are about Openverse's behaviour, and the
    # fallback to a second source has its own file (`test_photos_sources.py`).
    kw.setdefault("sources", [OpenverseSource()])
    return find_photos(descriptions, gate=gate, pending=pending, folder=folder, **kw)


def files(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


# ------------------------------------------------------------------ the happy path


class TestResolving:
    def test_a_description_becomes_a_cached_credited_photo(self, allowed, pending, net, folder):
        out = find(allowed, pending, folder, ["Lagos Lekki beach at sunset"])
        assert len(out) == 1
        photo = out[0]
        assert "error" not in photo
        assert photo["description"] == "Lagos Lekki beach at sunset"
        assert photo["title"] == "Photo 1"
        assert photo["creator"] == "Creator 1"
        assert photo["license"] == "by"
        assert photo["license_label"] == "CC BY 2.0"
        assert photo["license_url"].startswith("https://creativecommons.org/")
        assert photo["source_url"] == "https://flickr.example/photos/1"
        assert photo["credit"] == "\u201cPhoto 1\u201d by Creator 1, CC BY 2.0"
        assert photo["url"] == f"/photos/web/{photo['name']}"
        assert files(folder) == [photo["name"]]
        assert (folder / photo["name"]).read_bytes() == JPEG
        assert finder.CACHE_NAME.match(photo["name"])

    def test_the_search_asks_for_commercial_modifiable_licences_and_safe_results(
        self, allowed, pending, net, folder
    ):
        find(allowed, pending, folder, ["river at dawn"])
        url = net.searches[0]
        assert url.startswith("https://api.openverse.org/v1/images/?")
        assert "q=river+at+dawn" in url
        assert "license_type=commercial,modification" in url
        assert "mature=false" in url

    def test_the_download_is_built_from_the_id_on_the_same_host_never_from_the_response(
        self, allowed, pending, net, folder
    ):
        find(allowed, pending, folder, ["river at dawn"])
        assert net.downloads == [
            f"https://api.openverse.org/v1/images/{ident(1)}/thumb/?full_size=true&compressed=true"
        ]
        assert all("elsewhere.example" not in u for u in net.calls)
        assert all(u.startswith("https://api.openverse.org/") for u in net.calls)

    def test_the_first_usable_result_in_the_sources_order_wins(self, allowed, pending, net, folder):
        net.search_default = results(row(7), row(8), row(9))
        out = find(allowed, pending, folder, ["river at dawn"])
        assert out[0]["title"] == "Photo 7"

    def test_png_and_webp_are_kept_with_the_right_suffix(self, allowed, pending, net, folder):
        net.picture = PNG
        a = find(allowed, pending, folder, ["red door"])[0]
        net.picture = WEBP
        net.search_default = results(row(2))
        b = find(allowed, pending, folder, ["blue door"])[0]
        assert a["name"].endswith(".png") and a["mime"] == "image/png"
        assert b["name"].endswith(".webp") and b["mime"] == "image/webp"

    def test_inline_returns_the_picture_as_a_data_uri(self, allowed, pending, net, folder):
        out = find(allowed, pending, folder, ["river at dawn"], inline=True)
        assert out[0]["data_uri"].startswith("data:image/jpeg;base64,")

    def test_a_photo_already_on_disk_is_not_downloaded_again(self, allowed, pending, net, folder):
        find(allowed, pending, folder, ["river at dawn"])
        # Without the index only the file is known: the search is repeated, the
        # download is not.
        (folder.parent / INDEX_NAME).unlink()
        net.calls.clear()
        out = find(allowed, pending, folder, ["river at dawn"])
        assert "error" not in out[0]
        assert net.downloads == []
        assert len(net.searches) == 1

    def test_a_repeated_description_is_answered_from_the_index_with_no_request(
        self, allowed, pending, net, folder
    ):
        first = find(allowed, pending, folder, ["river at dawn"])[0]
        net.calls.clear()
        again = find(allowed, pending, folder, ["River  at dawn"])[0]
        assert net.calls == []
        assert again["name"] == first["name"]
        assert again["credit"] == first["credit"]
        assert again["source_url"] == first["source_url"]

    def test_a_long_description_retries_once_with_a_shorter_query(self, allowed, pending, net, folder):
        net.search_answers = [results(), results(row(3))]
        out = find(allowed, pending, folder, ["Lagos Lekki beach at sunset"])
        assert "error" not in out[0]
        assert len(net.searches) == 2
        assert "q=Lagos+Lekki+beach" in net.searches[1]

    def test_no_match_is_a_reason_not_an_invented_picture(self, allowed, pending, net, folder):
        net.search_default = results()
        out = find(allowed, pending, folder, ["river at dawn"])
        assert out[0]["code"] == "no_match"
        assert "name" not in out[0]
        assert files(folder) == []

    def test_different_descriptions_never_get_the_same_photo(self, allowed, pending, net, folder):
        net.search_default = results(row(1), row(2))
        out = find(allowed, pending, folder, ["red door", "blue door"])
        assert out[0]["title"] == "Photo 1"
        assert out[1]["title"] == "Photo 2"


# ---------------------------------------------------------------------- licences


class TestLicenceFilter:
    @pytest.mark.parametrize("bad", ["by-nc", "by-nd", "by-nc-sa", "by-nc-nd", "sampling+", ""])
    def test_a_licence_that_forbids_commercial_use_or_changes_is_skipped(
        self, allowed, pending, net, folder, bad
    ):
        net.search_default = results(row(1, license=bad), row(2, license="cc0"))
        out = find(allowed, pending, folder, ["river at dawn"])
        assert out[0]["title"] == "Photo 2"
        assert out[0]["license_label"] == "CC0 2.0" or out[0]["license"] == "cc0"

    @pytest.mark.parametrize("good", ["by", "by-sa", "cc0", "pdm"])
    def test_the_permitted_licences_are_accepted(self, allowed, pending, net, folder, good):
        net.search_default = results(row(1, license=good))
        assert "error" not in find(allowed, pending, folder, ["river at dawn"])[0]

    def test_mature_and_tiny_results_are_skipped(self, allowed, pending, net, folder):
        net.search_default = results(
            row(1, mature=True),
            row(2, width=300, height=200),
            row(3, width=0, height=0),
            row(4),
        )
        out = find(allowed, pending, folder, ["river at dawn"])
        assert out[0]["title"] == "Photo 4"

    def test_only_unusable_results_is_no_match(self, allowed, pending, net, folder):
        net.search_default = results(row(1, license="by-nc"), row(2, width=100, height=100))
        out = find(allowed, pending, folder, ["river at dawn"])
        assert out[0]["code"] == "no_match"
        assert net.downloads == []

    def test_a_result_without_a_creator_is_credited_without_inventing_one(
        self, allowed, pending, net, folder
    ):
        net.search_default = results(row(1, creator=None, title="Harbour"))
        out = find(allowed, pending, folder, ["river at dawn"])
        assert out[0]["credit"] == "\u201cHarbour\u201d, CC BY 2.0"

    def test_a_result_with_a_malformed_id_is_ignored(self, allowed, pending, net, folder):
        net.search_default = results(row(1, id="../../etc/passwd"), row(2))
        out = find(allowed, pending, folder, ["river at dawn"])
        assert out[0]["title"] == "Photo 2"


# ------------------------------------------------------------------ what is kept


class TestWhatIsKept:
    def test_a_response_over_the_size_cap_is_refused_and_nothing_is_written(
        self, allowed, pending, net, folder
    ):
        net.picture = JPEG + b"\x00" * MAX_BYTES
        out = find(allowed, pending, folder, ["river at dawn"])
        assert out[0]["code"] == "too_large"
        assert files(folder) == []

    def test_the_smaller_rendering_is_tried_when_the_large_one_is_over_the_cap(
        self, allowed, pending, net, folder
    ):
        big = JPEG + b"\x00" * MAX_BYTES
        net.picture_for = {"full_size=true": big}
        out = find(allowed, pending, folder, ["river at dawn"])
        assert "error" not in out[0]
        assert len(net.downloads) == 2
        assert net.downloads[1].endswith("/thumb/")

    @pytest.mark.parametrize(
        "body",
        [
            b"<html><body>Sign in to continue</body></html>",
            b'{"detail": "not found"}',
            b"GIF89a" + b"\x00" * 50,
            b"",
            b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
        ],
    )
    def test_what_is_not_a_photograph_is_refused_and_nothing_is_written(
        self, allowed, pending, net, folder, body
    ):
        net.picture = body
        out = find(allowed, pending, folder, ["river at dawn"])
        assert out[0]["code"] == "not_a_picture"
        assert files(folder) == []

    def test_the_cache_keeps_only_the_newest(self, tmp_path):
        folder = tmp_path / "web"
        folder.mkdir()
        for i in range(CACHE_KEPT + 7):
            p = folder / f"ov-{i:020x}.jpg"
            p.write_bytes(JPEG)
            import os

            os.utime(p, (1_000_000 + i, 1_000_000 + i))
        (folder / "notes.txt").write_text("not a cached photo")
        removed = prune_cache(folder)
        assert removed == 7
        left = sorted(p.name for p in folder.iterdir() if p.suffix == ".jpg")
        assert len(left) == CACHE_KEPT
        # The oldest went, the newest stayed, and a stranger's file was not touched.
        assert f"ov-{0:020x}.jpg" not in left
        assert f"ov-{CACHE_KEPT + 6:020x}.jpg" in left
        assert (folder / "notes.txt").exists()

    def test_fetching_prunes(self, allowed, pending, net, folder, monkeypatch):
        monkeypatch.setattr(finder, "CACHE_KEPT", 2)
        for n in range(1, 5):
            net.search_default = results(row(n))
            find(allowed, pending, folder, [f"picture number {n} here"])
            time.sleep(0.02)
        assert len([p for p in folder.iterdir() if p.suffix == ".jpg"]) == 2

    def test_the_sniffer_reads_the_bytes_not_a_header(self):
        assert sniff_photo(JPEG) == ("image/jpeg", ".jpg")
        assert sniff_photo(PNG) == ("image/png", ".png")
        assert sniff_photo(WEBP) == ("image/webp", ".webp")
        assert sniff_photo(b"<html>") is None
        assert sniff_photo(b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 20) is None


# --------------------------------------------------------------- limits, dedupe


class TestLimits:
    def test_identical_descriptions_are_fetched_once_and_answered_under_each_spelling(
        self, allowed, pending, net, folder
    ):
        out = find(allowed, pending, folder, ["Busy market", "busy  MARKET", "busy market"])
        assert len(out) == 3
        assert [o["description"] for o in out] == ["Busy market", "busy  MARKET", "busy market"]
        assert len({o["name"] for o in out}) == 1
        assert len(net.searches) == 1 and len(net.downloads) == 1

    def test_at_most_eight_photos_are_fetched_and_the_rest_say_why(
        self, allowed, pending, net, folder
    ):
        net.search_default = results(*[row(n) for n in range(1, 30)])
        descriptions = [f"scene number {word}" for word in
                        "one two three four five six seven eight nine ten".split()]
        out = find(allowed, pending, folder, descriptions)
        assert len(out) == 10
        assert [("error" in o) for o in out] == [False] * MAX_PHOTOS + [True] * 2
        assert out[-1]["code"] == "limit"
        assert len(net.downloads) == MAX_PHOTOS

    def test_an_empty_list_asks_nothing_and_sends_nothing(self, gate, pending, net, folder):
        assert find(gate, pending, folder, []) == []
        assert net.calls == [] and pending.pending() == []


# ----------------------------------------------------------------- rule 8 / guard


class TestRuleEight:
    def test_a_description_carrying_spine_content_is_never_sent(
        self, allowed, pending, net, folder
    ):
        spine = [f"The user's private note: {SECRET}"]
        out = find(allowed, pending, folder, [f"beach {SECRET}", "river at dawn"], spine_texts=spine)
        assert out[0]["code"] == "spine_derived"
        assert "error" not in out[1]
        # Not in any request, in any form, and not in the log either.
        assert all(SECRET not in u and "zzq" not in u for u in net.calls)
        assert all(SECRET not in (e.url + (e.body or "")) for e in allowed.log.entries())

    def test_an_unreadable_spine_sends_nothing(self, allowed, pending, net, folder):
        out = find(allowed, pending, folder, ["river at dawn"], spine_texts=None)
        assert out[0]["code"] == "spine_unreadable"
        assert net.calls == []

    def test_a_refused_description_does_not_cost_a_consent_question(
        self, gate, pending, net, folder
    ):
        out = find(gate, pending, folder, ["mail ada@example.com about it"])
        assert out[0]["code"] == "refused_description"
        assert pending.pending() == [] and net.calls == []

    def test_descriptions_are_capped_before_they_are_sent(self, allowed, pending, net, folder):
        find(allowed, pending, folder, ["one two three four five six seven eight nine ten"])
        assert "q=one+two+three+four+five+six+seven+eight" in net.searches[0]
        assert "nine" not in net.searches[0]


# ------------------------------------------------------------- the gate and the log


class TestEveryRequestIsGatedAndLogged:
    def test_each_request_is_logged_before_it_is_made(self, allowed, pending, net, folder):
        net.search_default = results(row(1), row(2))
        find(allowed, pending, folder, ["red door", "blue door"])
        assert len(net.calls) == 4
        entries = list(reversed(allowed.log.entries()))
        assert [e.url for e in entries] == net.calls
        assert all(e.decision == "allowed" and e.host == HOST for e in entries)
        assert all(e.source == finder.SOURCE for e in entries)

    def test_the_log_knew_before_each_send(self, allowed, pending, net, folder):
        net.search_default = results(row(1), row(2))
        before = allowed.log.count()
        find(allowed, pending, folder, ["red door", "blue door"])
        for i, seen in enumerate(net.logged_before):
            assert seen == before + i + 1, (i, seen, before)

    def test_nothing_is_sent_by_any_route_but_the_gate(self, allowed, pending, net, folder):
        """With the gate replaced by one that refuses, there is no request at all."""
        allowed.policy.set(HOST, Mode.DENY)
        out = find(allowed, pending, folder, ["red door"])
        assert net.calls == []
        assert out[0]["code"] == "blocked"

    def test_the_log_verifies_after_a_run(self, allowed, pending, net, folder):
        net.search_default = results(row(1), row(2))
        find(allowed, pending, folder, ["red door", "blue door"])
        assert allowed.log.verify() is True


# -------------------------------------------------------------------- consent


def _answer_when_asked(pending, *, approve: bool, body: str | None = None, hold=None):
    """Answer the first pending question from another thread, as the dialog would."""
    seen: dict = {}

    def run():
        for _ in range(400):
            waiting = pending.pending()
            if waiting:
                seen.update(waiting[0])
                if hold:
                    hold.wait(5)
                pending.decide(waiting[0]["id"], approved=approve, body=body)
                return
            time.sleep(0.01)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t, seen


class TestConsent:
    def test_an_unknown_destination_asks_once_and_shows_every_description_as_sent(
        self, gate, pending, net, folder
    ):
        net.search_default = results(row(1), row(2))
        t, seen = _answer_when_asked(pending, approve=True)
        out = find(gate, pending, folder, ["red door", "Blue river at dawn"])
        t.join(5)

        assert seen["host"] == HOST
        assert seen["data_class"] == "prompt"
        assert seen["remember"] is True
        assert seen["source"] == finder.SOURCE
        # The literal text: where it goes, then each description as searched.
        assert seen["literal_text"] == "https://api.openverse.org/v1/images/\n\nred door\nBlue river at dawn"
        assert "error" not in out[0] and "error" not in out[1]

    def test_a_yes_is_remembered_and_the_next_page_does_not_ask(self, gate, pending, net, folder):
        t, _ = _answer_when_asked(pending, approve=True)
        find(gate, pending, folder, ["red door"])
        t.join(5)
        assert gate.policy.decide(HOST).mode is Mode.ALLOW

        net.search_default = results(row(2))
        out = find(gate, pending, folder, ["blue door"])  # no thread answers: it must not ask
        assert "error" not in out[0]
        assert pending.pending() == []

    def test_the_yes_itself_is_on_the_record(self, gate, pending, net, folder):
        t, _ = _answer_when_asked(pending, approve=True)
        find(gate, pending, folder, ["red door"])
        t.join(5)
        consent = [e for e in gate.log.entries() if e.meta.get("consent")]
        assert len(consent) == 1
        assert consent[0].decision == "allowed"
        assert consent[0].byte_count == 0
        assert "red door" in (consent[0].body or "")
        assert "you confirmed" in consent[0].reason

    def test_a_no_sends_nothing_writes_nothing_and_is_logged(self, gate, pending, net, folder):
        t, _ = _answer_when_asked(pending, approve=False)
        out = find(gate, pending, folder, ["red door", "blue door"])
        t.join(5)
        assert net.calls == []
        assert files(folder) == []
        assert [o["code"] for o in out] == ["consent_declined", "consent_declined"]
        assert all("error" in o and "name" not in o for o in out)
        assert gate.policy.decide(HOST).mode is Mode.DENY
        assert gate.policy.has_rule(HOST) is False
        entries = gate.log.entries()
        assert [e.decision for e in entries] == ["cancelled"]

    def test_a_no_is_not_a_never(self, gate, pending, net, folder):
        t, _ = _answer_when_asked(pending, approve=False)
        find(gate, pending, folder, ["red door"])
        t.join(5)
        t2, seen = _answer_when_asked(pending, approve=True)
        out = find(gate, pending, folder, ["red door"])
        t2.join(5)
        assert seen["host"] == HOST  # asked again
        assert "error" not in out[0]

    def test_silence_is_a_no(self, gate, net, folder):
        quick = PendingConfirmations(timeout=0.2)
        out = find(gate, quick, folder, ["red door"])
        assert net.calls == []
        assert out[0]["code"] == "consent_unanswered"
        assert "nobody answered" in out[0]["error"]

    def test_striking_a_description_removes_that_photo(self, gate, pending, net, folder):
        t, _ = _answer_when_asked(pending, approve=True, body="red door")
        out = find(gate, pending, folder, ["red door", "blue river"])
        t.join(5)
        assert "error" not in out[0]
        assert out[1]["code"] == "removed"
        assert len(net.searches) == 1 and "q=red+door" in net.searches[0]

    def test_an_edited_description_is_what_is_searched_and_is_cleaned_again(
        self, gate, pending, net, folder
    ):
        t, _ = _answer_when_asked(pending, approve=True, body="green door <script>")
        find(gate, pending, folder, ["red door"])
        t.join(5)
        assert "q=green+door+script" in net.searches[0]

    def test_a_host_the_person_blocked_is_not_asked_about(self, gate, pending, net, folder):
        gate.policy.set(HOST, Mode.DENY)
        out = find(gate, pending, folder, ["red door"])
        assert pending.pending() == []
        assert net.calls == []
        assert out[0]["code"] == "blocked"
        assert "blocked" in out[0]["error"]

    def test_the_kill_switch_is_not_asked_about_and_is_logged_as_a_refusal(
        self, gate, pending, net, folder
    ):
        gate.policy.set_kill_switch(True)
        out = find(gate, pending, folder, ["red door", "blue door"])
        assert pending.pending() == [] and net.calls == []
        assert [o["code"] for o in out] == ["blocked", "blocked"]
        assert "kill switch" in out[0]["error"]
        assert [e.decision for e in gate.log.entries()] == ["denied"]

    def test_two_pages_asking_at_once_produce_one_question(self, gate, pending, net, folder):
        t, _ = _answer_when_asked(pending, approve=True)
        results_: list = []

        def go(desc):
            results_.append(find(gate, pending, folder, [desc]))

        a = threading.Thread(target=go, args=("red door",))
        b = threading.Thread(target=go, args=("blue door",))
        net.search_default = results(row(1), row(2))
        a.start(); b.start(); a.join(10); b.join(10); t.join(5)
        assert gate.log.count() >= 1
        asked = [e for e in gate.log.entries() if e.meta.get("consent")]
        assert len(asked) == 1


# ----------------------------------------------------------- offline, rate limit


class TestFailuresAreAnswersNotCrashes:
    def test_offline_stops_after_asking_twice(self, allowed, pending, net, folder, monkeypatch):
        monkeypatch.setattr(finder.time, "sleep", lambda _s: None)
        net.search_default = urllib.error.URLError("Network is unreachable")
        out = find(allowed, pending, folder, ["red door", "blue door", "green door"])
        assert [o["code"] for o in out] == ["offline"] * 3
        assert len(net.calls) == 2
        assert files(folder) == []

    def test_one_stalled_search_is_asked_again_and_the_page_goes_on(
        self, allowed, pending, net, folder, monkeypatch
    ):
        # Seen live: one slow answer was taken for "offline" and every photo
        # on the page was given up.
        monkeypatch.setattr(finder.time, "sleep", lambda _s: None)
        net.search_answers = [TimeoutError("timed out"), results(row(1)), results(row(2))]
        out = find(allowed, pending, folder, ["red door", "blue door"])
        assert out[0]["title"] == "Photo 1"
        assert out[1]["title"] == "Photo 2"

    def test_a_rate_limit_stops_and_says_when_to_retry(self, allowed, pending, net, folder):
        err = urllib.error.HTTPError(HOST, 429, "Too Many Requests", {}, io.BytesIO(b""))
        net.search_answers = [results(row(1)), err]
        net.search_default = err
        out = find(allowed, pending, folder, ["red door", "blue door", "green door"])
        assert "error" not in out[0]
        assert out[1]["code"] == "rate_limited" and out[2]["code"] == "rate_limited"
        assert "minute" in out[1]["error"]

    def test_a_dead_first_result_falls_through_to_the_next(self, allowed, pending, net, folder):
        # Seen against the live API: the catalogue lists a picture whose original
        # is gone and the thumbnail service answers 424 for it.
        net.search_default = results(row(1), row(2))
        net.picture_for = {ident(1): urllib.error.HTTPError(HOST, 424, "fd", {}, io.BytesIO(b""))}
        out = find(allowed, pending, folder, ["red door"])
        assert out[0]["title"] == "Photo 2"
        assert len(net.downloads) == 2

    def test_the_number_of_tries_for_one_description_is_bounded(
        self, allowed, pending, net, folder
    ):
        net.search_default = results(*[row(n) for n in range(1, 9)])
        net.picture = urllib.error.HTTPError(HOST, 424, "fd", {}, io.BytesIO(b""))
        out = find(allowed, pending, folder, ["red door"])
        assert out[0]["code"] == "unavailable"
        assert len(net.downloads) == finder.MAX_TRIES
        assert files(folder) == []

    def test_a_slow_download_skips_that_picture_and_keeps_going(self, allowed, pending, net, folder):
        # Seen live: one render timed out, was reported as "could not reach",
        # and every remaining photo of the page was abandoned with it.
        net.search_answers = [results(row(1), row(2)), results(row(3))]
        net.picture_for = {ident(1): TimeoutError("timed out")}
        out = find(allowed, pending, folder, ["red door", "blue door"])
        assert out[0]["title"] == "Photo 2"
        assert out[1]["title"] == "Photo 3"

    def test_a_place_with_no_photos_falls_back_to_the_picture_without_it(
        self, allowed, pending, net, folder
    ):
        empty = results()
        net.search_answers = [empty, empty, results(row(4))]
        out = find(allowed, pending, folder, ["Lagos beach with palm trees at sunset"])
        assert out[0]["title"] == "Photo 4"
        assert "Lagos" not in net.searches[-1]
        assert "beach" in net.searches[-1]

    def test_the_place_in_the_request_leads_a_description_that_lacks_it(
        self, allowed, pending, net, folder
    ):
        # Seen live: the model named Lagos in one description of six, and the
        # gallery came back as Tokyo nightlife and a Mexican beach.
        find(
            allowed, pending, folder, ["beach with palm trees", "Lagos market"],
            request_text="Build a tourism website for Lagos, Nigeria",
        )
        assert "q=Lagos+beach+with+palm+trees" in net.searches[0]
        assert "q=Lagos+market" in net.searches[1]

    def test_a_missing_picture_fails_that_photo_only(self, allowed, pending, net, folder):
        net.search_answers = [results(row(1)), results(row(2))]
        net.picture_for = {ident(1): urllib.error.HTTPError(HOST, 404, "nf", {}, io.BytesIO(b""))}
        out = find(allowed, pending, folder, ["red door", "blue door"])
        assert out[0]["code"] == "unavailable"
        assert "error" not in out[1]


class TestThePlaceInTheRequest:
    @pytest.mark.parametrize(
        "request_text,place",
        [
            ("Build a tourism website for Lagos, Nigeria: a hero banner", "Lagos"),
            ("a site for my guest house in Cape Town", "Cape Town"),
            ("Make a restaurant landing page. Use warm colours", ""),
            ("Build an HTML page for my bakery", ""),
            ("", ""),
        ],
    )
    def test_it_reads_only_the_persons_words(self, request_text, place):
        assert finder.place_in(request_text) == place


# ------------------------------------------------------------------------ routes


@pytest.fixture
def client(tmp_path, gate, pending, net, monkeypatch):
    from core.egress import set_gate, set_pending

    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path / "data"))
    set_gate(gate)
    set_pending(pending)

    async def spine():
        return []

    app = FastAPI()
    app.include_router(build_router(spine))
    try:
        yield TestClient(app), gate
    finally:
        set_gate(None)
        set_pending(None)


class TestRoutes:
    def test_find_returns_results_and_the_picture_is_then_served(self, client):
        c, gate = client
        gate.policy.set(HOST, Mode.ALLOW)
        r = c.post("/photos/find", json={"descriptions": ["red door"], "request": "a site"})
        assert r.status_code == 200
        body = r.json()
        assert body["found"] == 1 and body["failed"] == 0 and body["limit"] == MAX_PHOTOS
        photo = body["results"][0]
        got = c.get(photo["url"])
        assert got.status_code == 200
        assert got.headers["content-type"] == "image/jpeg"
        assert got.content == JPEG

    def test_a_declined_host_is_a_200_with_reasons_not_a_500(self, client):
        c, gate = client
        gate.policy.set(HOST, Mode.DENY)
        gate.policy.set("commons.wikimedia.org", Mode.DENY)
        r = c.post("/photos/find", json={"descriptions": ["red door"]})
        assert r.status_code == 200
        assert r.json()["results"][0]["code"] == "blocked"
        assert r.json()["found"] == 0

    @pytest.mark.parametrize(
        "name",
        [
            "..%2F..%2Fegress.db",
            "..\\..\\egress.db",
            "%2e%2e/%2e%2e/etc/passwd",
            "ov-0123456789abcdef0123.gif",
            "ov-0123456789abcdef0123.html",
            "ov-0123456789abcdef0123.jpg.exe",
            "notes.jpg",
            "ov-0123456789ABCDEF0123.jpg",
            "ov-0123.jpg",
            "/etc/passwd",
            "C:\\Windows\\win.ini",
        ],
    )
    def test_the_picture_route_refuses_traversal_and_anything_not_a_cached_photo(self, client, name):
        c, _ = client
        assert c.get(f"/photos/web/{name}").status_code == 404

    def test_a_well_formed_name_that_is_not_there_is_a_404(self, client):
        c, _ = client
        assert c.get("/photos/web/ov-0123456789abcdef0123.jpg").status_code == 404

    def test_a_file_that_is_not_a_cached_name_is_not_served_even_if_it_exists(self, client, tmp_path):
        c, _ = client
        folder = tmp_path / "data" / "photos" / "web"
        folder.mkdir(parents=True)
        (folder / "secret.jpg").write_bytes(JPEG)
        assert c.get("/photos/web/secret.jpg").status_code == 404

    def test_the_request_text_exempts_the_users_own_words(self, client):
        c, gate = client
        gate.policy.set(HOST, Mode.ALLOW)
        from packs.photos import api as api_module  # noqa: F401

        app = FastAPI()

        async def spine():
            return ["Northwind is a harbour hotel client"]

        app.include_router(build_router(spine))
        cc = TestClient(app)
        refused = cc.post("/photos/find", json={"descriptions": ["hotel in Northwind"]}).json()
        allowed_ = cc.post(
            "/photos/find",
            json={"descriptions": ["hotel in Northwind"], "request": "a site for Northwind"},
        ).json()
        assert refused["results"][0]["code"] == "spine_derived"
        assert "error" not in allowed_["results"][0]

    def test_an_unreadable_spine_refuses_everything(self, client, net):
        _, gate = client
        gate.policy.set(HOST, Mode.ALLOW)

        async def broken():
            return None

        app = FastAPI()
        app.include_router(build_router(broken))
        r = TestClient(app).post("/photos/find", json={"descriptions": ["red door"]}).json()
        assert r["results"][0]["code"] == "spine_unreadable"
        assert net.calls == []
