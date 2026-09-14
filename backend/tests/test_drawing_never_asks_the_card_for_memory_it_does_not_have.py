"""Asked for a picture on a full graphics card, Zaram frees the card or says no.

The failure this pins froze a machine. On 12 September 2026 the maintainer
used a local chat model, then asked for an image, and the PC stopped — not
slowed, stopped. `imaging/local_flux.py` loads about 8.4 GB of FLUX onto the
card while the chat model that answered a moment earlier (10 GB) is still
resident. Its only preflight was "does CUDA exist"; it never asked how much of
the card was *free* and never gave the chat model back first. Twenty gigabytes
were asked of twelve, the driver paged GPU memory through system RAM for every
process on the machine, and the offload hook then dragged whole components
across that starved bus on every denoising step.

`APPROXIMATE_VRAM_BYTES` was written "to warn" and had no caller — the
seventeenth complete, unreachable piece this repository has found, on the one
path where it could take the whole machine down.

What is pinned, in the order the runtime must do it:

1. **Free memory is read before anything loads**, and compared against the
   provider's own figure — the constant gets its reader, and a test that
   would fail if it went dark again.
2. **The chat model is released first, then the card is re-read.** Loading
   happens after the release, never before it, and never at all if the card
   is still short.
3. **A card that is still held is refused by name.** TabbyAPI has no unload
   route, so the refusal says who is holding what and where to free it,
   rather than falling through to CPU offload on a full card — which is the
   freeze.
4. **Say what will happen before it happens.** "Drawing this unloads
   qwen3-14b first" reaches the stream before the wait, not after.
5. **FLUX is unloaded after the picture.** Eight gigabytes held resident for a
   model used once an hour is the keep-alive mistake in a new tenant.

No GPU, no torch, no model. Every collaborator is a fake that records what was
asked of it and in what order, because the order is the fix.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Dict, List, Optional

import pytest

from artifacts.records import ArtifactRecords
from artifacts.service import ArtifactService
from artifacts.store import ArtifactStore
from imaging.contracts import Availability, GeneratedImage
from runtimes.images.runtime import GENERATE, ImagesRuntime

GB = 1_000_000_000

#: A 1x1 PNG, so the artifact path is exercised rather than mocked.
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000100ffff030000060005"
    "573f2c2c0000000049454e44ae426082"
)


class _Flux:
    """A provider shaped like `FluxProvider`: knows what it needs, loads on
    first use, can be unloaded, and records every one of those events."""

    name = "fake-flux"
    vram_needed_bytes = 8_400_000_000

    def __init__(self) -> None:
        self.events: List[str] = []
        self.loaded = False
        # The real provider serialises sampling on one lock; two requests in
        # flight draw one after the other on one loaded pipeline.
        self._lock = threading.Lock()

    def availability(self):
        return Availability(ok=True)

    def describe(self):
        return "fake-flux"

    def generate(self, request, on_progress=None):
        with self._lock:
            if not self.loaded:
                self.events.append("load")
                self.loaded = True
            self.events.append("draw")
            return [GeneratedImage(png=PIXEL, width=1, height=1, seed=7)]

    def unload(self):
        self.events.append("unload")
        self.loaded = False


class _Card:
    """The graphics card as the runtime sees it: how much is free, who holds
    it, and a release that may or may not get it all back.

    `free_after_release` is what the card reads once the chat model has gone;
    a release that frees nothing leaves it at `free`.
    """

    def __init__(
        self,
        *,
        free: Optional[int],
        resident: Optional[Dict[str, Optional[int]]] = None,
        outcome: Optional[Dict[str, str]] = None,
        free_after_release: Optional[int] = None,
        flux: Optional[_Flux] = None,
    ) -> None:
        self._free = free
        self._resident = resident if resident is not None else {}
        self._outcome = outcome if outcome is not None else {}
        self._free_after = free_after_release
        self._flux = flux
        self.events: List[str] = []

    def free_bytes(self) -> Optional[int]:
        self.events.append("read")
        if self._flux is not None:
            self._flux.events.append("read-free")
        return self._free

    def resident(self):
        return self._resident

    def release(self) -> Dict[str, str]:
        self.events.append("release")
        if self._flux is not None:
            self._flux.events.append("release")
        if self._free_after is not None:
            self._free = self._free_after
        return dict(self._outcome)


@pytest.fixture
def service(tmp_path):
    return ArtifactService(
        ArtifactRecords(str(tmp_path / "artifacts.db")),
        ArtifactStore(tmp_path / "out"),
    )


def _run(runtime, **extra):
    said: List[dict] = []
    payload = {"prompt": "a lighthouse", "steps": 1, "notice_sink": said.append}
    payload.update(extra)
    result = asyncio.run(runtime.execute(GENERATE, payload))
    return result, said


# ====================================================== the card is read first


class TestTheCardIsReadBeforeAnythingLoads:
    def test_a_card_with_room_is_drawn_on_without_a_release(self, service):
        flux = _Flux()
        card = _Card(free=11 * GB, resident={"qwen3-14b-16k:latest": 10 * GB}, flux=flux)
        runtime = ImagesRuntime(service, flux, card=card)

        result, _ = _run(runtime)

        assert result["success"] is True
        assert "release" not in card.events
        assert flux.events[:2] == ["read-free", "load"]

    def test_the_read_happens_before_the_load(self, service):
        """The order, not just the fact. A read after the load is a report
        on the freeze rather than a guard against it."""
        flux = _Flux()
        card = _Card(free=11 * GB, flux=flux)
        runtime = ImagesRuntime(service, flux, card=card)

        _run(runtime)

        assert flux.events.index("read-free") < flux.events.index("load")

    def test_an_unreadable_card_does_not_block(self, service):
        """No NVIDIA driver answers `None`, and `None` is unknown rather than
        empty. Refusing every AMD and Apple machine on the strength of a probe
        that cannot run there would be a wrong number with the sign flipped."""
        flux = _Flux()
        runtime = ImagesRuntime(service, flux, card=_Card(free=None, flux=flux))

        result, _ = _run(runtime)

        assert result["success"] is True
        assert "load" in flux.events

    def test_no_card_at_all_draws_as_before(self, service):
        """Tests and callers that inject nothing keep the old behaviour."""
        flux = _Flux()
        result, _ = _run(ImagesRuntime(service, flux))
        assert result["success"] is True

    def test_a_provider_with_no_figure_is_not_gated(self, service):
        """A cloud provider needs nothing from the card. Gating it on the
        local card's occupancy would refuse the one route that works when the
        card is full."""

        class _Cloud(_Flux):
            vram_needed_bytes = None

        flux = _Cloud()
        card = _Card(free=1 * GB, flux=flux)
        result, _ = _run(ImagesRuntime(service, flux, card=card))

        assert result["success"] is True
        assert "release" not in card.events


# ================================================= release first, then re-read


class TestTheChatModelIsReleasedFirst:
    def test_a_full_card_is_released_and_then_drawn_on(self, service):
        flux = _Flux()
        card = _Card(
            free=1 * GB,
            resident={"qwen3-14b-16k:latest": 10 * GB},
            outcome={"qwen3-14b-16k:latest": "released"},
            free_after_release=11 * GB,
            flux=flux,
        )
        runtime = ImagesRuntime(service, flux, card=card)

        result, _ = _run(runtime)

        assert result["success"] is True
        # Read, release, read again, and only then load. Loading before the
        # release is the freeze; loading without the second read trusts a
        # release that may have freed nothing.
        assert flux.events[:4] == ["read-free", "release", "read-free", "load"]

    def test_the_user_is_told_before_the_wait_what_will_be_unloaded(self, service):
        """"Drawing this unloads qwen3-14b first" — on screen before the
        seconds are spent, naming the model, so the next question's cold
        start is explained before it happens rather than discovered."""
        flux = _Flux()
        card = _Card(
            free=1 * GB,
            resident={"qwen3-14b-16k:latest": 10 * GB},
            outcome={"qwen3-14b-16k:latest": "released"},
            free_after_release=11 * GB,
            flux=flux,
        )
        runtime = ImagesRuntime(service, flux, card=card)

        _, said = _run(runtime)

        assert said, "nothing was said before the release"
        first = said[0]
        assert "qwen3-14b-16k" in first["content"]
        assert first["kind"] == "images"
        # And it was said *before* the release, not as a report on it.
        assert card.events.index("release") >= 1

    def test_a_release_that_frees_nothing_is_not_trusted(self, service):
        """Ollama answered "released" and the card is still full — a second
        server, or a program Zaram knows nothing about. The second read is
        what catches it; without one the load would go ahead on its word."""
        flux = _Flux()
        card = _Card(
            free=1 * GB,
            resident={"qwen3-14b-16k:latest": 10 * GB},
            outcome={"qwen3-14b-16k:latest": "released"},
            free_after_release=1 * GB,
            flux=flux,
        )
        result, _ = _run(ImagesRuntime(service, flux, card=card))

        assert result["success"] is False
        assert "load" not in flux.events


# ======================================================== refused, by name


class TestAHeldCardIsRefusedByName:
    @pytest.fixture
    def tabby(self):
        flux = _Flux()
        card = _Card(
            free=1 * GB,
            resident={"Qwen3.8-27B-exl3-2.20bpw": None},
            outcome={
                "Qwen3.8-27B-exl3-2.20bpw": (
                    "not released: TabbyAPI has no unload route; stop or "
                    "unload it from that app"
                )
            },
            free_after_release=1 * GB,
            flux=flux,
        )
        return flux, card

    def test_nothing_loads(self, service, tabby):
        """The whole fix in one assertion. Loading here is the freeze."""
        flux, card = tabby
        result, _ = _run(ImagesRuntime(service, flux, card=card))

        assert result["success"] is False
        assert "load" not in flux.events
        assert "draw" not in flux.events

    def test_the_refusal_names_the_holder_and_where_to_free_it(self, service, tabby):
        flux, card = tabby
        result, _ = _run(ImagesRuntime(service, flux, card=card))

        assert "Qwen3.8-27B-exl3-2.20bpw" in result["error"]
        assert "TabbyAPI" in result["error"]
        assert result["remedy"]
        # Named so the dispatcher refuses rather than falling back to prose —
        # a text model describing a picture it never drew is rule 9's failure.
        assert result["unavailable"] is True

    def test_the_refusal_reaches_the_stream_as_a_notice(self, service, tabby):
        flux, card = tabby
        _, said = _run(ImagesRuntime(service, flux, card=card))

        refusal = [n for n in said if "Qwen3.8-27B" in n["content"]]
        assert refusal, f"the refusal was not said on the stream: {said}"
        assert refusal[-1]["kind"] == "images"
        assert refusal[-1]["action"] == "settings"

    def test_a_model_on_the_cpu_is_neither_named_nor_released(self, service):
        """Measured on the first live run: Ollama reported bge-m3 resident
        with `size_vram: 0` — loaded, on the CPU — and the runtime announced
        it would unload it, did, and gained nothing on the card while recall
        lost its embedder. Zero bytes on the card is known, not unknown, and
        a release that frees nothing is not attempted."""
        flux = _Flux()
        card = _Card(free=1 * GB, resident={"bge-m3:latest": 0}, outcome={}, flux=flux)
        result, said = _run(ImagesRuntime(service, flux, card=card))

        assert result["success"] is False
        assert "release" not in card.events
        assert not any("bge-m3" in n["content"] and "unloads" in n["content"] for n in said)

    def test_a_card_held_by_something_zaram_cannot_see_is_still_refused(self, service):
        """Nothing Zaram's servers hold, the card is full anyway — a game, an
        editor, a render. There is no name to give, so it says that, and it
        still does not load."""
        flux = _Flux()
        card = _Card(free=1 * GB, resident={}, outcome={}, flux=flux)
        result, _ = _run(ImagesRuntime(service, flux, card=card))

        assert result["success"] is False
        assert "load" not in flux.events
        assert "else" in result["error"].lower() or "another" in result["error"].lower()

    def test_nothing_is_written(self, service, tabby, tmp_path):
        flux, card = tabby
        _run(ImagesRuntime(service, flux, card=card))
        assert list((tmp_path / "out").iterdir()) == []


# =================================================== the card is given back


class TestFluxIsUnloadedAfterThePicture:
    def test_unload_follows_the_draw(self, service):
        flux = _Flux()
        runtime = ImagesRuntime(service, flux, card=_Card(free=11 * GB, flux=flux))

        result, _ = _run(runtime)

        assert result["success"] is True
        assert flux.events[-1] == "unload"
        assert flux.loaded is False

    def test_unload_follows_a_draw_with_no_card_injected(self, service):
        """The unload is about the model, not about the probe."""
        flux = _Flux()
        _run(ImagesRuntime(service, flux))
        assert flux.events[-1] == "unload"

    def test_a_queued_request_keeps_the_model_loaded_between_them(self, service):
        """Two pictures asked for together are drawn on one load. Unloading
        between them would make the second as slow as the first."""
        flux = _Flux()
        runtime = ImagesRuntime(service, flux, card=_Card(free=11 * GB, flux=flux))

        async def two():
            return await asyncio.gather(
                runtime.execute(GENERATE, {"prompt": "a", "steps": 1}),
                runtime.execute(GENERATE, {"prompt": "b", "steps": 1}),
            )

        first, second = asyncio.run(two())

        assert first["success"] and second["success"]
        assert flux.events.count("load") == 1
        assert flux.events.count("unload") == 1
        assert flux.events[-1] == "unload"


# ========================================== the constant has a reader now


class TestTheConstantIsRead:
    def test_flux_reports_the_constant_as_what_it_needs(self, monkeypatch):
        """`APPROXIMATE_VRAM_BYTES` was written "to warn" and nothing read it.
        This is the reader, and the assertion that it stays one."""
        from imaging import local_flux

        monkeypatch.setattr(local_flux, "_cuda_available", lambda: True)
        assert local_flux.FluxProvider().vram_needed_bytes == local_flux.APPROXIMATE_VRAM_BYTES

    def test_on_a_cpu_it_needs_nothing_from_the_card(self, monkeypatch):
        """A CPU draw is tens of minutes and its own warning, but it does
        not touch the card — releasing the chat model for it would cost a
        cold start for nothing."""
        from imaging import local_flux

        monkeypatch.setattr(local_flux, "_cuda_available", lambda: False)
        assert local_flux.FluxProvider().vram_needed_bytes is None

    def test_the_runtime_compares_free_memory_against_the_providers_figure(self, service):
        """One byte short refuses; exactly enough draws. The comparison is
        against the provider's number and nothing else."""

        class _Needs(_Flux):
            vram_needed_bytes = 5 * GB

        short = _Needs()
        result, _ = _run(
            ImagesRuntime(service, short, card=_Card(free=5 * GB - 1, resident={}, flux=short))
        )
        assert result["success"] is False
        assert "load" not in short.events

        enough = _Needs()
        result, _ = _run(
            ImagesRuntime(service, enough, card=_Card(free=5 * GB, flux=enough))
        )
        assert result["success"] is True


