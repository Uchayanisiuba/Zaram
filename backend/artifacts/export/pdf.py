"""HTML → PDF, when the machine can do it — and a straight answer when it cannot.

WeasyPrint is the right converter: HTML is already the source of truth, so PDF
is the one format that needs no translation layer and loses nothing. It is also
the only exporter here that can be installed and still not work, because it
binds native GTK libraries (Pango, cairo, HarfBuzz) that are a system package on
Linux, a Homebrew formula on macOS, and on Windows an MSYS2 installation that
`pip install weasyprint` neither provides nor mentions.

**That is a packaging decision, not a missing import**, and it is the reason
this module checks twice. `find_spec` says whether the Python package is there;
only importing it says whether the native libraries behind it resolve — the
failure is an `OSError` raised from inside the import, naming a DLL, at the
moment of use. A user shown "cannot load libgobject-2.0-0" has been told nothing
about what to do. A user shown "PDF export needs the GTK runtime libraries,
which Zaram does not bundle yet" has been told the truth.

Until the packaging spike settles this, PDF reports itself unavailable with that
reason, Markdown and Word remain available on every machine, and the format
picker greys PDF out with the reason attached rather than offering a button that
raises. CLAUDE.md: "Disabled capabilities are visible, not silent."
"""

from __future__ import annotations

import functools
import sys

from .base import AVAILABLE, Availability


class PdfExporter:
    extension = "pdf"
    media_type = "application/pdf"
    label = "PDF"

    def availability(self) -> Availability:
        return _probe()

    def export(self, document_html: str, *, filename: str = "") -> bytes:
        from weasyprint import HTML

        # `string=` rather than a file: nothing is written before the store
        # writes it, and there is no temporary file to leak the document.
        #
        # No `base_url`. Without one, WeasyPrint cannot resolve a relative path,
        # which means a generated document cannot pull in a local file — and the
        # HTML layer already embeds images as data URIs precisely so it does not
        # need to. A base_url here would be an unlogged read of the filesystem
        # driven by model-authored markup.
        return HTML(string=document_html).write_pdf()


@functools.lru_cache(maxsize=1)
def _probe() -> Availability:
    """Import WeasyPrint once and remember what happened.

    Cached because the import is slow — it loads and links the native stack —
    and `availability()` is called on every render of the format picker. Cached
    for the process lifetime rather than permanently: installing GTK is a thing
    a user does between runs, and a restart is a reasonable price for picking it
    up. Persisting the answer to disk would not be.
    """
    import importlib.util

    try:
        if importlib.util.find_spec("weasyprint") is None:
            return Availability(
                ok=False,
                reason="PDF export needs WeasyPrint, which is not installed.",
                remedy=_platform_remedy(),
            )
    except (ImportError, ValueError):
        return Availability(
            ok=False,
            reason="PDF export needs WeasyPrint, which is not installed.",
            remedy=_platform_remedy(),
        )

    try:
        import weasyprint  # noqa: F401
    except OSError:
        # The native-library case: the package imported, the DLLs did not.
        return Availability(
            ok=False,
            reason=(
                "PDF export needs the GTK runtime libraries, which Zaram does "
                "not bundle yet."
            ),
            remedy=_platform_remedy(),
        )
    except ImportError as error:
        return Availability(
            ok=False,
            reason=f"PDF export could not load WeasyPrint: {error}",
            remedy=_platform_remedy(),
        )

    return AVAILABLE


def _platform_remedy() -> str:
    """What would actually fix it here.

    Named per platform because the generic advice is wrong on two of the three,
    and wrong advice about a system package costs a user an hour.
    """
    if sys.platform.startswith("win"):
        return (
            "On Windows this needs the MSYS2 GTK runtime as well as "
            "`pip install weasyprint`. Until Zaram bundles it, export as Word "
            "or Markdown."
        )
    if sys.platform == "darwin":
        return "brew install pango, then pip install weasyprint"
    return (
        "Install the Pango and cairo system packages "
        "(e.g. apt install libpango-1.0-0 libpangoft2-1.0-0), "
        "then pip install weasyprint"
    )
