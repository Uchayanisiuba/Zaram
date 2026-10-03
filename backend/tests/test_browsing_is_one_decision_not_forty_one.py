"""Browsing is one data class, not a rule per host.

Reported 3 October 2026 with a screenshot of the privacy pane: **41
per-source rules, and every one said Always.** That is a control somebody
clicks through, which is worse than no control because it looks like
protection.

Rule 7j names the failure in advance — *"forty dialogs a day is a product
nobody opens on day two"* — and records that it *"happened to the maintainer,
on their own build, with nothing on screen explaining why."* It happened
again, in a new place, and the maintainer's question was the right one: *"is
there a more elegant way to present this, these are many websites and
decisions for the user to make."*

**Per-host is not merely tiring for browsing, it is incoherent.** One news
page is sixty requests to companies the person never chose, so asking per
host is asking about ad networks. The unit of consent has to match the unit
of the act, and browsing's unit is browsing.

So: one standing answer for the class, the hosts become an exception list,
and rule 3 carries it afterwards — every page is still logged, and the log is
where you look instead of deciding beforehand. Logging and asking are
different rules, and only the second one was expensive.

**The line this must not cross** is the last class of tests here. A
class-wide default is exactly the shape that would delete the Spine's hard
stop — *"the first time facts recalled from the Spine go to a destination
that has not had them before"* — in one setting, so `SPINE` cannot have one
and the refusal is enforced at the write rather than described in a comment.
"""

from __future__ import annotations

import pytest

from core.egress.policy import DataClass, EgressPolicy, Mode


@pytest.fixture
def policy(tmp_path):
    return EgressPolicy(str(tmp_path / "egress-policy.json"))


class TestOneDecisionCoversBrowsing:
    def test_browsing_is_denied_until_it_is_turned_on(self, policy):
        """Default deny is unchanged. The switch is the deliberate act rule 5
        asks for; it is not on because a browser exists."""
        assert policy.decide("en.wikipedia.org", DataClass.BROWSE).mode is Mode.DENY

    def test_one_switch_covers_every_host(self, policy):
        policy.set_class_default(DataClass.BROWSE, Mode.ALLOW)
        for host in ("en.wikipedia.org", "dailypost.ng", "api.github.com"):
            assert policy.decide(host, DataClass.BROWSE).mode is Mode.ALLOW

    def test_including_hosts_nobody_chose(self, policy):
        """The reason per-host could never work here. A page the person asked
        for pulls in dozens they did not, and a question about each is a
        question about ad networks."""
        policy.set_class_default(DataClass.BROWSE, Mode.ALLOW)
        assert policy.decide("ads.doubleclick.net", DataClass.BROWSE).mode is Mode.ALLOW

    def test_turning_it_off_puts_it_back(self, policy):
        policy.set_class_default(DataClass.BROWSE, Mode.ALLOW)
        policy.set_class_default(DataClass.BROWSE, None)
        assert policy.decide("en.wikipedia.org", DataClass.BROWSE).mode is Mode.DENY

    def test_it_survives_a_restart(self, tmp_path):
        """A consent that forgets itself is a consent the person gives twice."""
        path = str(tmp_path / "p.json")
        EgressPolicy(path).set_class_default(DataClass.BROWSE, Mode.ALLOW)
        assert EgressPolicy(path).class_default(DataClass.BROWSE) is Mode.ALLOW


class TestTheHostsBecomeAnExceptionList:
    """Not deleted — demoted. Somebody who wants a rule for one host keeps
    it, and it still wins. What changes is that nobody needs forty-one."""

    def test_a_blocked_host_stays_blocked(self, policy):
        """The standing answer sits below the host rules deliberately, so it
        is an answer rather than an override. A host somebody shut must not
        be reopened by a switch about browsing in general."""
        policy.set_class_default(DataClass.BROWSE, Mode.ALLOW)
        policy.set("tracker.example.com", Mode.DENY)
        assert policy.decide("tracker.example.com", DataClass.BROWSE).mode is Mode.DENY

    def test_a_per_host_browse_rule_still_wins(self, policy):
        policy.set_class_default(DataClass.BROWSE, Mode.ALLOW)
        policy.set("awkward.example.com", Mode.ASK, DataClass.BROWSE)
        assert policy.decide("awkward.example.com", DataClass.BROWSE).mode is Mode.ASK

    def test_and_can_allow_one_host_with_browsing_off(self, policy):
        policy.set("docs.example.com", Mode.ALLOW, DataClass.BROWSE)
        assert policy.decide("docs.example.com", DataClass.BROWSE).mode is Mode.ALLOW
        assert policy.decide("elsewhere.example.com", DataClass.BROWSE).mode is Mode.DENY


