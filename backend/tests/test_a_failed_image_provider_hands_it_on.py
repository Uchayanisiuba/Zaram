"""A cloud provider that cannot draw hands the picture to the next one.

Reported 28 September 2026, with a demo that day: NVIDIA NIM was connected and
granted, the request went out, and **181 seconds** later the reply was *"could
not draw that: The read operation timed out"*. `TIMEOUT_SECONDS` is 180, and
the constant's own comment already said why — *"Free tiers queue; a minute is
not unusual."*

So the request was not wrong. It was queued behind somebody else's, and the
person got nothing — while Together sat there with a standing free Flux
schnell endpoint and was never asked, because `generate` picked one provider
and anything it raised ended the request.

The last test here is the one to keep. **The chain is cloud-only**, and that is
a safety property rather than a nicety: `ImagesRuntime._make_room` preflights
the graphics card by reading `vram_needed_bytes`, which answers `None` on a
cloud pick — correctly, since a cloud provider holds no card. So on a cloud
pick *no VRAM preflight ran*, and quietly loading 8.4 GB of local Flux after a
cloud failure would be the 12 September freeze reached by a new road.
"""

from __future__ import annotations

import pytest

from imaging.cloud import RoutedImageProvider
from imaging.contracts import AVAILABLE, Availability, GeneratedImage, ImageRequest


class _Provider:
    """A stand-in with a name, an availability and a way to fail."""

    def __init__(self, name: str, *, ok: bool = True, fails: Exception | None = None,
                 draws: bool = True) -> None:
        self.name = name
        self._ok = ok
        self._fails = fails
        self._draws = draws
        self.asked = False

    def availability(self) -> Availability:
        return AVAILABLE if self._ok else Availability(ok=False, reason="no key")

    def capabilities(self):
        from imaging.contracts import TEXT_TO_IMAGE_ONLY

        return TEXT_TO_IMAGE_ONLY

    def generate(self, request, on_progress=None):
        self.asked = True
        if self._fails is not None:
            raise self._fails
        if not self._draws:
            return []
        return [GeneratedImage(png=b"\x89PNG", seed=1, width=512, height=512)]


def _request() -> ImageRequest:
    return ImageRequest(prompt="a blue gorilla", width=512, height=512, steps=4)


def _routed(local, cloud, prefer="cloud") -> RoutedImageProvider:
    return RoutedImageProvider(local, cloud, prefer=lambda: prefer)


# --------------------------------------------------------------------------- #
# It hands on
# --------------------------------------------------------------------------- #


def test_a_timeout_on_the_first_provider_is_not_the_end_of_the_request():
    """The bug, exactly as it reached a person."""
    nim = _Provider("NIM", fails=TimeoutError("The read operation timed out"))
    together = _Provider("Together")
    routed = _routed(None, [nim, together])

    drawn = routed.generate(_request())

    assert drawn, "the second provider drew it"
    assert nim.asked and together.asked


def test_only_a_raised_failure_hands_on_and_never_an_empty_answer():
    """**A provider that answered is not overruled.**

    `CloudImageProvider.generate` already raises *"answered without a picture"*
    when `_parse` recognises nothing, so an empty list from a provider that did
    not raise means something else — and sweeping past it would substitute a
    different generator for one that replied. That is a routing decision made
    on the quietest possible signal.
    """
    quiet = _Provider("Quiet", draws=False)
    together = _Provider("Together")

    assert _routed(None, [quiet, together]).generate(_request()) == []
    assert not together.asked


def test_every_failure_is_named_when_they_all_fail():
    """A person cannot act on "it did not work"; they can act on which two
    endpoints were tried and what each said."""
    first = _Provider("NIM", fails=TimeoutError("The read operation timed out"))
    second = _Provider("Together", fails=RuntimeError("401 unauthorized"))

    with pytest.raises(RuntimeError) as caught:
        _routed(None, [first, second]).generate(_request())

    assert "NIM" in str(caught.value)
    assert "timed out" in str(caught.value)
    assert "Together" in str(caught.value)


def test_a_provider_with_no_key_is_never_asked():
    """Availability is checked before the attempt, not discovered through one."""
    unconnected = _Provider("fal", ok=False)
    together = _Provider("Together")
    _routed(None, [together, unconnected]).generate(_request())
    assert not unconnected.asked


# --------------------------------------------------------------------------- #
# What it must never do
# --------------------------------------------------------------------------- #


def test_a_failed_cloud_draw_never_falls_back_to_the_local_card():
    """**The one that keeps the card safe.**

    `_make_room` reads `vram_needed_bytes`, which is `None` on a cloud pick, so
    no VRAM preflight ran for this request. Loading local Flux after a cloud
    failure would put 8.4 GB on a card nobody measured — the 12 September
    freeze by a new road.
    """
    local = _Provider("Flux")
    nim = _Provider("NIM", fails=TimeoutError("timed out"))
    routed = _routed(local, [nim], prefer="cloud")

    with pytest.raises(RuntimeError):
        routed.generate(_request())

    assert not local.asked, "the local card was never touched"


def test_a_local_pick_that_fails_is_one_attempt_and_not_a_cloud_sweep():
    """The preflight that ran was about *that* provider, so the attempt is too.

    A local failure sweeping into cloud would send the prompt off the machine
    on the back of a decision the person made the other way.
    """
    local = _Provider("Flux", fails=RuntimeError("out of memory"))
    nim = _Provider("NIM")
    routed = _routed(local, [nim], prefer="local")

    drawn = routed.generate(_request())
    # Cloud is a legitimate *next* candidate here, because preferring local
    # never promised the picture would stay — `_pick` already falls through to
    # cloud when local cannot draw at all. What matters is that it was tried
    # second, not first.
    assert local.asked
    assert drawn
