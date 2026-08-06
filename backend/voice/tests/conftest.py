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

import pytest


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
