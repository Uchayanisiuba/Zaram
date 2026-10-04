"""The context window is worked out per model, not typed once per person.

Asked for 4 October 2026, in one sentence that names the whole flaw:
*"I don't want users to need to switch token limits every time they
switch or download a new model, there needs to be a more elegant
alternative."*

The proposal in the same message was to default high — 128k — and clamp
down to each model's own limit. Half of that is right and the other half
is the trap: **the model's limit is almost never the binding constraint.**
Measured on the maintainer's machine the day this was written,
`qwen3-14b-16k` costs 160 KiB per cached token, so

* 131,072 tokens is **21.5 GB** of cache, on a 12 GB card;
* its own declared ceiling of 40,960 is still **6.7 GB**, on top of 9.3 GB
  of weights — so clamping to the model's limit *also* produces a window
  that will not load.

And it does not fail cleanly. Ollama spills the cache into system RAM and
every reply becomes slow, which a person reads as the model being bad
rather than as a setting being wrong — the failure `ContextWindowField`'s
help text already warned about, now reachable by a default rather than on
purpose.

So the stored setting stops being a figure and becomes an intent, and the
figure is resolved against *(this model, this card)* at call time. Nothing
to re-pick on a model switch, which is what was actually asked for.
"""

from __future__ import annotations

import pytest

from core.context_budget import (
    COMPUTE_RESERVE_BYTES,
    CONTEXT_GRANULARITY,
    CONTEXT_STEPS,
    MIN_CONTEXT_TOKENS,
    affordable_context_length,
    resolve_context_window,
)

#: `qwen3-14b-16k`, measured: 40 blocks x 8 KV heads x (128+128) x 2 bytes.
QWEN_PER_TOKEN = 163_840
GB = 10**9


class TestPricingACachedToken:
    """The arithmetic, pure, so it is checked without a server."""

    def test_most_of_the_memory_is_actually_spent(self):
        """**The requirement, stated by the maintainer in one line:** *"the
        solution should give the user at least 50 to 90% of what the LLM
        and PC can handle in terms of tokens."*

        Asserted as a *proportion* rather than against a figure, because
        the figure is what the first version got wrong. Resolution rounded
        onto a power-of-two ladder, so between two steps it discarded up
        to half the card — 5.3 GB of room resolved to 16,384 tokens when
        29,696 fitted, which is 51%. A test pinned to `== 16_384` would
        have called that correct.
        """
        for room in (2 * GB, 2_908_703_384, 4 * GB, 5_300_000_000, 8 * GB, 12 * GB):
            tokens = affordable_context_length(QWEN_PER_TOKEN, room)
            assert tokens is not None
            # What the room allows once the compute buffer is held back.
            ceiling = (room - COMPUTE_RESERVE_BYTES) // QWEN_PER_TOKEN
            assert tokens <= ceiling, (room, tokens, ceiling)
            assert tokens / ceiling >= 0.90, (room, tokens, ceiling)

    def test_a_bigger_card_affords_a_bigger_window(self):
        small = affordable_context_length(QWEN_PER_TOKEN, 2_908_703_384)
        large = affordable_context_length(QWEN_PER_TOKEN, 12 * GB)
        assert small is not None and large is not None
        assert large > small * 4

    def test_a_compute_buffer_is_held_back(self):
        """Over and above the weights and the embedder, and **not as a
        percentage**: llama.cpp sizes its compute buffer by the model's
        dimensions, not by the cache, so a fraction would under-reserve on
        a small card and waste memory on a large one.

        The failure it prevents is the one quoted from LM Studio's own
        behaviour: a cache that overruns the card is not refused, it is
        offloaded to system RAM and generation speed collapses
        mid-conversation. So the margin sits on the safe side.
        """
        room = 4 * GB
        tokens = affordable_context_length(QWEN_PER_TOKEN, room)
        assert tokens is not None
        assert tokens * QWEN_PER_TOKEN <= room - COMPUTE_RESERVE_BYTES

    def test_the_figure_is_a_round_number(self):
        """A multiple of 1,024, so it reads as a setting rather than as a
        measurement with a remainder. Fine enough to spend ~99% of the
        memory, which is the whole reason it is not a power of two."""
        for room in (2 * GB, 3_333_333_333, 7 * GB):
            tokens = affordable_context_length(QWEN_PER_TOKEN, room)
            assert tokens is not None and tokens % CONTEXT_GRANULARITY == 0

    def test_an_unmeasured_machine_is_unknown_rather_than_nothing(self):
        """`None` out, not the smallest step. Apple and DirectML report no
        VRAM at all, and *"this machine affords 2,048 tokens"* would be a
        confident false claim about every Mac."""
        assert affordable_context_length(QWEN_PER_TOKEN, None) is None

    def test_an_unpriceable_model_is_unknown(self):
        assert affordable_context_length(None, 12 * GB) is None
        assert affordable_context_length(0, 12 * GB) is None

    def test_nothing_fitting_is_an_answer_and_not_an_absence_of_one(self):
        """The distinction the three-valued discipline exists for, and the
        one this function got wrong first. Both inputs were read; the
        conclusion is that the weights overrun the card. Returning `None`
        there sent the caller on to the model author's 128k — the largest
        possible window, chosen *because* nothing fitted."""
        assert affordable_context_length(QWEN_PER_TOKEN, 1_000) == MIN_CONTEXT_TOKENS
        assert affordable_context_length(QWEN_PER_TOKEN, -5 * GB) == MIN_CONTEXT_TOKENS

    def test_the_offered_ladder_descends(self):
        """`CONTEXT_STEPS` is what the *control* offers now — resolution
        does not round onto it. The order still matters because the
        interface renders it as given, and a list that climbed would put
        the smallest window first under a label reading "just for this
        model"."""
        assert list(CONTEXT_STEPS) == sorted(CONTEXT_STEPS, reverse=True)

    def test_resolution_does_not_round_onto_the_offered_ladder(self):
        """The separation this file exists to hold. The ladder is round
        numbers for a person to pick; the resolved window is arithmetic,
        and conflating them cost 48% of the card."""
        tokens = affordable_context_length(QWEN_PER_TOKEN, 5_300_000_000)
        assert tokens not in CONTEXT_STEPS
        assert tokens is not None and tokens > 16_384


