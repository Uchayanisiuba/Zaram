"""The text in an attached picture is read on this machine, at attach time.

`attachments/ocr.py`. Windows' own recogniser, nothing downloaded, nothing
sent. Three contracts: a picture of text carries its text after attaching;
it reaches the model as the picture's own section, beside the picture for
a model that sees and in place of it for one that cannot — and the account
under the reply says which; and a picture with no text carries none, so a
model that cannot see is still refused rather than answering blind.
"""

from __future__ import annotations

import io
import sys

import pytest
from PIL import Image, ImageDraw, ImageFont

from attachments.compose import Mode, compose
from attachments.contracts import Attachment, AttachmentKind
from attachments.store import AttachmentStore

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows' own OCR")


def _picture(text: str | None) -> bytes:
    img = Image.new("RGB", (900, 160), "white")
    if text:
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except Exception:  # noqa: BLE001
            font = None
        ImageDraw.Draw(img).text((20, 50), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@windows_only
def test_a_picture_of_text_carries_its_text_after_attaching(tmp_path, monkeypatch):
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    store = AttachmentStore()
    item, _ = store.add("s1", "terms.png", _picture("Payment terms: net 30 from date of invoice."))
    assert item.kind == AttachmentKind.IMAGE.value
    assert "net 30" in item.ocr_text
    assert item.text == ""  # still not a document


@windows_only
def test_a_picture_of_nothing_carries_no_text(tmp_path, monkeypatch):
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    store = AttachmentStore()
    item, _ = store.add("s1", "blank.png", _picture(None))
    assert item.ocr_text == ""


def _attached_picture(ocr: str) -> Attachment:
    return Attachment(
        id="att-1", session_id="s1", name="screenshot.png", suffix=".png", path="x",
        text="", parser="image", kind=AttachmentKind.IMAGE.value, data="AAAA", ocr_text=ocr,
    )


def test_the_text_reaches_the_model_as_the_pictures_own_section_and_the_account_says_so():
    seen = compose([_attached_picture("Error 0x80070005: access denied")], "what does this mean")
    assert "text read from screenshot.png (on this machine)" in seen.block
    assert "0x80070005" in seen.block
    assert seen.reads[0].mode == Mode.IMAGE
    assert "read its text on this machine" in seen.notice()

    unseen = compose([_attached_picture("Error 0x80070005")], "what does this mean", pictures_seen=False)
    assert unseen.reads[0].mode == Mode.IMAGE_TEXT
    assert "no model here can look at the picture itself" in unseen.notice()


def test_a_picture_without_text_adds_nothing_to_the_prompt():
    composition = compose([_attached_picture("")], "what is this")
    assert composition.block == ""
    assert composition.notice() == "Looked at screenshot.png."
