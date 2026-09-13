"""The project's installed libraries — read from the machine, never downloaded.

The hallucination problem, and where its answer already is
---------------------------------------------------------
A model writes `useFormState` against React 19, or `app.add_event_handler`
against a FastAPI that removed it, because it is answering from training data
about a version that is not the one in front of it. Every other coding agent
answers that by piping documentation in from a cloud service, or by asking the
person to attach the docs. Neither is needed. **The project's dependencies are
installed on this machine, at the exact version the project uses**, and an
installed package is documentation: its `package.json` and `.dist-info` say
the version, its `.d.ts` and `.pyi` and source say every signature, its
docstrings and JSDoc say what they mean, and its README says how it is meant to
be used. Reading that is deterministic, local, needs no download, and carries
provenance to a file — rule 2 for a library the same way `readiness.py:156`
is provenance for the project's own code.

Three things this module gives the model, in order of how cheaply each stops
a hallucination:

1. **The versions, in the briefing.** *"react 19.1.0, vite 6.3.5, fastapi
   0.139.0"* under the repository map. Most wrong APIs are version drift, and
   a model told the version reaches for the right one without a lookup.
2. **`find_symbol`** — the real definition of a name, from the installed
   package: signature, its docstring or JSDoc, the file and line. A model
   that is not sure how a function is called looks rather than guesses; that
   is rule 9 (fail rather than invent) with somewhere to look.
3. **`read_library_docs`** — the head of a package's README, for "how is this
   used at all".

What is read and what is deliberately not
-----------------------------------------
Node: `node_modules/<name>` for every dependency in `package.json`, reading
`.d.ts` first (the declared surface) and `.js`/`.ts` only when no declaration
answered. Python: the project's own interpreter's `site-packages` — resolved
through the same `_python_for` the runners use, so it is the environment the
tests run in and never Zaram's own — reading `.pyi` first, then `.py`.
Cargo and Go: versions from the lock file, no source lookup yet; saying
"version known, definitions not" beats guessing at a registry path.

`ingest` skips `node_modules` and `venv` on purpose, and that stays: the
project's own index must not fill with a thousand chunks of somebody else's
library competing with the user's code for every retrieval slot. This is a
*lookup*, not an index — nothing here enters the Spine — and it is scoped to
the project whose folder is open, because a symbol resolved against the
wrong project's `node_modules` is a confident wrong answer.

Bounded, like every read the pack makes: files per package, bytes per file,
matches per lookup, lines per signature. A definition the caps cut off says
so and names the file, which `read_lines` cannot open (it is outside the
project root) but a person can.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from runtimes.mcp.client import ToolDescriptor

from .runners import _python_for

logger = logging.getLogger(__name__)

FIND_SYMBOL = "find_symbol"
READ_LIBRARY_DOCS = "read_library_docs"
TOOL_NAMES = frozenset({FIND_SYMBOL, READ_LIBRARY_DOCS})

#: Tokens the library list may take in the briefing.
LIST_TOKENS = 300
#: How many libraries the briefing names before saying "and N more".
LIST_LIMIT = 40

#: Caps on a lookup.
MAX_FILES_PER_PACKAGE = 400
MAX_FILE_BYTES = 600_000
MAX_MATCHES = 5
SIGNATURE_LINES = 8
DOC_LINES = 14
README_LINES = 80

#: A lookup that has not named a package stops here and says so. Measured
#: 13 September on Zaram's own backend: an unqualified `find_symbol("Depends")`
#: across ~200 installed distributions, torch among them, took 69 s. Eight
#: seconds and three thousand files is more than any qualified lookup needs
#: and less than a person will wait.
LOOKUP_SECONDS = 8.0
LOOKUP_FILES = 3000

#: Folders inside a package that hold nothing a lookup wants.
_SKIP_IN_PACKAGE = frozenset({
    "node_modules", "test", "tests", "__tests__", "__pycache__", "dist", "build",
    "esm", "cjs", "umd", "lib-esm", ".git", "docs", "examples", "benchmark",
})

_DEF_JS = re.compile(
    r"^\s*(?:export\s+)?(?:declare\s+)?(?:default\s+)?"
    r"(?:async\s+)?(?:function\s*\*?|class|interface|type|enum|namespace|const|let|var)\s+"
    r"(?P<name>[A-Za-z_$][\w$]*)"
)
_DEF_PY = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+(?P<name>\w+)")
_DEF_RS = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:fn|struct|enum|trait|type|const|static)\s+(?P<name>\w+)")


@dataclass(frozen=True)
class Library:
    name: str
    version: str
    ecosystem: str
    #: Where the installed package lives, or ``None`` when only the version is
    #: known (a lock file with no resolvable source).
    path: Optional[Path]
    #: Python: the importable top-level names the distribution provides, which
    #: may differ from the distribution name (`pillow` → `PIL`).
    modules: Tuple[str, ...] = ()

    def to_json(self) -> Dict[str, Any]:
        return {"name": self.name, "version": self.version, "ecosystem": self.ecosystem, "installed": self.path is not None}


#: Keyed by root, holding the manifest fingerprint the table was built from.
#: Rebuilt when a manifest or an install folder changes, never on a clock:
#: resolving Zaram's own backend takes ~9 s, which is fine once and not fine
#: every thirty seconds.
_cache: Dict[str, Tuple[Tuple[Tuple[str, float], ...], Tuple[Library, ...]]] = {}

_MANIFESTS = ("package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
              "pyproject.toml", "Cargo.lock", "go.mod", "node_modules", "venv", ".venv")


def _fingerprint(root: Path) -> Tuple[Tuple[str, float], ...]:
    stamps: List[Tuple[str, float]] = []
    for name in _MANIFESTS:
        path = root / name
        try:
            stamps.append((name, path.stat().st_mtime))
        except OSError:
            continue
    for req in sorted(root.glob("requirements*.txt")):
        try:
            stamps.append((req.name, req.stat().st_mtime))
        except OSError:
            continue
    return tuple(stamps)


def forget(root: Optional[Path] = None) -> None:
    if root is None:
        _cache.clear()
    else:
        _cache.pop(str(root.resolve()), None)


# --------------------------------------------------------------- resolution

def libraries_for(root: Path) -> Tuple[Library, ...]:
    key = str(root.resolve())
    stamp = _fingerprint(root)
    cached = _cache.get(key)
    if cached and cached[0] == stamp:
        return cached[1]
    found: List[Library] = []
    try:
        found.extend(_node_libraries(root))
        found.extend(_python_libraries(root))
        found.extend(_lockfile_only(root))
    except Exception:  # noqa: BLE001 - a library list must never fail a reply
        logger.exception("code pack: could not resolve the project's libraries")
    table = tuple(sorted(found, key=lambda l: (l.ecosystem, l.name.lower())))
    _cache[key] = (stamp, table)
    return table


def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _node_libraries(root: Path) -> Iterable[Library]:
    manifest = _read_json(root / "package.json")
    if manifest is None:
        return []
    wanted: List[str] = []
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        section = manifest.get(key)
        if isinstance(section, dict):
            wanted.extend(str(n) for n in section)
    out: List[Library] = []
    modules = root / "node_modules"
    for name in sorted(set(wanted)):
        folder = modules / name
        installed = _read_json(folder / "package.json") if folder.is_dir() else None
        version = str(installed.get("version") or "") if installed else ""
        out.append(Library(name, version or "not installed", "node", folder if installed else None))
    return out


def _python_libraries(root: Path) -> Iterable[Library]:
    wanted = _python_requirements(root)
    if not wanted:
        return []
    site = _site_packages(root)
    installed: Dict[str, Tuple[str, Path, Tuple[str, ...]]] = {}
    if site is not None:
        for info in site.glob("*.dist-info"):
            meta = _dist_metadata(info)
            if meta:
                installed[_norm(meta[0])] = (meta[1], site, _top_level(info, site))
    out: List[Library] = []
    for name in sorted(set(wanted), key=str.lower):
        hit = installed.get(_norm(name))
        if hit:
            version, base, modules = hit
            out.append(Library(name, version, "python", base, modules))
        else:
            out.append(Library(name, "not installed", "python", None))
    return out


def _python_requirements(root: Path) -> List[str]:
    names: List[str] = []
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            import tomllib

            data = tomllib.loads(pyproject.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001 - a broken manifest lists nothing
            data = {}
        project = data.get("project") if isinstance(data, dict) else None
        if isinstance(project, dict):
            for spec in project.get("dependencies") or []:
                names.append(_requirement_name(str(spec)))
            optional = project.get("optional-dependencies")
            if isinstance(optional, dict):
                for specs in optional.values():
                    for spec in specs or []:
                        names.append(_requirement_name(str(spec)))
    for req in sorted(root.glob("requirements*.txt")):
        try:
            for line in req.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith(("#", "-")):
                    names.append(_requirement_name(line))
        except OSError:
            continue
    return [n for n in names if n]


def _requirement_name(spec: str) -> str:
    return re.split(r"[\s\[<>=!~;@]", spec.strip(), 1)[0]


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _site_packages(root: Path) -> Optional[Path]:
    """The project's own environment, never Zaram's."""
    argv = _python_for(root)
    if not argv:
        return None
    exe = Path(argv[0])
    # venv/Scripts/python.exe → venv/Lib/site-packages ; venv/bin/python → venv/lib/pythonX.Y/site-packages
    env = exe.parent.parent
    for candidate in (env / "Lib" / "site-packages", *sorted(env.glob("lib/python*/site-packages"))):
        if candidate.is_dir():
            return candidate
    return None


def _dist_metadata(info: Path) -> Optional[Tuple[str, str]]:
    try:
        name = version = ""
        with (info / "METADATA").open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if line.startswith("Name:"):
                    name = line[5:].strip()
                elif line.startswith("Version:"):
                    version = line[8:].strip()
                if name and version:
                    break
                if not line.strip():
                    break
        return (name, version) if name else None
    except OSError:
        return None


def _top_level(info: Path, site: Path) -> Tuple[str, ...]:
    try:
        text = (info / "top_level.txt").read_text(encoding="utf-8", errors="replace")
        names = tuple(n.strip() for n in text.splitlines() if n.strip())
        if names:
            return names
    except OSError:
        pass
    # No top_level.txt: guess from the distribution name, which is right for
    # most packages and wrong for `pillow`, which ships the file.
    stem = info.name.split("-", 1)[0]
    return (stem,) if (site / stem).is_dir() or (site / f"{stem}.py").is_file() else ()


def _lockfile_only(root: Path) -> Iterable[Library]:
    out: List[Library] = []
    cargo = root / "Cargo.lock"
    if cargo.is_file():
        try:
            text = cargo.read_text(encoding="utf-8", errors="replace")
            for name, version in re.findall(r'\[\[package\]\]\s*name = "([^"]+)"\s*version = "([^"]+)"', text):
                out.append(Library(name, version, "cargo", None))
        except OSError:
            pass
    gomod = root / "go.mod"
    if gomod.is_file():
        try:
            for line in gomod.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"^\s*([\w./~-]+)\s+(v[\w.+-]+)", line)
                if m and "/" in m.group(1):
                    out.append(Library(m.group(1), m.group(2), "go", None))
        except OSError:
            pass
    return out


# ----------------------------------------------------------------- briefing

def briefing(root: Path, *, budget_tokens: int = LIST_TOKENS) -> str:
    from core.context_budget import estimate_tokens

    libs = libraries_for(root)
    if not libs:
        return ""
    parts: List[str] = []
    spent = 0
    shown = 0
    for lib in libs:
        entry = f"{lib.name} {lib.version}"
        cost = estimate_tokens(entry) + 1
        if shown >= LIST_LIMIT or spent + cost > budget_tokens:
            break
        parts.append(entry)
        spent += cost
        shown += 1
    more = len(libs) - shown
    lines = [
        "",
        "## Installed libraries",
        "",
        "The project's dependencies, at the versions actually installed here. "
        "Write against these versions. `find_symbol` shows a name's real "
        "definition from the installed package; `read_library_docs` shows a package's README.",
        "",
        ", ".join(parts) + (f", and {more} more" if more > 0 else ""),
    ]
    return "\n".join(lines) + "\n"


# -------------------------------------------------------------------- tools

class LibraryTools:
    """`find_symbol` and `read_library_docs`, over the open project's dependencies."""

    def descriptors(self, server_id: str) -> List[ToolDescriptor]:
        return [
            ToolDescriptor(
                server_id=server_id,
                name=FIND_SYMBOL,
                description=(
                    "Find the real definition of a function, class, hook, type or constant in one of the "
                    "project's installed libraries: its signature, its documentation, and the file it is "
                    "in. Use it before calling a library API you are not certain of, instead of guessing."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "The symbol to find, e.g. useEffect or FastAPI."},
                        "package": {"type": "string", "description": "Limit to one library, by its dependency name."},
                    },
                    "required": ["name"],
                },
            ),
            ToolDescriptor(
                server_id=server_id,
                name=READ_LIBRARY_DOCS,
                description=(
                    "Read the start of an installed library's README and its installed version — "
                    "how the library is meant to be used."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "package": {"type": "string", "description": "The dependency name, e.g. react or fastapi."},
                    },
                    "required": ["package"],
                },
            ),
        ]

    def call(self, name: str, arguments: Dict[str, Any], root: Path) -> Dict[str, Any]:
        libs = libraries_for(root)
        if name == READ_LIBRARY_DOCS:
            return self._docs(libs, str(arguments.get("package") or ""))
        if name == FIND_SYMBOL:
            return self._find(libs, str(arguments.get("name") or ""), str(arguments.get("package") or ""))
        return {"error": f"no tool called {name!r}"}

    # ------------------------------------------------------------ docs

    def _docs(self, libs: Tuple[Library, ...], package: str) -> Dict[str, Any]:
        if not package.strip():
            return {"error": "no package was named"}
        lib = _by_name(libs, package)
        if lib is None:
            return {"error": f"{package} is not a dependency of this project. Installed: {_names(libs)}"}
        if lib.path is None:
            return {"package": lib.name, "version": lib.version, "error": f"{lib.name} is not installed here, so there is nothing to read"}
        readme = _readme_of(lib)
        if readme is None:
            return {"package": lib.name, "version": lib.version, "note": "no README in the installed package"}
        lines = readme.read_text(encoding="utf-8", errors="replace").splitlines()
        return {
            "package": lib.name,
            "version": lib.version,
            "path": str(readme),
            "text": "\n".join(lines[:README_LINES]),
            "truncated": len(lines) > README_LINES,
        }

    # ------------------------------------------------------------ find

    def _find(self, libs: Tuple[Library, ...], symbol: str, package: str) -> Dict[str, Any]:
        symbol = symbol.strip()
        if not symbol or not re.match(r"^[A-Za-z_$][\w$]*$", symbol):
            return {"error": "name must be a single identifier"}
        if package.strip():
            one = _by_name(libs, package)
            if one is None:
                return {"error": f"{package} is not a dependency of this project. Installed: {_names(libs)}"}
            candidates = [one]
        else:
            candidates = [l for l in libs if l.path is not None]
        if not candidates:
            return {"error": "no installed libraries to look in"}

        matches: List[Dict[str, Any]] = []
        started = time.monotonic()
        scanned = 0
        for lib in candidates:
            for path in _reference_files(lib):
                scanned += 1
                if scanned > LOOKUP_FILES or time.monotonic() - started > LOOKUP_SECONDS:
                    return {
                        "symbol": symbol,
                        "matches": matches,
                        "truncated": True,
                        "note": f"stopped after {scanned} files across {lib.name} and earlier packages; name the package to narrow it",
                    }
                for hit in _definitions_in(path, symbol):
                    hit.update({"package": lib.name, "version": lib.version})
                    matches.append(hit)
                    if len(matches) >= MAX_MATCHES:
                        return {"symbol": symbol, "matches": matches, "truncated": True, "note": f"stopped at {MAX_MATCHES}; name the package to narrow it"}
        if not matches:
            searched = ", ".join(l.name for l in candidates[:12]) + (" …" if len(candidates) > 12 else "")
            return {"symbol": symbol, "matches": [], "note": f"no definition of {symbol} in {searched}"}
        return {"symbol": symbol, "matches": matches, "truncated": False}


