# backend/tests/test_engine_routing.py
"""Which engine answers, and what happens when that cannot be decided.

`ModelsService` holds one engine. With a cloud engine in the picture, something
has to choose per message, and `RoutedEngine` is that something — it satisfies
`LLMEngine`, sits where the single engine used to, and delegates.

The tests worth writing here are almost all about the *wrong* answers, because
the right one is uninteresting: a local model goes to Ollama. The interesting
question is what happens when the model is unknown, when the lookup raises, and
when the user asked for cloud and there is no key — and in the first two cases
the answer must lean the same way, because the failure modes are not symmetric.
Guessing local costs a possibly-worse answer. Guessing cloud costs the user's
documents leaving the machine on the strength of a lookup that failed.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from runtimes.models.engines.base_engine import ERROR_PREFIX
from runtimes.models.engines.routed_engine import RoutedEngine


class _Recorder:
    """A minimal engine that records what it was asked, per the contract."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.calls: list[tuple[str, str, str | None]] = []
        #: Images seen per call. Recorded separately so a test can assert that
        #: the cloud side was never handed one without every existing
        #: assertion about `calls` having to change shape.
        self.images: list[list[str] | None] = []
        self.default_model: str | None = None

    def stream_response(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str | None = None,
        images: list[str] | None = None,
    ) -> Iterator[str]:
        self.calls.append((prompt, system_prompt, model))
        self.images.append(images)
        yield self.label


@pytest.fixture
def local():
    return _Recorder("local")


@pytest.fixture
def cloud():
    return _Recorder("cloud")


class TestItRoutesByDeclaredLocality:
    def test_a_local_model_goes_to_the_local_engine(self, local, cloud):
        engine = RoutedEngine(local=local, cloud=cloud, is_remote=lambda m: False)

        assert list(engine.stream_response("q", "sys", "llama3")) == ["local"]
        assert not cloud.calls

    def test_a_remote_model_goes_to_the_cloud_engine(self, local, cloud):
        engine = RoutedEngine(local=local, cloud=cloud, is_remote=lambda m: True)

        assert list(engine.stream_response("q", "sys", "some-cloud-model")) == ["cloud"]
        assert not local.calls

    def test_the_whole_call_is_passed_through_unchanged(self, local, cloud):
        """Including `system_prompt`, which is where recalled facts live.

        A router that dropped or rebuilt it would change what reaches the
        model — and on the cloud branch, what leaves the machine.
        """
        engine = RoutedEngine(local=local, cloud=cloud, is_remote=lambda m: True)

        list(engine.stream_response("the question", "the recalled facts", "m"))

        assert cloud.calls == [("the question", "the recalled facts", "m")]

    def test_no_model_named_is_local(self, local, cloud):
        """The default path. Nothing is sent off-device because a caller did
        not name a model — rule 5 forbids that as a default."""
        engine = RoutedEngine(
            local=local, cloud=cloud, is_remote=lambda m: pytest.fail("asked anyway")
        )

        assert list(engine.stream_response("q")) == ["local"]


class TestItFailsTowardsTheMachine:
    def test_an_unresolvable_model_routes_local(self, local, cloud):
        """The fail-safe direction, and the only defensible one.

        The gate would still refuse an unapproved host, but a design that leans
        on its last line of defence for ordinary behaviour has one line of
        defence.
        """
        engine = RoutedEngine(local=local, cloud=cloud, is_remote=lambda m: False)

        assert list(engine.stream_response("q", "sys", "never-heard-of-it")) == ["local"]
        assert not cloud.calls

    def test_a_raising_resolver_routes_local(self, local, cloud):
        """A lookup that blows up is not permission to send anything anywhere."""

        def boom(_model):
            raise RuntimeError("provider layer is having a day")

        engine = RoutedEngine(local=local, cloud=cloud, is_remote=boom)

        assert list(engine.stream_response("q", "sys", "anything")) == ["local"]
        assert not cloud.calls