class TestResolvingTheWindow:
    def test_fit_takes_the_card_into_account_not_only_the_model(self):
        """The measured case, and the answer the maintainer's own machine
        gives: 16k, which is also the figure the model's author put in its
        name."""
        choice = resolve_context_window(
            declared=40_960,
            configured=16_384,
            bytes_per_token=QWEN_PER_TOKEN,
            free_bytes=2_908_703_384,
        )
        # Well past Ollama's 4,096 and well short of the 40,960 the model
        # declares, which is the point: neither default was right.
        assert 12_000 < choice.tokens < 20_000
        assert "card" in choice.reason

    def test_fit_never_exceeds_what_the_model_declares(self):
        """A card with room for 128k and a model that admits to 40,960.
        The window is the model's, and rounded down to a step rather than
        reported as its exact ceiling — the ladder is what the control
        offers, so a resolved window and a chosen one stay comparable."""
        choice = resolve_context_window(
            declared=40_960,
            configured=16_384,
            bytes_per_token=QWEN_PER_TOKEN,
            free_bytes=40 * GB,
        )
        assert choice.tokens <= 40_960

    def test_an_unpriceable_model_falls_back_to_its_own_file(self):
        """`gemma4:12b` is this case and it is not an edge one: its
        sliding-window layers make the cache unpriceable from `model_info`
        alone, and its own Modelfile asks for 131,072. Its author knows its
        geometry; Zaram does not. The author wins, and both beat 4,096."""
        choice = resolve_context_window(
            declared=262_144,
            configured=131_072,
            bytes_per_token=None,
            free_bytes=4_630_000_000,
        )
        assert choice.tokens == 131_072
        assert "own file" in choice.reason

    def test_with_nothing_readable_the_server_decides(self):
        """`0`, which means *send no `num_ctx`*. Not a small window that
        looks chosen — the one honest answer when none of the three
        readings came back."""
        choice = resolve_context_window(
            declared=None, configured=None, bytes_per_token=None, free_bytes=None
        )
        assert choice.tokens == 0
        assert "server" in choice.reason

    def test_an_override_for_this_model_outranks_the_policy(self):
        choice = resolve_context_window(
            declared=40_960,
            configured=16_384,
            bytes_per_token=QWEN_PER_TOKEN,
            free_bytes=2_908_703_384,
            override=32_768,
        )
        assert choice.tokens == 32_768
        assert "this model" in choice.reason

    def test_an_override_is_still_capped_by_the_model(self):
        choice = resolve_context_window(
            declared=40_960,
            configured=16_384,
            bytes_per_token=QWEN_PER_TOKEN,
            free_bytes=12 * GB,
            override=131_072,
        )
        assert choice.tokens == 40_960
        assert "the most this model can hold" in choice.reason

    def test_an_override_wins_even_under_the_server_policy(self):
        """Otherwise a number set for one model is silently ignored, which
        is worse than refusing to store it."""
        choice = resolve_context_window(
            declared=40_960,
            configured=None,
            bytes_per_token=None,
            free_bytes=None,
            override=8_192,
            policy="server",
        )
        assert choice.tokens == 8_192

    def test_server_sends_nothing(self):
        choice = resolve_context_window(
            declared=262_144,
            configured=131_072,
            bytes_per_token=QWEN_PER_TOKEN,
            free_bytes=12 * GB,
            policy="server",
        )
        assert choice.tokens == 0

    def test_the_reason_names_a_source_rather_than_only_a_number(self):
        """Routing legibility, applied to the one setting whose wrong value
        makes a good model look bad. 16k *from the card* and 16k *because
        you set it* are the same figure and different facts, and the person
        cannot otherwise tell a window chosen for them from one they
        chose."""
        from_card = resolve_context_window(
            declared=40_960,
            configured=None,
            bytes_per_token=QWEN_PER_TOKEN,
            free_bytes=2_908_703_384,
        )
        from_person = resolve_context_window(
            declared=40_960,
            configured=None,
            bytes_per_token=QWEN_PER_TOKEN,
            free_bytes=2_908_703_384,
            override=16_384,
        )
        assert from_person.tokens == 16_384
        assert from_card.tokens == 15_360
        # Nearly the same window, two different facts about it, and the
        # reason is the only thing that distinguishes them.
        assert from_card.reason != from_person.reason