# ======================================================= what /health says


class TestHealthSaysWhatTheCardNeeds:
    def test_health_reports_the_figure_and_whether_it_is_loaded(self, service):
        flux = _Flux()
        runtime = ImagesRuntime(service, flux, card=_Card(free=11 * GB, flux=flux))

        before = asyncio.run(runtime.health_check())
        assert before["vram_needed_bytes"] == flux.vram_needed_bytes
        assert before["loaded"] is False

        _run(runtime)

        after = asyncio.run(runtime.health_check())
        # Unloaded after the picture, and health says so rather than
        # reporting the residency the old comment promised it never would.
        assert after["loaded"] is False
        assert after["last_preflight"]["free_bytes"] == 11 * GB
        assert after["last_preflight"]["fits"] is True

    def test_a_refusal_is_visible_in_health_afterwards(self, service):
        flux = _Flux()
        card = _Card(
            free=1 * GB,
            resident={"Qwen3.8-27B-exl3-2.20bpw": None},
            outcome={"Qwen3.8-27B-exl3-2.20bpw": "not released: TabbyAPI has no unload route"},
            flux=flux,
        )
        runtime = ImagesRuntime(service, flux, card=card)
        _run(runtime)

        health = asyncio.run(runtime.health_check())
        assert health["last_preflight"]["fits"] is False
        assert "Qwen3.8-27B-exl3-2.20bpw" in health["last_preflight"]["held_by"]


