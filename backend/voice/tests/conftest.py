"""Voice tests require the voice extra, which the base install does not have.

Voice is an optional extra: Kokoro pulls torch, transformers and the spaCy
stack, roughly 830 MB against a ~200 MB base, for a feature that is out of scope
for v1. Making CI install all of that to exercise it would be slow for no
benefit, so these skip instead when the extra is absent.

Skipped, not deleted, and skipped with a *reason* — a silently absent test and a
deliberately skipped one are indistinguishable in a summary line unless the
runner says which. `pytest -rs` prints it.

The import is checked rather than the package metadata. `kokoro` can be present
while spaCy is not, which is exactly the state that broke synthesis with
"No module named 'spacy'" while every metadata check said the dependency tree
was intact.
"""

from __future__ import annotations

import importlib.util
from typing import Any, Iterator

import pytest


class FakeToken:
    """Stand-in for ``misaki``'s ``MToken``.

    ``start_ts``/``end_ts`` default to ``None`` because that is what G2P
    actually returns before the model has run — it knows *what* sounds, not
    *when*. A fake that always carried numbers would hide the one case the
    provider has to handle: punctuation and whitespace tokens that never become
    sound and must not be given a viseme.
    """

    def __init__(
        self,
        text: str = "",
        phonemes: str = "",
        start_ts: float | None = None,
        end_ts: float | None = None,
    ) -> None:
        self.text = text
        self.phonemes = phonemes
        self.start_ts = start_ts
        self.end_ts = end_ts


class FakeResult:
    """Stand-in for ``kokoro.KPipeline.Result``, faithful in the way that bit.

    The real ``Result`` supports **both** tuple unpacking (for backwards
    compatibility) and attribute access — and ``tokens`` is reachable *only* as
    an attribute. That asymmetry is the entire reason phoneme timings were being
    thrown away: the provider unpacked ``for _g, _p, audio in pipeline(...)``,
    which is legal, silently drops ``tokens``, and looks correct.

    A fake that yielded a bare 3-tuple could not have caught that, and would
    equally fail to catch its return. So this supports both, exactly as the real
    class does. Fakes that are shaped more conveniently than the thing they
    stand for are how a green suite hides a live defect — the model-name
    matching in the swap pre-flight was the last one.
    """

    def __init__(self, audio: Any, tokens: list[FakeToken] | None = None) -> None:
        self.audio = audio
        self.tokens = tokens or []
        self.graphemes = "g"
        self.phonemes = "p"

    def __iter__(self) -> Iterator[Any]:
        return iter((self.graphemes, self.phonemes, self.audio))


def _voice_extra_installed() -> tuple[bool, str]:
    for module in ("kokoro", "spacy"):
        if importlib.util.find_spec(module) is None:
            return False, module
    return True, ""


_INSTALLED, _MISSING = _voice_extra_installed()

_SKIP = pytest.mark.skip(
    reason=(
        f"voice extra not installed ({_MISSING} missing) — "
        "pip install -r backend/requirements-voice.txt"
    )
)

_HERE = __file__.rsplit("conftest.py", 1)[0]


def pytest_collection_modifyitems(config, items):
    """Skip everything in this directory when the extra is absent.

    A module-level `pytestmark` in a conftest does not propagate to test
    modules — it would look like it worked and skip nothing. This hook is the
    supported route, filtered by path because conftest hooks are handed every
    collected item in the run, not only the ones beneath them.
    """
    if _INSTALLED:
        return
    for item in items:
        if str(item.fspath).startswith(_HERE):
            item.add_marker(_SKIP)
