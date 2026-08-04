"""No outbound HTTP anywhere except the gate.

This is the test that keeps Rule 3 true tomorrow. ``test_egress_gate.py`` proves
the gate behaves correctly; this one proves the gate is the *only* way out, by
reading the source and failing when a module opens its own socket.

Why a source scan rather than a runtime check: the failure being guarded against
is somebody adding a tenth call site six months from now, in a module nobody
thought to cover. A runtime test only sees code it executes. A source scan sees
code that merely exists, which is the point — this must fail in CI on the commit
that introduces the bypass, not in production when the path is first taken.

Adding a module to ``LOCAL_ONLY`` is deliberately awkward. It should require
writing down why the destination cannot leave the machine, and that justification
should be visible in a diff.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]

#: The gate is allowed to do outbound I/O. That is its job. ``aio.py`` is the
#: async half of the same gate and is exempt for the same reason.
GATE_MODULES = {
    BACKEND / "core" / "egress" / "gate.py",
    BACKEND / "core" / "egress" / "aio.py",
}

#: Modules that talk only to loopback, with the reason each one is exempt.
#: Ollama runs on the user's own machine; inference there is precisely what
#: Zaram exists to make possible, and logging it as egress would bury the real
#: entries under thousands of local calls.
LOCAL_ONLY = {
    "implementations/ollama_llm.py": "Ollama on localhost:11434",
    "interfaces/implementation/ollama_llm.py": "Ollama on localhost:11434",
    "runtimes/models/engines/ollama_engine.py": "Ollama on localhost:11434",
    "runtimes/memory/embeddings.py": "Ollama bge-m3 on localhost:11434",
    "garage/discoverers/ollama.py": "Ollama on localhost:11434",
}

#: Directories that are not shipped product code.
SKIP_DIRS = {"tests", "venv", ".venv", "__pycache__", "templates", "node_modules"}

#: Calls that open a connection to somewhere.
OUTBOUND_CALLS = {
    ("urllib", "request", "urlopen"),
    ("urllib", "request", "Request"),
    ("requests", "get"),
    ("requests", "post"),
    ("requests", "put"),
    ("requests", "delete"),
    ("requests", "request"),
    ("requests", "Session"),
    ("httpx", "get"),
    ("httpx", "post"),
    ("httpx", "Client"),
    ("httpx", "AsyncClient"),
    ("aiohttp", "ClientSession"),
    ("aiohttp", "request"),
}


def _dotted(node: ast.AST) -> tuple[str, ...]:
    """Flatten ``a.b.c`` into ``("a", "b", "c")``."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return tuple(reversed(parts))


def _product_files() -> list[Path]:
    files = []
    for p in BACKEND.rglob("*.py"):
        if any(part in SKIP_DIRS for part in p.relative_to(BACKEND).parts):
            continue
        if p in GATE_MODULES:
            continue
        files.append(p)
    return files


def _outbound_calls_in(path: Path) -> list[tuple[int, str]]:
    """Every outbound-looking call in ``path``, as (line, expression)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        dotted = _dotted(node.func)
        if not dotted:
            continue
        for pattern in OUTBOUND_CALLS:
            # Match on the tail so `import urllib.request` and
            # `from urllib import request` both register.
            if dotted[-len(pattern):] == pattern or dotted == pattern[-len(dotted):]:
                if len(dotted) >= 2 or dotted[0] in {"urlopen", "ClientSession"}:
                    found.append((node.lineno, ".".join(dotted)))
                break
    return found


class TestNothingBypassesTheGate:
    def test_no_module_opens_its_own_connection(self):
        """The whole invariant, in one assertion.

        If this fails, the fix is not to add the module to LOCAL_ONLY. It is to
        route the request through ``EgressGate``. LOCAL_ONLY is for destinations
        that provably cannot leave the machine — loopback, and nothing else.
        """
        offenders: list[str] = []

        for path in _product_files():
            rel = path.relative_to(BACKEND).as_posix()
            if rel in LOCAL_ONLY:
                continue
            for lineno, expr in _outbound_calls_in(path):
                offenders.append(f"  {rel}:{lineno} — {expr}(…)")

        assert not offenders, (
            "These modules open outbound connections without going through "
            "EgressGate, which makes Rule 3 unenforceable:\n\n"
            + "\n".join(sorted(offenders))
            + "\n\nRoute them through `core.egress.EgressGate`. Only add to "
              "LOCAL_ONLY if the destination is loopback and cannot leave the "
              "machine."
        )

    def test_local_only_entries_still_exist(self):
        """A stale exemption is a hole nobody is looking at."""
        missing = [rel for rel in LOCAL_ONLY if not (BACKEND / rel).exists()]
        assert not missing, (
            f"LOCAL_ONLY exempts modules that no longer exist: {missing}. "
            "Remove them, so the list stays a description of reality."
        )

    @pytest.mark.parametrize("rel,reason", sorted(LOCAL_ONLY.items()))
    def test_local_only_entries_really_are_local(self, rel: str, reason: str):
        """Every exemption must be justified by the code, not by the comment.

        Checks that the module contains no remote-looking URL literal. Not
        exhaustive — a URL assembled at runtime would slip past — but it does
        catch the realistic regression, which is somebody adding a cloud
        endpoint to a module that was exempted while it was local.
        """
        source = (BACKEND / rel).read_text(encoding="utf-8")
        suspicious = [
            line.strip()
            for line in source.splitlines()
            if ("https://" in line or "http://" in line)
            and "localhost" not in line
            and "127.0.0.1" not in line
            and not line.strip().startswith("#")
        ]
        assert not suspicious, (
            f"{rel} is exempted from the egress gate as {reason}, but contains "
            f"what looks like a remote URL:\n  " + "\n  ".join(suspicious)
        )
