"""Connecting a provider for text is not consent to send it a photograph.

Rule 7j: *"Consent given deliberately for a destination is consent"* — granted
"per destination **and data class**". `EgressPolicy` knew only about
destinations until 29 August 2026, so the second half of that sentence had
nowhere to live, and two things followed from the gap:

* `RoutedEngine` refused **every** cloud-bound image outright, with a comment
  saying the question was not being asked yet. Honest, and a dead end: OpenRouter
  discovery had just started reporting which cloud models can see, so a user
  with a dozen vision-capable models was told nothing could look at a picture.
* Nothing anywhere could record the answer if it had been asked.

The policy is now keyed on ``(host, DataClass)``. This file asserts the two
halves that matter: that a broader consent never implies a narrower and more
sensitive one, and that the ordinary chat path is untouched by the guard.

**Why the guarantee moved here from `test_engine_routing.py`.** That file tests
a router with two recording doubles, and a refusal asserted there proves only
that the router refused. The property worth having is that an image cannot
reach the network without its own grant *whatever route the code takes*, so the
tests below run a real engine against a real gate, a real policy and a real log,
with `urlopen` patched to fail loudly if a socket is ever opened.
"""
from __future__ import annotations

import json

import pytest

from core.egress import DataClass, EgressGate, EgressLog, EgressPolicy, Mode
from core.egress.policy import DEFAULT_DECISION
from runtimes.models.engines.openai_compatible_engine import OpenAICompatibleEngine

HOST = "api.example-cloud.test"
URL = f"https://{HOST}"

#: A 1x1 PNG, base64. Small, real, and decodable — `_data_uri` sniffs the bytes,
#: so a made-up string would be refused for the wrong reason entirely.
PIXEL = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


# ============================================================ the policy ===

@pytest.fixture
def policy(tmp_path):
    return EgressPolicy(str(tmp_path / "policy.json"))


class TestABroaderConsentNeverImpliesANarrowerOne:
    """The asymmetry is the whole feature."""

    def test_an_unknown_host_denies_both(self, policy):
        assert policy.decide(HOST).mode is Mode.DENY
        assert policy.decide(HOST, DataClass.IMAGE).mode is Mode.DENY

    def test_allowing_a_host_allows_chat(self, policy):
        policy.set(HOST, Mode.ALLOW)

        assert policy.decide(HOST).mode is Mode.ALLOW

    def test_allowing_a_host_does_not_allow_images(self, policy):
        """The sentence rule 7j actually contains."""
        policy.set(HOST, Mode.ALLOW)

        assert policy.decide(HOST, DataClass.IMAGE).mode is Mode.DENY

    def test_allowing_a_host_does_not_allow_spine_facts(self, policy):
        """`CLAUDE.md` keeps a hard stop here and it needs somewhere to live.

        *"The first time facts recalled from the Spine go to a destination that
        has not had them before."* A class is what makes that expressible.
        """
        policy.set(HOST, Mode.ALLOW)

        assert policy.decide(HOST, DataClass.SPINE).mode is Mode.DENY

    def test_the_refusal_says_which_decision_is_missing(self, policy):
        """Not a bare default-deny.

        The user *has* made a decision about this destination. Telling them it
        was refused for no stated reason sends them looking for a rule that
        does not exist; naming the class implies the shape of the fix.
        """
        policy.set(HOST, Mode.ALLOW)

        reason = policy.decide(HOST, DataClass.IMAGE).reason

        assert "image" in reason
        assert reason != DEFAULT_DECISION.reason

    def test_granting_the_class_allows_it(self, policy):
        policy.set(HOST, Mode.ALLOW)
        policy.set(HOST, Mode.ALLOW, DataClass.IMAGE)

        assert policy.decide(HOST, DataClass.IMAGE).mode is Mode.ALLOW
        assert policy.decide(HOST).mode is Mode.ALLOW

    def test_a_class_grant_alone_does_not_open_the_host_for_chat(self, policy):
        """Each direction is its own decision, including this one."""
        policy.set(HOST, Mode.ALLOW, DataClass.IMAGE)

        assert policy.decide(HOST).mode is Mode.DENY

    def test_a_blocked_host_blocks_every_class(self, policy):
        """A deliberate block is not a gap to be filled by a class grant.

        The reason must be the block, not the missing-grant wording: "you
        blocked this" and "you have not decided this" send the user to
        different places.
        """
        policy.set(HOST, Mode.DENY)

        decision = policy.decide(HOST, DataClass.IMAGE)

        assert decision.mode is Mode.DENY
        assert "blocked" in decision.reason

    def test_the_kill_switch_beats_a_class_grant(self, policy):
        """One control with no exceptions at all."""
        policy.set(HOST, Mode.ALLOW)
        policy.set(HOST, Mode.ALLOW, DataClass.IMAGE)
        policy.set_kill_switch(True)

        assert policy.decide(HOST, DataClass.IMAGE).mode is Mode.DENY
        assert "kill switch" in policy.decide(HOST, DataClass.IMAGE).reason

    def test_ask_is_available_per_class(self, policy):
        """A user may allow chat outright and still want to see each picture."""
        policy.set(HOST, Mode.ALLOW)
        policy.set(HOST, Mode.ASK, DataClass.IMAGE)

        assert policy.decide(HOST).mode is Mode.ALLOW
        assert policy.decide(HOST, DataClass.IMAGE).mode is Mode.ASK


