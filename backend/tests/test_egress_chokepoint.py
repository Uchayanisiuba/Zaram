"""No outbound HTTP anywhere except the gate.

This is the test that keeps Rule 3 true tomorrow. ``test_egress_gate.py`` proves
the gate behaves correctly; this one proves the gate is the *only* way out, by
reading the source and failing when a module opens its own socket.

Why a source scan rather than a runtime check: the failure being guarded against
is somebody adding a tenth call site six months from now, in a module nobody
thought to cover. A runtime test only sees code it executes. A source scan sees
code that merely exists, which is the point â€” this must fail in CI on the commit
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

#: Libraries that make HTTP requests *inside themselves*.
#:
#: The AST scan below catches a module calling ``urllib`` or ``aiohttp``
#: directly. It cannot see a module calling ``list_repo_files()``, which looks
#: like an ordinary function call and contacts huggingface.co. That gap was not
#: hypothetical: voice discovery was reaching HuggingFace on every single boot,
#: unlogged, and the only reason anyone noticed was a timeout in the startup log.
#:
#: So these are tracked by import. A module that imports one of them can leave
#: the machine without any of the syntax this file otherwise looks for.
NETWORK_LIBRARIES = {
    "huggingface_hub": "contacts huggingface.co to list or download repo files",
    "kokoro": "KPipeline downloads model weights from HuggingFace on first use",
    "duckduckgo_search": "queries the live DuckDuckGo API",
    "ddgs": "queries the live DuckDuckGo API",
    "openai": "contacts the OpenAI API",
    "anthropic": "contacts the Anthropic API",
}

#: Modules permitted to import a network library, each with the reason.
#:
#: Everything here is dormant: voice, the discovery runtime and the internet
#: runtime are all out of scope for v1 and unreachable from the chat path. They
#: are listed rather than fixed because deleting them is a separate decision.
#: What must stay true is that nothing *reachable* acquires an entry here.
NETWORK_LIBRARY_EXEMPT = {
    "knowledge/providers/duckduckgo_provider.py": "dormant: web search is off until policy exists",
    "runtimes/internet/runtime.py": "dormant: internet runtime does not boot",
    "runtimes/internet/connectors.py": "dormant: internet runtime does not boot",
    "runtimes/internet/connectors/base.py": "dormant: internet runtime does not boot",
    "runtime/discovery/providers/duckduckgo.py": "dormant: discovery is unreachable from chat",
    "runtimes/speech/connectors/kokoro.py": "dormant: voice is out of scope for v1",
    # Voice discovery used to contact huggingface.co on every launch. It is
    # exempted here only because `voice_discovery_enabled` now defaults to
    # False â€” see the guard test below, which fails if that default flips back.
    "voice/providers/kokoro.py": "voice discovery is off by default; model load is lazy",
    "voice/providers/__init__.py": "re-export only; the provider itself is exempted above",
}

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


def _network_imports_in(path: Path) -> list[tuple[int, str]]:
    """Every import of a library that makes its own requests, as (line, library)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in NETWORK_LIBRARIES:
                    found.append((node.lineno, root))
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in NETWORK_LIBRARIES:
                found.append((node.lineno, root))
    return found


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
        that provably cannot leave the machine â€” loopback, and nothing else.
        """
        offenders: list[str] = []

        for path in _product_files():
            rel = path.relative_to(BACKEND).as_posix()
            if rel in LOCAL_ONLY:
                continue
            for lineno, expr in _outbound_calls_in(path):
                offenders.append(f"  {rel}:{lineno} â€” {expr}(â€¦)")

        assert not offenders, (
            "These modules open outbound connections without going through "
            "EgressGate, which makes Rule 3 unenforceable:\n\n"
            + "\n".join(sorted(offenders))
            + "\n\nRoute them through `core.egress.EgressGate`. Only add to "
              "LOCAL_ONLY if the destination is loopback and cannot leave the "
              "machine."
        )

    def test_no_exemption_outlives_the_file_it_excuses(self):
        """An exemption for a file that no longer exists is a hole waiting to open.

        Both lists are keyed by path. When a module is deleted or moved, its
        entry stays behind and keeps matching nothing â€” until somebody recreates
        that path, at which point it silently inherits a waiver nobody granted
        it. The deletion of the two orphaned Kokoro copies is what surfaced this:
        removing the files left two entries here that no test would have flagged.
        """
        stale = [
            f"  {rel} ({listname})"
            for listname, entries in (
                ("LOCAL_ONLY", LOCAL_ONLY),
                ("NETWORK_LIBRARY_EXEMPT", NETWORK_LIBRARY_EXEMPT),
            )
            for rel in entries
            if not (BACKEND / rel).exists()
        ]

        assert not stale, (
            "These exemptions name files that do not exist:\n\n"
            + "\n".join(sorted(stale))
            + "\n\nDelete the entry. Leaving it means a future file at the same "
              "path is exempted by accident."
        )

    def test_no_unexpected_module_imports_a_network_library(self):
        """The hole the AST scan cannot see.

        A library that makes its own HTTP requests leaves no syntax for the scan
        above to match â€” ``list_repo_files(repo_id)`` looks like any other call.
        This catches them by import instead.
        """
        offenders: list[str] = []

        for path in _product_files():
            rel = path.relative_to(BACKEND).as_posix()
            if rel in NETWORK_LIBRARY_EXEMPT:
                continue
            for lineno, lib in _network_imports_in(path):
                offenders.append(f"  {rel}:{lineno} â€” {lib} ({NETWORK_LIBRARIES[lib]})")

        assert not offenders, (
            "These modules import a library that makes its own network requests, "
            "which the gate cannot see or log:\n\n"
            + "\n".join(sorted(offenders))
            + "\n\nEither route the traffic through EgressGate, or â€” if the code "
              "is dormant â€” add it to NETWORK_LIBRARY_EXEMPT with the reason."
        )

    def test_network_library_exemptions_are_not_reachable_at_boot(self):
        """An exemption is only acceptable while the code never runs.

        Every entry in NETWORK_LIBRARY_EXEMPT is justified by being dormant. If
        one of them is imported by the bootstrapper's live path, the
        justification has expired and the traffic is real.
        """
        boot = (BACKEND / "core" / "bootstrapper.py").read_text(encoding="utf-8")
        reachable = [
            rel
            for rel in NETWORK_LIBRARY_EXEMPT
            if rel.replace("/", ".")[:-3] in boot
        ]
        assert not reachable, (
            "These are exempted from the network-library check on the grounds "
            f"that they are dormant, but the bootstrapper imports them: {reachable}"
        )

    def test_voice_discovery_stays_off_by_default(self):
        """The specific regression that was live until this test existed.

        Kokoro voice discovery lists a HuggingFace repo, which contacts
        huggingface.co. It defaulted to on, so every launch made an unlogged
        outbound request before any policy had been consulted â€” found only
        because the connection timed out and left a line in the startup log.

        The exemption above is conditional on this default. If it flips back,
        the exemption becomes false and this fails.
        """
        from voice.config import KokoroConfig

        assert KokoroConfig.voice_discovery_enabled is False, (
            "Voice discovery contacts huggingface.co at startup. It must stay "
            "off by default, or Zaram makes an unlogged request on every launch."
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
        exhaustive â€” a URL assembled at runtime would slip past â€” but it does
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
