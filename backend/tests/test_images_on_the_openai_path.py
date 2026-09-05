"""An image attached while an OpenAI-compatible model is selected.

Queue item 4's remaining half. `OpenAICompatibleEngine.stream_response` took an
``images`` argument and `_body` did not have one, so nothing joined them: the
picture was accepted, discarded, and the model answered about an image it had
never seen.

That is rule 9 — *"generation must fail rather than invent"* — in a new medium,
and it is the silent version, which is the worse one. The reply is fluent,
nothing on screen says the image went nowhere, and the only way to notice is to
know the answer is wrong. Compare the local path, which has carried images on
whichever model was routed since 28 August and was measured doing it.

**The format has to be read from the picture.** By the time an image reaches an
engine its filename is gone — `main.py` passes ``[a.data for a in attached ...]``,
base64 and nothing else, while `Attachment.suffix` stays behind — and the
`image_url` content part needs a media type. So the type comes from the file's
own signature, which is a measurement. Defaulting to `image/png` because most
screenshots are PNGs would be a guess, and this file asserts that an image
whose format cannot be established is **refused rather than labelled**.
"""

from __future__ import annotations

import base64

import pytest

from runtimes.models.engines.base_engine import ERROR_PREFIX
from runtimes.models.engines.openai_compatible_engine import OpenAICompatibleEngine

#: Real leading bytes for each format, followed by filler. Only the signature
#: is read, so the filler stands in for the rest of a picture.
HEADS = {
    "image/png": bytes.fromhex("89504e470d0a1a0a") + b"\x00\x00\x00\rIHDR",
    "image/jpeg": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01",
    "image/gif": b"GIF89a\x10\x00\x10\x00\x80\x00",
    "image/bmp": b"BM\x8a\x00\x00\x00\x00\x00\x00\x00",
    "image/webp": b"RIFF\x24\x00\x00\x00WEBPVP8 ",
}


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


@pytest.fixture
def engine():
    """Pointed at loopback. Nothing here sends; `_body` is a pure builder.

    Loopback rather than a cloud host on purpose: this is the engine that
    serves TabbyAPI as well as a cloud provider, and the local case is the one
    that has a vision-capable model behind it on the maintainer's machine.
    """
    return OpenAICompatibleEngine(
        base_url="http://127.0.0.1:1234",
        api_key="",
        default_model="a-local-model",
        source="chat",
    )


class TestTheImageActuallyTravels:
    def test_an_attached_image_reaches_the_body(self, engine):
        """The defect itself. This was dropped between two signatures."""
        body = engine._body("what is in this?", "", None, [b64(HEADS["image/png"])])

        content = body["messages"][-1]["content"]
        assert isinstance(content, list), (
            "the image was dropped: the user message is still a plain string, "
            "so the request went without the picture and the model answered "
            "about something it never saw"
        )
        kinds = [part["type"] for part in content]
        assert kinds == ["text", "image_url"]
        assert content[0]["text"] == "what is in this?"

    def test_several_images_all_travel(self, engine):
        body = engine._body(
            "compare these",
            "",
            None,
            [b64(HEADS["image/png"]), b64(HEADS["image/jpeg"])],
        )
        content = body["messages"][-1]["content"]
        assert [part["type"] for part in content] == ["text", "image_url", "image_url"]

    def test_an_ordinary_message_is_still_a_plain_string(self, engine):
        """The guard against fixing this by changing every request.

        A one-element content array is valid OpenAI and is *not* accepted by
        every server that speaks the dialect — several older ones take a string
        only. Trading a fixed bug for a new one on endpoints nobody here can
        test is not a trade worth making, so the array form appears only when
        there is something that needs it.
        """
        body = engine._body("hello", "you are Zaram", None, None)

        assert body["messages"][-1]["content"] == "hello"
        assert body["messages"][0]["content"] == "you are Zaram"

    def test_an_empty_image_list_is_not_an_image(self, engine):
        assert engine._body("hello", "", None, []) == engine._body("hello", "", None, None)
        assert engine._body("hello", "", None, ["", "   "])["messages"][-1]["content"] == "hello"

    def test_the_sampling_defaults_still_ride_along(self):
        """Images must not displace `LOCAL_SAMPLING`.

        The local path supplies temperature and top-p deliberately — TabbyAPI's
        own factory default is unconstrained sampling from the raw
        distribution — and a body built down a different branch would quietly
        stop carrying them.
        """
        engine = OpenAICompatibleEngine(
            base_url="http://127.0.0.1:1234",
            api_key="",
            default_model="a-local-model",
            source="chat",
            sampling={"temperature": 0.6, "top_p": 0.95},
        )

        body = engine._body("look", "", None, [b64(HEADS["image/png"])])

        assert body["temperature"] == 0.6
        assert body["top_p"] == 0.95


class TestTheFormatIsMeasuredNotGuessed:
    @pytest.mark.parametrize("media_type", sorted(HEADS))
    def test_each_format_is_named_from_its_own_signature(self, engine, media_type):
        body = engine._body("look", "", None, [b64(HEADS[media_type])])

        url = body["messages"][-1]["content"][1]["image_url"]["url"]
        assert url.startswith(f"data:{media_type};base64,")

    def test_a_ready_made_data_uri_is_left_alone(self, engine):
        """A caller that knows the type has better information than a
        signature does, and re-encoding it would be an inference overruling a
        fact."""
        given = "data:image/heic;base64,AAAA"
        body = engine._body("look", "", None, [given])

        assert body["messages"][-1]["content"][1]["image_url"]["url"] == given

    def test_an_unidentifiable_image_is_refused_rather_than_labelled(self, engine):
        """Refusing is the point.

        The alternative is to call it `image/png` and send it anyway: the
        request goes, the provider rejects or misreads it, and the failure
        surfaces as something unrelated to the actual cause.
        """
        with pytest.raises(ValueError) as refusal:
            engine._body("look", "", None, [b64(b"not an image at all, just text")])

        assert "could not tell what kind of image" in str(refusal.value)

    def test_something_that_is_not_base64_is_refused(self, engine):
        with pytest.raises(ValueError):
            engine._body("look", "", None, ["!!!! not base64 !!!!"])


class TestTheRefusalReachesTheUser:
    def test_it_is_reported_in_band_and_nothing_is_sent(self, engine, monkeypatch):
        """A refusal is an answer, not a crash — and the socket never opens.

        Patched at `urlopen` inside the gate rather than on the engine, which
        is the same reasoning `test_cloud_generation_invariant.py` records: it
        proves *no request happened*, whatever route the code took to not make
        one.
        """
        def fail(request, **kwargs):
            raise AssertionError("an unreadable image was sent anyway")

        monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", fail)

        chunks = list(
            engine.stream_response("look at this", "", None, [b64(b"plain text, not a picture")])
        )

        assert len(chunks) == 1
        assert chunks[0].startswith(ERROR_PREFIX)

    def test_it_does_not_read_as_a_network_failure(self, engine, monkeypatch):
        """The general handler below it says "could not reach", which would
        send the user looking at their connection for a problem that is in the
        file they attached."""
        monkeypatch.setattr(
            "core.egress.gate.urllib.request.urlopen",
            lambda request, **kwargs: (_ for _ in ()).throw(AssertionError("sent")),
        )

        message = "".join(
            engine.stream_response("look", "", None, [b64(b"plain text, not a picture")])
        )

        assert "could not reach" not in message.lower()
        assert "image" in message.lower()
