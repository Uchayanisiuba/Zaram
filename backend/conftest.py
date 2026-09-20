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
def _test_client_presents_the_credential():
    """Every `TestClient` request carries the API credential.

    The API now refuses anything that does not, so the alternative to this was
    editing two thousand call sites — or exempting the test client in the
    middleware, which is the same mistake as an `ALLOWED_HOSTS` entry that
    switches the host guard off in the suite. A check the tests bypass is a
    check nobody runs. This makes the credential *present* rather than the
    check absent, so the guard executes on every one of those requests and a
    change that broke it would be caught.

    `setdefault`, so a test that sets the header itself still wins — which is
    how `test_api_requires_the_credential.py` is able to send a wrong one and
    assert the refusal.

    The environment variable is set before anything reads it, because
    `api_secret()` caches on first call and a fixture that ran afterwards
    would be measuring a value from a file in the developer's own data
    directory.
    """
    import os

    from starlette.testclient import TestClient

    import core.api_secret as api_secret

    os.environ[api_secret.SECRET_ENV] = "test-credential-not-a-real-secret"
    api_secret.reset_cache()

    original = TestClient.request

    def request(self, method, url, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        headers.setdefault(api_secret.HEADER, api_secret.api_secret())
        return original(self, method, url, headers=headers, **kwargs)

    TestClient.request = request
    try:
        yield
    finally:
        TestClient.request = original


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


@pytest.fixture(autouse=True, scope="session")
def _isolate_data_dir(tmp_path_factory):
    """No test reads the developer's own data directory.

    The settings fixture above closed this for one file and left every other
    store open. Measured 19 September 2026: `test_read_page_is_offered_from_the_
    real_boot` calls `KernelBootstrapper().boot()`, which reads
    `mcp-servers.json` from `data_dir()` — in a checkout that holds data, the
    backend folder itself — and **spawned the maintainer's own attached
    servers**: a Blender MCP that then waited on a Blender that was not
    running, and would equally have started the GitHub server with its token
    and the mail server. The suite stalled at 5% for six minutes, and an
    earlier run left `blender-mcp.exe` orphaned after the test was killed.

    A test suite must never touch the real data directory, whatever the
    developer's environment says — so this sets the variable rather than
    defaulting it. A test that wants a specific location still wins, because
    `monkeypatch.setenv` runs after this and is undone after the test.
    """
    import os

    os.environ["ZARAM_DATA_DIR"] = str(tmp_path_factory.mktemp("zaram-data"))
    yield


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "measure: drives a real resident model; runs only when asked for with -m measure",
    )


def pytest_collection_modifyitems(config, items):
    """`measure` is opt-in, not "whenever a model happens to be up".

    Every file that wears the marker says "run with ``-m measure``" in its own
    docstring, and until 13 September 2026 that was not what happened: the
    tests skipped themselves only when no model answered, so on a machine
    with TabbyAPI serving they ran inside the ordinary suite. The eval set
    made that cost visible — eight model-driven tasks at minutes each, and a
    27B that passed a task at 08:00 and failed the same task at 11:30 with no
    tool call at all. A suite that takes a different amount of time and
    reaches a different verdict depending on which server is up is not a
    suite; it is a measurement dressed as one. `CLAUDE.md`: say which
    environment you measured in — and keep the two apart.
    """
    expr = config.getoption("-m") or ""
    if "measure" in expr:
        return
    skip = pytest.mark.skip(reason="a measurement; run with -m measure")
    for item in items:
        if "measure" in item.keywords:
            item.add_marker(skip)