class TestNothingElseMoved:
    """Browsing being permitted says nothing about the other classes.

    A broader consent must never imply a narrower and more sensitive one —
    the same asymmetry `_INHERITS_HOST_RULE` already draws.
    """

    def test_prompts_are_unaffected(self, policy):
        policy.set_class_default(DataClass.BROWSE, Mode.ALLOW)
        assert policy.decide("en.wikipedia.org", DataClass.PROMPT).mode is Mode.DENY

    def test_images_are_unaffected(self, policy):
        policy.set_class_default(DataClass.BROWSE, Mode.ALLOW)
        assert policy.decide("en.wikipedia.org", DataClass.IMAGE).mode is Mode.DENY

    def test_the_spine_is_unaffected(self, policy):
        policy.set_class_default(DataClass.BROWSE, Mode.ALLOW)
        assert policy.decide("en.wikipedia.org", DataClass.SPINE).mode is Mode.DENY

    def test_a_provider_the_person_connected_still_only_gets_prompts(self, policy):
        """Browsing on must not widen what "I connected this provider" meant."""
        policy.set_class_default(DataClass.BROWSE, Mode.ALLOW)
        policy.set("api.openai.com", Mode.ALLOW)
        assert policy.decide("api.openai.com", DataClass.PROMPT).mode is Mode.ALLOW
        assert policy.decide("api.openai.com", DataClass.SPINE).mode is not Mode.ALLOW

    def test_the_kill_switch_still_beats_everything(self, policy):
        policy.set_class_default(DataClass.BROWSE, Mode.ALLOW)
        policy.set_kill_switch(True)
        assert policy.decide("en.wikipedia.org", DataClass.BROWSE).mode is Mode.DENY


class TestTheSpineCannotHaveAStandingAnswer:
    """The line this mechanism must not cross, enforced where it is written.

    A class-wide allow for `SPINE` would delete, in one setting, the hard
    stop `CLAUDE.md` keeps by name. The check lives in `set_class_default`
    rather than in its callers precisely because a caller is the thing that
    gets forgotten.
    """

    @pytest.mark.parametrize("cls", [DataClass.SPINE, DataClass.IMAGE, DataClass.PROMPT])
    def test_only_browsing_may_default(self, policy, cls):
        with pytest.raises(ValueError):
            policy.set_class_default(cls, Mode.ALLOW)

    def test_the_refusal_says_why(self, policy):
        """A permission call that quietly does nothing is how somebody
        believes they granted something they did not."""
        with pytest.raises(ValueError) as caught:
            policy.set_class_default(DataClass.SPINE, Mode.ALLOW)
        assert "destination that has not had it before" in str(caught.value)

    def test_a_hand_edited_file_cannot_smuggle_one_in(self, tmp_path):
        """The file is the user's and they may read or edit it, so the load
        path is a second way in and is checked the same way."""
        import json

        path = tmp_path / "p.json"
        path.write_text(
            json.dumps({"classDefaults": {"spine": "allow", "browse": "allow"}}),
            encoding="utf-8",
        )
        policy = EgressPolicy(str(path))
        assert policy.class_default(DataClass.SPINE) is None
        assert policy.class_default(DataClass.BROWSE) is Mode.ALLOW
        assert policy.decide("anywhere.example.com", DataClass.SPINE).mode is not Mode.ALLOW

    def test_nonsense_in_the_file_loses_nothing_else(self, tmp_path):
        """An unknown class name must not take the real rules with it."""
        import json

        path = tmp_path / "p.json"
        path.write_text(
            json.dumps(
                {
                    "classDefaults": {"telepathy": "allow", "browse": "allow"},
                    "hosts": {"api.openai.com": "allow"},
                }
            ),
            encoding="utf-8",
        )
        policy = EgressPolicy(str(path))
        assert policy.class_default(DataClass.BROWSE) is Mode.ALLOW
        assert policy.decide("api.openai.com", DataClass.PROMPT).mode is Mode.ALLOW
