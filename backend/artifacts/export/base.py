"""What every exporter is, and how one says it cannot run.

Two ideas live here.

**An exporter turns HTML into bytes.** It never writes a file. `ArtifactStore`
is the only thing that touches the filesystem, and keeping the two apart is what
keeps the "no delete or overwrite capability at all" guarantee auditable: it is
a property of one small module, and adding a format cannot weaken it.

**Unavailability is a first-class answer, not an exception.** WeasyPrint needs
native GTK libraries that are not a `pip install` on Windows; matplotlib may not
be installed. CLAUDE.md: "Disabled capabilities are visible, not silent" and
"Never render invented values." So an exporter reports whether it can run and
*why not*, in language that names the missing thing and what would fix it —
before it is called, so the UI can grey the format out with the reason attached
rather than offering a button that throws.

An `ImportError` surfaced to a user as "PDF failed" is the failure mode this
shape exists to prevent. It tells them nothing they can act on, and it looks
like a bug in Zaram rather than a missing system library.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class Availability:
    """Whether a format can be produced on this machine, and why not."""

    ok: bool
    #: Plain language, for a user. Empty when `ok`.
    reason: str = ""
    #: What would make it work. Empty when `ok`, or when nothing the user can
    #: reasonably do would help — in which case saying nothing is more honest
    #: than inventing a step.
    remedy: str = ""

    def __bool__(self) -> bool:
        return self.ok


AVAILABLE = Availability(ok=True)


class ExportUnavailable(RuntimeError):
    """Raised when `export` is called on a format that cannot run here.

    Carries the `Availability` so a caller that skipped the check still gets the
    reason rather than a bare import traceback.
    """

    def __init__(self, fmt: str, availability: Availability) -> None:
        self.format = fmt
        self.availability = availability
        detail = availability.reason or "unavailable"
        if availability.remedy:
            detail = f"{detail} — {availability.remedy}"
        super().__init__(f"cannot export {fmt}: {detail}")


@runtime_checkable
class Exporter(Protocol):
    """HTML in, bytes out. No filesystem, no network, no state."""

    #: The file extension, without the dot. Also the format's name everywhere.
    extension: str
    #: For the HTTP response and the file card.
    media_type: str
    #: One line, for the format picker.
    label: str

    def availability(self) -> Availability:
        """Can this run here? Called before `export`, and cheap enough to call
        on every render of the format picker."""
        ...

    def export(self, document_html: str, *, filename: str = "") -> bytes:
        """Render the HTML into this format.

        `filename` is advisory — some formats embed a title or a sheet name and
        the artifact's filename is the best available default. Nothing here
        opens it.
        """
        ...


def module_available(
    module: str, *, needed_for: str, remedy: Optional[str] = None
) -> Availability:
    """Availability of a pure-Python dependency, by trying to import it.

    By import rather than by metadata, deliberately: CLAUDE.md records spaCy
    being nearly removed because `pip show` reported no dependents while misaki
    reached it at runtime. Metadata answers a question next to the one being
    asked. `find_spec` answers this one.
    """
    import importlib.util

    try:
        if importlib.util.find_spec(module) is not None:
            return AVAILABLE
    except (ImportError, ValueError):
        pass

    return Availability(
        ok=False,
        reason=f"{needed_for} needs {module}, which is not installed.",
        remedy=remedy or f"pip install {module}",
    )
