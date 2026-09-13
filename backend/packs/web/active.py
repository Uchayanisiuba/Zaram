"""The URLs the person named in the request in flight.

A `ContextVar`, for the reason `packs/code/active.py` gives: two requests
are in flight the moment a second window exists, and a global would let one
person's named page be read on the other's behalf. Set once per request by
the chat endpoint from the message *as typed*; read by `WebTools` to build
the grant. The model cannot add to it — there is no tool for that, which is
the point.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from typing import FrozenSet, Iterable
from urllib.parse import urlsplit, urlunsplit

__all__ = ["set_named_urls", "named_urls", "urls_in", "normalise"]

_NAMED: ContextVar[FrozenSet[str]] = ContextVar("zaram_web_named_urls", default=frozenset())

#: A URL with a scheme, or a bare host with a dot and an optional path —
#: "pmnewsnigeria.com" is how people write it. Trailing punctuation that is
#: sentence, not address, is trimmed afterwards.
_URL = re.compile(
    r"(?:https?://[^\s<>\"']+)"
    r"|(?:\b(?:www\.)?[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+"
    r"(?:/[^\s<>\"']*)?)",
    re.IGNORECASE,
)
#: Bare hosts are only read as addresses when they end in something that
#: is a top-level domain rather than a filename — `calc.py` is not a site.
_NOT_A_TLD = frozenset({
    "py", "js", "ts", "tsx", "jsx", "json", "md", "txt", "csv", "html", "css",
    "yml", "yaml", "toml", "ini", "cfg", "log", "png", "jpg", "jpeg", "gif",
    "pdf", "docx", "xlsx", "zip", "exe", "sh", "bat", "ps1", "db", "sql",
})


def normalise(url: str) -> str:
    """One spelling per address, so the grant and the fetch agree byte for
    byte: scheme added when missing, host lowercased, no trailing slash on
    a bare host, fragment dropped."""
    text = url.strip().rstrip(".,;:!?)]}'\"")
    if not re.match(r"^https?://", text, re.IGNORECASE):
        text = "https://" + text
    parts = urlsplit(text)
    host = (parts.hostname or "").lower()
    if parts.port:
        host = f"{host}:{parts.port}"
    path = parts.path or ""
    if path == "/":
        path = ""
    return urlunsplit((parts.scheme.lower(), host, path, parts.query, ""))


def urls_in(text: str) -> FrozenSet[str]:
    """Every address in a message, normalised. Bare hosts whose last label is
    a file extension are not addresses."""
    found = set()
    for match in _URL.finditer(text or ""):
        raw = match.group(0)
        if not re.match(r"^https?://", raw, re.IGNORECASE):
            host = raw.split("/", 1)[0]
            if host.rsplit(".", 1)[-1].lower() in _NOT_A_TLD:
                continue
        try:
            found.add(normalise(raw))
        except ValueError:
            continue
    return frozenset(found)


def set_named_urls(text: str) -> None:
    """Record the addresses in the person's own message, for this request."""
    _NAMED.set(urls_in(text))


def named_urls() -> FrozenSet[str]:
    return _NAMED.get()


def _iter(urls: Iterable[str]) -> FrozenSet[str]:
    return frozenset(normalise(u) for u in urls if u)