class TestReadingTheGeometry:
    """What `kv_bytes_per_token` does with the shapes Ollama really
    reports. Both fixtures are copied from `/api/show` on the maintainer's
    machine, 4 October 2026, rather than invented."""

    @staticmethod
    def _show(monkeypatch, info):
        import core.context_budget as module

        class Reply:
            @staticmethod
            def raise_for_status():
                return None

            @staticmethod
            def json():
                return {"model_info": info}

        monkeypatch.setattr(module.requests, "post", lambda *a, **k: Reply())

    def test_a_plain_grouped_query_model_is_priced(self, monkeypatch):
        from core.context_budget import kv_bytes_per_token

        self._show(
            monkeypatch,
            {
                "general.architecture": "qwen3",
                "qwen3.block_count": 40,
                "qwen3.attention.head_count_kv": 8,
                "qwen3.attention.key_length": 128,
                "qwen3.attention.value_length": 128,
            },
        )
        assert kv_bytes_per_token("qwen3-14b-16k") == QWEN_PER_TOKEN

    def test_sliding_window_attention_is_refused_rather_than_guessed(self, monkeypatch):
        """`gemma4:12b`'s real `model_info`. Most of its layers attend over
        a window and cache a fraction of the context, and nothing here says
        which layers those are — the naive sum overstates its cost roughly
        tenfold, which would cap a 262,144 ceiling at a few thousand tokens
        and call that a measurement. Rule 9 applied to arithmetic."""
        from core.context_budget import kv_bytes_per_token

        self._show(
            monkeypatch,
            {
                "general.architecture": "gemma4",
                "gemma4.block_count": 48,
                "gemma4.attention.head_count_kv": [8, 8, 8, 8, 8, 1] * 8,
                "gemma4.attention.key_length": 512,
                "gemma4.attention.value_length": 512,
                "gemma4.attention.key_length_swa": 256,
                "gemma4.attention.value_length_swa": 256,
            },
        )
        assert kv_bytes_per_token("gemma4:12b") is None

    def test_a_per_layer_head_count_is_summed_not_multiplied(self, monkeypatch):
        """Without the `_swa` keys the list is unambiguous, and summing it
        is the honest reading: multiplying one entry by `block_count` would
        be wrong for any model that varies it."""
        from core.context_budget import kv_bytes_per_token

        self._show(
            monkeypatch,
            {
                "x.block_count": 4,
                "x.attention.head_count_kv": [8, 8, 4, 4],
                "x.attention.key_length": 64,
                "x.attention.value_length": 64,
            },
        )
        assert kv_bytes_per_token("x:1b") == 24 * 128 * 2

    def test_the_architecture_prefix_is_not_hardcoded(self, monkeypatch):
        from core.context_budget import kv_bytes_per_token

        self._show(
            monkeypatch,
            {
                "something_new.block_count": 2,
                "something_new.attention.head_count_kv": 2,
                "something_new.attention.key_length": 8,
                "something_new.attention.value_length": 8,
            },
        )
        assert kv_bytes_per_token("new:1b") == 2 * 2 * 16 * 2

    def test_missing_geometry_is_unknown(self, monkeypatch):
        from core.context_budget import kv_bytes_per_token

        self._show(monkeypatch, {"general.architecture": "llama"})
        assert kv_bytes_per_token("x:1b") is None

    def test_no_model_is_unknown(self):
        from core.context_budget import kv_bytes_per_token

        assert kv_bytes_per_token("") is None
        assert kv_bytes_per_token(None) is None

    def test_it_refuses_a_host_that_is_not_loopback(self, monkeypatch):
        """The boundary every reader in this module keeps. Asking a
        stranger's server about a model is a request nobody asked for."""
        import core.context_budget as module
        from core.context_budget import kv_bytes_per_token

        called = []
        monkeypatch.setattr(module.requests, "post", lambda *a, **k: called.append(1))
        assert kv_bytes_per_token("x:1b", "http://example.com:11434") is None
        assert called == []

    def test_a_server_that_will_not_answer_is_unknown_not_an_error(self, monkeypatch):
        import core.context_budget as module
        from core.context_budget import kv_bytes_per_token

        def explode(*_a, **_k):
            raise OSError("no ollama")

        monkeypatch.setattr(module.requests, "post", explode)
        assert kv_bytes_per_token("x:1b") is None


