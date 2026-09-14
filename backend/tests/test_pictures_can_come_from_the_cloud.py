"""Pictures from a provider the user connected — with their key, through the gate.

Three contracts, in the order a person meets them.

**No key, no provider.** A cloud image provider is available exactly when the
connection the user made in Settings holds a key. Nothing here asks for a
second credential (rule 1).

**A picture is its own consent.** The key grants ``prompt`` to the host and
nothing more (rule 7j). Until the person allows ``image`` to that host the
provider refuses *before* sending, and the refusal names the missing grant
and where to give it — a sentence about the cargo, not the address.

**Every byte goes through the gate, as an image.** With the grant, the
request is sent by ``EgressGate.request`` with ``DataClass.IMAGE`` and lands
in the log; there is no second HTTP path. The three providers' response
shapes are parsed to one ``GeneratedImage`` each.

And the router: **local draws when it can, whatever keys exist.**
"""

from __future__ import annotations

import base64
import json
import struct
import zlib

import pytest

from core.egress import DataClass, EgressGate, EgressLog, EgressPolicy, Mode, set_gate
from imaging.cloud import FalImages, NimImages, RoutedImageProvider, TogetherImages
from imaging.contracts import AVAILABLE, Availability, ImageRequest


def _png(width: int = 16, height: int = 8) -> bytes:
    """A real PNG header, so the size can be read off it."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", len(ihdr)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
        + b"\x00" * 16
    )


PNG_B64 = base64.b64encode(_png()).decode()


@pytest.fixture
def gate(tmp_path):
    policy = EgressPolicy(str(tmp_path / "policy.json"))
    log = EgressLog(str(tmp_path / "egress.db"))
    set_gate(EgressGate(log, policy))
    try:
        yield policy, log
    finally:
        set_gate(None)


@pytest.fixture
def connections(monkeypatch):
    from providers import cloud_config
    from providers.cloud_config import CloudConnection

    store = {}
    monkeypatch.setattr(cloud_config, "_connections", store, raising=False)

    def connect(provider_id: str, base_url: str) -> None:
        store[provider_id] = CloudConnection(
            provider_id=provider_id, base_url=base_url, api_key="not-a-real-key", display_name=provider_id
        )

    return connect


class _Wire:
    """What went out, and what comes back. Stands in for urllib."""

    def __init__(self, answer):
        self.answer = answer
        self.sent = []

    def __call__(self, req, timeout=None):
        self.sent.append(req)
        wire = self

        class _Resp:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False

            def read(self_inner):
                return json.dumps(wire.answer).encode()

        return _Resp()


class TestNoKeyNoProvider:
    def test_unavailable_until_the_user_connects_it(self, gate, connections):
        a = NimImages().availability()
        assert not a.ok
        assert "key" in a.reason.lower()
        assert "Settings" in a.remedy


class TestAPictureIsItsOwnConsent:
    def test_a_permitted_hosts_first_picture_is_a_question_not_a_refusal(self, gate, connections):
        """Rule 7j, both halves: the picture is its own consent, asked once
        on the request itself, then remembered. Availability says yes —
        the gate asks at send time — and nothing has been granted yet."""
        policy, _ = gate
        connections("nvidia_nim", "https://integrate.api.nvidia.com/v1")
        policy.set("ai.api.nvidia.com", Mode.ALLOW, DataClass.PROMPT)

        assert NimImages().availability().ok
        assert policy.decide("ai.api.nvidia.com", DataClass.IMAGE).mode is Mode.ASK
        assert not policy.has_rule("ai.api.nvidia.com", DataClass.IMAGE)

    def test_a_host_nobody_permitted_still_refuses_pictures(self, gate, connections):
        policy, _ = gate
        connections("nvidia_nim", "https://integrate.api.nvidia.com/v1")

        a = NimImages().availability()

        assert not a.ok
        assert "Allow images to ai.api.nvidia.com" in a.remedy

    def test_allowed_once_it_draws_and_is_logged_as_an_image(self, gate, connections, monkeypatch):
        policy, log = gate
        connections("nvidia_nim", "https://integrate.api.nvidia.com/v1")
        policy.set("ai.api.nvidia.com", Mode.ALLOW, DataClass.IMAGE)
        wire = _Wire({"artifacts": [{"base64": PNG_B64, "seed": 7}]})
        monkeypatch.setattr("urllib.request.urlopen", wire)

        assert NimImages().availability() == AVAILABLE
        out = NimImages().generate(ImageRequest(prompt="a lighthouse at dusk", seed=7))

        assert len(out) == 1
        assert (out[0].width, out[0].height, out[0].seed) == (16, 8, 7)
        assert wire.sent[0].full_url.startswith("https://ai.api.nvidia.com/v1/genai/")
        assert wire.sent[0].get_header("Authorization") == "Bearer not-a-real-key"
        entry = log.entries(limit=1)[0]
        assert entry.host == "ai.api.nvidia.com"
        assert entry.decision == "allowed"
        # Logged under the image grant, from the images runtime, with the
        # prompt as what left.
        assert "image" in entry.reason.lower()
        assert entry.source == "images"
        assert "lighthouse" in (entry.body or "")


class TestEveryShapeBecomesOnePicture:
    def test_together_openai_shape(self, gate, connections, monkeypatch):
        policy, _ = gate
        connections("together", "https://api.together.xyz/v1")
        policy.set("api.together.xyz", Mode.ALLOW, DataClass.IMAGE)
        monkeypatch.setattr("urllib.request.urlopen", _Wire({"data": [{"b64_json": PNG_B64}]}))
        out = TogetherImages().generate(ImageRequest(prompt="x", seed=3))
        assert (out[0].width, out[0].seed) == (16, 3)

    def test_fal_data_uri_shape_with_its_own_auth(self, gate, connections, monkeypatch):
        policy, _ = gate
        connections("fal", "https://fal.run")
        policy.set("fal.run", Mode.ALLOW, DataClass.IMAGE)
        wire = _Wire({"images": [{"url": f"data:image/png;base64,{PNG_B64}"}], "seed": 11})
        monkeypatch.setattr("urllib.request.urlopen", wire)
        out = FalImages().generate(ImageRequest(prompt="x"))
        assert out[0].seed == 11
        assert wire.sent[0].get_header("Authorization") == "Key not-a-real-key"

    def test_an_answer_without_a_picture_is_refused_by_name(self, gate, connections, monkeypatch):
        policy, _ = gate
        connections("together", "https://api.together.xyz/v1")
        policy.set("api.together.xyz", Mode.ALLOW, DataClass.IMAGE)
        monkeypatch.setattr("urllib.request.urlopen", _Wire({"data": []}))
        with pytest.raises(RuntimeError, match="Together"):
            TogetherImages().generate(ImageRequest(prompt="x"))


class _Local:
    name = "flux-schnell"
    vram_needed_bytes = 12_000_000_000

    def __init__(self, ok: bool):
        self._ok = ok
        self.drew = 0

    def availability(self):
        return AVAILABLE if self._ok else Availability(ok=False, reason="no card", remedy="install Flux (13 GB)")

    def generate(self, request, on_progress=None):
        self.drew += 1
        return [type("Img", (), {"png": _png(), "width": 16, "height": 8, "seed": 1})()]


class TestLocalFirst:
    def test_local_draws_whatever_keys_exist(self, gate, connections, monkeypatch):
        policy, _ = gate
        connections("nvidia_nim", "https://integrate.api.nvidia.com/v1")
        policy.set("ai.api.nvidia.com", Mode.ALLOW, DataClass.IMAGE)
        local = _Local(ok=True)
        router = RoutedImageProvider(local, prefer=lambda: "local")
        router.generate(ImageRequest(prompt="x"))
        assert local.drew == 1
        assert router.vram_needed_bytes == 12_000_000_000

    def test_cloud_takes_over_only_when_local_cannot(self, gate, connections, monkeypatch):
        policy, _ = gate
        connections("nvidia_nim", "https://integrate.api.nvidia.com/v1")
        policy.set("ai.api.nvidia.com", Mode.ALLOW, DataClass.IMAGE)
        monkeypatch.setattr("urllib.request.urlopen", _Wire({"image": PNG_B64}))
        router = RoutedImageProvider(_Local(ok=False), prefer=lambda: "local")
        assert router.availability().ok
        assert "NVIDIA" in router.name
        # A cloud provider holds no card; nothing must be preflighted for it.
        assert router.vram_needed_bytes is None
        assert router.generate(ImageRequest(prompt="x"))[0].width == 16

    def test_the_person_may_put_cloud_first_and_local_is_then_the_fallback(self, gate, connections, monkeypatch):
        # Cloud first: Flux is never loaded while a cloud provider can draw —
        # the card stays with the chat model. Flip it and local draws again.
        policy, _ = gate
        connections("nvidia_nim", "https://integrate.api.nvidia.com/v1")
        policy.set("ai.api.nvidia.com", Mode.ALLOW, DataClass.IMAGE)
        monkeypatch.setattr("urllib.request.urlopen", _Wire({"image": PNG_B64}))
        local = _Local(ok=True)
        prefer = {"where": "cloud"}
        router = RoutedImageProvider(local, prefer=lambda: prefer["where"])

        router.generate(ImageRequest(prompt="x"))
        assert local.drew == 0
        assert router.vram_needed_bytes is None

        prefer["where"] = "local"
        router.generate(ImageRequest(prompt="x"))
        assert local.drew == 1

    def test_cloud_first_still_falls_back_to_local_when_no_cloud_can_draw(self, gate, connections):
        local = _Local(ok=True)
        router = RoutedImageProvider(local, prefer=lambda: "cloud")
        router.generate(ImageRequest(prompt="x"))
        assert local.drew == 1

    def test_the_preference_is_stored_and_read_back(self, tmp_path):
        from core.user_settings import ImageLocality, UserSettings

        settings = UserSettings(str(tmp_path / "settings.json"))
        assert settings.image_locality is ImageLocality.LOCAL
        settings.set_image_locality("cloud")
        assert UserSettings(str(tmp_path / "settings.json")).image_locality is ImageLocality.CLOUD
        with pytest.raises(ValueError):
            settings.set_image_locality("somewhere")

    def test_nothing_can_draw_says_both_remedies(self, gate, connections):
        policy, _ = gate
        connections("nvidia_nim", "https://integrate.api.nvidia.com/v1")
        a = RoutedImageProvider(_Local(ok=False), prefer=lambda: "local").availability()
        assert not a.ok
        assert "install Flux" in a.remedy
        assert "Allow images to ai.api.nvidia.com" in a.remedy
