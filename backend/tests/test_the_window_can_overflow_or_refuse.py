"""What happens when a conversation outgrows the window, and how long a
reply may run.

The last two of LM Studio's four token controls, asked for 4 October
2026 after the maintainer sent an account of how LM Studio handles them.
The other two — the context window itself and the per-model override —
are in `test_the_window_is_decided_not_typed.py`.

**Zaram already had the better half of the overflow behaviour and no
choice about it.** `core/transcript.fit` drops whole turns, oldest
first, never leaves a reply whose question was cut, and the engine says
so once per session. That is a rolling window, and it is a more careful
one than the description the maintainer quoted.

What was missing is the alternative. Trimming is right for chat, where
the recent end is what matters. It is wrong for an answer grounded in
something said at the start — a document pasted an hour ago, a
constraint agreed in the first message — because the model cannot know
what was cut and answers confidently from a premise that is no longer
there. **That is rule 9 exactly**, and `stop` is the one place in the
conversation path where a person can ask to have it enforced.

The reply cap is a different quantity from the window and the two are
easy to confuse. The window is the whole pool: prompt, history and reply
together. The cap bounds the reply alone, and a small one cuts a model
off mid-sentence however much room is left.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def settings(tmp_path, monkeypatch):
    import core.user_settings as module

    monkeypatch.setattr(module, "_SETTINGS", None, raising=False)
    return module.UserSettings(str(tmp_path / "settings.json"))


class TestTheSetting:
    def test_trimming_is_the_default(self, settings):
        """What Zaram did before there was a choice. A default that
        refuses to answer would be a product that stops working on a long
        conversation, which is worse than one that forgets the start."""
        assert settings.to_dict()["overflow_policy"] == "trim"

    def test_there_is_no_reply_cap_by_default(self, settings):
        """`0`, because a quarter of the window is already reserved for
        the reply. A number here would compete with arithmetic that is
        already right."""
        assert settings.to_dict()["max_reply_tokens"] == 0

    def test_an_unrecognised_policy_resolves_to_trimming(self, settings):
        assert settings.set_overflow_policy("explode") == "trim"

    def test_a_choice_survives_a_restart(self, tmp_path, monkeypatch):
        import core.user_settings as module

        path = str(tmp_path / "s.json")
        monkeypatch.setattr(module, "_SETTINGS", None, raising=False)
        module.UserSettings(path).set_overflow_policy("stop")
        assert module.UserSettings(path).to_dict()["overflow_policy"] == "stop"

    def test_the_reply_cap_is_bounded(self, settings):
        from core.user_settings import MAX_CONTEXT_TOKENS

        settings.set_max_reply_tokens(99_999_999)
        assert settings.to_dict()["max_reply_tokens"] == MAX_CONTEXT_TOKENS

    def test_a_negative_cap_means_none(self, settings):
        assert settings.set_max_reply_tokens(-5) == 0

    def test_nonsense_in_the_file_is_ignored_rather_than_coerced(
        self, tmp_path, monkeypatch
    ):
        import json

        import core.user_settings as module

        path = tmp_path / "s.json"
        path.write_text(
            json.dumps({"overflow_policy": 7, "max_reply_tokens": "lots"}),
            encoding="utf-8",
        )
        monkeypatch.setattr(module, "_SETTINGS", None, raising=False)
        stored = module.UserSettings(str(path)).to_dict()
        assert stored["overflow_policy"] == "trim"
        assert stored["max_reply_tokens"] == 0

    def test_the_vocabulary_is_sent_rather_than_left_to_be_invented(self, settings):
        """The argument `task_slots` makes: a client free to invent its
        own list could offer a policy this backend accepts the write for
        and then resolves to the default."""
        assert settings.to_dict()["overflow_policies"] == ["stop", "trim"]


class TestRefusingRatherThanTrimming:
    @pytest.fixture()
    def engine(self, monkeypatch):
        """A bare engine with two long turns and a window too small for
        them, which is the only state this behaviour depends on."""
        from core.execution_engine import ExecutionEngine

        made = ExecutionEngine.__new__(ExecutionEngine)
        made._session_turns = {"s": [("question " * 400, "answer " * 400)] * 3}
        made._front_cut = __import__("collections").OrderedDict()
        made._told_about_dropped_turns = set()

        from core.context_budget import ContextBudget

        monkeypatch.setattr(
            ExecutionEngine,
            "_budget_for",
            lambda self, model: ContextBudget(
                total_tokens=2_048, measured=True, reply_reserve_tokens=512
            ),
            raising=False,
        )
        return made

    def _policy(self, monkeypatch, value):
        import core.execution_engine as module

        monkeypatch.setattr(module, "_overflow_policy", lambda: value)

    def test_trimming_keeps_answering(self, engine, monkeypatch):
        self._policy(monkeypatch, "trim")
        _prompt, notice = engine._augment_with_conversation("", "s", "m")
        # Something was dropped, and the notice says so — but it is a
        # notice, not a refusal.
        assert notice is None or notice.data.get("kind") != "context_overflow"

    def test_stopping_refuses_the_turn(self, engine, monkeypatch):
        self._policy(monkeypatch, "stop")
        _prompt, notice = engine._augment_with_conversation("", "s", "m")
        assert notice is not None
        assert notice.data.get("kind") == "context_overflow"

    def test_the_refusal_says_what_to_do_about_it(self, engine, monkeypatch):
        """A refusal with no route is a dead end, and this one has two
        real ones: a new conversation, or a larger window."""
        self._policy(monkeypatch, "stop")
        _prompt, notice = engine._augment_with_conversation("", "s", "m")
        text = notice.data["content"]
        assert "new conversation" in text
        assert "larger window" in text

    def test_a_conversation_that_fits_is_never_refused(self, engine, monkeypatch):
        """`stop` is about overflow, not about being strict. A short
        conversation under this policy behaves exactly as before."""
        self._policy(monkeypatch, "stop")
        engine._session_turns = {"s": [("hello", "hi")]}
        _prompt, notice = engine._augment_with_conversation("", "s", "m")
        assert notice is None or notice.data.get("kind") != "context_overflow"

    def test_a_broken_settings_store_keeps_answering(self, monkeypatch):
        """**Failing closed is right for egress and wrong here**, because
        the closed position is silence. A settings file that will not
        parse must not be able to make the product refuse to answer."""
        import core.execution_engine as module

        def explode():
            raise RuntimeError("no settings")

        monkeypatch.setattr(
            "core.user_settings.get_user_settings", explode, raising=False
        )
        assert module._overflow_policy() == "trim"


class TestTheCallerHalts:
    def test_nothing_is_generated_after_the_refusal(self):
        """**Asserted against the source**, because the property is that
        a generator *stops* — and code that does not run is the one thing
        a response-shape test cannot see.

        A refusal followed by an answer would be the worst of both: the
        warning read as advice, and the reply still built on the
        shortened history it warned about.
        """
        import inspect

        import core.execution_engine as module

        source = inspect.getsource(module.ExecutionEngine.execute)
        assert 'memory_notice.data.get("kind") == "context_overflow"' in source
        marker = source.index('== "context_overflow"')
        # The `return` is the whole point, so it is asserted to be there
        # and to be close enough to belong to this branch.
        assert "return" in source[marker : marker + 200]


class TestTheReplyCap:
    def test_it_is_not_sent_when_nobody_asked(self, monkeypatch):
        import core.context_budget as module

        monkeypatch.setattr(
            "core.user_settings.get_user_settings",
            lambda: type("S", (), {"to_dict": lambda self: {}})(),
            raising=False,
        )
        assert module.requested_reply_cap() == 0

    def test_a_broken_store_leaves_replies_uncapped(self, monkeypatch):
        import core.context_budget as module

        def explode():
            raise RuntimeError("no settings")

        monkeypatch.setattr(
            "core.user_settings.get_user_settings", explode, raising=False
        )
        assert module.requested_reply_cap() == 0

    def test_every_runtime_honours_it_not_just_ollama(self):
        """**The model-neutrality rule applied to a setting.** The same
        control is `num_predict` inside `options` on Ollama and
        `max_tokens` at the top level on every OpenAI-compatible server —
        TabbyAPI, LM Studio, OpenRouter, the paid providers. A cap
        honoured by whichever runtime the maintainer happens to run is
        not a cap, and the model that answers on their machine is served
        by the second one.
        """
        import inspect

        import runtimes.models.engines.ollama_engine as ollama
        import runtimes.models.engines.openai_compatible_engine as compat

        ollama_source = inspect.getsource(ollama)
        assert '"num_predict"] = cap' in ollama_source

        compat_source = inspect.getsource(compat)
        assert 'body["max_tokens"] = reply_cap' in compat_source

    def test_both_engines_read_the_same_setting(self):
        """Two copies of one settings read is how they drift. The reader
        lives in `context_budget` and both import it."""
        import inspect

        import runtimes.models.engines.ollama_engine as ollama
        import runtimes.models.engines.openai_compatible_engine as compat

        assert "requested_reply_cap" in inspect.getsource(ollama)
        assert "requested_reply_cap" in inspect.getsource(compat)

    def test_the_key_is_absent_rather_than_zero_when_uncapped(self):
        """`num_predict: 0` is not "no limit" to Ollama, and `max_tokens:
        0` is a 400 from most servers. Absent is the only correct way to
        say nothing was asked for."""
        import inspect

        import runtimes.models.engines.ollama_engine as ollama

        source = inspect.getsource(ollama)
        assert "if cap:" in source


class TestTheRoute:
    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        import main

        return TestClient(main.app)

    def test_both_controls_are_in_the_payload(self, client):
        body = client.get("/routing/preference").json()
        assert body["overflow_policy"] in {"trim", "stop"}
        assert isinstance(body["max_reply_tokens"], int)
        assert sorted(body["overflow_policies"]) == ["stop", "trim"]

    def test_they_can_be_set_over_the_wire(self, client):
        """End to end, because a store being right is not evidence that
        the route reaches it — a complete, tested thing nothing calls is
        this repository's most expensive recurring failure."""
        client.post(
            "/routing/preference",
            json={"overflow_policy": "stop", "max_reply_tokens": 2_048},
        )
        body = client.get("/routing/preference").json()
        assert body["overflow_policy"] == "stop"
        assert body["max_reply_tokens"] == 2_048

        # Put it back, so this test does not change what the next one reads.
        client.post(
            "/routing/preference",
            json={"overflow_policy": "trim", "max_reply_tokens": 0},
        )
