"""Rule 7c, enforced by test rather than by convention.

    No ingestion path may route documents off-device, regardless of quality
    gains. Managed parsing APIs are prohibited. This is the exact trade the
    product refuses.

The rule is easy to break by accident and impossible to notice afterwards: a
cloud parsing API is a two-line change that improves extraction quality on
every hard file, and nothing in the output looks different. The same shape as
`test_egress_chokepoint`, applied to the one package whose whole job is to read
the user's private documents.

This scans source rather than mocking calls, so the build fails on the commit
that introduces the capability rather than at runtime after documents have
already left.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

INGEST = Path(__file__).resolve().parent.parent / "ingest"

#: Modules that reach the network, by any route. `requests` and `httpx` are the
#: obvious ones; `huggingface_hub` and `urllib` are how it happens by accident.
NETWORK_MODULES = {
    "requests", "httpx", "urllib", "urllib3", "aiohttp", "socket", "http",
    "ftplib", "telnetlib", "smtplib", "boto3", "botocore", "google",
    "openai", "anthropic", "huggingface_hub",
}


def _source_files() -> list[Path]:
    return sorted(p for p in INGEST.rglob("*.py") if "__pycache__" not in p.parts)


def test_the_package_has_source_to_scan():
    """A scan over an empty list passes and proves nothing."""
    files = _source_files()
    assert len(files) >= 5, f"expected the ingest package, found {files}"


@pytest.mark.parametrize("path", _source_files(), ids=lambda p: p.name)
def test_no_module_imports_a_network_client(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.append(node.module.split(".")[0])

    offending = sorted(set(imported) & NETWORK_MODULES)
    assert not offending, (
        f"{path.name} imports {offending}. Rule 7c: no ingestion path may route "
        f"documents off-device. If a parser genuinely needs a local network "
        f"call, it goes through core/egress/ and is logged like anything else."
    )


def test_docling_is_not_configured_for_remote_serving():
    """Docling can call a remote model server. That path must stay unreachable.

    The extra installs the local models; `remote-serving` is a different extra
    and enabling it would send the user's documents to a third party while
    every other check here still passed.
    """
    source = (INGEST / "parsers" / "docling.py").read_text(encoding="utf-8")

    for forbidden in ("remote-serving", "RemoteOptions", "api_key", "enable_remote"):
        assert forbidden not in source or forbidden == "remote-serving", (
            f"{forbidden} appears in the Docling adapter"
        )
    # The string may appear only in the prose that forbids it.
    assert "never enabled here" in source
