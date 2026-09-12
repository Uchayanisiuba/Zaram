"""On a card that cannot hold both, the embedder runs on the CPU.

**Measured 12 September 2026 on a 12 GB RTX 3060.** Ollama held a 10.4 GB chat
model entirely in VRAM. One embedding call loaded bge-m3 (0.66 GB) and Ollama
evicted the chat model to make room; the next reply loaded the chat model back
and evicted the embedder. Recall runs before every reply and the duplicate check
runs after it, so every exchange moved ~10 GB through PCIe at least twice, and
the whole desktop stalled while it did — with the routing preference set to
cloud, because recall still embeds.

With ``num_gpu: 0`` the same embedder reported ``size_vram: 0`` and answered a
query in 89 ms. That is the whole trade: 0.66 GB of VRAM is the margin that
decides whether a 14B fits, and a query embedding on the CPU costs a tenth of a
second.

The decision lives in `embed_on_gpu`, keyed on the card's size, and the memory
runtime only carries the answer — it must not know about hardware.
"""

from __future__ import annotations

import json

import pytest

from runtimes.memory.embeddings import (
    EMBED_ON_GPU_MIN_VRAM_BYTES,
    EmbeddingService,
    embed_on_gpu,
)

GB = 1024**3


class TestTheDecision:
    def test_a_twelve_gigabyte_card_keeps_the_embedder_on_the_cpu(self):
        assert embed_on_gpu(12 * GB) is False

    def test_a_sixteen_gigabyte_card_may_use_the_gpu(self):
        assert embed_on_gpu(16 * GB) is True
        assert embed_on_gpu(24 * GB) is True

    def test_unknown_vram_answers_cpu(self):
        """An unmeasurable card is where a confident wrong answer costs most;
        CPU embedding is slower rather than broken."""
        assert embed_on_gpu(None) is False

    def test_the_threshold_is_what_the_measurement_says(self):
        assert EMBED_ON_GPU_MIN_VRAM_BYTES == 16 * GB

    @pytest.mark.parametrize("pref", ["gpu", "GPU", " gpu "])
    def test_an_explicit_gpu_preference_wins_on_any_card(self, pref):
        assert embed_on_gpu(8 * GB, pref) is True

    @pytest.mark.parametrize("pref", ["cpu", "CPU"])
    def test_an_explicit_cpu_preference_wins_on_any_card(self, pref):
        assert embed_on_gpu(48 * GB, pref) is False

    def test_anything_else_is_automatic(self):
        assert embed_on_gpu(24 * GB, "auto") is True
        assert embed_on_gpu(8 * GB, "") is False


def _captured_payload(monkeypatch, svc: EmbeddingService) -> dict:
    """Run `_embed_ollama` against a fake server and return what it sent."""
    import urllib.request

    sent: dict = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"embedding": [0.0] * svc.get_dim()}).encode()

    def fake_urlopen(req, timeout=None):
        sent.update(json.loads(req.data))
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    svc._embed_ollama("hello")
    return sent


class TestTheRequestCarriesTheDecision:
    def test_cpu_placement_sends_num_gpu_zero(self, monkeypatch):
        svc = EmbeddingService(backend="ollama", dim=4, ollama_model="bge-m3", on_gpu=False)
        sent = _captured_payload(monkeypatch, svc)
        assert sent.get("options") == {"num_gpu": 0}

    def test_gpu_placement_sends_no_options(self, monkeypatch):
        """Ollama's default is the card; saying nothing is how it is asked for.
        An explicit `num_gpu` would also pin the layer count, which is Ollama's
        to decide."""
        svc = EmbeddingService(backend="ollama", dim=4, ollama_model="bge-m3", on_gpu=True)
        sent = _captured_payload(monkeypatch, svc)
        assert "options" not in sent

    def test_the_default_is_the_card(self):
        """Callers that do not say are unchanged; only the bootstrapper decides."""
        assert EmbeddingService().on_gpu is True
