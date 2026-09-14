"""The two things the maintainer saw on 14 September, verified end to end.

Not unit tests of the pieces — those exist beside each piece. These run the
real adapter, the real catalogue, the real budget, the real policy, the real
gate and the real image provider, with only the network faked, because the
report was about what happened *between* the pieces and a fake at any seam
would have passed before the fix too. No credential of the maintainer's is
used: the key here is a string that never leaves the process.

1. `nvidia_nim:z-ai/glm-5.3-flash` — discovered by the OpenAI-compatible
   adapter exactly as the connect path builds it, put in a `ProviderManager`
   catalogue, and sized by the engine's own `_budget_for`: 131,072, not
   4,096, with the conversation share to match.
2. The first picture on NIM — after connecting, the picture host is
   permitted; the first draw is asked once through the gate's confirm hook
   with `remember` set; the class rule is written; the second draw is not
   asked; both leave through the gate as images and are logged.
"""

from __future__ import annotations

import json

import pytest

from core.context_budget import FALLBACK_CONTEXT_TOKENS, budget_for
from core.egress import DataClass, EgressGate, EgressLog, EgressPolicy, Mode, set_gate
from core.egress.gate import EgressRequest
from providers.contracts import ProviderKind
from providers.discoverers.openai_compat import OpenAICompatibleAdapter
from providers.manager import ProviderManager


class TestTheGlmWindow:
    def _manager_with_glm(self) -> ProviderManager:
        adapter = OpenAICompatibleAdapter(
            provider_id="nvidia_nim",
            base_url="https://integrate.api.nvidia.com/v1",
            kind=ProviderKind.CLOUD_API,
            api_key="not-a-real-key",
        )
        # What NIM's `/v1/models` actually returns for an entry: id and
        # ownership, nothing about the window.
        info = adapter._to_model(
            "z-ai/glm-5.3-flash", {"id": "z-ai/glm-5.3-flash", "object": "model", "owned_by": "z-ai"}
        )
        manager = ProviderManager()
        manager.catalog.upsert(info)
        return manager

    def test_the_engine_sizes_glm_by_its_family_not_by_ollamas_default(self, monkeypatch):
        import core.context_budget as cb

        # No local server may be consulted for a cloud model.
        monkeypatch.setattr(cb.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("loopback probed")))
        manager = self._manager_with_glm()
        assert manager.get_model("nvidia_nim:z-ai/glm-5.3-flash") is not None

        from core.execution_engine import ExecutionEngine

        engine = ExecutionEngine.__new__(ExecutionEngine)
        engine._provider_manager = manager
        engine._router = None
        budget = engine._budget_for("nvidia_nim:z-ai/glm-5.3-flash")

        assert budget.total_tokens == 131072
        assert budget.source == "declared"
        assert budget.input_tokens >= 90_000
        assert budget.total_tokens != FALLBACK_CONTEXT_TOKENS

    def test_the_chat_route_sizes_attachments_the_same_way(self, monkeypatch):
        import core.context_budget as cb

        monkeypatch.setattr(cb.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("loopback probed")))
        budget = budget_for("nvidia_nim:z-ai/glm-5.3-flash", catalog=self._manager_with_glm())
        assert budget.document_chars > 100_000


class _Wire:
    def __init__(self) -> None:
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
                return json.dumps({"artifacts": [{"base64": PNG_B64, "seed": 7}]}).encode()

        return _Resp()


def _png() -> bytes:
    import struct
    import zlib

    ihdr = struct.pack(">IIBBBBB", 16, 8, 8, 6, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    return (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", len(ihdr)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)
        + b"\x00" * 16
    )


import base64  # noqa: E402

PNG_B64 = base64.b64encode(_png()).decode()


class TestTheFirstPictureOnNim:
    @pytest.fixture
    def gate(self, tmp_path):
        policy = EgressPolicy(str(tmp_path / "policy.json"))
        log = EgressLog(str(tmp_path / "egress.db"))
        gate = EgressGate(log, policy)
        set_gate(gate)
        try:
            yield gate
        finally:
            set_gate(None)

    @pytest.fixture
    def connected(self, monkeypatch):
        """NIM connected the way the connect route leaves it: a key stored,
        and every host the provider answers from permitted for prompts."""
        from providers import api, cloud_config
        from providers.cloud_config import CloudConnection

        store = {
            "nvidia_nim": CloudConnection(
                provider_id="nvidia_nim",
                base_url="https://integrate.api.nvidia.com/v1",
                api_key="not-a-real-key",
                display_name="NVIDIA NIM",
            )
        }
        monkeypatch.setattr(cloud_config, "_connections", store, raising=False)
        api._consent_to_the_host_just_connected(
            {"connections": [{"provider_id": "nvidia_nim", "base_url": "https://integrate.api.nvidia.com/v1"}]},
            "nvidia_nim",
            None,
        )

    def test_asked_once_then_remembered_and_both_pictures_logged(self, gate, connected, monkeypatch):
        from imaging.cloud import RoutedImageProvider
        from imaging.contracts import Availability, ImageRequest

        policy = gate.policy
        assert policy.rules()["integrate.api.nvidia.com"] == "allow"
        assert policy.rules()["ai.api.nvidia.com"] == "allow"
        assert not policy.has_rule("ai.api.nvidia.com", DataClass.IMAGE)

        asked: list[EgressRequest] = []

        def the_person_says_yes(request: EgressRequest) -> bool:
            asked.append(request)
            return True

        gate.set_confirm(the_person_says_yes)
        wire = _Wire()
        monkeypatch.setattr("urllib.request.urlopen", wire)

        class _NoFlux:
            name = "flux-schnell"

            def availability(self):
                return Availability(ok=False, reason="no weights", remedy="install Flux")

        router = RoutedImageProvider(_NoFlux(), prefer=lambda: "cloud")
        assert router.availability().ok, router.availability()
        assert "NVIDIA" in router.name

        first = router.generate(ImageRequest(prompt="a lighthouse at dusk", seed=7))
        second = router.generate(ImageRequest(prompt="the same, at dawn", seed=8))

        assert first[0].width == 16 and second[0].width == 16
        assert len(wire.sent) == 2
        assert len(asked) == 1, "the second picture was asked about"
        assert asked[0].host == "ai.api.nvidia.com"
        assert asked[0].data_class is DataClass.IMAGE
        assert asked[0].remember is True
        assert policy.decide("ai.api.nvidia.com", DataClass.IMAGE).mode is Mode.ALLOW

        entries = gate.log.entries(limit=5)
        assert [e.decision for e in entries[:2]] == ["allowed", "allowed"]
        assert any("from now on" in e.reason for e in entries)
        assert all(e.host == "ai.api.nvidia.com" for e in entries[:2])

    def test_a_no_leaves_nothing_and_remembers_nothing(self, gate, connected, monkeypatch):
        from imaging.cloud import NimImages
        from imaging.contracts import ImageRequest

        gate.set_confirm(lambda request: False)
        wire = _Wire()
        monkeypatch.setattr("urllib.request.urlopen", wire)

        with pytest.raises(Exception):
            NimImages().generate(ImageRequest(prompt="a lighthouse"))

        assert wire.sent == []
        assert not gate.policy.has_rule("ai.api.nvidia.com", DataClass.IMAGE)
        assert gate.log.entries(limit=1)[0].decision == "cancelled"