def _names(libs: Tuple[Library, ...]) -> str:
    return ", ".join(l.name for l in libs[:30]) + (" …" if len(libs) > 30 else "") or "none"


def _by_name(libs: Tuple[Library, ...], package: str) -> Optional[Library]:
    wanted = _norm(package)
    for lib in libs:
        if _norm(lib.name) == wanted or wanted in {_norm(m) for m in lib.modules}:
            return lib
    return None


def _readme_of(lib: Library) -> Optional[Path]:
    if lib.path is None:
        return None
    if lib.ecosystem == "node":
        for candidate in ("README.md", "readme.md", "README", "Readme.md"):
            if (lib.path / candidate).is_file():
                return lib.path / candidate
        return None
    # Python: the METADATA long description is the README, but a `README` on
    # disk is rarer; fall back to the dist-info's METADATA body.
    for info in lib.path.glob("*.dist-info"):
        if _dist_metadata(info) and _norm(_dist_metadata(info)[0]) == _norm(lib.name):  # type: ignore[index]
            return info / "METADATA"
    return None


def _reference_files(lib: Library) -> Iterable[Path]:
    """The files worth reading for definitions, declared surface first."""
    if lib.path is None:
        return []
    if lib.ecosystem == "node":
        roots = [lib.path]
        # `@types/<name>` beside a JS-only package is where the declarations are.
        types = lib.path.parent / "@types" / lib.name.split("/")[-1]
        if types.is_dir():
            roots.append(types)
        first = (".d.ts", ".d.mts", ".d.cts")
        second = (".ts", ".tsx", ".mjs", ".js")
    elif lib.ecosystem == "python":
        roots = []
        for module in lib.modules or (lib.name,):
            if (lib.path / module).is_dir():
                roots.append(lib.path / module)
            elif (lib.path / f"{module}.py").is_file():
                roots.append(lib.path / f"{module}.py")
        first = (".pyi",)
        second = (".py",)
    else:
        return []

    ordered: List[Path] = []
    later: List[Path] = []
    count = 0
    for base in roots:
        if base.is_file():
            ordered.append(base)
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_IN_PACKAGE and not d.startswith("."))
            for filename in sorted(filenames):
                path = Path(dirpath) / filename
                if filename.endswith(first):
                    ordered.append(path)
                elif filename.endswith(second):
                    later.append(path)
                count += 1
                if count >= MAX_FILES_PER_PACKAGE:
                    return ordered + later
    return ordered + later