class TestAnImageIsCarriedRatherThanJudgedHere:
    """Rule 7j: consent is per destination *and data class*.

    **This class used to assert the opposite, and the change is deliberate.**
    It was `TestAnImageNeverLeavesTheDevice`, and it pinned a blanket refusal:
    every cloud-bound image was rejected by `RoutedEngine` itself. That was the
    right behaviour while it lasted, for a reason that has since stopped being
    true — `EgressPolicy` was keyed on host alone, so there was nowhere to
    record "this provider may receive pictures", and a blanket refusal was the
    only honest position available.

    Since 29 August 2026 the policy is keyed on ``(host, DataClass)``. The
    question is therefore asked properly, at the chokepoint, and **the
    guarantee moved with it** — see `test_an_image_needs_its_own_consent.py`,
    which asserts against a real gate, a real policy and a real log that an
    image bound for a host approved only for chat is refused and recorded.

    What is left to assert *here* is the narrower thing this module is
    responsible for: it carries the image to the engine that knows the host,
    and it does not make a second, private copy of the decision. A second copy
    is exactly the defect `_local_endpoint_for` shipped — four call sites
    resolving a model one way and a fifth resolving it another.
    """

    def test_a_picture_reaches_a_local_engine(self, local, cloud):
        engine = RoutedEngine(local=local, cloud=cloud, is_remote=lambda m: False)

        list(engine.stream_response("what is this", "sys", "gemma4:12b", ["aGk="]))

        assert local.images == [["aGk="]]

    def test_a_picture_reaches_the_cloud_engine_intact(self, local, cloud):
        """Handed on, not stripped.

        The strip is the failure worth guarding: an answer built from the
        prompt with the picture quietly removed is confident prose about
        something nobody looked at, and it reads exactly like a real answer.
        Whether it is then *sent* is the gate's decision, not this module's.
        """
        engine = RoutedEngine(local=local, cloud=cloud, is_remote=lambda m: True)

        list(engine.stream_response("what is this", "sys", "gpt-4o", ["aGk="]))

        assert cloud.images == [["aGk="]]

    def test_routing_holds_no_opinion_of_its_own_about_images(self, local, cloud):
        """No second implementation of the consent rule lives here.

        `RoutedEngine` takes an `is_remote` callable precisely so the chat path
        acquires no dependency on the provider or policy layers. If a future
        change reintroduces a refusal here, this fails — and it should, because
        two places answering one question is how they come to disagree.
        """
        engine = RoutedEngine(local=local, cloud=cloud, is_remote=lambda m: True)

        out = "".join(
            engine.stream_response("what is this", "sys", "gpt-4o", ["aGk="])
        )

        assert not out.startswith(ERROR_PREFIX)
        assert out == cloud.label

    def test_a_text_request_still_reaches_the_cloud(self, local, cloud):
        engine = RoutedEngine(local=local, cloud=cloud, is_remote=lambda m: True)

        out = "".join(engine.stream_response("hello", "sys", "gpt-4o"))

        # The refusal must not leak into requests that carry no image.
        assert out == cloud.label
        assert cloud.images == [None]


class TestAMissingCloudEngineIsSaidOutLoud:
    def test_it_reports_rather_than_answering_locally(self, local):
        """`CLAUDE.md`: disabled capabilities are visible, not silent.

        Quietly answering from a small local model when the user picked a large
        cloud one gives a worse answer with nothing to indicate why — the same
        failure as answering without search when search is off.
        """
        engine = RoutedEngine(local=local, cloud=None, is_remote=lambda m: True)

        chunks = list(engine.stream_response("q", "sys", "gpt-4o"))

        assert len(chunks) == 1
        assert chunks[0].startswith(ERROR_PREFIX)
        assert "gpt-4o" in chunks[0]
        assert not local.calls, "it answered locally instead of saying it could not"

    def test_local_models_still_work_with_no_cloud_configured(self, local):
        """The overwhelmingly common case: no key, everything as before."""
        engine = RoutedEngine(local=local, cloud=None, is_remote=lambda m: False)

        assert list(engine.stream_response("q", "sys", "llama3")) == ["local"]


