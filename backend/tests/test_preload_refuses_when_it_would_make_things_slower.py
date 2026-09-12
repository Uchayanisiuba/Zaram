"""The boot preload asks three questions before it spends the card.

**Measured 12 September 2026, on a 12 GB card.** The routing preference was
`prefer_cloud`; the user's day-to-day model lived on TabbyAPI holding 9.5 GB;
the desktop held another 3 GB. `warm_local_model` loaded Ollama's 10.4 GB pick
anyway, because the only thing it checked was that a model had been selected.
That is 23 GB asked of a 12 GB card: the driver paged GPU memory over PCIe for
every process on the machine, and the whole desktop was slow with Unreal
closed.

Three refusals, each pinned here, and one property they all share: **an
unknown answers "preload as before"**. A missing preference, a provider layer
that has not scanned, a card the driver cannot read — none of those is a reason
to refuse, because refusing on a number nobody has is a guess, and the cost of
that guess is a first-message cold start with no explanation.
"""

from __future__ import annotations

import pytest

from core.user_settings import get_user_settings
from runtimes.models.models_runtime import ModelsRuntime


class _RecordingEngine:
    def __init__(self) -> None:
        self.warmed: list = []

    def warm(self, model=None):
        self.warmed.append(model)
        return True


class _Service:
    def __init__(self, engine) -> None:
        self.engine = engine


class _Model:
    def __init__(self, size_bytes):
        self.size_bytes = size_bytes


class _Manager:
    """Only what `_catalogued` and `_local_endpoint_for` reach."""

    def __init__(self, sizes: dict, endpoints: dict | None = None):
        self._sizes = sizes
        self._endpoints = endpoints or {}

    def get_model(self, model):
        if model in self._sizes:
            return _Model(self._sizes[model])
        return None


def _runtime(*, selected="ollama:qwen3-14b-16k:latest", manager=None) -> tuple[ModelsRuntime, _RecordingEngine]:
    engine = _RecordingEngine()
    runtime = ModelsRuntime(event_bus=None, provider_manager=manager)
    runtime._service = _Service(engine)
    runtime._selected_model = selected
    return runtime, engine


GB = 1_000_000_000  # decimal, as the sentence the user reads shows it


class TestPreferCloudMeansNoPreload:
    @pytest.mark.asyncio
    async def test_prefer_cloud_skips_and_says_why(self):
        get_user_settings().set_routing_preference("prefer_cloud")
        runtime, engine = _runtime()

        assert await runtime.warm_local_model() is False
        assert engine.warmed == []
        assert "cloud" in runtime.preload_skipped_because

    @pytest.mark.asyncio
    async def test_auto_still_preloads(self):
        get_user_settings().set_routing_preference("auto")
        runtime, engine = _runtime()

        assert await runtime.warm_local_model() is True
        assert engine.warmed == ["ollama:qwen3-14b-16k:latest"]
        assert runtime.preload_skipped_because == ""

    @pytest.mark.asyncio
    async def test_prefer_local_still_preloads(self):
        get_user_settings().set_routing_preference("prefer_local")
        runtime, engine = _runtime()

        assert await runtime.warm_local_model() is True


class TestAModelOnAnotherServerMeansNoPreload:
    @pytest.mark.asyncio
    async def test_a_default_served_elsewhere_refuses_a_second_chat_model(self, monkeypatch):
        get_user_settings().set_routing_preference("auto")
        get_user_settings().set_default_model("Qwen3.8-27B-exl3-2.20bpw")
        runtime, engine = _runtime()
        monkeypatch.setattr(
            runtime, "_local_endpoint_for",
            lambda model: "http://127.0.0.1:1234" if "27B" in model else None,
        )

        assert await runtime.warm_local_model() is False
        assert engine.warmed == []
        assert "another local server" in runtime.preload_skipped_because
        assert "127.0.0.1:1234" in runtime.preload_skipped_because

    @pytest.mark.asyncio
    async def test_a_default_on_ollama_itself_preloads(self, monkeypatch):
        get_user_settings().set_routing_preference("auto")
        get_user_settings().set_default_model("qwen3-14b-16k:latest")
        runtime, engine = _runtime()
        monkeypatch.setattr(runtime, "_local_endpoint_for", lambda model: None)

        assert await runtime.warm_local_model() is True


class TestWhatIsFreeNowDecides:
    @pytest.mark.asyncio
    async def test_a_model_larger_than_free_vram_is_not_preloaded(self):
        get_user_settings().set_routing_preference("auto")
        manager = _Manager({"ollama:qwen3-14b-16k:latest": int(10.4 * GB)})
        runtime, engine = _runtime(manager=manager)
        runtime.set_free_vram_probe(lambda: int(9.2 * GB))

        assert await runtime.warm_local_model() is False
        assert engine.warmed == []
        assert "10.4 GB" in runtime.preload_skipped_because
        assert "9.2 GB free" in runtime.preload_skipped_because

    @pytest.mark.asyncio
    async def test_a_model_that_fits_what_is_free_is_preloaded(self):
        get_user_settings().set_routing_preference("auto")
        manager = _Manager({"ollama:qwen3-14b-16k:latest": int(10.4 * GB)})
        runtime, engine = _runtime(manager=manager)
        runtime.set_free_vram_probe(lambda: int(11.0 * GB))

        assert await runtime.warm_local_model() is True

    @pytest.mark.asyncio
    async def test_unknown_free_vram_preloads_as_before(self):
        """No probe, or a probe that cannot read the card: not a refusal."""
        get_user_settings().set_routing_preference("auto")
        manager = _Manager({"ollama:qwen3-14b-16k:latest": int(10.4 * GB)})
        runtime, engine = _runtime(manager=manager)
        runtime.set_free_vram_probe(lambda: None)

        assert await runtime.warm_local_model() is True

    @pytest.mark.asyncio
    async def test_unknown_model_size_preloads_as_before(self):
        get_user_settings().set_routing_preference("auto")
        runtime, engine = _runtime(manager=_Manager({}))
        runtime.set_free_vram_probe(lambda: int(1 * GB))

        assert await runtime.warm_local_model() is True

    @pytest.mark.asyncio
    async def test_a_probe_that_raises_preloads_as_before(self):
        get_user_settings().set_routing_preference("auto")
        manager = _Manager({"ollama:qwen3-14b-16k:latest": int(10.4 * GB)})
        runtime, engine = _runtime(manager=manager)

        def broken():
            raise OSError("nvidia-smi not found")

        runtime.set_free_vram_probe(broken)

        assert await runtime.warm_local_model() is True
