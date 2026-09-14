"""The text in a picture, read on this machine, before any model is asked.

A screenshot of an error, a photo of a receipt, a slide from a call — most
pictures people attach are pictures *of text*, and the text is what the
question is about. A vision model can read it; so can the operating
system, in 40 ms, with nothing downloaded and nothing sent. Measured 14
September 2026 on Windows' own OCR (`winocr`, MIT, over the WinRT
`Windows.Media.Ocr` engine that ships with the OS): a rendered line came
back exact in 0.037 s.

So an attached image is read here at attach time and the text rides with
it. Two things follow.

**A model that cannot see can still answer.** Where nothing installed can
look at a picture, the chat path used to refuse — rightly, rather than
answer around it. Now, when every attached picture has text, it answers
from that text and *says so*: "read the text in screenshot.png on this
machine; no model here can look at the picture itself." A photo of a
room has no text and is still refused, which is the honest line.

**A model that can see gets both.** The picture reaches it as before; the
text reaches it too, cited as the picture's, so a small vision model that
misreads a figure has the OCR beside it.

Elsewhere than Windows, `rapidocr_onnxruntime` is used when it is
installed and nothing when it is not — the field is then empty, which is
exactly what it was before this module existed. Nothing here invents
text: an engine that returns nothing leaves the field empty, and a picture
with no text is a picture with no text.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

#: Enough for a dense screenshot; more than this is a document, not a picture.
MAX_CHARS = 6000
#: Below this, what came back is noise from a picture of a thing, not text.
MIN_CHARS = 8


def read_text(path: Path | str) -> str:
    """The text in the image at ``path``, or ``""`` when there is none or no
    engine can read it here. Never raises."""
    try:
        if sys.platform == "win32":
            text = _windows(Path(path))
        else:
            text = _rapidocr(Path(path))
    except Exception:  # noqa: BLE001 - a picture that cannot be read is a picture with no text
        logger.debug("OCR failed for %s", path, exc_info=True)
        return ""
    text = " ".join(line.strip() for line in text.splitlines() if line.strip()) if text else ""
    if len(text) < MIN_CHARS:
        return ""
    return text[:MAX_CHARS]


def _windows(path: Path) -> str:
    import winocr
    from PIL import Image

    with Image.open(path) as img:
        result = winocr.recognize_pil_sync(img.convert("RGB"), "en")
    # winocr returns a dict; `lines` keeps the layout, `text` flattens it.
    if isinstance(result, dict):
        lines = result.get("lines")
        if isinstance(lines, list) and lines:
            return "\n".join(str(line.get("text", "")) if isinstance(line, dict) else str(line) for line in lines)
        return str(result.get("text") or "")
    return str(getattr(result, "text", "") or "")


def _rapidocr(path: Path) -> str:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return ""
    engine = RapidOCR()
    result, _ = engine(str(path))
    if not result:
        return ""
    return "\n".join(str(item[1]) for item in result if len(item) > 1)
