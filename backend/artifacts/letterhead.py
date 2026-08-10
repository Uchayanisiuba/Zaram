"""The user's own branding, carried into every document they generate.

An invoice with no letterhead is a draft. This is what makes a generated file
something a freelancer can send to a client rather than something they retype
into Word first — which is the difference between the business layer being used
and being demonstrated.

**The logo is embedded, never linked, and that is not a style choice.**
`artifacts/export/pdf.py` calls WeasyPrint with no `base_url`, so a relative
path cannot resolve; and `check-no-remote-assets.mjs` bans a remote URL outright
because the preview renders the same string. A `data:` URI is the only form that
works in both the preview and the PDF, so it is the only form accepted.

**Raster only, deliberately.** SVG would be smaller and sharper and is refused:
an SVG can carry `<image href="https://…">` or a script, which would put a
remote fetch inside a document the product promises fetches nothing. That
promise is worth more than a few kilobytes, and the check that enforces it
elsewhere cannot see inside a data URI.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Sequence

#: Formats a logo may be supplied in. PNG first because a logo with a
#: transparent background is the common case and the only one that sits on a
#: masthead without a white box around it.
ALLOWED_LOGO_TYPES = ("image/png", "image/jpeg", "image/webp")

#: The largest logo accepted, before base64. Base64 inflates by a third and the
#: result is embedded in *every* document generated — so a 5 MB logo is 6.7 MB
#: added to each invoice. 512 KB is far more than a masthead needs and small
#: enough that nobody notices the cost.
MAX_LOGO_BYTES = 512 * 1024


class LogoRejected(ValueError):
    """The logo cannot be used, with a reason written for the user."""


def logo_data_uri(data: bytes, content_type: str) -> str:
    """Turn uploaded bytes into something a document can carry.

    Raises `LogoRejected` with a sentence the interface can show as-is, rather
    than returning None — a logo silently missing from an invoice is worse than
    an upload that refuses and says why.
    """
    normalised = (content_type or "").split(";")[0].strip().lower()
    if normalised not in ALLOWED_LOGO_TYPES:
        raise LogoRejected(
            f"A logo has to be a PNG, JPEG or WebP image. This one is "
            f"{normalised or 'of an unknown type'}. SVG is not accepted because "
            "it can reference files from the internet, and a generated document "
            "must not fetch anything."
        )
    if not data:
        raise LogoRejected("That file is empty.")
    if len(data) > MAX_LOGO_BYTES:
        raise LogoRejected(
            f"That logo is {len(data) / 1024:.0f} KB. The limit is "
            f"{MAX_LOGO_BYTES // 1024} KB, because the image is embedded in "
            "every document you generate rather than linked."
        )

    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{normalised};base64,{encoded}"


@dataclass(frozen=True)
class Letterhead:
    """Who the document is from, as it should appear at the top of the page.

    Every field is optional and the masthead renders whatever is present. A user
    who has uploaded nothing still gets a titled, ruled document rather than a
    bare `<h1>` — the absence of branding must not read as a rendering failure.
    """

    #: Trading name. The one line set in bold on the masthead.
    name: str = ""
    #: Address, contact, registration number — whatever the user supplies, in
    #: the order they supply it. Not parsed; this is their business, not ours to
    #: model, and a schema here would be wrong in a different country.
    lines: Sequence[str] = field(default_factory=tuple)
    #: A `data:` URI from `logo_data_uri`. Never a path and never a URL.
    logo: str = ""

    def is_empty(self) -> bool:
        return not (self.name or self.lines or self.logo)
