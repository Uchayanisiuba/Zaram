"""Is there still a way into a model that the egress log cannot see?

Rule 3: *"Every byte that leaves is logged — including bytes sent by tools, not
only by chat. The egress log is append-only and tamper-evident, built into the
core."* Rule 9: *"Generation must fail rather than invent."*

`POST /vision/analyze` broke the first and, once deleted carelessly, would have
broken the second. It reached `OllamaEngine.stream_vision_response`, whose own
docstring said it bypassed **routing and the egress gate**, against a hardcoded
`qwen2.5vl:7b` that was not installed on the machine it was written on. Three
further things were true of it when it was removed on 28 August 2026, and each
one is worth recording because none was visible from the route table:

* **Its only caller could not authenticate.** `desktop/src/capabilities/vision/`
  posted to `127.0.0.1:8420/vision/analyze` with `Content-Type` and
  `Content-Length` and nothing else, and `RequireApiSecret` exempts nothing —
  so every call had returned 401 since the per-launch secret shipped. The live
  React frontend never referenced the route at all.
* **It could not have run even so.** The endpoint called `_parse_legacy_sse`,
  which is defined nowhere in the repository. The first streamed chunk would
  have raised `NameError`.
* **Nothing tested it.** The suite's pass count was identical before and after
  the deletion — an ungated path into inference with zero coverage.

The deletion had one trap in it, which is the second half of this file.
`IntentPlanner` still emits a `vision.*` step when the *words* suggest a
picture and nothing is attached — that is what `has_images` fixed for the case
where an image *is* attached, and it left the no-image case alone. Had the
dispatcher's vision branch simply been removed, such a step would have fallen
through to `generate_response`, and a model asked to describe a picture nobody
supplied writes a confident description of nothing. Deleting a side door into a
rule 9 failure would have been a poor trade.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.contracts import ExecutionStep
from core.dispatcher import ExecutionDispatcher

BACKEND = Path(__file__).resolve().parents[1]

#: Directories that are not shipped code.
#:
#: `venv` is here because it is really there: `backend/venv/` holds 12,748
#: files and 200 MB of installed packages, and scanning it took this file from
#: 15 seconds to 131. It is also the reason this list names both spellings —
#: a blocklist that misses one directory is slow, and a blocklist that misses
#: one *source* directory is silently blind, which is why the pre-filter below
#: exists as well.
_SKIP = {
    "tests", "__pycache__", "node_modules",
    "venv", ".venv", "env", ".env", "site-packages",
}


def _shipped_sources(containing: str | None = None):
    """Every shipped module, as (path, source).

    ``containing`` is a cheap substring pre-filter. Reading 100-odd files is
    free; parsing them is not, so a caller that only cares about files
    mentioning a token says so and the AST work lands on the two that do.

    Read with ``errors="ignore"``: at least one file under `backend/` is not
    valid UTF-8, and a scan that dies on it would report nothing rather than
    something wrong — which is the one failure a guard like this cannot
    afford, since a green run is exactly what it is asked to mean.
    """
    for path in BACKEND.rglob("*.py"):
        if any(part in _SKIP for part in path.parts):
            continue
        src = path.read_text(encoding="utf-8", errors="ignore")
        if containing is not None and containing not in src:
            continue
        yield path, src


class TestTheSideDoorIsShut:
    """Asserted against the source, not against a running server.

    The same posture as `check-no-cloud-speech.mjs` and the egress chokepoint
    test: *assert the quarantine rather than describe it*. A comment saying
    "this was removed" is worth nothing the next time someone needs a quick way
    to get an image to a model — and a quick way to get an image to a model is
    exactly how this arrived the first time.
    """

    def test_no_module_reimplements_an_ungated_vision_call(self):
        offenders = [
            str(p.relative_to(BACKEND))
            for p, src in _shipped_sources()
            if "def stream_vision_response" in src
        ]
        assert offenders == [], (
            "`stream_vision_response` is back. It is not a vision feature, it is "
            "a second entrance to inference: it chose its own model, skipped "
            f"`ProviderManager.select_model_for_task`, and skipped the gate. {offenders}"
        )

    def test_no_vision_route_exists(self):
        offenders = [
            str(p.relative_to(BACKEND))
            for p, src in _shipped_sources()
            if "/vision/analyze" in src and "@app." in src
        ]
        assert offenders == [], (
            f"a `/vision/analyze` route is being served again: {offenders}"
        )

    def test_the_route_is_absent_from_the_application_itself(self):
        """The source scan above cannot see a route added by a router include."""
        from main import app

        paths = {getattr(route, "path", None) for route in app.routes}
        assert "/vision/analyze" not in paths

    def test_the_model_nobody_installed_is_not_named_in_live_code(self):
        """`qwen2.5vl:7b` was the side door's model and was never installed.

        `docs/NEXT-SESSION.md` was explicit that the fix must not be to pull
        it: that would have made a broken, ungated path start working, which is
        the worse outcome of the two.

        **String constants only, docstrings and comments excluded**, and the
        distinction is the point rather than a convenience. Prose explaining
        why the model was removed is worth keeping — it is what stops the next
        person reintroducing it. A *string* naming it is either a request body
        or a sentence shown to a user, and both are wrong: one calls a model
        that is not there, the other advises installing one, and `CLAUDE.md`
        keeps model filenames out of the primary path regardless.

        This found something on its first run, which is the only reason to
        trust it. `implementations/ollama_llm.py` had this exact advice fixed
        on 19 August 2026 — *"names no model deliberately"* — and
        `OllamaEngine` carried a second copy of the same sentence that was
        missed, still naming the uninstalled model.
        """
        offenders = []
        for path, src in _shipped_sources(containing="qwen2.5vl"):
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            docstrings = {
                id(node.body[0].value)
                for node in ast.walk(tree)
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            }
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and "qwen2.5vl" in node.value
                    and id(node) not in docstrings
                ):
                    offenders.append(f"{path.relative_to(BACKEND)}:{node.lineno}")
        assert offenders == [], offenders


class _Service:
    """A models service that records whether generation was reached."""

    def __init__(self):
        self.generated_with = None

    def generate_response(self, prompt, model=None, system_prompt="", images=None):
        self.generated_with = {"prompt": prompt, "images": images}
        yield "a confident description of nothing"


class _Runtime:
    """Shaped like `ModelsRuntime`: `get_service`, and no `execute`.

    Both halves matter. `ExecutionDispatcher` tries `execute` first, and a
    runtime that grew one would take a different branch entirely — so this
    asserts the shape the real runtime has rather than a convenient one.
    """

    def __init__(self, service):
        self._service = service

    def get_runtime_id(self):
        return "models"

    def get_service(self):
        return self._service


class _Router:
    def __init__(self, runtime):
        self._runtime = runtime

    def resolve(self, capability_id):
        return self._runtime


class TestAVisionStepRefusesRatherThanGenerating:
    def test_the_real_runtime_still_takes_the_service_branch(self):
        """The fake above is only honest while this holds."""
        from core.contracts import Runtime
        from runtimes.models.models_runtime import ModelsRuntime

        assert not hasattr(Runtime, "execute")
        assert not hasattr(ModelsRuntime, "execute")
        assert hasattr(ModelsRuntime, "get_service")

    @pytest.mark.parametrize(
        "capability",
        ["vision.analyze", "vision.screen", "vision.camera", "vision.document", "vision.ocr"],
    )
    def test_every_vision_capability_refuses(self, capability):
        """All five were registered; all five had no way to be given an image.

        `IntentPlanner` fills a step's `input_data` with `{"prompt": ...}` and
        nothing else, so the singular `image` these were written to read is
        never present.
        """
        service = _Service()
        dispatcher = ExecutionDispatcher(_Router(_Runtime(service)))
        step = ExecutionStep(
            capability_id=capability,
            input_data={"prompt": "describe this screenshot"},
            depends_on=[],
        )

        out = "".join(dispatcher.execute_step(step))

        assert service.generated_with is None, (
            "a vision step reached generation with no image, which is a model "
            "describing a picture it was never given — rule 9"
        )
        assert "[ERROR]" in out
        assert "no image" in out.lower()

    def test_the_refusal_says_what_to_do_next(self):
        """A refusal that does not name the remedy reads as a broken product.

        Same shape as the existing refusal for an image pasted into the message
        text, which points at the paperclip rather than merely declining.
        """
        service = _Service()
        dispatcher = ExecutionDispatcher(_Router(_Runtime(service)))
        step = ExecutionStep(
            capability_id="vision.analyze",
            input_data={"prompt": "what is in this photo"},
            depends_on=[],
        )

        out = "".join(dispatcher.execute_step(step))

        assert "paperclip" in out.lower()

    def test_an_ordinary_step_still_generates(self):
        """The guard against fixing the above by refusing everything."""
        service = _Service()
        dispatcher = ExecutionDispatcher(_Router(_Runtime(service)))
        step = ExecutionStep(
            capability_id="reasoning.generate",
            input_data={"prompt": "hello"},
            depends_on=[],
        )

        out = "".join(dispatcher.execute_step(step))

        assert service.generated_with is not None
        assert "confident description" in out
