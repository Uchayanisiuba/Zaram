"""The full three-minute wait belongs to the last provider, not the first.

`TIMEOUT_SECONDS` is 180 because free tiers queue, and that is right for the
last provider standing: giving up at a minute when nothing else can draw costs
the picture outright.

It is wrong for the first of several. Measured 28 September 2026 — NVIDIA NIM
was connected, queued, and returned nothing; the person waited **181 seconds**
for *"The read operation timed out"* while Together sat unasked with a standing
free endpoint. Handing the picture on fixes the outcome and not the wait: they
would now get a picture at 185 seconds, which is not a product anybody
demonstrates.

So the wait is bounded by what being wrong costs. Another provider available
means the first attempt is cheap to abandon.
"""

from __future__ import annotations

import pytest

from imaging import cloud
from imaging.cloud import FIRST_TIMEOUT_SECONDS, TIMEOUT_SECONDS, RoutedImageProvider
from imaging.contracts import AVAILABLE, Availability, GeneratedImage, ImageRequest


class _Recording:
    """Records the deadline it was given, then fails or draws."""

    timeout = None

    def __init__(self, name: str, *, fails: bool = False) -> None:
        self.name = name
        self._fails = fails
        self.seen: list = []

    def availability(self) -> Availability:
        return AVAILABLE

    def capabilities(self):
        from imaging.contracts import TEXT_TO_IMAGE_ONLY

        return TEXT_TO_IMAGE_ONLY

    def generate(self, request, on_progress=None):
        self.seen.append(self.timeout)
        if self._fails:
            raise TimeoutError("The read operation timed out")
        return [GeneratedImage(png=b"\x89PNG", seed=1, width=512, height=512)]


def _request() -> ImageRequest:
    return ImageRequest(prompt="a blue gorilla", width=512, height=512, steps=4)


def test_the_first_of_several_is_given_the_shorter_wait():
    first = _Recording("NIM", fails=True)
    second = _Recording("Together")
    RoutedImageProvider(None, [first, second], prefer=lambda: "cloud").generate(_request())

    assert first.seen == [FIRST_TIMEOUT_SECONDS]


def test_the_last_one_standing_is_given_the_full_budget():
    """`None` means the module constant — there is nowhere left to hand it to,
    so a queued free tier is worth waiting out."""
    first = _Recording("NIM", fails=True)
    second = _Recording("Together")
    RoutedImageProvider(None, [first, second], prefer=lambda: "cloud").generate(_request())

    assert second.seen == [None]


def test_the_only_provider_is_the_last_one():
    only = _Recording("NIM")
    RoutedImageProvider(None, [only], prefer=lambda: "cloud").generate(_request())
    assert only.seen == [None]


def test_the_deadline_never_outlives_the_request():
    """Providers are module-level singletons shared across requests.

    A deadline left on one would silently shorten the next request's wait, and
    the failure that produced would be a timeout nobody could account for.
    """
    first = _Recording("NIM", fails=True)
    second = _Recording("Together")
    RoutedImageProvider(None, [first, second], prefer=lambda: "cloud").generate(_request())

    assert first.timeout is None
    assert second.timeout is None


def test_the_short_wait_is_a_fair_attempt_and_not_a_formality():
    """A bound low enough to fail a healthy provider would make the hand-on a
    round trip tax on every picture."""
    assert 30.0 <= FIRST_TIMEOUT_SECONDS < TIMEOUT_SECONDS


def test_the_transport_still_defaults_to_the_full_budget():
    """Nothing that does not pass a deadline gets a shorter one by accident."""
    seen = {}

    class _Gate:
        def request(self, url, **kw):
            seen.update(kw)
            return b"{}"

    import core.egress as egress

    original = egress.get_gate
    egress.get_gate = lambda: _Gate()
    try:
        cloud._send_json("https://example.invalid", {}, {})
    finally:
        egress.get_gate = original

    assert seen["timeout"] == TIMEOUT_SECONDS