class TestTheRuntimeBuildsTheRightEngine:
    """The seam, not the component.

    Everything above tests `RoutedEngine` in isolation, which would stay green
    if `ModelsRuntime` never constructed one. This is the repo's own "test the
    seams" note applied to the wiring that makes cloud reachable at all.
    """

    @staticmethod
    def _runtime():
        from core.event_bus import EventBus
        from runtimes.models.models_runtime import ModelsRuntime

        return ModelsRuntime(EventBus())

    def test_with_no_key_nothing_that_can_leave_the_device_is_built(self, monkeypatch):
        """The overwhelmingly common case, and the one that must not regress.

        Asserted as *no cloud path exists*, not as an exact class. This test
        read `isinstance(..., OllamaEngine)` until local dispatch landed, and
        that was the wrong assertion the whole time: it pinned which local
        server answers, when what rule 5 actually requires is that **no engine
        capable of leaving the machine** is constructed without a key. The
        distinction became load-bearing the moment a second local server
        (`lm_studio`) could hold a model, and a test written against the class
        would have blocked the fix while claiming to protect the rule.
        """
        for var in ("ZARAM_OPENAI_ENDPOINT", "ZARAM_OPENAI_KEY", "OPENROUTER_API_KEY"):
            monkeypatch.delenv(var, raising=False)

        engine = self._runtime()._build_engine()
        assert not isinstance(engine, RoutedEngine)
        assert getattr(engine, "_cloud", None) is None

    def test_a_configured_key_produces_a_routed_engine(self, monkeypatch):
        monkeypatch.setenv("ZARAM_OPENAI_ENDPOINT", "https://api.example.test")
        monkeypatch.setenv("ZARAM_OPENAI_KEY", "sk-not-real")

        assert isinstance(self._runtime()._build_engine(), RoutedEngine)

    def test_openrouter_alone_is_enough(self, monkeypatch):
        """One variable, and the endpoint is not a preference the user supplies.

        The provider layer already registers OpenRouter from this key. Reading
        the same variable here is what stops a configured key producing a
        catalogue of models that cannot actually be called.
        """
        monkeypatch.delenv("ZARAM_OPENAI_ENDPOINT", raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-not-real")

        assert isinstance(self._runtime()._build_engine(), RoutedEngine)

    def test_an_endpoint_without_a_key_is_not_a_cloud_engine(self, monkeypatch):
        """Rule 1. Zaram never supplies inference, so half a configuration is
        no configuration — and it must not half-build something that fails on
        the user's first message."""
        monkeypatch.setenv("ZARAM_OPENAI_ENDPOINT", "https://api.example.test")
        monkeypatch.delenv("ZARAM_OPENAI_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        engine = self._runtime()._build_engine()
        assert not isinstance(engine, RoutedEngine)
        assert getattr(engine, "_cloud", None) is None

    def test_locality_is_read_from_the_provider_record(self, monkeypatch):
        """Not from the name. `gpt-oss` runs on Ollama.

        A router matching `"gpt"` would send a local model's prompts — and the
        recalled facts in its system prompt — to a cloud provider. That is the
        exact mistake the `locality` field exists to prevent, so the test names
        a model whose name lies about where it runs.
        """
        from core.contracts import CapabilityLocality

        class _Info:
            def __init__(self, locality):
                self.locality = locality

        class _Manager:
            def get_model(self, name):
                if name == "gpt-oss":
                    return _Info(CapabilityLocality.LOCAL)
                if name == "claude-via-router":
                    return _Info(CapabilityLocality.CLOUD)
                return None

        runtime = self._runtime()
        runtime._provider_manager = _Manager()

        assert runtime._is_remote_model("gpt-oss") is False
        assert runtime._is_remote_model("claude-via-router") is True
        assert runtime._is_remote_model("never-seen") is False
        assert runtime._is_remote_model(None) is False

    def test_hybrid_counts_as_remote(self, monkeypatch):
        """A maybe has to be treated as a yes.

        `HYBRID` says a provider *may* go off-device. Routing it local would be
        right half the time, and the wrong half is the one where data leaves.
        """
        from core.contracts import CapabilityLocality

        class _Info:
            locality = CapabilityLocality.HYBRID

        class _Manager:
            def get_model(self, name):
                return _Info()

        runtime = self._runtime()
        runtime._provider_manager = _Manager()

        assert runtime._is_remote_model("something-hybrid") is True

    def test_no_provider_layer_means_local(self, monkeypatch):
        """Boot must not start depending on a network scan, and an absent
        provider layer must not become a reason to send anything anywhere."""
        runtime = self._runtime()
        runtime._provider_manager = None

        assert runtime._is_remote_model("anything-at-all") is False


class TestTheDefaultModelStaysLocal:
    def test_setting_it_reaches_the_local_engine(self, local, cloud):
        """`ModelsRuntime` assigns `engine.default_model` after asking the
        provider layer which model may be used unprompted.

        It must land on the local engine. A cloud default would mean Zaram
        chose to send data off-device without being asked — rule 5 forbids it
        as a default, and rule 7g forbids deciding it at startup.
        """
        engine = RoutedEngine(local=local, cloud=cloud, is_remote=lambda m: False)

        engine.default_model = "llama3"

        assert local.default_model == "llama3"
        assert cloud.default_model is None
        assert engine.default_model == "llama3"
