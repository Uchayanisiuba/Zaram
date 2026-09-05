# backend/tests/test_installer_payload.py
"""What the installer is allowed to carry.

`electron-builder.yml` used to include the backend as one glob — `- backend` —
with four exclusions after it. Three of those exclusions were fine and the set
was wrong in the only direction that matters, because a denylist is wrong
silently:

* `!backend/.venv` does not match `backend/venv`, which is what the directory
  is actually called on a working machine. 376 MB.
* Nothing excluded `backend/spine.db`, `backend/egress.db`,
  `backend/artifacts.db`, `backend/projects.db` or `backend/egress-policy.json`
  — the maintainer's own memory, their append-only record of everything that
  ever left their machine, their generated documents and their per-host privacy
  rules. Every one of those files exists on disk right now.
* `backend/generated/` holds documents the maintainer produced, invoices
  included.

Shipping any of that to a stranger is the exact failure the product exists to
prevent, and it would have shipped without anyone seeing it.

So the config is now an allow-list, and this is the test that keeps it one.
**The polarity is the whole lesson.** `pyproject.toml` argues the opposite case
for test collection — a stale exclusion merely collects extra tests, while a
missing inclusion hides them — and that reasoning is correct there and inverted
here. When the cost of a missing entry is *publishing private data*, the safe
default is to carry nothing nobody named.

This reads the real config rather than a copy. A test asserting a duplicated
list would pass forever while the file it describes drifted.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "electron-builder.yml"

#: Extensions the backend legitimately needs at runtime. Anything else found
#: under `backend/` is a file nobody decided about — see the test below.
CARRIED_SUFFIXES = {".py", ".json", ".txt", ".yaml", ".yml"}

#: Directories that are scratch, tooling or the user's own material. Kept in
#: step with `pyproject.toml`'s `norecursedirs`, which calls the same set
#: "runtime scratch dirs — data, never tests".
NOT_OURS = {
    "venv", ".venv", "tests", "__pycache__", "node_modules", "generated",
    "audio", "audio_cache", "audio_clips", "audio_output", "image_output",
    "temp", "uploads",
}


def load_patterns() -> tuple[list[str], list[str]]:
    """The `files:` entries, split into includes and exclusions.

    Parsed by hand rather than with PyYAML: the backend does not depend on it,
    and adding a dependency so that a packaging test can read five lines of a
    list would be the wrong trade.
    """
    includes: list[str] = []
    excludes: list[str] = []
    in_files = False

    for raw in CONFIG.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if not raw.startswith((" ", "\t")) and stripped.endswith(":"):
            in_files = stripped == "files:"
            continue
        if not in_files or not stripped.startswith("- "):
            continue

        entry = stripped[2:].strip().strip('"').strip("'")
        # Trailing comments on an entry, e.g. `- "!backend/venv"  # 376 MB`
        if "#" in entry and not entry.startswith("#"):
            entry = entry.split("#", 1)[0].strip().strip('"').strip("'")
        (excludes if entry.startswith("!") else includes).append(entry.lstrip("!"))

    return includes, excludes


def is_excluded(rel_path: str, excludes: list[str]) -> bool:
    """True when the path, or any directory above it, is excluded.

    Mirrors how minimatch-style exclusions behave in electron-builder: naming a
    directory removes everything beneath it, not just the directory entry.
    """
    posix = rel_path.replace(os.sep, "/")
    candidates = [posix]
    parts = posix.split("/")
    for i in range(1, len(parts)):
        candidates.append("/".join(parts[:i]))

    for pattern in excludes:
        # In minimatch, `**` matches *zero* or more path segments, so
        # `backend/**/*.db` covers `backend/spine.db`. `fnmatch` has no such
        # rule, so the zero-segment reading is added explicitly — without it
        # this matcher is stricter than the tool it models, and would report a
        # file as shipped when the real build excludes it.
        forms = {pattern, pattern.replace("/**/", "/")}
        if pattern.startswith("**/"):
            forms.add(pattern[3:])
        for form in forms:
            for candidate in candidates:
                if fnmatch.fnmatch(candidate, form):
                    return True
    return False


@pytest.fixture(scope="module")
def patterns():
    assert CONFIG.exists(), f"no electron-builder.yml at {CONFIG}"
    includes, excludes = load_patterns()
    assert includes, "parsed no include patterns — the parser or the file moved"
    return includes, excludes


class TestNothingPrivateIsCarried:
    """Named files, because these exist and would have shipped."""

    @pytest.mark.parametrize(
        "path",
        [
            "backend/spine.db",
            "backend/egress.db",
            "backend/egress.db-wal",
            "backend/egress.db-shm",
            "backend/artifacts.db",
            "backend/projects.db",
            "backend/egress-policy.json",
            "backend/generated/invoices-q3.xlsx",
            "backend/venv/Lib/site-packages/torch/__init__.py",
            "backend/.venv/Scripts/python.exe",
            "backend/audio_cache/whatever.wav",
            "backend/uploads/a-client-contract.pdf",
            # 6.9 GB of somebody else's weights, and it is on this machine:
            # `default_model_dir()` is `data_dir()/models/image`, which in a
            # checkout is under `backend/`.
            "backend/models/image/sd_xl_base_1.0.safetensors",
        ],
    )
    def test_it_is_excluded(self, patterns, path):
        _, excludes = patterns
        assert is_excluded(path, excludes), f"{path} would be shipped to every user"

    def test_the_backend_is_not_included_wholesale(self, patterns):
        """`- backend` is what made every file above a default.

        The allow-list only holds while nothing re-adds the directory itself.
        """
        includes, _ = patterns
        assert "backend" not in includes, (
            "electron-builder.yml includes the whole backend directory again — "
            "every database and generated document under it ships by default"
        )


class TestEveryRealFileIsAccountedFor:
    """The allow-list's own failure mode, asserted rather than hoped for.

    An allow-list fails closed, which is why it was chosen — but "fails closed"
    means a data file the backend genuinely reads goes missing from the
    installer and the product breaks on a stranger's machine rather than on
    this one. So the risk is worth a test of its own.
    """

    def test_no_backend_file_has_an_uncarried_extension(self):
        surprises: list[str] = []
        backend = REPO_ROOT / "backend"

        for root, dirs, files in os.walk(backend):
            dirs[:] = [d for d in dirs if d not in NOT_OURS]
            for name in files:
                suffix = Path(name).suffix.lower()
                if suffix in CARRIED_SUFFIXES:
                    continue
                if suffix in {".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3"}:
                    continue  # user data, excluded on purpose and tested above
                if suffix in {".safetensors", ".gguf", ".bin", ".pt", ".onnx"}:
                    # Model weights the user brought, in the same category and
                    # for the same reason: `data_dir()` is `backend/` in a
                    # checkout, so `default_model_dir()` puts an SDXL
                    # checkpoint here. It is excluded on purpose — see
                    # `!backend/models` in electron-builder.yml, asserted above
                    # — and it is emphatically not a file to "add to the
                    # allow-list", which is what this test's message otherwise
                    # advises. That advice would put 6.9 GB in the installer.
                    continue
                if suffix in {".bat", ".md", ".log", ".pyc"}:
                    continue  # tooling and notes; not needed at runtime
                if name == "api-secret":
                    # The API credential's development fallback. It has no
                    # extension deliberately, so the allow-list cannot carry it
                    # and it can never reach an installer — which is the
                    # correct outcome, not an oversight: a packaged build mints
                    # a fresh one per launch, and shipping this would give
                    # every user on earth the same credential.
                    continue
                surprises.append(str(Path(root, name).relative_to(REPO_ROOT)))

        assert not surprises, (
            "the backend carries files the installer's allow-list does not "
            f"cover, so they would be missing at runtime: {surprises[:10]}. "
            "Add the extension to electron-builder.yml and to CARRIED_SUFFIXES, "
            "or move the file out of backend/."
        )
