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
    "runtimes/models/engines/ollama_engine.py": "Ollama on localhost:11434",
    "runtimes/memory/embeddings.py": "Ollama bge-m3 on localhost:11434",
    "providers/discoverers/ollama.py": "Ollama on localhost:11434",
    # Reads the window a model is *loaded* with from Ollama's `/api/ps`, which
    # is the same loopback server the engines above talk to. `base_url` is a
    # parameter, so the module refuses any host that is not loopback rather
    # than trusting its own default -- an exemption written here has to be a
    # fact about the code, not an intention.
    "core/context_budget.py": "Ollama /api/ps on localhost:11434, loopback enforced",
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
    # Ours, and listed here on purpose: it re-exports DDGS, so importing it
    # hands the caller a client that opens its own socket. Tracking only the
    # third-party names would let the indirection erase every caller's entry
    # from this file in a single refactor — which is exactly what happened.
    "core.ddgs_import": "re-exports DDGS, which queries the live DuckDuckGo API",
    "openai": "contacts the OpenAI API",
    "anthropic": "contacts the Anthropic API",
    # Added before the provider that uses it, deliberately. WhisperModel resolves
    # its weights through huggingface_hub and downloads them on first use, which
    # is the exact shape of the defect this list was built for: voice discovery
    # reached HuggingFace on every boot, unlogged, and the only reason anyone
    # noticed was a timeout in the startup log.
    "faster_whisper": "downloads Whisper weights from huggingface.co on first use",
}

#: Modules that import a network library and never run. Dormancy is the strongest
#: justification available short of removal, and it is checked below against the
#: bootstrapper.
#:
#: They are listed rather than fixed because deleting them is a separate
#: decision. What must stay true is that nothing *reachable* acquires an entry
#: here — a reachable module needs the gate, which is the list after this one.
NETWORK_LIBRARY_DORMANT = {
    # `runtimes/internet/connectors.py` and `runtimes/internet/connectors/base.py`
    # were exempted here as "superseded copy; no production module imports it",
    # with a comment saying deleting them was a separate decision. That decision
    # was taken on 19 August and they are gone — `connectors.py` raised
    # `NameError` on import, which is the strongest possible evidence that
    # nothing was using it, and `connectors/base.py` was shadowed by it and
    # imported a `.contracts` that did not exist beside it. Their entries are
    # removed with them, which `test_no_exemption_outlives_the_file_it_excuses`
    # requires:
    # an exemption keyed by a path outlives the file and silently covers
    # whatever is written there next.
    "runtime/discovery/providers/duckduckgo.py": "discovery is unreachable from chat",
}

#: Modules that import a network library, *do* run, and ask the gate before the
#: library can reach anything. A weaker justification than dormancy, so it gets
#: its own assertion rather than a comment: see
#: ``test_gated_exemptions_actually_ask_the_gate``.
#:
#: The distinction exists because the DuckDuckGo entry used to sit in the
#: dormant list claiming to be unreachable, and the claim was false — this
#: file's own suite called search() on every run, so a module exempted for being
#: unreachable was making an unlogged live request from inside the tests. The
#: dormancy guard checks reachability *at boot*, which is why it passed. Two
#: lists with two different tests is what stops that from recurring: a gated
#: module is *expected* to be reachable, and is checked on the property that
#: actually protects the user.
#:
#: The library still opens its own socket in both cases, so the gate cannot
#: carry the bytes. It owns the *decision*, which is the property that matters:
#: ask first, and under default deny the library is never reached.
#: Modules that import a network library **only to re-export it**, and never
#: call it. A third category because the other two do not fit and forcing one
#: would make it a lie: this is not dormant — it is imported by live code — and
#: it cannot ask the gate, because it never reaches the network to be gated.
#:
#: The risk lives entirely with the callers, which are covered by the two lists
#: above. What has to stay true here is the *only* part: the moment such a
#: module starts calling the library, it becomes an ungated network path and
#: `test_reexport_exemptions_never_call_the_library` fails.
#:
#: `core/ddgs_import.py` exists because five modules imported
#: `duckduckgo_search` independently and that package answers successfully with
#: **zero results** against the current endpoints — so web search appeared to
#: work, was logged as allowed, and returned nothing. Centralising the import
#: is what makes "which package are we actually using" a question with one
#: answer.
NETWORK_LIBRARY_REEXPORT = {
    "core/ddgs_import.py": "binds DDGS for callers and never calls it",
}

