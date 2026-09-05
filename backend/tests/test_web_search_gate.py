"""The web search gate: what turns it on, and what turning it on does not do.

`CLAUDE.md` sequences this feature more explicitly than any other — *egress log
→ per-source policy → web search as its first governed source*, because bytes
cannot be logged retroactively. Both prerequisites now exist, so the gate has
become something a user can open, and these are the properties that must hold
once they can.

The one worth stating plainly, because it is the whole design and it looks like
a bug from the outside: **turning web search on does not permit a search.** It
permits a search *step to be planned*. Whether the request may be sent is the
per-host policy's decision, and its default is refuse. A user who turns the
switch on and immediately gets a refusal is seeing the product work.
"""

from __future__ import annotations

import os
import urllib.parse
from contextlib import contextmanager

import pytest

from core.planner import SEARCH_HOST, web_search_enabled
from core.user_settings import UserSettings, set_user_settings_path


@contextmanager
def env(value: str | None):
    """Set, or genuinely unset, ``ZARAM_WEB_SEARCH``."""
    previous = os.environ.get("ZARAM_WEB_SEARCH")
    if value is None:
        os.environ.pop("ZARAM_WEB_SEARCH", None)
    else:
        os.environ["ZARAM_WEB_SEARCH"] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("ZARAM_WEB_SEARCH", None)
        else:
            os.environ["ZARAM_WEB_SEARCH"] = previous


@pytest.fixture
def settings(tmp_path):
    """A settings file of this test's own, with the singleton properly restored.

    The teardown matters more than it looks. `web_search_enabled` consults the
    singleton, so a test that leaves it pointed at a temp file where search is
    *on* opens the gate for everything that runs afterwards — and the first
    casualty is `test_web_search_is_off_by_default` in
    `test_outbound_query_invariant.py`, which then fails in a way that reads
    like a product defect rather than like pollution. It did exactly that
    before this teardown was written.
    """
    import core.user_settings as module

    previous_path = module._settings_path
    previous_instance = module._settings

    path = str(tmp_path / "settings.json")
    set_user_settings_path(path)
    try:
        yield UserSettings(path)
    finally:
        module._settings_path = previous_path
        module._settings = previous_instance


class TestTheDefault:
    def test_off_with_no_environment_and_no_preference(self, settings):
        with env(None):
            assert web_search_enabled() is False

    def test_a_fresh_settings_file_says_off(self, settings):
        assert settings.web_search is False


class TestTheToggle:
    def test_turning_it_on_opens_the_gate(self, settings):
        with env(None):
            settings.set_web_search(True)
            assert web_search_enabled() is True

    def test_turning_it_off_closes_it_again(self, settings):
        with env(None):
            settings.set_web_search(True)
            settings.set_web_search(False)
            assert web_search_enabled() is False

    def test_the_choice_survives_a_restart(self, settings, tmp_path):
        settings.set_web_search(True)
        # A new object over the same file is what a restart looks like from
        # here. A gate that forgets itself would silently close the internet on
        # a user who opened it, which is the less dangerous direction and still
        # wrong.
        assert UserSettings(str(tmp_path / "settings.json")).web_search is True


class TestTheEnvironmentWins:
    """A variable someone exported deliberately outranks a stored preference.

    Both directions are asserted. Only checking that the environment can turn
    it *on* would let a later change quietly ignore an explicit
    ``ZARAM_WEB_SEARCH=0`` — the case where someone has deliberately sealed a
    machine and a stored preference would reopen it.
    """

    def test_environment_off_beats_a_stored_on(self, settings):
        settings.set_web_search(True)
        with env("0"):
            assert web_search_enabled() is False

    def test_environment_on_beats_a_stored_off(self, settings):
        settings.set_web_search(False)
        with env("1"):
            assert web_search_enabled() is True

    def test_an_empty_variable_is_not_a_setting(self, settings):
        # An exported-but-empty variable is what a shell script that computed
        # nothing leaves behind. Treating it as "off" would make the toggle
        # mysteriously inert; treating it as absent hands the decision back.
        settings.set_web_search(True)
        with env(""):
            assert web_search_enabled() is True


class TestOnIsNotALicence:
    def test_the_named_host_is_the_one_the_provider_contacts(self):
        """`SEARCH_HOST` and the provider's probe must not drift apart.

        The Settings screen shows the user which host's rule will decide their
        searches. If this constant and the provider disagreed, the screen would
        show a rule that governs nothing while a different host was contacted
        under a rule the user never saw — which is worse than showing nothing,
        because it is reassuring and wrong.
        """
        from core.egress import EgressDenied
        from knowledge.providers import duckduckgo_provider as module

        seen: list[str] = []

        class Recorder:
            def check(self, url, **_):
                seen.append(url)
                # Refusing is what keeps this test offline. The provider's own
                # `EgressDenied` branch then returns an empty result, which is
                # the ordinary default-deny path rather than a special case
                # invented for the test.
                raise EgressDenied("refused by this test", host=SEARCH_HOST, entry_id="test")

        # Patched where it is *used*, not where it is defined. The provider does
        # `from core.egress import get_gate` at import, which binds the name in
        # its own module — rebinding `core.egress.get_gate` leaves that untouched
        # and the real gate would be consulted, which on a permissive machine
        # means this test makes a live search.
        original = module.get_gate
        module.get_gate = lambda: Recorder()  # type: ignore[assignment]
        try:
            assert module.DuckDuckGoProvider().search("anything") == []
        finally:
            module.get_gate = original  # type: ignore[assignment]

        assert seen, "the provider did not consult the gate at all"
        assert urllib.parse.urlparse(seen[0]).hostname == SEARCH_HOST

    def test_the_gate_being_open_does_not_change_the_host_policy(self, settings):
        """The switch stores a preference. It grants no destination anything.

        Rule 5 is per-item and explicit, and search was sequenced behind the
        policy rather than beside it precisely so that enabling the feature and
        permitting the destination stay two decisions.
        """
        from core.egress import get_gate

        before = get_gate().policy.rules().get(SEARCH_HOST)
        settings.set_web_search(True)
        assert get_gate().policy.rules().get(SEARCH_HOST) == before
