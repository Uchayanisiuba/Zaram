"""The name in the request body is the one Ollama answers to.

**This is a live defect, measured against the running product.** The provider
layer catalogues every discovered model as ``<provider_id>:<model>``, Settings
stores what the user picked, which is that id, and `OllamaEngine` put whatever
it was handed straight into `/api/generate`. So choosing any model deliberately
sent ``ollama:qwen2.5-coder:1.5b`` and got::

    400 Client Error: Bad Request for url: http://127.0.0.1:11434/api/generate

The bare name returned 200 on the same server seconds later. Only the model
Zaram had auto-selected worked, because that path carried `display_name`
already — so "switching models is broken and the default is fine" was exactly
the symptom.

`CloudFanout` fixed the same conflation on the cloud side and the local side
never learned it. These tests assert the conversion on the path that actually
reaches the wire, and the first one exists so the rest cannot pass vacuously:
if ids ever stop being prefixed, this file should say so rather than quietly
testing an identity function.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import pytest

from providers.contracts import CapabilityLocality, ModelInfo
from providers.discoverers.ollama import OllamaAdapter
from runtimes.models.engines.ollama_engine import OllamaEngine
from runtimes.models.models_runtime import ModelsRuntime


class TestTheCatalogueIdIsNotTheWireName:
    """Without this, everything below could be testing ``x == x``."""

    def test_ollama_ids_carry_a_provider_prefix(self, monkeypatch):
        adapter = OllamaAdapter()
        monkeypatch.setattr(adapter, "_post", lambda *a, **k: {})

        model = adapter._to_model("qwen2.5-coder:1.5b", {"size": 1_000}, timeout=0.1)

        assert model.id == "ollama:qwen2.5-coder:1.5b"
        assert model.display_name == "qwen2.5-coder:1.5b"
        assert model.id != model.display_name


def _catalogued(model_id: str, display_name: str) -> ModelInfo:
    return ModelInfo(
        id=model_id,
        display_name=display_name,
        provider="ollama",
        locality=CapabilityLocality.LOCAL,
    )


class _Manager:
    """The two lookups `ModelsRuntime` uses, and nothing else."""

    def __init__(self, *models: ModelInfo) -> None:
        self._models = {m.id: m for m in models}

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        return self._models.get(model_id)


class TestTheRuntimeResolvesTheName:
    def test_a_catalogue_id_becomes_the_provider_native_name(self):
        runtime = ModelsRuntime(
            event_bus=None,
            provider_manager=_Manager(
                _catalogued("ollama:qwen2.5-coder:1.5b", "qwen2.5-coder:1.5b")
            ),
        )

        assert runtime.wire_name("ollama:qwen2.5-coder:1.5b") == "qwen2.5-coder:1.5b"

    def test_a_name_the_catalogue_cannot_place_passes_through(self):
        """`qwen3` is a name Ollama resolves itself. Refusing it would break
        the ordinary case in the name of tidiness."""
        runtime = ModelsRuntime(event_bus=None, provider_manager=_Manager())

        assert runtime.wire_name("qwen3") == "qwen3"

    def test_no_provider_layer_is_not_a_failure(self):
        runtime = ModelsRuntime(event_bus=None, provider_manager=None)

        assert runtime.wire_name("gemma3:latest") == "gemma3:latest"

    def test_a_lookup_that_raises_never_takes_chat_down(self):
        class Exploding:
            def get_model(self, model_id):
                raise RuntimeError("catalogue unavailable")

        runtime = ModelsRuntime(event_bus=None, provider_manager=Exploding())

        assert runtime.wire_name("ollama:gemma3:latest") == "ollama:gemma3:latest"


class _Captured:
    """Stands in for `requests.post`, recording the body it was given."""

    def __init__(self) -> None:
        self.payload: Dict[str, Any] = {}

    def __call__(self, url, json=None, **kwargs):  # noqa: A002 - requests' own name
        self.payload = json or {}
        return _Response()


class _Response:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self):
        yield json.dumps({"response": "hi", "done": True}).encode()


class TestTheEngineSendsTheWireName:
    def test_the_request_body_carries_the_name_ollama_answers_to(self, monkeypatch):
        captured = _Captured()
        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", captured)
        engine = OllamaEngine(wire_name=lambda m: "qwen2.5-coder:1.5b")

        list(engine.stream_response("hello", model="ollama:qwen2.5-coder:1.5b"))

        assert captured.payload["model"] == "qwen2.5-coder:1.5b"

    def test_the_preload_asks_for_the_same_name(self, monkeypatch):
        captured = _Captured()
        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", captured)
        engine = OllamaEngine(wire_name=lambda m: "gemma4:12b")

        engine.warm("ollama:gemma4:12b")

        assert captured.payload["model"] == "gemma4:12b"

    def test_without_a_resolver_the_name_is_unchanged(self, monkeypatch):
        """Constructed standalone in several places, including the vision path."""
        captured = _Captured()
        monkeypatch.setattr("runtimes.models.engines.ollama_engine.requests.post", captured)
        engine = OllamaEngine()

        list(engine.stream_response("hello", model="gemma3:latest"))

        assert captured.payload["model"] == "gemma3:latest"


class TestTheRefusalSaysWhichModelAndWhy:
    """"400 Client Error ... for url" names neither the model nor the cause."""

    def test_ollamas_own_reason_is_quoted(self, monkeypatch):
        class Refused:
            status_code = 400

            def json(self):
                return {"error": "model 'nope' not found"}

            def raise_for_status(self):
                error = Exception("400 Client Error: Bad Request for url: /api/generate")
                error.response = self
                raise error

            def iter_lines(self):
                return iter(())

        monkeypatch.setattr(
            "runtimes.models.engines.ollama_engine.requests.post",
            lambda *a, **k: Refused(),
        )
        engine = OllamaEngine()

        out = "".join(engine.stream_response("hello", model="nope"))

        assert "nope" in out
        assert "model 'nope' not found" in out


@pytest.mark.parametrize("name", ["ollama:gemma3:latest", "ollama:qwen3:latest"])
def test_the_prefix_is_never_removed_by_string_surgery(name):
    """A lookup, not a `split(":")`.

    Stripping a leading provider id by hand is the same guess-from-the-name
    mistake `RoutedEngine` refuses for locality, and it mangles a model whose
    own name carries a prefix — `qllama/bge-reranker-v2-m3:latest` is installed
    on the maintainer's machine today.
    """
    runtime = ModelsRuntime(event_bus=None, provider_manager=_Manager())

    assert runtime.wire_name(name) == name