class TestARuleAboutAHostIsNotAnOpinionAboutEveryCargo:
    def test_has_rule_is_false_for_an_ungranted_class(self, policy):
        """`SearchReadGrant` leans on `has_rule`, so this is load-bearing.

        The grant may cover a host nobody has an opinion about and must never
        cover one they blocked. If a host rule counted as an opinion about
        images, a grant written for reading a web page would start reasoning
        about a class it was never meant to touch.
        """
        policy.set(HOST, Mode.ALLOW)

        assert policy.has_rule(HOST) is True
        assert policy.has_rule(HOST, DataClass.IMAGE) is False

    def test_forgetting_the_host_forgets_its_class_grants(self, policy):
        """A permission must not outlive the decision that created it.

        Leaving an image grant behind after the provider is removed would be
        invisible: the privacy pane lists host rules, so nothing on screen
        would show that the destination could still receive pictures.
        """
        policy.set(HOST, Mode.ALLOW)
        policy.set(HOST, Mode.ALLOW, DataClass.IMAGE)

        policy.forget(HOST)

        assert policy.decide(HOST, DataClass.IMAGE).mode is Mode.DENY
        assert policy.class_rules() == {}

    def test_a_class_grant_can_be_forgotten_on_its_own(self, policy):
        policy.set(HOST, Mode.ALLOW)
        policy.set(HOST, Mode.ALLOW, DataClass.IMAGE)

        policy.forget(HOST, DataClass.IMAGE)

        assert policy.decide(HOST).mode is Mode.ALLOW
        assert policy.decide(HOST, DataClass.IMAGE).mode is Mode.DENY


class TestExistingPolicyFilesKeepMeaningWhatTheyMeant:
    def test_a_file_written_before_classes_existed_allows_chat_only(self, tmp_path):
        """The upgrade path, and it has to fail in the safe direction.

        Every policy file on every machine predates this change. Read as
        "permission for everything" they would silently grant image egress
        nobody agreed to; read as "permission for chat" they mean exactly what
        the user was asked at the time.
        """
        path = tmp_path / "policy.json"
        path.write_text(json.dumps({"hosts": {HOST: "allow"}}), encoding="utf-8")

        loaded = EgressPolicy(str(path))

        assert loaded.decide(HOST).mode is Mode.ALLOW
        assert loaded.decide(HOST, DataClass.IMAGE).mode is Mode.DENY

    def test_class_rules_survive_a_restart(self, tmp_path):
        path = str(tmp_path / "policy.json")
        first = EgressPolicy(path)
        first.set(HOST, Mode.ALLOW)
        first.set(HOST, Mode.ALLOW, DataClass.IMAGE)

        second = EgressPolicy(path)

        assert second.decide(HOST, DataClass.IMAGE).mode is Mode.ALLOW

    def test_an_unknown_class_name_does_not_discard_the_rest(self, tmp_path):
        """Read member by member, not all-or-nothing.

        The bare `except` in `_load` falls back to *no rules at all* — the safe
        direction for a request and a terrible one for the user, who would
        silently lose every decision they had made. A newer or hand-edited file
        naming a class this build does not know must not trigger it.
        """
        path = tmp_path / "policy.json"
        path.write_text(
            json.dumps({
                "hosts": {HOST: "allow"},
                "classes": {HOST: {"image": "allow", "hologram": "allow"}},
            }),
            encoding="utf-8",
        )

        loaded = EgressPolicy(str(path))

        assert loaded.decide(HOST).mode is Mode.ALLOW
        assert loaded.decide(HOST, DataClass.IMAGE).mode is Mode.ALLOW


# =========================================== through a real gate and engine ===

@pytest.fixture
def gate(tmp_path):
    return EgressGate(
        log=EgressLog(str(tmp_path / "egress.db")),
        policy=EgressPolicy(str(tmp_path / "policy.json")),
    )


@pytest.fixture
def engine(gate):
    return OpenAICompatibleEngine(
        base_url=URL,
        api_key="sk-test-key-not-real",
        default_model="test-model",
        gate=gate,
        source="chat",
    )


