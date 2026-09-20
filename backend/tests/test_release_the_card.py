"""Give the card back, on request, and say what could not be given back.

Until 12 September 2026 the only way to get VRAM back from Zaram was to wait
out the thirty-minute keep-alive or quit — and on a 12 GB card that a game, a
render or a second local server also needs, that is the difference between
"Zaram is in the background" and "my PC is slow". `warm` spends the card at
boot; this is the other half.

Two things are pinned. Ollama's models are released by name with
``keep_alive: 0``, the documented mirror of how they were loaded. And a server
with no unload route — TabbyAPI, LM Studio — is **reported, not skipped**: the
answer names what it still holds and why, so the screen can say "still holding
9.5 GB" rather than "done". A release that quietly leaves 9.5 GB on the card is
worse than no button.
"""

from __future__ import annotations

import pytest

from providers.contracts import ProviderKind
from providers.discoverers.ollama import OllamaAdapter
from providers.manager import ProviderManager


class _Ollama:
    kind = ProviderKind.LOCAL_LLM
    provider_id = "ollama"

    def __init__(self, resident):
        self._resident = resident
        self.released: list[str] = []

    def resident_models(self, *, timeout: float = 1.0):
        return self._resident

    def release_resident(self, *, timeout: float = 10.0):
        self.released.extend(self._resident)
        return {name: "released" for name in self._resident}


class _Tabby:
    """An OpenAI-compatible server: can say what it holds, cannot unload it."""

    kind = ProviderKind.LOCAL_AI_SERVER
    provider_id = "lm_studio"

    def __init__(self, resident):
        self._resident = resident

    def resident_models(self, *, timeout: float = 1.0):
        return self._resident


class _Cloud:
    kind = ProviderKind.CLOUD_API
    provider_id = "openrouter"

    def resident_models(self, *, timeout: float = 1.0):  # pragma: no cover - must not be asked
        raise AssertionError("a cloud provider holds nothing on this machine")


def _manager(*adapters) -> ProviderManager:
    mgr = ProviderManager()
    for adapter in adapters:
        mgr.registry.register_model_provider(adapter)
    return mgr


class TestReleasing:
    def test_ollama_models_are_released_by_name(self):
        ollama = _Ollama({"qwen3-14b-16k:latest": 10_400_000_000, "bge-m3:latest": 664_000_000})
        outcome = _manager(ollama).release_resident()

        assert sorted(ollama.released) == ["bge-m3:latest", "qwen3-14b-16k:latest"]
        assert outcome == {"qwen3-14b-16k:latest": "released", "bge-m3:latest": "released"}

    def test_a_server_with_no_unload_route_is_reported_not_skipped(self):
        tabby = _Tabby({"Qwen3.8-27B-exl3-2.20bpw": None})
        outcome = _manager(_Ollama({}), tabby).release_resident()

        assert "Qwen3.8-27B-exl3-2.20bpw" in outcome
        assert outcome["Qwen3.8-27B-exl3-2.20bpw"].startswith("not released")
        assert "lm_studio" in outcome["Qwen3.8-27B-exl3-2.20bpw"]

    def test_cloud_providers_are_never_asked(self):
        outcome = _manager(_Ollama({"a": 1}), _Cloud()).release_resident()
        assert outcome == {"a": "released"}

    def test_nothing_resident_is_an_empty_outcome(self):
        assert _manager(_Ollama({})).release_resident() == {}


class TestTheWire:
    def test_ollama_is_asked_with_keep_alive_zero(self, monkeypatch):
        """The documented way to unload: an empty prompt and `keep_alive: 0`."""
        import providers.discoverers.ollama as mod

        sent: list[dict] = []

        class _Resp:
            def raise_for_status(self):
                return None

        def fake_post(url, json=None, timeout=None):
            sent.append({"url": url, **(json or {})})
            return _Resp()

        adapter = OllamaAdapter(base_url="http://127.0.0.1:11434")
        monkeypatch.setattr(adapter, "resident_models", lambda timeout=1.0: {"qwen3:latest": 1})
        monkeypatch.setattr(mod.requests, "post", fake_post)

        outcome = adapter.release_resident()

        assert outcome == {"qwen3:latest": "released"}
        assert sent == [{
            "url": "http://127.0.0.1:11434/api/generate",
            "model": "qwen3:latest",
            "prompt": "",
            "stream": False,
            "keep_alive": 0,
        }]

    def test_a_refusal_on_one_model_does_not_stop_the_rest(self, monkeypatch):
        import providers.discoverers.ollama as mod

        class _Resp:
            def __init__(self, ok):
                self._ok = ok

            def raise_for_status(self):
                if not self._ok:
                    raise RuntimeError("500")

        def fake_post(url, json=None, timeout=None):
            return _Resp(ok=json["model"] != "stuck")

        adapter = OllamaAdapter(base_url="http://127.0.0.1:11434")
        monkeypatch.setattr(adapter, "resident_models", lambda timeout=1.0: {"stuck": 1, "fine": 1})
        monkeypatch.setattr(mod.requests, "post", fake_post)

        outcome = adapter.release_resident()

        assert outcome["fine"] == "released"
        assert outcome["stuck"].startswith("not released")


class TestAnOpenAICompatibleServerIsAsked:
    """TabbyAPI has an unload route, and this adapter used to say it did not.

    Measured 20 September 2026 against the maintainer's own server:
    `POST /v1/model/unload` took about thirty seconds and the card went from
    11.8 GB to 5 GB. The route is asked and its answer reported — nothing is
    inferred from the server's name, so LM Studio (404) still reads as "no
    unload route" and a server with auth on reads as wanting a key.
    """

    def _adapter(self, monkeypatch, answer):
        import urllib.error

        from providers.discoverers.openai_compat import OpenAICompatibleAdapter

        adapter = OpenAICompatibleAdapter("lm_studio", base_url="http://127.0.0.1:1234")
        monkeypatch.setattr(adapter, "resident_models", lambda timeout=1.0: {"Qwen3.8-27B": None})
        sent: list[dict] = []

        class _Gate:
            def request(self, url, *, method="GET", **kw):
                sent.append({"url": url, "method": method})
                if answer >= 400:
                    raise urllib.error.HTTPError(url, answer, "x", {}, None)
                return b"{}"

        import core.egress as egress

        monkeypatch.setattr(egress, "get_gate", lambda: _Gate())
        return adapter, sent

    def test_tabby_is_asked_on_its_unload_route(self, monkeypatch):
        adapter, sent = self._adapter(monkeypatch, 200)
        assert adapter.release_resident() == {"Qwen3.8-27B": "released"}
        assert sent == [{"url": "http://127.0.0.1:1234/v1/model/unload", "method": "POST"}]

    def test_a_server_without_the_route_is_reported(self, monkeypatch):
        adapter, _ = self._adapter(monkeypatch, 404)
        assert adapter.release_resident() == {
            "Qwen3.8-27B": "not released: lm_studio has no unload route; stop or unload it from that app"
        }

    def test_a_server_that_wants_a_key_says_so(self, monkeypatch):
        adapter, _ = self._adapter(monkeypatch, 401)
        assert adapter.release_resident() == {"Qwen3.8-27B": "not released: lm_studio wants an admin key to unload"}
