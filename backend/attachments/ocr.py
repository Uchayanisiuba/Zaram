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


#: How long a picture may take to read before it is given up on.
TIMEOUT_SECONDS = 20


def read_text(path: Path | str) -> str:
    """The text in the image at ``path``, or ``""`` when there is none or no
    engine can read it here. Never raises — and never crashes the engine.

    **Read in a child process, deliberately.** The Windows engine is native
    code reached through WinRT, and on 14 September 2026 it took the whole
    backend down with an access violation from inside the test suite — a
    fault no ``except`` can catch, on the one path a person uses several
    times a day. In isolation the same call is fine; under a process that
    has threads and an event loop already, it is not always, and the
    reason is not worth a tester's afternoon. So the engine runs in a
    process of its own: a crash there costs one picture's text and a log
    line. Measured cost, interpreter start included: well under a second,
    against a ~40 ms in-process read. Reliability wins on this path.
    """
    try:
        text = _in_a_child_process(Path(path))
    except Exception:  # noqa: BLE001 - a picture that cannot be read is a picture with no text
        logger.debug("OCR failed for %s", path, exc_info=True)
        return ""
    return _clean(text)


def _clean(text: str) -> str:
    text = " ".join(line.strip() for line in text.splitlines() if line.strip()) if text else ""
    if len(text) < MIN_CHARS:
        return ""
    return text[:MAX_CHARS]


def _in_a_child_process(path: Path) -> str:
    import json
    import subprocess

    done = subprocess.run(
        [sys.executable, "-m", "attachments.ocr", str(path)],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_SECONDS,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if done.returncode != 0:
        logger.info("OCR child exited %s for %s: %s", done.returncode, path, (done.stderr or "").strip()[-200:])
        return ""
    try:
        return str(json.loads(done.stdout or "{}").get("text") or "")
    except ValueError:
        return ""


def read_text_here(path: Path | str) -> str:
    """The same read, in this process. What the child runs; also what a
    caller that has its own isolation may use."""
    try:
        if sys.platform == "win32":
            text = _windows(Path(path))
        else:
            text = _rapidocr(Path(path))
    except Exception:  # noqa: BLE001
        logger.debug("OCR failed for %s", path, exc_info=True)
        return ""
    return _clean(text)


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


if __name__ == "__main__":  # the child: one path in, one JSON line out
    import json as _json

    _target = sys.argv[1] if len(sys.argv) > 1 else ""
    print(_json.dumps({"text": read_text_here(_target) if _target else ""}))
