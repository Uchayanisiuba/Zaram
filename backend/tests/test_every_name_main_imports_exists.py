"""Every `from module import name` inside `main.py` names something that exists.

10 October 2026. `main.py` imports most of what it uses lazily, inside the route that
needs it, so that a missing optional package fails one route and not start-up. The cost
is that a wrong name is invisible until somebody opens that screen: a route imported
`DEFAULT_KOKORO_VOICE` from `voice.cleanup` when it lives in `voice.config`, and
Settings showed "Internal Server Error" instead of the voice cache. Its tests read the
route's source and never ran it.

This reads every such import, imports the module (never calling anything), and checks
the name is there. A module that cannot be imported *here* because an optional
package is absent is reported as skipped, not as a pass.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
MAIN = BACKEND / "main.py"


def _ours(module: str) -> bool:
    root = module.split(".")[0]
    return (BACKEND / root).is_dir() or (BACKEND / f"{root}.py").is_file()


def _imports():
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module and _ours(node.module):
            for alias in node.names:
                if alias.name != "*":
                    found.append((node.module, alias.name, node.lineno))
    return sorted(set(found))


IMPORTS = _imports()


def test_the_scan_found_the_imports_it_is_meant_to_check():
    assert len(IMPORTS) > 50, "the parser found almost nothing; the guard would pass on an empty set"
    pairs = {(m, n) for m, n, _l in IMPORTS}
    assert ("voice.cleanup", "resolve_keep_voice") in pairs
    assert ("voice.config", "DEFAULT_KOKORO_VOICE") in pairs


@pytest.mark.parametrize("module,name,line", IMPORTS, ids=[f"{m}.{n}@{l}" for m, n, l in IMPORTS])
def test_the_name_exists(module, name, line):
    try:
        loaded = importlib.import_module(module)
    except ModuleNotFoundError as missing:
        pytest.skip(f"{module} needs {missing.name}, which is not installed here")
    except Exception as error:  # noqa: BLE001 - an import that raises is a finding, not a skip
        pytest.fail(f"main.py:{line} imports from {module}, which raises on import: {error!r}")
    if hasattr(loaded, name):
        return
    # `from package import submodule` is a name too.
    try:
        importlib.import_module(f"{module}.{name}")
    except ModuleNotFoundError:
        pytest.fail(f"main.py:{line}: `from {module} import {name}` -- {module} has no {name}")