# ================================================ a full card draws elsewhere


class _Routed(_Flux):
    """Shaped like `RoutedImageProvider` with a connected cloud provider
    behind the local one: the runtime asks it who draws instead."""

    def __init__(self, cloud) -> None:
        super().__init__()
        self._cloud = cloud

    def instead_of_the_card(self):
        return self._cloud


class _Cloud:
    name = "NVIDIA NIM"

    def __init__(self) -> None:
        self.drew = 0

    def generate(self, request, on_progress=None):
        self.drew += 1
        return [GeneratedImage(png=PIXEL, width=1, height=1, seed=3)]


class TestAFullCardDrawsElsewhere:
    """Seen on screen 14 September 2026: three notices for one picture — the
    unload announcement, then the refusal naming TabbyAPI, then a remedy
    pointing at Settings — while a connected NVIDIA key sat unused. A full
    card is a reason to draw elsewhere, not a reason to stop."""

    @pytest.fixture
    def held(self):
        cloud = _Cloud()
        flux = _Routed(cloud)
        card = _Card(
            free=1 * GB,
            resident={"Qwen3.8-27B-exl3-2.20bpw": None},
            outcome={"Qwen3.8-27B-exl3-2.20bpw": "not released: TabbyAPI has no unload route"},
            free_after_release=1 * GB,
            flux=flux,
        )
        return flux, cloud, card

    def test_the_cloud_provider_draws_and_nothing_loads_here(self, service, held):
        flux, cloud, card = held
        result, _ = _run(ImagesRuntime(service, flux, card=card))

        assert result["success"] is True
        assert cloud.drew == 1
        assert "load" not in flux.events and "draw" not in flux.events

    def test_one_line_says_so_and_the_refusal_is_not_spoken(self, service, held):
        flux, cloud, card = held
        _, said = _run(ImagesRuntime(service, flux, card=card))

        contents = [n["content"] for n in said]
        assert any("NVIDIA NIM is drawing this one" in c for c in contents), contents
        assert not any(n["action"] == "settings" for n in said), "the refusal was said as well"
        assert not any("cannot unload" in c for c in contents), contents

    def test_without_a_cloud_provider_the_refusal_stands(self, service):
        flux = _Routed(None)
        card = _Card(
            free=1 * GB,
            resident={"Qwen3.8-27B-exl3-2.20bpw": None},
            outcome={"Qwen3.8-27B-exl3-2.20bpw": "not released: TabbyAPI has no unload route"},
            free_after_release=1 * GB,
            flux=flux,
        )
        result, said = _run(ImagesRuntime(service, flux, card=card))

        assert result["success"] is False
        assert any(n["action"] == "settings" for n in said)

    def test_a_releasable_chat_model_is_left_warm_when_the_cloud_can_draw(self, service):
        """Evicting the chat model to draw one picture costs its reload twice;
        with a cloud provider connected the card is not touched."""
        cloud = _Cloud()
        flux = _Routed(cloud)
        card = _Card(
            free=1 * GB,
            resident={"qwen3-14b-16k:latest": 10 * GB},
            outcome={"qwen3-14b-16k:latest": "released"},
            free_after_release=11 * GB,
            flux=flux,
        )
        result, said = _run(ImagesRuntime(service, flux, card=card))

        assert result["success"] is True
        assert cloud.drew == 1
        assert "release" not in card.events, "the chat model was unloaded for a picture the cloud drew"
        assert "load" not in flux.events
        assert not any("unloads" in n["content"] for n in said), said
        assert sum("NVIDIA NIM is drawing" in n["content"] for n in said) == 1