def _definitions_in(path: Path, symbol: str) -> List[Dict[str, Any]]:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return []
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    suffix = path.suffix.lower()
    pattern = _DEF_PY if suffix in (".py", ".pyi") else _DEF_RS if suffix == ".rs" else _DEF_JS
    out: List[Dict[str, Any]] = []
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if not match or match.group("name") != symbol:
            continue
        signature = _signature(lines, index)
        doc = _doc_before(lines, index) if suffix not in (".py", ".pyi") else _doc_after(lines, index, len(signature.splitlines()))
        out.append({
            "path": str(path),
            "line": index + 1,
            "signature": signature,
            "doc": doc,
        })
        if len(out) >= MAX_MATCHES:
            break
    return out


def _signature(lines: List[str], start: int) -> str:
    """The definition line and its continuation, until it closes or the cap."""
    taken: List[str] = []
    depth = 0
    for line in lines[start : start + SIGNATURE_LINES]:
        taken.append(line.rstrip())
        depth += line.count("(") - line.count(")")
        stripped = line.rstrip()
        if depth <= 0 and (stripped.endswith((":", ";", "{", "=>")) or "=>" in stripped or stripped.endswith(")")):
            break
    return "\n".join(taken)


def _doc_before(lines: List[str], start: int) -> str:
    """A JSDoc block ending on the line above the definition."""
    end = start - 1
    while end >= 0 and not lines[end].strip():
        end -= 1
    if end < 0 or not lines[end].strip().endswith("*/"):
        return ""
    begin = end
    while begin >= 0 and "/**" not in lines[begin] and end - begin < DOC_LINES:
        begin -= 1
    if begin < 0 or "/**" not in lines[begin]:
        return ""
    block = [re.sub(r"^\s*/?\*+/?\s?", "", l).rstrip() for l in lines[begin : end + 1]]
    return "\n".join(l for l in block if l).strip()


def _doc_after(lines: List[str], start: int, signature_lines: int) -> str:
    """A Python docstring on the lines after the signature."""
    index = start + max(1, signature_lines)
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines):
        return ""
    head = lines[index].strip()
    quote = '"""' if head.startswith('"""') else "'''" if head.startswith("'''") else None
    if quote is None:
        return ""
    body: List[str] = []
    for line in lines[index : index + DOC_LINES]:
        body.append(line.strip())
        if line.strip().endswith(quote) and (len(body) > 1 or line.strip().count(quote) == 2):
            break
    text = "\n".join(body).strip(quote).strip()
    return text
