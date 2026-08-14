# backend/conftest.py
"""Pytest configuration: ensure the backend package root is importable.

The application packages (``core``, ``runtimes``, ``implementations``,
``services``) use absolute imports that resolve against the ``backend/``
directory. Adding it to ``sys.path`` lets the test suite run from any cwd.
"""
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


@pytest.fixture(autouse=True, scope="session")
def _isolate_user_settings(tmp_path_factory):
    """No test reads the developer's own settings file.

    `web_search_enabled()` consults a persisted preference, so the moment web
    search became a stored setting, four unrelated tests started failing on
    whichever machine had turned it on — including
    ``test_web_search_is_off_by_default``, which then reported a product
    defect that was really a fact about my laptop.

    That is precisely the failure mode this repo keeps paying for: a stable
    failure count nobody can explain. A suite whose result depends on the
    machine's configuration is not measuring the code, and the fix belongs here
    rather than in each test, because every future setting inherits it for
    free.

    Session-scoped and autouse: a per-test temp file would let a test that
    writes a preference leak nothing, which is right, but would also re-read
    the real path in any test that resolves it lazily. One redirect for the
    whole session removes the question.
    """
    from core.user_settings import set_user_settings_path

    path = tmp_path_factory.mktemp("zaram-settings") / "settings.json"
    set_user_settings_path(str(path))
    yield