class TestTheStore:
    @pytest.fixture()
    def settings(self, tmp_path, monkeypatch):
        import core.user_settings as module

        monkeypatch.setattr(module, "_SETTINGS", None, raising=False)
        store = module.UserSettings(str(tmp_path / "settings.json"))
        return store

    def test_fit_is_the_default(self, settings):
        """The point of the change: a fresh install needs no decision, and
        no decision again when a model is added."""
        assert settings.to_dict()["context_policy"] == "fit"

    def test_an_unrecognised_policy_resolves_to_the_default(self, settings):
        assert settings.set_context_policy("whatever") == "fit"

    def test_an_override_is_remembered_against_one_model(self, settings):
        settings.set_context_override("qwen3:8b", 32_768)
        assert settings.to_dict()["context_overrides"] == {"qwen3:8b": 32_768}

    def test_zero_forgets_rather_than_stores(self, settings):
        """*"No opinion about this model"* and *"this model should use the
        server default"* are different states. The first falls through to
        the policy; the second is `set_context_policy("server")`."""
        settings.set_context_override("qwen3:8b", 32_768)
        settings.set_context_override("qwen3:8b", 0)
        assert settings.to_dict()["context_overrides"] == {}

    def test_an_override_is_bounded(self, settings):
        from core.user_settings import MAX_CONTEXT_TOKENS

        settings.set_context_override("x:1b", 10_000_000)
        assert settings.to_dict()["context_overrides"]["x:1b"] == MAX_CONTEXT_TOKENS

    def test_an_unnamed_model_is_not_stored(self, settings):
        settings.set_context_override("   ", 8_192)
        assert settings.to_dict()["context_overrides"] == {}

    def test_a_number_stored_before_the_policy_existed_is_discarded(
        self, tmp_path, monkeypatch
    ):
        """**The global number is gone, and an old file holding one lands
        on `fit`.**

        It was built on 4 October and removed on 4 October, on the
        maintainer's question: *"if this is true do we still need the
        token limit options in the settings, perhaps we should remove
        it."* The answer was no. The only route past Ollama's 4,096 used
        to be that field, so a number in it is evidence that the default
        was wrong rather than that one figure was wanted for every model
        — the maintainer's own store held 131,072, which `qwen3-14b-16k`
        cannot hold at all.

        `fit` cannot produce a window past what the model declares or the
        card affords, so discarding it can only be in the safe direction.
        """
        import json

        import core.user_settings as module

        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"context_tokens": 131_072, "context_policy": "fixed"}),
            encoding="utf-8",
        )
        monkeypatch.setattr(module, "_SETTINGS", None, raising=False)
        stored = module.UserSettings(str(path)).to_dict()

        assert stored["context_policy"] == "fit"
        assert "context_tokens" not in stored

    def test_there_are_two_policies_and_only_two(self):
        """A mode with no use `fit` does not cover, and a bug history, is
        not kept for symmetry. `fixed` was the only branch that skipped
        the declared-ceiling cap — it shipped asking a model declaring
        40,960 for 131,072."""
        from core.user_settings import CONTEXT_POLICIES

        assert CONTEXT_POLICIES == frozenset({"fit", "server"})

    def test_a_policy_someone_chose_survives_a_reload(self, tmp_path, monkeypatch):
        import json

        import core.user_settings as module

        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps({"context_policy": "server", "context_tokens": 8_192}),
            encoding="utf-8",
        )
        monkeypatch.setattr(module, "_SETTINGS", None, raising=False)
        assert module.UserSettings(str(path)).to_dict()["context_policy"] == "server"

    def test_a_hostile_overrides_block_is_read_defensively(self, tmp_path, monkeypatch):
        """A settings file is a file. Anything that is not a name against a
        number is dropped rather than coerced, which is how the character
        fields are read for the same reason."""
        import json

        import core.user_settings as module

        path = tmp_path / "settings.json"
        path.write_text(
            json.dumps(
                {
                    "context_overrides": {
                        "good:1b": 8_192,
                        "bad:1b": "lots",
                        "": 8_192,
                        "huge:1b": 99_999_999,
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(module, "_SETTINGS", None, raising=False)
        kept = module.UserSettings(str(path)).to_dict()["context_overrides"]

        from core.user_settings import MAX_CONTEXT_TOKENS

        assert kept == {"good:1b": 8_192, "huge:1b": MAX_CONTEXT_TOKENS}


class TestTheEngineAsksForIt:
    def test_the_window_is_resolved_against_the_model_being_called(self, monkeypatch):
        """**The regression this whole change is about.** The reader used to
        take no arguments at all, so one number was sent to every model.
        Its signature now requires the model, which is the version of the
        claim a test can hold."""
        import inspect

        from runtimes.models.engines.ollama_engine import _requested_context_tokens

        assert "model" in inspect.signature(_requested_context_tokens).parameters

    def test_a_settings_store_that_will_not_load_sends_nothing(self, monkeypatch):
        """Every failure resolves to `0` — leave the server's default
        alone. A broken settings file must not be able to change how a
        model is called."""
        import runtimes.models.engines.ollama_engine as engine

        def explode():
            raise RuntimeError("no settings")

        monkeypatch.setattr(
            "core.user_settings.get_user_settings", explode, raising=False
        )
        assert engine._requested_context_tokens("x:1b") == 0

    def test_the_cache_holds_only_what_belongs_to_the_model_file(self):
        """`_model_geometry` is cached per model because the declared
        ceiling, the Modelfile's window and the cost per token are
        properties of a file on disk. **Free memory is deliberately not in
        there** — it is the part that moves, and caching it would freeze a
        reading taken once per launch."""
        import inspect

        import runtimes.models.engines.ollama_engine as engine

        source = inspect.getsource(engine._model_geometry)
        assert "free_bytes" not in source
        assert "room_for_a_cache" not in source


class TestItIsNotMeasuredAgainstWhatIsFreeRightNow:
    """The error made while building this, kept because the reasoning is
    the useful part."""

    def test_the_basis_is_the_cards_capacity(self):
        """`vram_free_bytes` is the better reading for a preload and its own
        docstring says why. It is the wrong one here, and trying it first is
        how that was found: probed with TabbyAPI resident, **1.2 GB free of
        12.3**, which resolves a 14B's window to the smallest step on the
        ladder — and leaves it there. A window that shrinks because
        something else is open, and stays shrunk, is not a setting; the
        person experiences it as Zaram quietly getting worse."""
        import inspect

        from core.context_budget import room_for_a_cache

        source = inspect.getsource(room_for_a_cache)
        assert "vram_free_bytes" not in source.split('"""')[2]

    def test_a_card_that_cannot_be_measured_is_unknown(self, monkeypatch):
        """Apple shares one pool with the CPU and DirectML reports nothing,
        so this is the common path off NVIDIA rather than an edge. The
        resolver then uses the model author's own figure."""
        import core.context_budget as module

        class NoCard:
            vram_bytes = None

        class Profiler:
            @staticmethod
            def profile():
                return NoCard()

        monkeypatch.setattr(
            "providers.discoverers.hardware.HardwareProfiler", Profiler, raising=False
        )
        assert module.room_for_a_cache("x:1b") is None


class TestWhatReachesOllama:
    """Folded in from `test_the_context_window_can_be_set.py`, which was
    deleted when the global number was: ten of its seventeen tests
    asserted a setting that no longer exists, and two files covering one
    feature with one of them mostly dead is worse than one file."""

    def test_nothing_is_sent_under_the_server_policy(self, monkeypatch, tmp_path):
        """**This test used to patch the function and then call its own
        patch**, so it asserted that a one-line lambda returns what it
        returns and would have passed against any engine at all — the
        trap `CLAUDE.md` names as worse than no test, because it reports
        coverage it does not have."""
        import core.user_settings as us
        import runtimes.models.engines.ollama_engine as engine

        store = us.UserSettings(str(tmp_path / "s.json"))
        store.set_context_policy("server")
        monkeypatch.setattr(us, "get_user_settings", lambda: store)

        assert engine._requested_context_tokens("anything:1b") == 0

    def test_the_setting_is_read_per_request(self, monkeypatch, tmp_path):
        """Per request rather than captured at construction: somebody who
        changes it in Settings should see the next reply use it, not the
        next launch.

        Driven through a **per-model override**, which is the only number
        anybody sets now. This is the one assertion that the reader is
        not memoised across a settings change.
        """
        import core.user_settings as us
        import runtimes.models.engines.ollama_engine as engine

        store = us.UserSettings(str(tmp_path / "s.json"))
        store.set_context_policy("server")
        monkeypatch.setattr(us, "get_user_settings", lambda: store)

        assert engine._requested_context_tokens("anything:1b") == 0
        store.set_context_override("anything:1b", 16_384)
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


class TestTheSettingsRoute:
    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient

        import main

        return TestClient(main.app)

    def test_the_payload_carries_the_policy_rather_than_a_number(self, client):
        """There is no number in the payload any more, and its absence is
        asserted: a client still reading `context_tokens` would get
        `undefined` and render a blank where a decision belongs."""
        body = client.get("/routing/preference").json()
        assert body["context_policy"] in {"fit", "server"}
        assert "context_tokens" not in body

    def test_it_carries_the_vocabulary_rather_than_leaving_it_to_be_invented(
        self, client
    ):
        """The same argument `task_slots` makes: a client free to invent
        its own list could offer a policy this backend accepts the write
        for and then resolves to the default."""
        body = client.get("/routing/preference").json()
        assert sorted(body["context_policies"]) == ["fit", "server"]

    def test_and_the_ceiling_so_the_interface_need_not_hardcode_one(self, client):
        """Still sent, because it still bounds a per-model window."""
        from core.user_settings import MAX_CONTEXT_TOKENS

        body = client.get("/routing/preference").json()
        assert body["max_context_tokens"] == MAX_CONTEXT_TOKENS

    def test_the_ceiling_is_high_enough_to_be_useful(self):
        from core.user_settings import MAX_CONTEXT_TOKENS

        assert MAX_CONTEXT_TOKENS >= 131_072

    def test_a_window_can_be_set_for_one_model_over_the_wire(self, client):
        """End to end, because the store being right is not evidence that
        the route reaches it — this repository's most expensive recurring
        failure is a complete, tested thing nothing calls."""
        client.post(
            "/routing/preference",
            json={"context_override": {"model": "probe:1b", "tokens": 8_192}},
        )
        body = client.get("/routing/preference").json()
        assert body["context_overrides"].get("probe:1b") == 8_192

        client.post(
            "/routing/preference",
            json={"context_override": {"model": "probe:1b", "tokens": 0}},
        )
        after = client.get("/routing/preference").json()
        assert "probe:1b" not in after["context_overrides"]
