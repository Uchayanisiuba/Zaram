"""Asking a local model for more context, from inside Zaram.

Built 4 October 2026, and the reason is a sentence from the maintainer:
*"a while ago, I needed to use Claude to increase Zaram's LLM context
token limit."*

**Zaram could read the window and not set it.** `core/context_budget.py`
exists precisely because Ollama serves its own default `num_ctx` whatever
a model advertises — measured on that machine, `gemma4:12b` reports a
262,144-token maximum and loads with **4,096**. That module is the
measurement; there was no control, and the only way past the default was
a Modelfile written by hand in another tool.

Two properties here are the design rather than the plumbing:

* **Unset means unset.** Nothing is sent unless somebody asked, because a
  KV cache is VRAM and raising it on a user's behalf spends their card
  without asking.
* **It is bounded.** Asking a 12 GB card for 262,144 tokens does not fail
  cleanly; it spills to system RAM and every reply becomes slow, which
  reads as the model being bad rather than the setting being wrong.
"""

from __future__ import annotations

import pytest

from core.user_settings import MAX_CONTEXT_TOKENS, UserSettings


@pytest.fixture
def settings(tmp_path):
    return UserSettings(str(tmp_path / "settings.json"))


class TestTheSetting:
    def test_it_starts_unset(self, settings):
        """Zero, meaning *leave the server's default alone*. A product
        that quietly raised somebody's KV cache would be spending their
        VRAM on a choice they did not make."""
        assert settings.to_dict()["context_tokens"] == 0

    def test_a_number_is_kept(self, settings):
        assert settings.set_context_tokens(32_768) == 32_768
        assert settings.to_dict()["context_tokens"] == 32_768

    def test_it_survives_a_restart(self, tmp_path):
        path = str(tmp_path / "s.json")
        UserSettings(path).set_context_tokens(16_384)
        assert UserSettings(path).to_dict()["context_tokens"] == 16_384

    def test_clearing_it_goes_back_to_the_default(self, settings):
        settings.set_context_tokens(32_768)
        assert settings.set_context_tokens(0) == 0

    def test_negative_means_the_same_as_clearing(self, settings):
        """What a person means by emptying the box."""
        assert settings.set_context_tokens(-5) == 0


class TestItIsBounded:
    def test_an_enormous_window_is_clamped_not_refused(self, settings):
        # Refusing would make the box reject a number somebody typed in
        # good faith; clamping applies the ceiling and keeps the value.
        assert settings.set_context_tokens(10_000_000) == MAX_CONTEXT_TOKENS

    def test_the_ceiling_is_high_enough_to_be_useful(self):
        """A guard, not a limitation. Any real document fits under it."""
        assert MAX_CONTEXT_TOKENS >= 65_536

    def test_a_hand_edited_file_cannot_exceed_it(self, tmp_path):
        """The file is the user's and they may edit it, so the load path
        is a second way in and is bounded the same way."""
        import json

        path = tmp_path / "s.json"
        path.write_text(json.dumps({"context_tokens": 10_000_000}), encoding="utf-8")
        assert UserSettings(str(path)).to_dict()["context_tokens"] == MAX_CONTEXT_TOKENS

    def test_nonsense_in_the_file_leaves_it_unset(self, tmp_path):
        import json

        path = tmp_path / "s.json"
        path.write_text(json.dumps({"context_tokens": "lots"}), encoding="utf-8")
        assert UserSettings(str(path)).to_dict()["context_tokens"] == 0


class TestWhatReachesOllama:
    """The half that was missing: a number nobody could set changed
    nothing."""

    def test_nothing_is_sent_under_the_server_policy(self, monkeypatch, tmp_path):
        """**This test used to patch the function and then call its own
        patch**, so it asserted that a one-line lambda returns what it
        returns and would have passed against any engine at all. Rewritten
        to call the real reader, which is what its name claims — the trap
        `CLAUDE.md` names as worse than no test, because it reports
        coverage it does not have."""
        import core.user_settings as us
        import runtimes.models.engines.ollama_engine as engine

        store = us.UserSettings(str(tmp_path / "s.json"))
        store.set_context_policy("server")
        monkeypatch.setattr(us, "get_user_settings", lambda: store)

        assert engine._requested_context_tokens("anything:1b") == 0

    def test_the_engine_reads_the_setting_per_request(self, monkeypatch, tmp_path):
        """Per request rather than captured at construction: somebody who
        changes it in Settings should see the next reply use it, not the
        next launch.

        **Under `fixed`, because a stored number no longer acts on its
        own.** That is the contract the policy replaced — the default is
        now `fit` and the figure is resolved per model, which is what
        `test_the_window_is_decided_not_typed.py` covers. The surviving
        claim here is the *per request* half, and it is still worth
        holding: this is the only assertion that the reader is not
        memoised across a settings change.
        """
        import core.user_settings as us
        import runtimes.models.engines.ollama_engine as engine

        store = us.UserSettings(str(tmp_path / "s.json"))
        store.set_context_policy("fixed")
        monkeypatch.setattr(us, "get_user_settings", lambda: store)

        assert engine._requested_context_tokens("anything:1b") == 0
        store.set_context_tokens(16_384)
        assert engine._requested_context_tokens("anything:1b") == 16_384

    def test_a_broken_settings_store_leaves_the_default_alone(self, monkeypatch):
        """A settings store that will not load must not be able to change
        how a model is called."""
        import core.user_settings as us
        import runtimes.models.engines.ollama_engine as engine

        def explode():
            raise RuntimeError("no settings")

        monkeypatch.setattr(us, "get_user_settings", explode)
        assert engine._requested_context_tokens("anything:1b") == 0

    def test_the_payload_carries_num_ctx_only_when_asked(self):
        """Asserted against the source, because the property is that the
        key is *absent* by default — and an absent key is the one thing a
        response-shape test cannot see."""
        import inspect

        import runtimes.models.engines.ollama_engine as engine

        source = inspect.getsource(engine)
        assert "if window:" in source
        assert 'payload["options"] = {"num_ctx": window}' in source


class TestTheRoute:
    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        import main

        return TestClient(main.app)

    def test_the_settings_payload_reports_it(self, client):
        body = client.get("/routing/preference").json()
        assert "context_tokens" in body

    def test_and_the_ceiling_so_the_interface_need_not_hardcode_one(self, client):
        """The same argument `task_slots` makes: a client free to invent
        its own number would offer a window this backend accepts and then
        silently clamps."""
        body = client.get("/routing/preference").json()
        assert body["max_context_tokens"] == MAX_CONTEXT_TOKENS
