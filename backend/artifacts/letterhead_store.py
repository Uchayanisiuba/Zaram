"""Where the user's letterhead is kept between documents.

`letterhead.py` has been able to put a logo and an address on every generated
document since it was written. Nothing ever supplied one. `Letterhead(...)` is
constructed in exactly two places in `main.py`, both from per-request fields,
both without a logo — and the comment there says why: *"where branding is
captured is an open decision"*. It is not open any more; `docs/MILESTONES.md`
settled it under *"Where branding is captured — decided, not yet built"*, and
this is the *not yet built* half.

**Global scope, and rule 7i is what decides that.** A letterhead is about the
user, not about the work — the same person's name and mark go on a proposal for
one client and an invoice to another. A per-project override belongs to someone
genuinely trading under two names, and it is not built here; the field it would
key on does not exist yet, and inventing it now would be a schema guessed ahead
of the case.

**A file of its own, not a key in `settings.json`.** The logo is a base64
`data:` URI and may be most of a megabyte. `settings.json` is read to answer
"which model, which voice, is search on" — questions asked constantly and on
paths that must stay cheap. Putting a megabyte in front of them would make every
one of those reads pay for a picture nobody asked about.

**What this is not.** It is not the only way in, and it must not become one.
The decision on record is that a letterhead is captured *in chat* — drop a logo
in the composer and say "use this as my letterhead" — and offered at the moment
of doubt, the first time a document is generated without one. Rule 7e is
explicit that a form filled in before the first document is the wrong shape.
This store is what those routes write to, and what Settings shows afterwards.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from .letterhead import Letterhead

logger = logging.getLogger(__name__)

DEFAULT_FILE_NAME = "letterhead.json"

#: The longest business name kept. Bounded for the reason the manner is
#: bounded in `user_settings`: this string is rendered into a document that
#: leaves the machine, and an unbounded one is the cheapest way to break a
#: masthead's layout.
MAX_NAME_CHARS = 120

#: The longest single address line, and how many are kept.
MAX_LINE_CHARS = 120
MAX_LINES = 8


class LetterheadStore:
    """The user's branding, loaded once and written atomically.

    Mirrors `UserSettings` deliberately — same load-defensively, same
    temp-file-and-replace, same "a file written by a newer version must not
    stop an older one starting". Two stores in one product that disagree about
    how they survive a half-written file is a bug waiting for a power cut.
    """

    def __init__(self, path: str):
        self._path = path
        self._name = ""
        self._lines: List[str] = []
        self._logo = ""
        self._load()

    @property
    def name(self) -> str:
        return self._name

    @property
    def lines(self) -> List[str]:
        return list(self._lines)

    @property
    def logo(self) -> str:
        """The `data:` URI, or empty. Never a path and never a URL — see
        `letterhead.logo_data_uri`, which is the only thing that may produce
        this value."""
        return self._logo

    def is_empty(self) -> bool:
        return not (self._name or self._lines or self._logo)

    def as_letterhead(self) -> Optional[Letterhead]:
        """What `render_document` takes, or None when nothing is configured.

        None rather than an empty `Letterhead`, because the masthead already
        distinguishes them: given a letterhead object it renders a `who` block,
        and given None it renders a titled document under a rule. An empty
        object would produce an empty div where the branding goes.
        """
        if self.is_empty():
            return None
        return Letterhead(name=self._name, lines=tuple(self._lines), logo=self._logo)

    def set_identity(
        self, *, name: Optional[str] = None, lines: Optional[List[str]] = None
    ) -> None:
        """Set the name, the address lines, or both. None leaves a field alone.

        None and empty are different answers and both are honoured: passing
        `""` clears the name, passing nothing keeps it. A store where clearing
        is impossible is one where a typo in a business name is permanent.
        """
        if name is not None:
            self._name = " ".join(name.split())[:MAX_NAME_CHARS]
        if lines is not None:
            self._lines = [
                " ".join(str(line).split())[:MAX_LINE_CHARS]
                for line in lines[:MAX_LINES]
                if str(line).strip()
            ]
        self._save()

    def set_logo(self, data_uri: str) -> None:
        """Store a logo already validated by `logo_data_uri`.

        **Validation is not repeated here and must not move here.**
        `letterhead.logo_data_uri` owns the rules — which types, how large, why
        SVG is refused — and its refusals are written as sentences for the user.
        A second check in the store would be a second place for those rules to
        drift, which is the failure `theme.py` and the default-voice constant
        were both written to end.
        """
        self._logo = data_uri or ""
        self._save()

    def clear_logo(self) -> None:
        self._logo = ""
        self._save()

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self._name, "lines": list(self._lines), "logo": self._logo}

    def describe(self) -> Dict[str, Any]:
        """The same thing without the logo's bytes, for an interface.

        Settings needs to know a logo *exists* and how big it is far more often
        than it needs the pixels, and a list endpoint that returns a megabyte
        per call is one nobody can poll. `has_logo` plus a size is what a
        control needs to render "Replace" rather than "Add".
        """
        return {
            "name": self._name,
            "lines": list(self._lines),
            "has_logo": bool(self._logo),
            "logo_bytes": len(self._logo),
        }

    # -------------------------------------------------------------- internals

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            logger.warning("letterhead file unreadable, using defaults", exc_info=True)
            return
        if not isinstance(raw, dict):
            return

        name = raw.get("name")
        if isinstance(name, str):
            self._name = " ".join(name.split())[:MAX_NAME_CHARS]

        lines = raw.get("lines")
        if isinstance(lines, list):
            self._lines = [
                " ".join(str(line).split())[:MAX_LINE_CHARS]
                for line in lines[:MAX_LINES]
                if isinstance(line, str) and line.strip()
            ]

        # **Read strictly, and this is the one that matters.** The value is
        # interpolated into an `<img src>` in a document, so a file on disk
        # that has been edited by hand — or by anything else running as this
        # user — must not be able to put a `https://` or a `javascript:` there.
        # `check-no-remote-assets.mjs` scans source and cannot see a JSON file,
        # so the check has to happen where the value is read.
        logo = raw.get("logo")
        if isinstance(logo, str) and logo.startswith("data:image/"):
            self._logo = logo

    def _save(self) -> None:
        tmp = self._path + ".tmp"
        parent = os.path.dirname(os.path.abspath(self._path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        os.replace(tmp, self._path)


def default_letterhead_path() -> str:
    """Beside the other user-level state, and overridable the same way.

    Derived from `default_settings_path` rather than recomputed, for the reason
    that function gives for deriving from the egress policy: two modules
    independently working out "the data directory" is how they come to disagree
    about it.
    """
    from core.user_settings import default_settings_path

    return os.environ.get(
        "ZARAM_LETTERHEAD",
        os.path.join(
            os.path.dirname(os.path.abspath(default_settings_path())),
            DEFAULT_FILE_NAME,
        ),
    )


_store: Optional[LetterheadStore] = None
_store_path: Optional[str] = None


def set_letterhead_path(path: str) -> None:
    """Point the singleton at a file. Called by tests and by the bootstrap."""
    global _store, _store_path
    _store_path = path
    _store = None


def get_letterhead_store() -> LetterheadStore:
    """The process-wide letterhead, matching `get_user_settings()` next door."""
    global _store
    if _store is None:
        _store = LetterheadStore(_store_path or default_letterhead_path())
    return _store