NETWORK_LIBRARY_GATED = {
    "knowledge/providers/duckduckgo_provider.py": "asks get_gate().check() before constructing DDGS",
    "runtimes/internet/runtime.py": "asks get_gate().check() before constructing DDGS",
    "voice/stt/whisper.py": "asks get_gate().check() before any weight download; loads cached weights offline",
    # Was exempted as dormant, and was not. The bootstrapper reaches it through
    # runtimes.speech.runtime, and health_check() built the pipeline as a side
    # effect of reporting health — so the backend loaded the model and contacted
    # huggingface.co on every single boot, unlogged, while `load_model_eagerly`
    # sat at False and a test asserted dormancy. Same remedy as Whisper: try the
    # cache offline first, ask the gate only when weights are genuinely absent.
    "voice/providers/kokoro.py": "asks get_gate().check() before any weight download; loads cached weights offline",
    # Same posture as the torch provider above, with one addition worth naming.
    # The ONNX pipeline loads a *voice* lazily, at synthesis time, from inside
    # __call__ — which is outside the window KokoroProvider._ensure_pipeline
    # wraps. So every fetch it makes (graph, voices, vocabulary) goes through one
    # helper that tries the cache offline first and asks the gate only when there
    # is genuinely something to download. The torch path still has that hole:
    # KPipeline.load_voice downloads a .pt on first use with nothing asked.
    "voice/providers/kokoro_onnx.py": "asks get_gate().check() before any weight, voice or vocab download; loads cached files offline",
}

#: Modules that import a network library **in order to switch its network off**.
#:
#: A different and stronger claim than "gated". A gated module asks the gate and
#: then lets the library reach out; these never let it reach out at all, so
#: there is nothing for the gate to be asked about. Asking would in fact be
#: misleading — it would put an entry in the egress log for a request that is
#: structurally impossible.
#:
#: The category exists because `imaging/local_sdxl.py` is the first module with
#: this shape and neither of the existing lists describes it honestly. It is
#: dormant in no sense — it runs on every image request — and it is not gated,
#: because it makes no request to gate.
#:
#: Like the gated list, the reason is asserted rather than believed: see
#: ``test_disarmed_exemptions_actually_disarm_the_library``.
NETWORK_LIBRARY_DISARMED = {
    "imaging/local_flux.py": (
        "imports huggingface_hub only to force it offline; the pipeline is "
        "resolved from a local directory so there is nothing to fetch"
    ),
}

