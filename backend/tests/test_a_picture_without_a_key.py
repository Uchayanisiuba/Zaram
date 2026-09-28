"""The rung that answers on a machine with nothing connected.

Every image provider needed a key, and the free ones stopped covering the case:
NVIDIA NIM queues past three minutes on the maintainer's machine — measured, 28
September 2026, three requests at 181 seconds each — and Together now asks for
a card. So someone who installed Zaram, added a local chat model and asked for
a picture got a refusal and a shopping list, on a product whose first promise
is that it works with what you already have.

These pin the four things that make a keyless rung safe rather than merely
convenient: it still asks for the grant, it is still last, the prompt is still
escaped into the URL correctly, and the bytes are still read as an image rather
than as JSON.
"""

from __future__ import annotations

import pytest

from imaging import cloud
from imaging.cloud import CLOUD_PROVIDERS, PollinationsImages
from imaging.contracts import ImageRequest


class _Gate:
    """Records the request instead of sending it, and hands back a PNG."""

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.seen: dict = {}

    def request(self, url, **kw):
        self.seen = {"url": url, **kw}
        return self.body


def _png(width: int = 512, height: int = 512) -> bytes:
    """A PNG header `_image` can read a size out of, and nothing more."""
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x06\x00\x00\x00"
    )


@pytest.fixture
def gate(monkeypatch):
    import core.egress as egress

    held = _Gate(_png())
    monkeypatch.setattr(egress, "get_gate", lambda: held)
    return held


# --------------------------------------------------------------------------- #
# It draws
# --------------------------------------------------------------------------- #


def test_it_needs_no_key_and_returns_a_picture(gate):
    drawn = PollinationsImages().generate(ImageRequest(prompt="a blue gorilla", seed=7))
    assert len(drawn) == 1
    assert drawn[0].width == 512 and drawn[0].height == 512


def test_the_prompt_is_escaped_into_the_path(gate):
    """A slash in a prompt would otherwise become another path segment, and
    the picture would be drawn from a truncated sentence."""
    PollinationsImages().generate(ImageRequest(prompt="a cat / dog hybrid", seed=1))
    assert "a%20cat%20%2F%20dog%20hybrid" in gate.seen["url"]
    assert "/dog" not in gate.seen["url"].split("?")[0].removeprefix(
        "https://image.pollinations.ai/prompt/"
    )


def test_it_travels_as_a_gated_image_egress(gate):
    """Rule 3 and rule 7j are untouched by a provider having no key: the
    prompt still leaves through the gate, as an image, and is still logged."""
    from core.egress import DataClass

    PollinationsImages().generate(ImageRequest(prompt="x"))
    assert gate.seen["method"] == "GET"
    assert gate.seen["data_class"] is DataClass.IMAGE
    assert gate.seen["source"] == cloud.SOURCE


def test_an_empty_answer_is_a_failure_and_not_a_blank_picture(monkeypatch):
    """Rule 9 in the one medium where nothing on screen shows the omission."""
    import core.egress as egress

    monkeypatch.setattr(egress, "get_gate", lambda: _Gate(b""))
    with pytest.raises(RuntimeError):
        PollinationsImages().generate(ImageRequest(prompt="x"))


# --------------------------------------------------------------------------- #
# What it must not become
# --------------------------------------------------------------------------- #


def test_no_key_is_not_no_permission(monkeypatch):
    """**The one that keeps rule 5 intact.**

    Having nothing to configure must not mean having nothing to consent to. A
    host nobody allowed is still denied, exactly as for a provider with a key.
    """
    from core.egress import DataClass, Mode

    class _Denying:
        class policy:
            @staticmethod
            def decide(host, data_class):
                assert data_class is DataClass.IMAGE
                return type("D", (), {"mode": Mode.DENY, "reason": "not allowed"})()

    import core.egress as egress

    monkeypatch.setattr(egress, "get_gate", lambda: _Denying())
    assert not PollinationsImages().availability().ok


def test_it_is_last_so_a_connected_provider_always_wins():
    """Anyone with a key gets the provider they chose or paid for. This is what
    a machine with nothing connected falls to — never what it starts from."""
    assert isinstance(CLOUD_PROVIDERS[-1], PollinationsImages)
    assert len(CLOUD_PROVIDERS) > 1


def test_the_disclosure_rides_with_the_name():
    """The prompt goes in the URL, which is the part of a request most likely
    to be written down in between. Said where the reply can show it, not left
    on a settings page."""
    described = PollinationsImages().describe()
    assert "no key" in described
    assert "URL" in described
    assert "watermark" in described


def test_the_paid_parameter_is_never_asked_for(monkeypatch):
    """**`nologo` is paid, and asking for it fails the draw.**

    Measured 28 September 2026: the identical request returns **402 Payment
    Required** with `nologo=true` and **200** without it. So a parameter that
    looks like a nicety is the difference between a picture and nothing, on
    the one rung whose entire job is to answer when nothing is configured.
    """
    import core.egress as egress
    held = _Gate(_png())
    monkeypatch.setattr(egress, "get_gate", lambda: held)
    PollinationsImages().generate(ImageRequest(prompt="x"))
    assert "nologo" not in held.seen["url"]
