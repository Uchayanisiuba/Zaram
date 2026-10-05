"""Drawing evicts the chat model, and now brings it back.

The first half of the swap shipped on 12 September: read the card, release the
chat model, refuse by name if the card is still held, unload FLUX afterwards.
The return trip was left to the next question, which then paid the whole reload
-- 106 s measured for the maintainer's 26B -- *after* they pressed Enter. The
ask, 4 October: "release the chat model's hold on the card, load the image
model, and switch back when the questions stop being about pictures."

What is pinned:

* It comes back **only if drawing evicted it.** A card with room never lost the
  chat model, and warming it again is work for nothing.
* **It is said**, naming what is coming back, so the wait is something the
  person was told about rather than something that happened to them.
* **It is an optimisation and never a failure.** A reload that raises or is
  refused must not turn a saved picture into an error.
* **It only reloads what the server said it let go of.** A model that could not
  be unloaded never left.
"""

from __future__ import annotations

import asyncio
from typing import List

import pytest

from runtimes.images.runtime import GENERATE, ImagesRuntime
from tests.test_drawing_never_asks_the_card_for_memory_it_does_not_have import (
    GB,
    _Card,
    _Flux,
    service,  # noqa: F401 - fixture
)


class _Restore:
    def __init__(self, raises: bool = False):
        self.calls = 0
        self.raises = raises

    async def __call__(self):
        self.calls += 1
        if self.raises:
            raise RuntimeError("the card is full again")
        return True


def _run(runtime, **extra):
    """Run one request, then let the background reload finish.

    `asyncio.run` closes its loop the moment `execute` returns, which would
    cancel a fire-and-forget reload before it ran -- so the tasks the runtime
    is holding are awaited inside the same loop.
    """
    said: List[dict] = []

    async def go():
        payload = {"prompt": "a lighthouse", "steps": 1, "notice_sink": said.append}
        payload.update(extra)
        result = await runtime.execute(GENERATE, payload)
        if runtime._restoring:
            await asyncio.gather(*list(runtime._restoring), return_exceptions=True)
        return result

    return asyncio.run(go()), said


def _evicting_card(flux):
    return _Card(
        free=1 * GB,
        resident={"qwen3-14b-16k:latest": 10 * GB},
        outcome={"qwen3-14b-16k:latest": "released by Ollama"},
        free_after_release=11 * GB,
        flux=flux,
    )


class TestItComesBack:
    def test_the_chat_model_is_reloaded_after_the_picture(self, service):
        flux, restore = _Flux(), _Restore()
        runtime = ImagesRuntime(service, flux, card=_evicting_card(flux), restore=restore)

        result, _ = _run(runtime)

        assert result["success"] is True
        assert restore.calls == 1

    def test_it_is_reloaded_after_flux_has_gone_not_before(self, service):
        """The order is the whole point: two models on one card is the freeze."""
        flux = _Flux()
        order: List[str] = []

        async def restore():
            order.append("restore")
            order.append("flux-loaded" if flux.loaded else "flux-gone")

        runtime = ImagesRuntime(service, flux, card=_evicting_card(flux), restore=restore)
        _run(runtime)

        assert order == ["restore", "flux-gone"]

    def test_the_person_is_told_what_is_coming_back(self, service):
        flux = _Flux()
        runtime = ImagesRuntime(service, flux, card=_evicting_card(flux), restore=_Restore())

        _, said = _run(runtime)

        returning = [n["content"] for n in said if "back onto the card" in n["content"]]
        assert len(returning) == 1
        assert "qwen3-14b-16k" in returning[0]


class TestItOnlyComesBackWhenItLeft:
    def test_a_card_with_room_never_lost_it(self, service):
        flux, restore = _Flux(), _Restore()
        card = _Card(free=11 * GB, resident={"qwen3-14b-16k:latest": 10 * GB}, flux=flux)
        runtime = ImagesRuntime(service, flux, card=card, restore=restore)

        _run(runtime)

        assert restore.calls == 0

    def test_a_model_that_could_not_be_unloaded_is_not_reloaded(self, service):
        """The server said it could not let go, so it never left -- and the
        draw is refused anyway, so nothing here has a picture to wait for."""
        flux, restore = _Flux(), _Restore()
        card = _Card(
            free=1 * GB,
            resident={"Qwen3.8-27B": 10 * GB},
            outcome={"Qwen3.8-27B": "held by TabbyAPI, which has no unload route"},
            flux=flux,
        )
        runtime = ImagesRuntime(service, flux, card=card, restore=restore)

        _run(runtime)

        assert restore.calls == 0

    def test_no_restore_wired_means_the_old_behaviour(self, service):
        flux = _Flux()
        runtime = ImagesRuntime(service, flux, card=_evicting_card(flux))
        result, said = _run(runtime)
        assert result["success"] is True
        assert not any("back onto the card" in n["content"] for n in said)


class TestItIsAnOptimisationNotAFailure:
    def test_a_reload_that_raises_does_not_spoil_the_picture(self, service):
        flux = _Flux()
        runtime = ImagesRuntime(
            service, flux, card=_evicting_card(flux), restore=_Restore(raises=True)
        )

        result, _ = _run(runtime)

        assert result["success"] is True
        assert result["artifact"]

    def test_the_card_is_asked_once_for_pictures_asked_for_together(self, service):
        flux, restore = _Flux(), _Restore()
        runtime = ImagesRuntime(service, flux, card=_evicting_card(flux), restore=restore)

        async def two():
            a = runtime.execute(GENERATE, {"prompt": "one", "steps": 1})
            b = runtime.execute(GENERATE, {"prompt": "two", "steps": 1})
            await asyncio.gather(a, b)
            if runtime._restoring:
                await asyncio.gather(*list(runtime._restoring), return_exceptions=True)

        asyncio.run(two())

        assert restore.calls <= 1


def test_it_is_wired_at_boot():
    """A complete, tested, unreachable subsystem is this repository's most
    common defect. The bootstrapper must hand the runtime a way back."""
    import inspect

    from core import bootstrapper

    source = inspect.getsource(bootstrapper)
    assert "restore=bring_the_chat_model_back" in source
    assert "warm_local_model" in source