NETWORK_LIBRARY_EXEMPT = {
    **NETWORK_LIBRARY_DORMANT,
    **NETWORK_LIBRARY_GATED,
    **NETWORK_LIBRARY_REEXPORT,
    **NETWORK_LIBRARY_DISARMED,
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
            # `node.level` > 0 is a *relative* import, which can only ever name a
            # sibling module — never a third-party package. Counting them was a
            # false positive with real cost: `from .kokoro import KokoroProvider`
            # in voice/providers/__init__.py was read as the PyPI `kokoro`, and
            # the module was given a standing exemption to silence it. An
            # exemption granted to quiet a scanner bug is a hole that outlives
            # the bug, because nothing revisits it once the noise stops.
            if node.level:
                continue
            # Matched on the full dotted path first, then on the root package.
            #
            # Without the full-path check, centralising an import *launders it
            # past this scanner*: `core/ddgs_import.py` re-exports DDGS, so
            # `from core.ddgs_import import DDGS` has the root `core` and reads
            # as an ordinary internal import while handing the caller a client
            # that opens its own socket. Five modules moved to that import in
            # one change, and all five silently lost their coverage here. A
            # guard that a refactor can switch off is not a guard.
            if node.module in NETWORK_LIBRARIES:
                found.append((node.lineno, node.module))
                continue
            root = node.module.split(".")[0]
            if root in NETWORK_LIBRARIES:
                found.append((node.lineno, root))
    return found


def _module_to_path(dotted: str) -> Path | None:
    """Resolve ``a.b.c`` to the file that defines it, if it is ours.

    Both spellings have to resolve, because both occur: a module file
    (``a/b/c.py``) and a package (``a/b/c/__init__.py``). Returning ``None`` for
    anything outside ``backend/`` is what keeps the walk finite — third-party
    packages are not ours to audit here.
    """
    relative = dotted.replace(".", "/")
    for candidate in (BACKEND / f"{relative}.py", BACKEND / relative / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _local_imports_in(path: Path) -> set[str]:
    """Every dotted module this file imports that resolves inside ``backend/``."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # A relative import. Resolve it against the importing package so
                # `from .connectors import X` inside runtimes/speech is followed;
                # skipping them would leave exactly the hole this walk exists to
                # close, since packages import their own submodules that way.
                package = path.parent
                for _ in range(node.level - 1):
                    package = package.parent
                base = package.relative_to(BACKEND).as_posix().replace("/", ".")
                module = f"{base}.{node.module}" if node.module else base
            elif node.module:
                module = node.module
            else:
                continue
            found.add(module)
            # `from x.y import z` may be importing the submodule `x.y.z` rather
            # than a name defined in `x.y`, and only the filesystem can say.
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


def _reachable_from_boot() -> set[str]:
    """Every product module the bootstrapper can reach, transitively.

    Static and therefore over-approximate: an import inside a function body
    counts as reachable even when the branch never runs. That is the right
    direction to be wrong in. This walk exists because the previous check —
    a string search of one file — reported a module dormant while the backend
    was loading its model and contacting HuggingFace at every startup.
    """
    start = BACKEND / "core" / "bootstrapper.py"
    seen: set[Path] = {start}
    queue = [start]
    while queue:
        current = queue.pop()
        for dotted in _local_imports_in(current):
            resolved = _module_to_path(dotted)
            if resolved is not None and resolved not in seen:
                seen.add(resolved)
                queue.append(resolved)
    return {p.relative_to(BACKEND).as_posix() for p in seen}


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
                ("NETWORK_LIBRARY_DORMANT", NETWORK_LIBRARY_DORMANT),
                ("NETWORK_LIBRARY_GATED", NETWORK_LIBRARY_GATED),
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

    def test_dormant_exemptions_are_not_reachable_at_boot(self):
        """A dormancy exemption is only acceptable while the code never runs.

        Every entry in NETWORK_LIBRARY_DORMANT is justified by being dormant. If
        the bootstrapper reaches one of them, the justification has expired and
        the traffic is real.

        **This used to grep `bootstrapper.py` for a dotted module path, and that
        is how it missed a live one.** The bootstrapper imports
        `runtimes.speech.runtime`, which imports the Kokoro connector, which
        loads the model — so the backend contacted huggingface.co on every boot,
        unlogged, while a test asserting dormancy passed. A one-file string
        search asks whether the bootstrapper *names* the module; the question
        that matters is whether it *reaches* it. So the import graph is walked.

        NETWORK_LIBRARY_GATED is deliberately not checked here: those modules are
        *expected* to run, and asking whether they boot would be asking the wrong
        question of them. What protects the user there is the gate, asserted in
        the next test.
        """
        reachable = sorted(_reachable_from_boot() & set(NETWORK_LIBRARY_DORMANT))
        assert not reachable, (
            "These are exempted from the network-library check on the grounds "
            "that they are dormant, but the bootstrapper reaches them:\n\n"
            + "\n".join(f"  {rel} — {NETWORK_LIBRARY_DORMANT[rel]}" for rel in reachable)
            + "\n\nEither make them genuinely unreachable at boot, or move them "
              "to NETWORK_LIBRARY_GATED and make them ask the gate."
        )

    @pytest.mark.parametrize(
        "rel", sorted(set(NETWORK_LIBRARY_DORMANT) | set(NETWORK_LIBRARY_GATED))
    )
    def test_no_exemption_is_unnecessary(self, rel: str):
        """An exemption for a module that imports nothing is a hole, not a no-op.

        The staleness test above only asks whether the *file* still exists. A
        file that exists but has stopped importing a network library keeps its
        waiver forever — and the day someone adds ``import huggingface_hub`` back
        to it, the scan stays silent because the entry was already there.

        Two such entries were found by hand on 10 August 2026 —
        ``runtimes/speech/connectors/kokoro.py`` and
        ``voice/providers/__init__.py`` imported no network library at all.
        One of them existed only to paper over a **bug in this scanner**, which
        read the relative ``from .kokoro import …`` as the PyPI ``kokoro``. That
        is the worst kind of exemption: granted to silence a false positive,
        outliving the false positive, and covering a real import afterwards.
        """
        imports = _network_imports_in(BACKEND / rel)
        assert imports, (
            f"{rel} is exempted from the network-library check, but imports no "
            "network library. The exemption does nothing today and silently "
            "covers whatever gets added tomorrow.\n\n"
            "Delete the entry. If the scan was wrong about this file, fix the "
            "scan — an exemption granted to quiet a scanner bug outlives the bug."
        )

    @pytest.mark.parametrize("rel,reason", sorted(NETWORK_LIBRARY_GATED.items()))
    def test_gated_exemptions_actually_ask_the_gate(self, rel: str, reason: str):
        """The claim in the reason column, asserted rather than described.

        A gated exemption says the module asks the gate before the library can
        reach anything. Nothing enforced that: the entry was prose, and prose
        survives the deletion of the code it describes. Two things have to hold
        for the exemption to mean anything, and both are checked:

        * ``get_gate()`` is *called* — found in the AST, so a mention in a
          comment or a docstring does not satisfy it, which is precisely how a
          stale justification would otherwise pass;
        * ``EgressDenied`` is named, because a check whose refusal is not handled
          is a crash rather than a policy.

        Not proof that the gate is asked on *every* path — the AST cannot know
        that. It is proof that removing the gate breaks this test, which is what
        a guard is for.
        """
        tree = ast.parse((BACKEND / rel).read_text(encoding="utf-8"), filename=rel)

        calls_gate = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "get_gate"
            for node in ast.walk(tree)
        )
        handles_denial = any(
            isinstance(node, ast.Name) and node.id == "EgressDenied"
            for node in ast.walk(tree)
        )

        assert calls_gate, (
            f"{rel} is exempted from the network-library check because it "
            f"{reason}, but it never calls get_gate(). Either it does ask the "
            "gate by some other route — in which case say so here — or the "
            "exemption is now false and the traffic is unlogged."
        )
        assert handles_denial, (
            f"{rel} calls the gate but never names EgressDenied. Default deny "
            "means refusal is the *common* path, not the exceptional one, and "
            "an unhandled refusal is a 500 where the honest answer is "
            "'unavailable, and here is why'."
        )

    @pytest.mark.parametrize("rel,reason", sorted(NETWORK_LIBRARY_DISARMED.items()))
    def test_disarmed_exemptions_actually_disarm_the_library(self, rel: str, reason: str):
        """The claim asserted, and asserted at the level that actually works.

        A disarmed exemption says the module imports a network library only to
        switch its network off. Two things have to be in the source for that to
        be true, and the second is the one that was got wrong first time:

        * ``HF_HUB_OFFLINE`` appears — the switch is named;
        * ``huggingface_hub.constants`` is imported, because **setting the
          environment variable alone does nothing**. That library reads it once,
          at import, into a module constant, and ``import diffusers`` has
          already done so by the time this code runs. Measured 3 September
          2026: with only the environment variable set, 3.2 MB of tokeniser and
          config files were written into ``~/.cache/huggingface`` during a run
          the suite reported as passing.

        So this asserts the *effective* form of the guard rather than the form
        that reads correctly. A test that accepted the environment variable
        would be the same test that let the original bug through.

        Not proof that nothing reaches the network — the AST cannot know that.
        `test_local_image_generation.py` is the proof, and it gets it by
        blocking sockets for the whole load and sample rather than by
        inspecting a flag.
        """
        source = (BACKEND / rel).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=rel)

        names_the_switch = any(
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "HF_HUB_OFFLINE" in node.value
            for node in ast.walk(tree)
        )
        sets_the_constant = any(
            isinstance(node, (ast.Import, ast.ImportFrom))
            and any(
                "huggingface_hub.constants" in (alias.name or "")
                for alias in node.names
            )
            or (
                isinstance(node, ast.ImportFrom)
                and (node.module or "").startswith("huggingface_hub.constants")
            )
            for node in ast.walk(tree)
        )

        assert names_the_switch, (
            f"{rel} is exempted because it {reason}, but nothing in it names "
            "HF_HUB_OFFLINE. Either the switch moved — in which case say so "
            "here — or the exemption is now false and the library is free to "
            "fetch, unlogged."
        )
        assert sets_the_constant, (
            f"{rel} names HF_HUB_OFFLINE but never touches "
            "huggingface_hub.constants. The environment variable on its own is "
            "read once at import and diffusers has already imported the "
            "library, so a guard that only sets the variable does nothing at "
            "all — which is exactly the bug this entry exists because of."
        )

    @pytest.mark.parametrize("rel,reason", sorted(NETWORK_LIBRARY_REEXPORT.items()))
    def test_reexport_exemptions_never_call_the_library(self, rel: str, reason: str):
        """A re-export module binds the name and does nothing with it.

        That is the whole justification for the exemption: the module cannot
        need the gate because it never reaches the network. The moment it calls
        the library — a convenience wrapper, a health probe, "just one search to
        check it works" — it becomes an ungated outbound path, and the reason in
        the table stops being true while still reading as though it is.

        Checked in the AST rather than by grep so a mention in a docstring does
        not trip it, matching the gated test next door.
        """
        tree = ast.parse((BACKEND / rel).read_text(encoding="utf-8"), filename=rel)

        # Every name this module imports from a known network library.
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in NETWORK_LIBRARIES:
                imported.update(alias.asname or alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in NETWORK_LIBRARIES:
                        imported.add(alias.asname or alias.name.split(".")[0])

        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        } | {
            node.func.value.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
        }

        used = imported & called
        assert not used, (
            f"{rel} is exempted because it {reason}, but it calls "
            f"{', '.join(sorted(used))}. A module that uses a network library "
            "needs the gate; move it to NETWORK_LIBRARY_GATED and make the "
            "claim true."
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
