"""No engine may carry a model name of its own.

**The fourth instance of one bug.** `OllamaEngine.__init__` held
``self.default_model = "gemma3:latest"`` — a model uninstalled months earlier
that no interface control had ever offered. `ModelsRuntime.initialize` assigns
the provider layer's real pick over it, but only behind ``if
self._selected_model:``, so a selection that yields *nothing* leaves the
literal in place and it goes out on the wire.

Measured 30 August 2026, clean data dir, first message of the session::

    [ERROR] Ollama refused the request for gemma3:latest:
    model 'gemma3:latest' not found

The branch is the one `CLAUDE.md` names: it runs "never with Ollama up, always
on a stranger's machine", because an empty candidate set is the ordinary
outcome when every installed model is too large to select — which is precisely
the first-run state the product is blocked on.

`implementations/ollama_llm.py` carries the identical fix and the identical
note, ending *"naming a different model would repeat the mistake with a fresher
name"*. It was fixed; the engine actually on the chat path was not. So the last
test here does not check that *this* name is gone — it checks that **no engine
assigns any model name at all**, because three prose warnings did not stop the
fourth instance and a rule you cannot break beats a rule you must remember.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from runtimes.models.engines.ollama_engine import OllamaEngine


class _Exploding:
    """Any HTTP call is the failure under test."""

    def __call__(self, *args, **kwargs):  # pragma: no cover - only on failure
        raise AssertionError(
            "asked Ollama for a model when none was selected — the request "
            "should never have been built"
        )


class TestTheEngineNamesNoModelOfItsOwn:
    def test_the_default_is_unset(self):
        assert OllamaEngine().default_model is None

    def test_a_reply_says_so_rather_than_guessing(self, monkeypatch):
        """The sentence is about the caller, not about the server.

        A guessed name produces a 404 that reads as "the local model is
        unreachable", which sends whoever debugs it to look at Ollama instead
        of at the empty selection that caused it.
        """
        import runtimes.models.engines.ollama_engine as module

        monkeypatch.setattr(module.requests, "post", _Exploding())

        out = "".join(OllamaEngine().stream_response("hello"))

        assert "No model was selected" in out
        assert "gemma3" not in out

    def test_extraction_refuses_rather_than_posting(self, monkeypatch):
        import runtimes.models.engines.ollama_engine as module

        monkeypatch.setattr(module.requests, "post", _Exploding())

        with pytest.raises(RuntimeError, match="No model was selected"):
            OllamaEngine().read_structured("read this")

    def test_a_named_model_still_reaches_the_wire(self, monkeypatch):
        """The guard must not swallow the ordinary case.

        Without this the three assertions above pass just as well against an
        engine that refuses every request, which is the assertion-free shape
        `CLAUDE.md` warns costs more than no test.
        """
        import runtimes.models.engines.ollama_engine as module

        sent: dict = {}

        class _Response:
            def raise_for_status(self):
                return None

            def iter_lines(self):
                return iter([b'{"response": "hi", "done": true}'])

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def _capture(url, **kwargs):
            sent.update(kwargs.get("json") or {})
            return _Response()

        monkeypatch.setattr(module.requests, "post", _capture)

        list(OllamaEngine().stream_response("hello", model="qwen2.5:7b"))

        assert sent.get("model") == "qwen2.5:7b"


#: `default_model` assigned a string literal, in any engine.
#:
#: Env-var reads and assignments from a variable are what a real pick looks
#: like and are left alone; only a name written into the source is refused.
_HARDCODED = re.compile(r"""default_model[^=\n]*=\s*["'][^"']+["']""")

_ENGINE_DIRS = (
    Path(__file__).resolve().parents[1] / "runtimes" / "models" / "engines",
    Path(__file__).resolve().parents[1] / "implementations",
)


class TestNoEngineCarriesAModelName:
    def test_no_module_writes_a_model_name_into_its_source(self):
        offenders = []
        for directory in _ENGINE_DIRS:
            for path in sorted(directory.glob("*.py")):
                for number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), start=1
                ):
                    stripped = line.strip()
                    if stripped.startswith("#") or stripped.startswith("#:"):
                        continue
                    if _HARDCODED.search(line):
                        offenders.append(f"{path.name}:{number}: {stripped}")

        assert not offenders, (
            "a model name is written into an engine's source; it must come "
            "from the provider layer's pick instead:\n" + "\n".join(offenders)
        )

    def test_the_guard_catches_the_shape_it_was_written_for(self):
        """The instrument, checked against the line that caused this."""
        assert _HARDCODED.search('        self.default_model = "gemma3:latest"')
        assert _HARDCODED.search("    default_model = 'llama3'")
        # What a real pick looks like — never flagged.
        assert not _HARDCODED.search("        self.default_model = value")
        assert not _HARDCODED.search("        self._default_model: Optional[str] = None")
        assert not _HARDCODED.search(
            '    default_model = (os.getenv("ZARAM_CLOUD_MODEL") or "").strip()'
        )