@pytest.fixture
def no_socket(monkeypatch):
    """Record any attempt to open a connection, and refuse it.

    Patched at the gate's own transport, which is the lowest point every path
    passes through. Stubbing the engine would prove only that one method was
    not called; this proves no request happened whatever route the code took.

    **It records rather than raising, and that detail is the point.** Raising
    was the first version, and it made
    `test_an_image_to_a_chat_approved_host_is_refused` pass with the consent
    classification deliberately disabled: the engine caught the assertion in
    its own "could not reach the provider" handler and produced an `[ERROR]`
    line naming the host — which is exactly what the test was checking for. A
    network failure and a refusal are not the same event and must not be
    indistinguishable to a test, so callers assert on this list instead.
    """
    attempts: list[str] = []

    def fake_urlopen(request, **kwargs):
        attempts.append(getattr(request, "full_url", str(request)))
        raise AssertionError("the transport should not have been reached")

    monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", fake_urlopen)
    return attempts


class TestThePictureDoesNotLeaveWithoutItsOwnGrant:
    def test_an_image_to_a_chat_approved_host_is_refused(self, engine, gate, no_socket):
        gate.policy.set(HOST, Mode.ALLOW)

        out = "".join(engine.stream_response("what is this", "", None, [PIXEL]))

        # The refusal happened *before* the transport, not as a consequence of
        # it failing. Asserting only on the `[ERROR]` line cannot tell those
        # apart — see `no_socket`.
        assert no_socket == [], "the picture reached the transport"
        assert out.startswith("[ERROR]")
        assert "image" in out, f"the refusal did not say what was missing: {out!r}"

    def test_the_refusal_is_recorded(self, engine, gate, no_socket):
        """Rule 3 does not pause because rule 5 said no.

        A refusal the log cannot show is indistinguishable from a request that
        was never made, and the difference is exactly what someone auditing
        this would want to see.
        """
        gate.policy.set(HOST, Mode.ALLOW)

        list(engine.stream_response("what is this", "", None, [PIXEL]))

        entries = gate.log.entries()
        assert len(entries) == 1
        assert entries[0].decision == "denied"
        assert "image" in entries[0].reason

    def test_granting_the_class_lets_the_picture_through(self, engine, gate, monkeypatch):
        """The other half. A guard that refuses everything is not consent."""
        gate.policy.set(HOST, Mode.ALLOW)
        gate.policy.set(HOST, Mode.ALLOW, DataClass.IMAGE)

        sent: list[str] = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def __iter__(self):
                return iter([b'data: {"choices":[{"delta":{"content":"a cat"}}]}\n', b"data: [DONE]\n"])

        def fake_urlopen(request, **kwargs):
            sent.append(getattr(request, "full_url", str(request)))
            return _Response()

        monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", fake_urlopen)

        out = "".join(engine.stream_response("what is this", "", None, [PIXEL]))

        assert sent, "the approved request never reached the transport"
        assert "a cat" in out

    def test_ordinary_chat_is_untouched_by_the_guard(self, engine, gate, monkeypatch):
        """The regression that would matter most, and would be found last.

        Every existing user has a host rule and no class rules. If the guard
        leaked into the text path, chat would stop working for all of them.
        """
        gate.policy.set(HOST, Mode.ALLOW)

        sent: list[str] = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def __iter__(self):
                return iter([b'data: {"choices":[{"delta":{"content":"hello"}}]}\n', b"data: [DONE]\n"])

        def fake_urlopen(request, **kwargs):
            sent.append(getattr(request, "full_url", str(request)))
            return _Response()

        monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", fake_urlopen)

        out = "".join(engine.stream_response("hello", "", None, None))

        assert sent
        assert "hello" in out


class TestTheClassIsReadOffTheBodyNotTheArgument:
    """A caller saying what it is sending is a label; the body is the fact.

    `stream_response` takes an ``images`` list that may be empty, may be
    whitespace, and — for two milestones — was accepted and then silently
    dropped by `_body`. Deriving consent from the argument would ask the user's
    permission for a picture that is not there, and would fail the other way
    round if those shapes ever drift apart again.
    """

    def test_an_empty_image_list_is_an_ordinary_prompt(self, engine, gate, monkeypatch):
        gate.policy.set(HOST, Mode.ALLOW)

        sent: list[str] = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def __iter__(self):
                return iter([b"data: [DONE]\n"])

        monkeypatch.setattr(
            "core.egress.gate.urllib.request.urlopen",
            lambda request, **kw: (sent.append(1), _Response())[1],
        )

        list(engine.stream_response("hello", "", None, ["", "   "]))

        assert sent, "a whitespace-only image list was treated as a picture"

    def test_the_detector_matches_what_body_builds(self, engine):
        """Guards the pair, not either half.

        If `_body` ever changes how it carries a picture, this fails rather
        than the consent class quietly becoming `PROMPT` for every image.
        """
        with_image = engine._body("q", "", None, [PIXEL])
        without = engine._body("q", "", None, None)

        assert engine._body_carries_images(with_image) is True
        assert engine._body_carries_images(without) is False
