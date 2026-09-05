"""What a search-result grant may and may not do.

Rule 7j permits consent once per destination *and data class*. Reading a page a
search just returned is that case: the host is chosen by the search engine, the
user cannot pre-allow it, and under default-deny every article is refused —
which is how a regional election was answered from a headline in a URL while
the article sat unread.

**This file exists because the first attempt was a hole.** The exemption was
keyed off ``source="internet.deep_read"``, a string the caller supplies about
itself, which is `X-Zaram-Client` enforced as a credential. Any call site could
have skipped default-deny by naming itself correctly. The grant carries exact
URLs instead, and these tests are the four ways that could still go wrong.
"""

from __future__ import annotations

import pytest

from core.egress.gate import EgressDenied, EgressGate, SearchReadGrant
from core.egress.log import EgressLog
from core.egress.policy import EgressPolicy

PAGE = "https://dailypost.ng/2026/08/16/osun-decides/"
OTHER = "https://elsewhere.example/whatever"


@pytest.fixture
def gate(tmp_path):
    policy = EgressPolicy(str(tmp_path / "policy.json"))
    return EgressGate(EgressLog(str(tmp_path / "egress.db")), policy), policy


@pytest.fixture
def grant():
    return SearchReadGrant.of([PAGE])


class TestWhatItPermits:
    def test_a_granted_page_is_read(self, gate, grant):
        """The whole point: an unknown host, no rule, and the page is fetched."""
        egress, _policy = gate
        approved = egress.check(PAGE, source="internet.deep_read", grant=grant)
        assert approved is not None and approved.host == "dailypost.ng"

    def test_it_is_still_logged(self, gate, grant):
        """Rule 3 has no exceptions. A permitted fetch is disclosed like any
        other, with the *page's* host rather than the search engine's."""
        egress, _policy = gate
        egress.check(PAGE, source="internet.deep_read", grant=grant)
        entries = list(egress.log.entries())
        assert entries and entries[0].host == "dailypost.ng"
        assert entries[0].decision == "allowed"

    def test_without_a_grant_nothing_changes(self, gate):
        """The default path is untouched — this is an opt-in capability, not a
        loosening of the policy."""
        egress, _policy = gate
        with pytest.raises(EgressDenied):
            egress.check(PAGE, source="internet.deep_read")


class TestWhatItRefuses:
    def test_a_url_not_in_the_grant(self, gate, grant):
        """The defect the label version had. Holding a grant for one page must
        not open every page — otherwise it is a source label with extra steps."""
        egress, _policy = gate
        with pytest.raises(EgressDenied):
            egress.check(OTHER, source="internet.deep_read", grant=grant)

    def test_a_post(self, gate):
        """Reading a page is a GET. A POST is sending something, and this class
        of consent covers fetching public pages, not uploading."""
        egress, _policy = gate
        grant = SearchReadGrant.of([PAGE])
        with pytest.raises(EgressDenied):
            egress.check(PAGE, method="POST", source="internet.deep_read", grant=grant)

    def test_anything_with_a_body(self, gate):
        """**Rule 8, structurally.** Nothing derived from the Spine may appear
        in an outbound query, and the way to guarantee that here is to refuse
        every request that carries a body at all — then there is nowhere for it
        to ride, and the guarantee needs no inspection of what the body says."""
        egress, _policy = gate
        grant = SearchReadGrant.of([PAGE])
        with pytest.raises(EgressDenied):
            egress.check(PAGE, method="GET", body="my day rate is 425000",
                         source="internet.deep_read", grant=grant)

    def test_a_host_the_user_blocked(self, gate, grant):
        """A deliberate decision by a person beats a grant every time.

        The grant covers the *absence* of an opinion — a host nobody has ruled
        on. A host somebody blocked has been ruled on, and a search result
        turning up from it is not a reason to revisit that.
        """
        egress, policy = gate
        policy.set("dailypost.ng", "deny")
        with pytest.raises(EgressDenied):
            egress.check(PAGE, source="internet.deep_read", grant=grant)

    def test_the_kill_switch(self, gate, grant):
        """"Cut all outbound traffic" has no exceptions.

        `decide` collapses the kill switch into the same DENY as an unknown
        host, so without an explicit check a grant would sail straight through
        the one control that must be absolute. This is that check.
        """
        egress, policy = gate
        policy.set_kill_switch(True)
        with pytest.raises(EgressDenied):
            egress.check(PAGE, source="internet.deep_read", grant=grant)


class TestTheGrantItself:
    def test_a_name_grants_nothing(self, gate):
        """The regression that names the original defect.

        Calling yourself the deep reader must buy exactly nothing. If this ever
        passes with an empty grant, the label has become a credential again.
        """
        egress, _policy = gate
        empty = SearchReadGrant.of([])
        with pytest.raises(EgressDenied):
            egress.check(PAGE, source="internet.deep_read", grant=empty)

    def test_it_is_immutable(self):
        """A frozen dataclass over a frozenset: a caller that is handed a grant
        cannot quietly add to it."""
        grant = SearchReadGrant.of([PAGE])
        with pytest.raises(Exception):
            grant.urls = frozenset([OTHER])  # type: ignore[misc]
